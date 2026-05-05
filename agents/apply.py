"""jireh-apply — submits job applications via Playwright before the 9:15 AM deadline."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from agents.tailor import TailoredApplication

logger = logging.getLogger(__name__)


class _ExternalApplicationError(Exception):
    """Raised when a job has no Easy Apply — requires manual application."""


class ApplyStatus(str, Enum):
    SUBMITTED = "submitted"
    QUEUED_FOR_HUMAN = "queued_for_human"
    EXTERNAL_APPLY = "external_apply"   # no Easy Apply — Anand must apply manually
    SKIPPED_CAPTCHA = "skipped_captcha"
    SKIPPED_DEADLINE = "skipped_deadline"
    FAILED = "failed"
    DRY_RUN = "dry_run"


@dataclass
class ApplicationResult:
    application: TailoredApplication
    status: ApplyStatus
    timestamp: datetime = field(default_factory=datetime.utcnow)
    platform: str = ""
    error: str = ""
    confirmation_id: str = ""


class JirehApply:
    """
    Submits applications for Path B jobs automatically.
    Path A jobs are queued for human approval without submitting.

    live_mode=False (default) logs every action without actually submitting.
    Set live_mode=True in agent_config.yaml only after thorough testing.
    """

    def __init__(self, config: dict[str, Any]):
        self.config = config
        apply_cfg = config.get("apply", {})
        self._live_mode: bool = apply_cfg.get("live_mode", False)
        self._headless: bool = apply_cfg.get("headless", True)
        self._slow_mo: int = apply_cfg.get("slow_mo_ms", 50)
        self._timeout: int = apply_cfg.get("timeout_ms", 30000)
        self._retry: int = apply_cfg.get("retry_attempts", 2)
        self._on_captcha: str = apply_cfg.get("on_captcha", "skip_and_flag")
        self._session_dir = Path(
            config.get("vault", {}).get("session_dir", "resources/credentials/sessions/")
        )

        if not self._live_mode:
            logger.warning(
                "jireh-apply running in DRY-RUN mode. "
                "Set apply.live_mode=true in agent_config.yaml to submit real applications."
            )

    def _load_platform_session(self, platform: str) -> list[dict] | None:
        """Load saved browser cookies for a platform. Returns None if missing."""
        path = self._session_dir / f"{platform}_session.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text())
        except Exception:
            logger.warning("Could not load session for %s", platform)
            return None

    async def apply(self, app: TailoredApplication) -> ApplicationResult:
        """Apply to a single job. Respects path and deadline constraints."""
        posting = app.scored_job.posting
        path = app.scored_job.path_recommendation

        if path == "path_a":
            logger.info(
                "Path A — queuing for human approval: %s @ %s",
                posting.title,
                posting.company,
            )
            return ApplicationResult(
                application=app,
                status=ApplyStatus.QUEUED_FOR_HUMAN,
                platform=posting.platform,
            )

        if not self._live_mode:
            logger.info(
                "[DRY-RUN] Would apply to: %s @ %s (%s)",
                posting.title,
                posting.company,
                posting.url,
            )
            return ApplicationResult(
                application=app,
                status=ApplyStatus.DRY_RUN,
                platform=posting.platform,
            )

        return await self._submit_via_playwright(app)

    async def _submit_via_playwright(self, app: TailoredApplication) -> ApplicationResult:
        """Browser-based application submission using Playwright."""
        from playwright.async_api import TimeoutError as PWTimeout
        from playwright.async_api import async_playwright

        posting = app.scored_job.posting
        session_cookies = self._load_platform_session(posting.platform)

        for attempt in range(1, self._retry + 2):
            try:
                async with async_playwright() as pw:
                    browser = await pw.chromium.launch(
                        headless=self._headless, slow_mo=self._slow_mo
                    )
                    context = await browser.new_context(
                        user_agent=(
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0.0.0 Safari/537.36"
                        )
                    )
                    if session_cookies:
                        await context.add_cookies(session_cookies)

                    page = await context.new_page()
                    await page.goto(posting.url, timeout=self._timeout)

                    adapter_method = getattr(self, f"_apply_{posting.platform}", None)
                    if adapter_method is None:
                        logger.warning(
                            "No apply adapter for platform: %s — skipping", posting.platform
                        )
                        await browser.close()
                        return ApplicationResult(
                            application=app,
                            status=ApplyStatus.FAILED,
                            platform=posting.platform,
                            error=f"No adapter for {posting.platform}",
                        )

                    confirmation = await adapter_method(page, app)
                    await browser.close()
                    logger.info(
                        "Applied ✓ %s @ %s [%s]",
                        posting.title,
                        posting.company,
                        confirmation,
                    )
                    return ApplicationResult(
                        application=app,
                        status=ApplyStatus.SUBMITTED,
                        platform=posting.platform,
                        confirmation_id=confirmation,
                    )

            except PWTimeout:
                logger.warning("Playwright timeout on attempt %d/%d", attempt, self._retry + 1)
            except _ExternalApplicationError as exc:
                # Not retryable — job redirects to an external site
                logger.info("External apply (no Easy Apply): %s @ %s", posting.title, posting.company)
                return ApplicationResult(
                    application=app,
                    status=ApplyStatus.EXTERNAL_APPLY,
                    platform=posting.platform,
                    error=str(exc),
                )
            except Exception as exc:
                captcha_signals = ["captcha", "recaptcha", "challenge", "verify"]
                if any(sig in str(exc).lower() for sig in captcha_signals):
                    logger.warning("CAPTCHA detected at %s — flagging", posting.url)
                    return ApplicationResult(
                        application=app,
                        status=ApplyStatus.SKIPPED_CAPTCHA,
                        platform=posting.platform,
                        error=str(exc),
                    )
                logger.exception("Apply attempt %d failed: %s", attempt, exc)

        return ApplicationResult(
            application=app,
            status=ApplyStatus.FAILED,
            platform=posting.platform,
            error=f"All {self._retry + 1} attempts exhausted",
        )

    # ── Platform adapters ────────────────────────────────────────────────────

    async def _apply_linkedin(self, page: Any, app: TailoredApplication) -> str:
        """
        Apply via LinkedIn Easy Apply modal.

        Walks the multi-step modal: fills cover letter, answers yes/no and
        numeric questions with safe defaults, then submits. Uses the LinkedIn
        profile resume (no file upload — tailored resume is .md, not PDF).

        Raises RuntimeError if Easy Apply button is not found (external job link).
        """
        from playwright.async_api import TimeoutError as PWTimeout

        posting = app.scored_job.posting

        # Find and click the Easy Apply button
        try:
            easy_apply_btn = await page.wait_for_selector(
                ".jobs-apply-button, button[aria-label*='Easy Apply']",
                timeout=10_000,
            )
        except PWTimeout:
            raise _ExternalApplicationError(posting.url)

        await easy_apply_btn.click()
        await page.wait_for_timeout(2000)

        # Walk the modal — up to 10 steps
        for _ in range(10):
            await self._linkedin_fill_step(page, app)

            if await self._linkedin_click_button(page, "Submit application"):
                logger.info("LinkedIn: submitted application for %s", posting.title)
                break
            if await self._linkedin_click_button(page, "Review"):
                await page.wait_for_timeout(1000)
                continue
            if await self._linkedin_click_button(page, "Continue to next step"):
                await page.wait_for_timeout(1000)
                continue
            if await self._linkedin_click_button(page, "Next"):
                await page.wait_for_timeout(1000)
                continue
            # No recognised button — assume modal closed after submit
            break

        await page.wait_for_timeout(2000)
        return posting.job_id

    async def _linkedin_fill_step(self, page: Any, app: TailoredApplication) -> None:
        """Fill in fields on the current Easy Apply step."""
        # Cover letter textarea — fill only if empty
        for sel in [
            "textarea[id*='cover-letter']",
            "textarea[aria-label*='cover letter' i]",
            "div[data-test-single-line-text-form-component] textarea",
            ".jobs-easy-apply-form-section__grouping textarea",
        ]:
            el = await page.query_selector(sel)
            if el and app.cover_letter:
                current = await el.input_value()
                if not current.strip():
                    await el.fill(app.cover_letter[:2000])
                break

        # Yes/No radio buttons — select "Yes" for qualification questions
        yes_radios = await page.query_selector_all(
            "fieldset input[type='radio'][value='Yes'], "
            "fieldset input[type='radio'][value='yes']"
        )
        for radio in yes_radios:
            if not await radio.is_checked():
                await radio.check()

        # Numeric / text inputs for years of experience — fill if empty
        numeric_inputs = await page.query_selector_all(
            "input[type='text'][id*='year'], "
            "input[type='number'], "
            "input[aria-label*='year' i]"
        )
        for inp in numeric_inputs:
            val = await inp.input_value()
            if not val.strip():
                await inp.fill("17")

        # Dropdowns — pick first non-placeholder option if unset
        selects = await page.query_selector_all(
            ".jobs-easy-apply-form-section__grouping select"
        )
        for sel_el in selects:
            current_val = await sel_el.input_value()
            if not current_val:
                options = await sel_el.query_selector_all("option[value]:not([value=''])")
                if options:
                    opt_val = await options[0].get_attribute("value")
                    if opt_val:
                        await sel_el.select_option(opt_val)

    async def _linkedin_click_button(self, page: Any, label: str) -> bool:
        """Click a button by aria-label or visible text. Returns True if clicked."""
        for sel in [
            f"button[aria-label='{label}']",
            f"footer button:has-text('{label}')",
            f"button:has-text('{label}')",
        ]:
            el = await page.query_selector(sel)
            if el and not await el.is_disabled():
                await el.click()
                return True
        return False

    async def _apply_greenhouse(self, page: Any, app: TailoredApplication) -> str:
        """
        Apply via Greenhouse standard application form.

        Fills personal details from env vars (CANDIDATE_NAME, CANDIDATE_EMAIL,
        CANDIDATE_PHONE) and cover letter from the tailored application.
        Resume file upload is not supported — Greenhouse requires PDF/DOCX.
        """
        import os

        from playwright.async_api import TimeoutError as PWTimeout

        posting = app.scored_job.posting
        name = os.getenv("CANDIDATE_NAME", "")
        email = os.getenv("CANDIDATE_EMAIL", os.getenv("GMAIL_SENDER", ""))
        phone = os.getenv("CANDIDATE_PHONE", "")

        try:
            await page.wait_for_selector("#application_form, form.application-form", timeout=10_000)
        except PWTimeout:
            raise RuntimeError(f"Greenhouse form not found at {posting.url}")

        parts = name.split(maxsplit=1)
        for sel, value in [
            ("#first_name", parts[0] if parts else ""),
            ("#last_name", parts[1] if len(parts) > 1 else ""),
            ("#email", email),
            ("#phone", phone),
        ]:
            el = await page.query_selector(sel)
            if el and value:
                await el.fill(value)

        for sel in ["#cover_letter", "textarea[id*='cover']", "textarea[name*='cover']"]:
            el = await page.query_selector(sel)
            if el and app.cover_letter:
                await el.fill(app.cover_letter[:3000])
                break

        if app.pdf_path and app.pdf_path.exists():
            for sel in ["input[type='file'][name*='resume']", "input[type='file'][id*='resume']", "input[type='file']"]:
                el = await page.query_selector(sel)
                if el:
                    await el.set_input_files(str(app.pdf_path))
                    break

        try:
            submit = await page.wait_for_selector("#submit_app, input[type='submit']", timeout=5_000)
            await submit.click()
        except PWTimeout:
            raise RuntimeError(f"Greenhouse submit button not found at {posting.url}")

        await page.wait_for_timeout(3000)
        return posting.job_id

    async def _apply_lever(self, page: Any, app: TailoredApplication) -> str:
        """
        Apply via Lever standard application form.

        Fills personal details from env vars (CANDIDATE_NAME, CANDIDATE_EMAIL,
        CANDIDATE_PHONE) and cover letter from the tailored application.
        Resume file upload is not supported — Lever requires PDF/DOCX.
        """
        import os

        from playwright.async_api import TimeoutError as PWTimeout

        posting = app.scored_job.posting
        name = os.getenv("CANDIDATE_NAME", "")
        email = os.getenv("CANDIDATE_EMAIL", os.getenv("GMAIL_SENDER", ""))
        phone = os.getenv("CANDIDATE_PHONE", "")

        try:
            await page.wait_for_selector(
                ".application-form, form[data-qa='application-form']", timeout=10_000
            )
        except PWTimeout:
            raise RuntimeError(f"Lever form not found at {posting.url}")

        for sel, value in [
            ("input[name='name']", name),
            ("input[name='email']", email),
            ("input[name='phone']", phone),
        ]:
            el = await page.query_selector(sel)
            if el and value:
                await el.fill(value)

        for sel in ["textarea[name='comments']", "textarea[name='cover_letter']", "textarea"]:
            el = await page.query_selector(sel)
            if el and app.cover_letter:
                await el.fill(app.cover_letter[:3000])
                break

        if app.pdf_path and app.pdf_path.exists():
            for sel in ["input[type='file'][name*='resume']", "input[type='file']"]:
                el = await page.query_selector(sel)
                if el:
                    await el.set_input_files(str(app.pdf_path))
                    break

        try:
            submit = await page.wait_for_selector(
                ".template-btn-submit, button[data-qa='btn-submit']", timeout=5_000
            )
            await submit.click()
        except PWTimeout:
            raise RuntimeError(f"Lever submit button not found at {posting.url}")

        await page.wait_for_timeout(3000)
        return posting.job_id

    async def _apply_naukri(self, page: Any, app: TailoredApplication) -> str:
        """
        Apply via Naukri's native apply flow.

        Naukri pre-fills profile data, so most fields are already populated.
        We click Apply, confirm any quick-apply modal, and handle simple
        screening questions with safe defaults.

        Raises RuntimeError if the Apply button is not found (e.g. already applied
        or the job uses an external redirect).
        """
        from playwright.async_api import TimeoutError as PWTimeout

        posting = app.scored_job.posting

        try:
            apply_btn = await page.wait_for_selector(
                "#apply-button, a.apply-button, button.apply-button, "
                "a[id*='apply'][class*='btn'], .apply-btn",
                timeout=10_000,
            )
        except PWTimeout:
            raise RuntimeError(f"No Apply button found at {posting.url}")

        await apply_btn.click()
        await page.wait_for_timeout(2000)

        # Walk up to 5 confirmation / screening steps
        for _ in range(5):
            # Already-applied banner — bail early, treat as success
            if await page.query_selector(".already-applied, [class*='already-applied']"):
                logger.info("Naukri: already applied to %s", posting.title)
                break

            # Success banner
            if await page.query_selector(
                ".success-msg, .application-success, [class*='applySuccess']"
            ):
                break

            # Click the primary confirm / submit button in any order of preference
            clicked = False
            for label in ("Apply Now", "Submit Application", "Submit", "Apply", "Confirm"):
                for sel in [
                    f"button:has-text('{label}')",
                    f"a:has-text('{label}')",
                ]:
                    el = await page.query_selector(sel)
                    if el and not await el.is_disabled():
                        await el.click()
                        await page.wait_for_timeout(1000)
                        clicked = True
                        break
                if clicked:
                    break

            if not clicked:
                break

        await page.wait_for_timeout(2000)
        return posting.job_id

    async def apply_batch(
        self, applications: list[TailoredApplication]
    ) -> list[ApplicationResult]:
        results = []
        for app in applications:
            result = await self.apply(app)
            results.append(result)
        return results