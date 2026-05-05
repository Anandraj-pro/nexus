"""Unit tests for jireh-voice — pure logic paths, no mic or TTS required."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.voice import JirehVoice, _extract_json


# ─── _extract_json ────────────────────────────────────────────────────────────

def test_extract_json_plain():
    raw = '{"action": "run", "params": {}}'
    assert json.loads(_extract_json(raw))["action"] == "run"


def test_extract_json_strips_fence():
    raw = '```json\n{"action": "help"}\n```'
    assert json.loads(_extract_json(raw))["action"] == "help"


def test_extract_json_with_surrounding_text():
    raw = 'Here is the intent:\n{"action": "exit"}\nEnd.'
    assert json.loads(_extract_json(raw))["action"] == "exit"


# ─── Fixtures ─────────────────────────────────────────────────────────────────

CONFIG = {
    "voice": {"whisper_model": "base", "tts_rate": 170},
    "apply": {"live_mode": False},
    "scorer": {"path_b_threshold": 72},
    "schedule": {"apply_deadline": "09:15"},
    "tailor": {"output_dir": "resources/resumes/tailored/"},
}


def _make_voice(pipeline_fn=None) -> JirehVoice:
    """Build a JirehVoice with all hardware dependencies stubbed out.

    Injects fake pyttsx3 / whisper into sys.modules before the constructor
    runs its lazy imports, so no voice extras need to be installed.
    """
    import sys

    if pipeline_fn is None:
        pipeline_fn = AsyncMock()

    fake_tts = MagicMock()
    fake_pyttsx3 = MagicMock()
    fake_pyttsx3.init.return_value = fake_tts

    fake_model = MagicMock()
    fake_whisper = MagicMock()
    fake_whisper.load_model.return_value = fake_model

    saved = {k: sys.modules.get(k) for k in ("pyttsx3", "whisper")}
    sys.modules["pyttsx3"] = fake_pyttsx3
    sys.modules["whisper"] = fake_whisper
    try:
        v = JirehVoice(CONFIG, pipeline_fn)
    finally:
        for mod, orig in saved.items():
            if orig is None:
                sys.modules.pop(mod, None)
            else:
                sys.modules[mod] = orig

    return v


# ─── parse_intent ─────────────────────────────────────────────────────────────

def test_parse_intent_run_command():
    voice = _make_voice()
    response = json.dumps({"action": "run", "params": {"dry_run": True}, "response_hint": "ok"})
    with patch("agents.voice._ollama_chat", return_value=response):
        intent = voice.parse_intent("run now")
    assert intent["action"] == "run"


def test_parse_intent_exit_command():
    voice = _make_voice()
    response = json.dumps({"action": "exit", "params": {}, "response_hint": "bye"})
    with patch("agents.voice._ollama_chat", return_value=response):
        intent = voice.parse_intent("stop")
    assert intent["action"] == "exit"


def test_parse_intent_skip_with_keyword():
    voice = _make_voice()
    response = json.dumps(
        {"action": "skip", "params": {"keyword": "fintech"}, "response_hint": "ok"}
    )
    with patch("agents.voice._ollama_chat", return_value=response):
        intent = voice.parse_intent("skip fintech")
    assert intent["action"] == "skip"
    assert intent["params"]["keyword"] == "fintech"


def test_parse_intent_falls_back_on_bad_response():
    voice = _make_voice()
    with patch("agents.voice._ollama_chat", return_value="not json at all"):
        intent = voice.parse_intent("mumble mumble")
    assert intent["action"] == "unknown"


def test_parse_intent_falls_back_on_ollama_error():
    voice = _make_voice()
    with patch("agents.voice._ollama_chat", side_effect=RuntimeError("Ollama down")):
        intent = voice.parse_intent("run")
    assert intent["action"] == "unknown"


# ─── dispatch — status ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dispatch_status_contains_live_mode():
    voice = _make_voice()
    text, exit_flag = await voice.dispatch({"action": "status", "params": {}})
    assert "off" in text.lower() or "on" in text.lower()
    assert not exit_flag


@pytest.mark.asyncio
async def test_dispatch_status_contains_threshold():
    voice = _make_voice()
    text, _ = await voice.dispatch({"action": "status", "params": {}})
    assert "72" in text


@pytest.mark.asyncio
async def test_dispatch_status_lists_skip_keywords():
    voice = _make_voice()
    voice._skip_keywords = ["fintech", "banking"]
    text, _ = await voice.dispatch({"action": "status", "params": {}})
    assert "fintech" in text
    assert "banking" in text


# ─── dispatch — skip ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dispatch_skip_adds_to_list():
    voice = _make_voice()
    await voice.dispatch({"action": "skip", "params": {"keyword": "fintech"}})
    assert "fintech" in voice._skip_keywords


@pytest.mark.asyncio
async def test_dispatch_skip_multiple_keywords():
    voice = _make_voice()
    await voice.dispatch({"action": "skip", "params": {"keyword": "fintech"}})
    await voice.dispatch({"action": "skip", "params": {"keyword": "banking"}})
    assert len(voice._skip_keywords) == 2


@pytest.mark.asyncio
async def test_dispatch_skip_empty_keyword_returns_prompt():
    voice = _make_voice()
    text, _ = await voice.dispatch({"action": "skip", "params": {}})
    assert "keyword" in text.lower() or "company" in text.lower()


# ─── dispatch — help & unknown ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dispatch_help_lists_commands():
    voice = _make_voice()
    text, exit_flag = await voice.dispatch({"action": "help", "params": {}})
    assert "run" in text.lower()
    assert "status" in text.lower()
    assert not exit_flag


@pytest.mark.asyncio
async def test_dispatch_unknown_suggests_help():
    voice = _make_voice()
    text, exit_flag = await voice.dispatch({"action": "unknown", "params": {}})
    assert "help" in text.lower() or "try" in text.lower()
    assert not exit_flag


# ─── dispatch — exit ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dispatch_exit_returns_should_exit_true():
    voice = _make_voice()
    _, exit_flag = await voice.dispatch({"action": "exit", "params": {}})
    assert exit_flag is True


# ─── dispatch — run ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dispatch_run_calls_pipeline():
    pipeline = AsyncMock()
    voice = _make_voice(pipeline_fn=pipeline)
    voice.speak = MagicMock()  # silence TTS in test
    await voice.dispatch({"action": "run", "params": {"dry_run": True}})
    pipeline.assert_awaited_once_with(dry_run=True)


@pytest.mark.asyncio
async def test_dispatch_run_pipeline_error_returns_message():
    pipeline = AsyncMock(side_effect=RuntimeError("Ollama not running"))
    voice = _make_voice(pipeline_fn=pipeline)
    voice.speak = MagicMock()
    text, exit_flag = await voice.dispatch({"action": "run", "params": {}})
    assert "error" in text.lower() or "log" in text.lower()
    assert not exit_flag


# ─── dispatch — digest ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dispatch_digest_no_files_returns_prompt(tmp_path: Path):
    cfg = {**CONFIG, "tailor": {"output_dir": str(tmp_path)}}
    voice = _make_voice()
    voice._config = cfg
    text, _ = await voice.dispatch({"action": "digest", "params": {}})
    assert "pipeline" in text.lower() or "no application" in text.lower()


@pytest.mark.asyncio
async def test_dispatch_digest_lists_recent_files(tmp_path: Path):
    (tmp_path / "Acme_QA_Manager_resume.md").write_text("resume")
    (tmp_path / "Acme_QA_Manager_cover.md").write_text("cover")
    cfg = {**CONFIG, "tailor": {"output_dir": str(tmp_path)}}
    voice = _make_voice()
    voice._config = cfg
    text, _ = await voice.dispatch({"action": "digest", "params": {}})
    assert "Acme" in text or "QA" in text