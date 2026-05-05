"""jireh-tailor — rewrites the resume and generates a cover letter per job using Ollama/Llama."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import ollama

from agents.scorer import ScoredJob

logger = logging.getLogger(__name__)

TAILOR_SYSTEM_PROMPT = """\
You are jireh-tailor, an expert technical recruiter and resume writer specializing in
QA/QE leadership roles. Tailor a candidate's resume to a specific job description.

Rules:
1. Keep the resume under 800 words. Every sentence must earn its place.
2. Mirror the exact terminology from the JD — if they say "test automation framework",
   use that phrase, not "automation suite".
3. Lead with the strongest matching experiences first.
4. Quantify everything possible. Generic bullets are useless.
5. Never invent skills or experiences the candidate doesn't have.
6. Cover letter: 3 short paragraphs. Hook → Value proof → Call to action.
   No fluff. No "I am excited to apply."

Return ONLY a valid JSON object — no markdown fences, no explanation:
{"tailored_resume": "<markdown string>", "cover_letter": "<markdown string>", "key_changes": ["<what changed and why>", ...]}
"""


def _escape_json_strings(text: str) -> str:
    """Escape literal newlines/tabs inside JSON string values (LLM output repair)."""
    result = []
    in_string = False
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and in_string:
            result.append(ch)
            if i + 1 < len(text):
                result.append(text[i + 1])
            i += 2
            continue
        if ch == '"':
            in_string = not in_string
            result.append(ch)
        elif in_string and ch == "\n":
            result.append("\\n")
        elif in_string and ch == "\r":
            result.append("\\r")
        elif in_string and ch == "\t":
            result.append("\\t")
        else:
            result.append(ch)
        i += 1
    return "".join(result)


def _extract_json(text: str) -> str:
    """Strip markdown code fences and extract the first JSON object found."""
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text)
    start = text.find("{")
    if start == -1:
        return text
    try:
        _, end = json.JSONDecoder(strict=False).raw_decode(text, start)
        return text[start:end]
    except json.JSONDecodeError:
        pass
    try:
        repaired = _escape_json_strings(text[start:])
        _, end = json.JSONDecoder(strict=False).raw_decode(repaired, 0)
        return repaired[:end]
    except json.JSONDecodeError:
        return text[start:]


def _ollama_chat(model: str, messages: list[dict]) -> str:
    response = ollama.chat(model=model, messages=messages)
    return response["message"]["content"]


@dataclass
class TailoredApplication:
    scored_job: ScoredJob
    tailored_resume: str
    cover_letter: str
    key_changes: list[str]
    output_path: Path | None = None
    pdf_path: Path | None = None


class JirehTailor:
    """
    Tailors the resume and cover letter for each ScoredJob using Ollama/Llama.

    Uses llama3.1:8b (higher quality) for resume rewriting.
    Saves tailored documents to resources/resumes/tailored/.
    """

    def __init__(self, config: dict[str, Any]):
        self.config = config
        llm_cfg = config.get("llm", {})
        tailor_cfg = config.get("tailor", {})
        self._model = llm_cfg.get("tailor_model", "llama3.1:8b")
        self._output_dir = Path(tailor_cfg.get("output_dir", "resources/resumes/tailored/"))
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._templates: dict[str, str] = {}
        self._load_templates(tailor_cfg)

    def _load_templates(self, tailor_cfg: dict[str, Any]) -> None:
        for path_key in ("path_a", "path_b"):
            template_path = Path(tailor_cfg.get(f"resume_template_{path_key}", ""))
            if template_path.exists():
                self._templates[path_key] = template_path.read_text()
            else:
                logger.warning("Resume template not found: %s", template_path)
                self._templates[path_key] = ""

    async def tailor(self, scored_job: ScoredJob) -> TailoredApplication:
        """Produce a tailored resume + cover letter for one scored job."""
        path_key = scored_job.path_recommendation
        base_resume = self._templates.get(path_key, "")

        user_content = (
            f"BASE RESUME:\n{base_resume}\n\n"
            f"JOB TITLE: {scored_job.posting.title}\n"
            f"COMPANY: {scored_job.posting.company}\n"
            f"MATCHED SKILLS: {', '.join(scored_job.matched_skills)}\n"
            f"MISSING SKILLS (do NOT fabricate): {', '.join(scored_job.missing_skills)}\n\n"
            f"JOB DESCRIPTION:\n{scored_job.posting.description[:3000]}"
        )

        messages = [
            {"role": "system", "content": TAILOR_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        try:
            raw = await asyncio.to_thread(_ollama_chat, self._model, messages)
            data = json.loads(_extract_json(raw), strict=False)
            app = TailoredApplication(
                scored_job=scored_job,
                tailored_resume=data["tailored_resume"],
                cover_letter=data["cover_letter"],
                key_changes=data.get("key_changes", []),
            )
            app.output_path = self._save(app)
            return app

        except (json.JSONDecodeError, KeyError) as exc:
            logger.exception(
                "Tailor failed for %s @ %s: %s",
                scored_job.posting.title,
                scored_job.posting.company,
                exc,
            )
            return TailoredApplication(
                scored_job=scored_job,
                tailored_resume=base_resume,
                cover_letter="",
                key_changes=[f"Tailoring failed: {exc}"],
            )

    def _save(self, app: TailoredApplication) -> Path:
        """Persist tailored resume and cover letter to disk."""
        safe_company = "".join(
            c if c.isalnum() else "_" for c in app.scored_job.posting.company
        )[:30]
        safe_title = "".join(
            c if c.isalnum() else "_" for c in app.scored_job.posting.title
        )[:30]
        stem = f"{safe_company}_{safe_title}"

        resume_path = self._output_dir / f"{stem}_resume.md"
        cover_path = self._output_dir / f"{stem}_cover.md"

        resume_path.write_text(app.tailored_resume)
        cover_path.write_text(app.cover_letter)

        pdf_path = self._md_to_pdf(app.tailored_resume, self._output_dir / f"{stem}_resume.pdf")
        app.pdf_path = pdf_path

        logger.info("Tailor saved → %s (pdf: %s)", stem, "ok" if pdf_path else "skipped")
        return resume_path

    @staticmethod
    def _md_to_pdf(md_text: str, dest: Path) -> Path | None:
        """Convert markdown resume to PDF using fpdf2. Returns dest path on success."""
        try:
            import markdown as md_lib
            from fpdf import FPDF

            # Replace common Unicode chars that Helvetica can't encode
            clean = (
                md_text
                .replace("—", "--").replace("–", "-")   # em/en dash
                .replace("‘", "'").replace("’", "'")    # smart single quotes
                .replace("“", '"').replace("”", '"')    # smart double quotes
                .replace("•", "*").replace("…", "...")  # bullet, ellipsis
                .replace(" ", " ")                           # non-breaking space
            )
            html = md_lib.markdown(clean)
            full_html = (
                "<html><head></head>"
                f"<body>{html}</body></html>"
            )
            pdf = FPDF()
            pdf.set_margins(20, 20, 20)
            pdf.add_page()
            pdf.set_font("Helvetica", size=11)
            pdf.write_html(full_html)
            pdf.output(str(dest))
            return dest
        except Exception as exc:
            logger.warning("PDF generation failed: %s", exc)
            return None

    async def tailor_batch(self, scored_jobs: list[ScoredJob]) -> list[TailoredApplication]:
        results = []
        for job in scored_jobs:
            app = await self.tailor(job)
            results.append(app)
        return results