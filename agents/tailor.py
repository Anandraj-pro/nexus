"""nexus-tailor — selects the right base resume for each scored job and converts to PDF."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agents.scorer import ScoredJob

logger = logging.getLogger(__name__)


@dataclass
class TailoredApplication:
    scored_job: ScoredJob
    tailored_resume: str
    cover_letter: str
    key_changes: list[str]
    output_path: Path | None = None
    pdf_path: Path | None = None


class NexusTailor:
    """
    Selects the appropriate base resume (path_a or path_b) for each scored job.

    No LLM is used — applications are evaluated by ATS on the base resume score.
    Converts the resume to PDF for platforms that require file upload (Greenhouse, Lever).
    """

    def __init__(self, config: dict[str, Any]):
        tailor_cfg = config.get("tailor", {})
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
        path_key = scored_job.path_recommendation
        base_resume = self._templates.get(path_key, "")

        app = TailoredApplication(
            scored_job=scored_job,
            tailored_resume=base_resume,
            cover_letter="",
            key_changes=[],
        )
        app.output_path = self._save(app)
        return app

    def _save(self, app: TailoredApplication) -> Path:
        safe_company = "".join(
            c if c.isalnum() else "_" for c in app.scored_job.posting.company
        )[:30]
        safe_title = "".join(
            c if c.isalnum() else "_" for c in app.scored_job.posting.title
        )[:30]
        stem = f"{safe_company}_{safe_title}"

        resume_path = self._output_dir / f"{stem}_resume.md"
        resume_path.write_text(app.tailored_resume)

        pdf_path = self._md_to_pdf(app.tailored_resume, self._output_dir / f"{stem}_resume.pdf")
        app.pdf_path = pdf_path

        logger.info("Tailor saved → %s (pdf: %s)", stem, "ok" if pdf_path else "skipped")
        return resume_path

    @staticmethod
    def _md_to_pdf(md_text: str, dest: Path) -> Path | None:
        try:
            import markdown as md_lib
            from fpdf import FPDF

            clean = (
                md_text
                .replace("—", "--").replace("–", "-")
                .replace("‘", "'").replace("’", "'")
                .replace("“", '"').replace("”", '"')
                .replace("•", "*").replace("…", "...")
                .replace(" ", " ")
            )
            html = md_lib.markdown(clean)
            pdf = FPDF()
            pdf.set_margins(20, 20, 20)
            pdf.add_page()
            pdf.set_font("Helvetica", size=11)
            pdf.write_html(f"<html><head></head><body>{html}</body></html>")
            pdf.output(str(dest))
            return dest
        except Exception as exc:
            logger.warning("PDF generation failed: %s", exc)
            return None

    async def tailor_batch(self, scored_jobs: list[ScoredJob]) -> list[TailoredApplication]:
        results = []
        for job in scored_jobs:
            results.append(await self.tailor(job))
        return results
