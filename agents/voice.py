"""nexus-voice — voice-activated interface for Nexus.

Press Enter to speak a command. Jireh listens, transcribes with Whisper,
parses intent with Ollama, executes the action, and responds by voice.

Requires the [voice] extras:
    pip install -e ".[voice]"

macOS note: sounddevice requires portaudio — install once with:
    brew install portaudio
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import tempfile
from pathlib import Path
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16_000        # Hz — Whisper requires 16 kHz
SILENCE_THRESHOLD = 0.015   # RMS amplitude below this = silence
SILENCE_SECS = 1.5          # stop after this many seconds of silence post-speech
MAX_RECORD_SECS = 12        # hard ceiling per utterance

INTENT_PROMPT = """\
Parse this voice command for a job-hunt assistant named Jireh: "{text}"

Return ONLY a valid JSON object, no explanation:
{{"action": "<run|status|digest|skip|help|exit|unknown>",
  "params": {{}},
  "response_hint": "<one short sentence>"}}

action meanings:
  run    — start the job-hunt pipeline (params may include dry_run: true/false)
  status — read current config aloud
  digest — summarise recent applications
  skip   — exclude a keyword/company this session (params: {{"keyword": "..."}})
  help   — list available commands
  exit   — end voice mode
  unknown — command not understood
"""


def _extract_json(text: str) -> str:
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    start = text.find("{")
    if start == -1:
        return text
    _, end = json.JSONDecoder().raw_decode(text, start)
    return text[start:end]


def _ollama_chat(model: str, messages: list[dict]) -> str:
    import ollama
    response = ollama.chat(model=model, messages=messages)
    return response["message"]["content"]


class NexusVoice:
    """
    Hotkey-activated voice interface.

    Press Enter → speak → Jireh transcribes (Whisper) → parses intent
    (Ollama) → executes action → responds by voice (pyttsx3).
    """

    def __init__(
        self,
        config: dict[str, Any],
        pipeline_fn: Callable[..., Awaitable[None]],
    ) -> None:
        self._config = config
        self._pipeline_fn = pipeline_fn
        self._skip_keywords: list[str] = []

        import pyttsx3
        import whisper

        voice_cfg = config.get("voice", {})
        self._tts = pyttsx3.init()
        self._tts.setProperty("rate", voice_cfg.get("tts_rate", 170))

        model_name = voice_cfg.get("whisper_model", "base")
        logger.info("Loading Whisper model '%s' — first run downloads ~%s",
                    model_name, {"tiny": "75MB", "base": "145MB", "small": "460MB"}.get(model_name, "?"))
        self._whisper = whisper.load_model(model_name)
        logger.info("NexusVoice ready")

    # ── TTS ───────────────────────────────────────────────────────────────────

    def speak(self, text: str) -> None:
        logger.info("Jireh: %s", text)
        print(f"\n  🔊  Jireh: {text}\n")
        self._tts.say(text)
        self._tts.runAndWait()

    # ── STT ───────────────────────────────────────────────────────────────────

    def listen(self) -> str:
        """
        Record from the default microphone until silence is detected,
        then transcribe with Whisper. Returns the transcribed text.
        """
        import numpy as np
        import scipy.io.wavfile as wav_io
        import sounddevice as sd

        voice_cfg = self._config.get("voice", {})
        silence_threshold: float = voice_cfg.get("silence_threshold", SILENCE_THRESHOLD)
        silence_secs: float = voice_cfg.get("silence_secs", SILENCE_SECS)
        chunk_size = int(SAMPLE_RATE * 0.1)   # 100 ms chunks
        silence_chunks_needed = int(silence_secs * SAMPLE_RATE / chunk_size)
        max_chunks = int(MAX_RECORD_SECS * SAMPLE_RATE / chunk_size)

        print("  🎙  Listening… (speak your command)")
        chunks: list[np.ndarray] = []
        silent_streak = 0
        has_speech = False

        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32") as stream:
            for _ in range(max_chunks):
                data, _ = stream.read(chunk_size)
                chunks.append(data.copy())
                rms = float(np.sqrt(np.mean(data ** 2)))
                if rms > silence_threshold:
                    has_speech = True
                    silent_streak = 0
                elif has_speech:
                    silent_streak += 1
                    if silent_streak >= silence_chunks_needed:
                        break

        if not has_speech:
            return ""

        audio = np.concatenate(chunks).flatten()
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp = f.name
        try:
            wav_io.write(tmp, SAMPLE_RATE, (audio * 32_767).astype("int16"))
            result = self._whisper.transcribe(tmp, language="en", fp16=False)
        finally:
            Path(tmp).unlink(missing_ok=True)

        text = result["text"].strip()
        logger.info("Transcribed: %s", text)
        return text

    # ── Intent ────────────────────────────────────────────────────────────────

    def parse_intent(self, text: str) -> dict[str, Any]:
        """Use Ollama llama3.2 to parse spoken text into a structured intent dict."""
        prompt = INTENT_PROMPT.format(text=text)
        try:
            raw = _ollama_chat("llama3.2", [{"role": "user", "content": prompt}])
            return json.loads(_extract_json(raw))
        except Exception:
            logger.debug("Intent parse failed", exc_info=True)
            return {"action": "unknown", "params": {}, "response_hint": ""}

    # ── Dispatch ──────────────────────────────────────────────────────────────

    async def dispatch(self, intent: dict[str, Any]) -> tuple[str, bool]:
        """
        Execute the intent.

        Returns (response_text, should_exit).
        """
        action = intent.get("action", "unknown")
        params = intent.get("params", {})

        if action == "run":
            dry_run: bool = params.get("dry_run", True)
            label = "dry run — no real submissions" if dry_run else "live mode"
            self.speak(f"Starting Jireh pipeline in {label}. Give me a moment.")
            try:
                await self._pipeline_fn(dry_run=dry_run)
                return "Pipeline complete. He provided.", False
            except Exception as exc:
                logger.exception("Pipeline failed from voice command")
                return f"Pipeline hit an error. Check the logs. {exc}", False

        if action == "status":
            cfg_apply = self._config.get("apply", {})
            cfg_scorer = self._config.get("scorer", {})
            live = cfg_apply.get("live_mode", False)
            threshold = cfg_scorer.get("path_b_threshold", 72)
            deadline = self._config.get("schedule", {}).get("apply_deadline", "09:15")
            skip_note = f" Skipping: {', '.join(self._skip_keywords)}." if self._skip_keywords else ""
            return (
                f"Live mode is {'on' if live else 'off'}. "
                f"Auto-apply threshold is {threshold} out of 100. "
                f"Deadline is {deadline} I S T.{skip_note}"
            ), False

        if action == "digest":
            tailored_dir = Path(
                self._config.get("tailor", {}).get("output_dir", "resources/resumes/tailored/")
            )
            if tailored_dir.exists():
                files = sorted(
                    tailored_dir.glob("*_resume.md"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                if files:
                    names = [
                        p.stem.replace("_resume", "").replace("_", " ")
                        for p in files[:3]
                    ]
                    return f"Recent applications: {', '.join(names)}.", False
            return "No applications on record yet. Run the pipeline first.", False

        if action == "skip":
            keyword = str(params.get("keyword", "")).strip()
            if keyword:
                self._skip_keywords.append(keyword)
                return f"Got it. I will skip '{keyword}' for this session.", False
            return "Please tell me which keyword or company to skip.", False

        if action == "help":
            return (
                "You can say: run now, run live, run dry run, status, "
                "what did you apply for, skip fintech, or stop."
            ), False

        if action == "exit":
            return "Signing off. He goes before you, Anand. God bless.", True

        return "I did not catch that. Try: run now, status, help, or stop.", False

    # ── Main loop ─────────────────────────────────────────────────────────────

    async def run_loop(self) -> None:
        """Main voice interaction loop. Press Enter to activate each command."""
        self.speak(
            "Jireh voice interface activated. "
            "Press Enter to speak a command, or say help for options."
        )

        while True:
            try:
                input("  [Press Enter to speak  |  Ctrl+C to quit]\n")
            except (EOFError, KeyboardInterrupt):
                self.speak("Goodbye. He provides.")
                break

            text = await asyncio.to_thread(self.listen)
            if not text:
                self.speak("I did not hear anything. Please try again.")
                continue

            print(f"  📝  You said: {text}")

            intent = await asyncio.to_thread(self.parse_intent, text)
            response, should_exit = await self.dispatch(intent)
            self.speak(response)

            if should_exit:
                break