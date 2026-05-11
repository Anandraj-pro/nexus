"""nexus-reporter — compiles and sends the daily digest via Telegram and/or email."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

from agents.apply import ApplicationResult, ApplyStatus

logger = logging.getLogger(__name__)

DAILY_SCRIPTURES = [
    "Proverbs 16:9 — A man's heart plans his way, but the Lord directs his steps.",
    "Jeremiah 29:11 — For I know the plans I have for you, plans to prosper you.",
    "Psalm 37:4 — Delight yourself in the Lord, and He will give you the desires of your heart.",
    "Isaiah 40:31 — Those who wait on the Lord shall renew their strength.",
    "Romans 8:28 — All things work together for good to those who love God.",
    "Philippians 4:19 — My God shall supply all your need according to His riches in glory.",
    "Joshua 1:9 — Be strong and courageous. Do not be afraid; the Lord your God is with you.",
]


@dataclass
class DigestReport:
    date: date
    total_scouted: int
    total_scored: int
    path_a_queued: list[ApplicationResult]
    path_b_applied: list[ApplicationResult]
    path_b_dry_run: list[ApplicationResult]
    external_apply: list[ApplicationResult]
    skipped_captcha: list[ApplicationResult]
    failed: list[ApplicationResult]
    scripture: str


class NexusReporter:
    """
    Builds the daily digest and sends it to configured channels.

    Telegram gets a clean Markdown message. Email gets a structured HTML report.
    Both always lead with the scripture — that is non-negotiable.
    """

    def __init__(self, config: dict[str, Any]):
        self.config = config
        reporter_cfg = config.get("reporter", {})
        self._channels: list[str] = reporter_cfg.get("channels", [])

    def build_digest(
        self,
        results: list[ApplicationResult],
        total_scouted: int,
        total_scored: int,
        run_date: date | None = None,
    ) -> DigestReport:
        run_date = run_date or date.today()
        import hashlib

        # Deterministic scripture selection based on date
        day_index = int(hashlib.md5(str(run_date).encode()).hexdigest(), 16) % len(
            DAILY_SCRIPTURES
        )
        scripture = DAILY_SCRIPTURES[day_index]

        return DigestReport(
            date=run_date,
            total_scouted=total_scouted,
            total_scored=total_scored,
            path_a_queued=[r for r in results if r.status == ApplyStatus.QUEUED_FOR_HUMAN],
            path_b_applied=[r for r in results if r.status == ApplyStatus.SUBMITTED],
            path_b_dry_run=[r for r in results if r.status == ApplyStatus.DRY_RUN],
            external_apply=[r for r in results if r.status == ApplyStatus.EXTERNAL_APPLY],
            skipped_captcha=[r for r in results if r.status == ApplyStatus.SKIPPED_CAPTCHA],
            failed=[r for r in results if r.status == ApplyStatus.FAILED],
            scripture=scripture,
        )

    def render_telegram(self, digest: DigestReport) -> str:
        """Renders the digest as Telegram Markdown."""
        is_dry_run = bool(digest.path_b_dry_run) and not digest.path_b_applied
        path_b_count = len(digest.path_b_applied) if not is_dry_run else len(digest.path_b_dry_run)
        path_b_label = "Would auto-apply (Path B — dry run)" if is_dry_run else "Auto-applied (Path B)"

        lines = [
            f"✦ *Nexus Daily Report — {digest.date}*",
            f"_{digest.scripture}_",
            "",
            f"📊 *Overview*",
            f"  Scouted: {digest.total_scouted} jobs",
            f"  Scored & qualified: {digest.total_scored}",
            f"  {path_b_label}: {path_b_count}",
            f"  Queued for your review (Path A): {len(digest.path_a_queued)}",
            f"  Apply manually (external sites): {len(digest.external_apply)}",
            "",
        ]

        if digest.path_a_queued:
            lines.append("🔵 *Needs Your Review — Path A*")
            for r in digest.path_a_queued:
                p = r.application.scored_job.posting
                score = r.application.scored_job.total_score
                lines.append(f"  [{p.title} @ {p.company}]({p.url}) — Score: {score}/100")
            lines.append("")

        if digest.path_b_applied:
            lines.append("🟢 *Auto-Applied — Path B*")
            for r in digest.path_b_applied:
                p = r.application.scored_job.posting
                score = r.application.scored_job.total_score
                lines.append(f"  ✓ {p.title} @ {p.company} — Score: {score}/100")
            lines.append("")

        if digest.path_b_dry_run:
            lines.append("🟡 *Would Apply — Path B (Dry Run)*")
            for r in digest.path_b_dry_run:
                p = r.application.scored_job.posting
                score = r.application.scored_job.total_score
                lines.append(f"  [{p.title} @ {p.company}]({p.url}) — Score: {score}/100")
            lines.append("")

        if digest.external_apply:
            lines.append("📧 *Apply Manually — External Sites*")
            for r in digest.external_apply:
                p = r.application.scored_job.posting
                score = r.application.scored_job.total_score
                lines.append(f"  [{p.title} @ {p.company}]({p.url}) — Score: {score}/100")
            lines.append("")

        if digest.skipped_captcha:
            lines.append("⚠️ *Flagged — CAPTCHA / Manual Needed*")
            for r in digest.skipped_captcha:
                p = r.application.scored_job.posting
                lines.append(f"  [{p.title} @ {p.company}]({p.url})")
            lines.append("")

        lines.append("_He goes before you. Trust the process._")
        return "\n".join(lines)

    def render_manual_apply_email(self, digest: DigestReport) -> str:
        """Plain-text email body listing jobs that need manual application."""
        jobs = digest.external_apply + digest.path_a_queued
        if not jobs:
            return ""
        lines = [
            f"Nexus — Jobs Requiring Your Attention ({digest.date})",
            "=" * 60,
            "",
            f"{digest.scripture}",
            "",
            "The following jobs could not be auto-applied.",
            "Please apply to each one manually:",
            "",
        ]
        for r in jobs:
            p = r.application.scored_job.posting
            score = r.application.scored_job.total_score
            reason = "External site (no Easy Apply)" if r.status == ApplyStatus.EXTERNAL_APPLY else "Path A — Director/VP level"
            lines += [
                f"  {p.title} @ {p.company}",
                f"  Score: {score}/100  |  {reason}",
                f"  {p.url}",
                "",
            ]
        lines.append("He goes before you. Trust the process.")
        return "\n".join(lines)

    async def send(self, digest: DigestReport) -> None:
        """Dispatch digest to all configured channels."""
        if "telegram" in self._channels:
            await self._send_telegram(digest)
        if "email" in self._channels:
            await self._send_email(digest)
            if digest.external_apply or digest.path_a_queued:
                await self._send_manual_apply_email(digest)

    async def _send_telegram(self, digest: DigestReport) -> None:
        import os

        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

        if not token or not chat_id:
            logger.warning("Telegram not configured — skipping")
            return

        try:
            from telegram import Bot

            bot = Bot(token=token)
            text = self.render_telegram(digest)
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
            logger.info("Reporter → Telegram digest sent")
        except Exception:
            logger.exception("Telegram send failed")

    async def _send_email(self, digest: DigestReport) -> None:
        import asyncio
        import os

        sender = os.getenv("GMAIL_SENDER", "")
        recipient = os.getenv("GMAIL_RECIPIENT", "")

        if not sender or not recipient:
            logger.warning("Gmail not configured — skipping")
            return

        try:
            import base64
            import email.mime.text as mt
            from pathlib import Path

            body = self.render_telegram(digest).replace("*", "").replace("_", "")
            msg = mt.MIMEText(body, "plain")
            msg["Subject"] = f"Nexus Daily Report — {digest.date}"
            msg["From"] = sender
            msg["To"] = recipient
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

            await asyncio.to_thread(self._gmail_send, raw, os.getenv, recipient)
            logger.info("Reporter → Email digest sent to %s", recipient)
        except Exception:
            logger.exception("Email send failed")

    async def _send_manual_apply_email(self, digest: DigestReport) -> None:
        import asyncio
        import os

        sender = os.getenv("GMAIL_SENDER", "")
        recipient = os.getenv("GMAIL_RECIPIENT", "")

        if not sender or not recipient:
            return

        try:
            import base64
            import email.mime.text as mt

            body = self.render_manual_apply_email(digest)
            count = len(digest.external_apply) + len(digest.path_a_queued)
            msg = mt.MIMEText(body, "plain")
            msg["Subject"] = f"Nexus — {count} Jobs Need Your Application ({digest.date})"
            msg["From"] = sender
            msg["To"] = recipient
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

            await asyncio.to_thread(self._gmail_send, raw, os.getenv, recipient)
            logger.info("Reporter → Manual-apply email sent (%d jobs)", count)
        except Exception:
            logger.exception("Manual-apply email send failed")

    @staticmethod
    def _gmail_send(raw: str, getenv: Any, recipient: str) -> None:
        """Blocking Gmail API send — called via asyncio.to_thread."""
        from pathlib import Path

        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        scopes = ["https://www.googleapis.com/auth/gmail.send"]
        token_path = Path(getenv("GMAIL_TOKEN_PATH", "resources/credentials/gmail_token.json"))
        creds_path = Path(
            getenv("GMAIL_CREDENTIALS_PATH", "resources/credentials/gmail_credentials.json")
        )

        creds: Credentials | None = None
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), scopes)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            elif creds_path.exists():
                flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), scopes)
                creds = flow.run_local_server(port=0)
            else:
                raise FileNotFoundError(
                    f"Gmail credentials not found at {creds_path}. "
                    "Run `python orchestrator.py status` to see setup instructions."
                )
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(creds.to_json())

        service = build("gmail", "v1", credentials=creds)
        service.users().messages().send(userId="me", body={"raw": raw}).execute()