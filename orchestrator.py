"""
Jireh Orchestrator — the central coordinator for all agents.

Jehovah Jireh: The Lord Will Provide. (Genesis 22:14)
Proverbs 16:9: A man's heart plans his way, but the Lord directs his steps.

Run the full pipeline:
    python orchestrator.py run

Run on schedule (daemon — wakes at 5 AM IST, re-checks every 30 min):
    python orchestrator.py schedule

Check status:
    python orchestrator.py status

Dry-run (no actual submissions):
    python orchestrator.py run --dry-run
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import click
import yaml
from dotenv import load_dotenv
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel

load_dotenv()

console = Console()

# ─── Logging setup ────────────────────────────────────────────────────────────

def _setup_logging(log_level: str = "INFO", log_file: str = "logs/jireh.log") -> None:
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s",
        handlers=[
            RichHandler(console=console, show_path=False, rich_tracebacks=True),
            logging.FileHandler(log_file),
        ],
    )


logger = logging.getLogger("jireh.orchestrator")


# ─── Config loader ────────────────────────────────────────────────────────────

def load_config(config_path: str = "resources/config/agent_config.yaml") -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


def load_skills(skills_path: str = "resources/skills/skills_profile.yaml") -> dict:
    with open(skills_path) as f:
        return yaml.safe_load(f)


def load_career_paths(paths_file: str = "resources/config/career_paths.yaml") -> dict:
    with open(paths_file) as f:
        return yaml.safe_load(f)


# ─── Deadline guard ───────────────────────────────────────────────────────────

def _past_deadline(deadline_ist: str = "09:15") -> bool:
    """Returns True if current IST time is past the apply deadline."""
    import pytz

    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)
    h, m = map(int, deadline_ist.split(":"))
    cutoff = now.replace(hour=h, minute=m, second=0, microsecond=0)
    return now >= cutoff


# ─── Core pipeline ────────────────────────────────────────────────────────────

async def run_pipeline(config: dict, skills: dict, dry_run: bool = False, ignore_deadline: bool = False) -> None:
    from agents.scout import JirehScout
    from agents.scorer import JirehScorer
    from agents.tailor import JirehTailor
    from agents.apply import JirehApply
    from agents.reporter import JirehReporter
    from agents.vault import JirehVault

    # Override live_mode if dry_run flag is set
    if dry_run:
        config.setdefault("apply", {})["live_mode"] = False

    deadline = config.get("schedule", {}).get("apply_deadline", "09:15")

    console.print(
        Panel(
            "[bold gold1]Jireh is awake.[/]\n"
            "[dim]Jehovah Jireh — The Lord Will Provide[/]\n"
            f"[dim]Pipeline start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/]",
            border_style="gold1",
        )
    )

    vault = JirehVault(config)
    scout = JirehScout(config, vault=vault)
    scorer = JirehScorer(config, skills)
    tailor = JirehTailor(config)
    applier = JirehApply(config)
    reporter = JirehReporter(config)

    # ── 1. Scout ──────────────────────────────────────────────────────────────
    logger.info("Phase 1/5 — jireh-scout starting")
    postings = await scout.run()
    logger.info("Scout complete: %d new postings", len(postings))

    if not postings:
        logger.info("No new postings found. Sending minimal digest.")
        digest = reporter.build_digest([], 0, 0)
        await reporter.send(digest)
        return

    # ── 2. Score ──────────────────────────────────────────────────────────────
    logger.info("Phase 2/5 — jireh-scorer starting")
    scored_jobs = await scorer.score_batch(postings)
    logger.info(
        "Scorer complete: %d/%d qualified (path_a: %d, path_b: %d)",
        len(scored_jobs),
        len(postings),
        sum(1 for j in scored_jobs if j.path_recommendation == "path_a"),
        sum(1 for j in scored_jobs if j.path_recommendation == "path_b"),
    )

    # ── 3. Tailor ─────────────────────────────────────────────────────────────
    logger.info("Phase 3/5 — jireh-tailor starting")
    applications = await tailor.tailor_batch(scored_jobs)
    logger.info("Tailor complete: %d applications prepared", len(applications))

    # ── 4. Apply ──────────────────────────────────────────────────────────────
    if not ignore_deadline and _past_deadline(deadline):
        logger.warning("Past apply deadline (%s IST) — skipping submission phase", deadline)
        results = []
    else:
        logger.info("Phase 4/5 — jireh-apply starting")
        results = await applier.apply_batch(applications)
        submitted = sum(1 for r in results if r.status.value == "submitted")
        logger.info("Apply complete: %d submitted", submitted)

    # ── 5. Report ─────────────────────────────────────────────────────────────
    logger.info("Phase 5/5 — jireh-reporter starting")
    digest = reporter.build_digest(results, len(postings), len(scored_jobs))
    telegram_text = reporter.render_telegram(digest)
    console.print(Panel(telegram_text, title="Daily Digest Preview", border_style="blue"))
    await reporter.send(digest)
    logger.info("Pipeline complete. He goes before you.")


# ─── Scheduler helpers ────────────────────────────────────────────────────────

def _build_schedule_times(
    scout_start: str,
    interval_minutes: int,
    deadline: str,
) -> list[tuple[int, int]]:
    """
    Return (hour, minute) pairs from scout_start up to (but not including)
    deadline, stepping by interval_minutes.

    Example: ("05:00", 30, "09:15") → [(5,0),(5,30),(6,0),...,(9,0)]
    """
    fmt = "%H:%M"
    current = datetime.strptime(scout_start, fmt)
    end = datetime.strptime(deadline, fmt)
    times: list[tuple[int, int]] = []
    while current < end:
        times.append((current.hour, current.minute))
        current += timedelta(minutes=interval_minutes)
    return times


def _next_run_label(run_times: list[tuple[int, int]], timezone: str) -> str:
    """Return a human-readable string for the next scheduled run."""
    import pytz

    tz = pytz.timezone(timezone)
    now = datetime.now(tz)
    # Find the first slot today that is still in the future
    for h, m in run_times:
        candidate = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if candidate > now:
            return candidate.strftime("%Y-%m-%d %H:%M %Z")
    # All today's slots have passed — next run is the first slot tomorrow
    tomorrow = now + timedelta(days=1)
    h, m = run_times[0]
    return tomorrow.replace(hour=h, minute=m, second=0, microsecond=0).strftime(
        "%Y-%m-%d %H:%M %Z"
    )


# ─── CLI ──────────────────────────────────────────────────────────────────────

@click.group()
def cli() -> None:
    """Jireh — Autonomous Job Hunt Agent. Jehovah Jireh: The Lord Will Provide."""


@cli.command()
@click.option("--dry-run", is_flag=True, default=False, help="Run without submitting applications")
@click.option("--ignore-deadline", is_flag=True, default=False, help="Bypass the 9:15 IST cutoff")
@click.option("--config", "config_path", default="resources/config/agent_config.yaml")
@click.option("--skills", "skills_path", default="resources/skills/skills_profile.yaml")
def run(dry_run: bool, ignore_deadline: bool, config_path: str, skills_path: str) -> None:
    """Execute the full Jireh pipeline: Scout → Score → Tailor → Apply → Report."""
    config = load_config(config_path)
    skills = load_skills(skills_path)
    _setup_logging(
        config.get("system", {}).get("log_level", "INFO"),
        config.get("system", {}).get("log_file", "logs/jireh.log"),
    )
    if dry_run:
        console.print("[yellow]DRY-RUN mode — no applications will be submitted[/]")
    if ignore_deadline:
        console.print("[yellow]Deadline guard bypassed — will submit regardless of time[/]")
    asyncio.run(run_pipeline(config, skills, dry_run=dry_run, ignore_deadline=ignore_deadline))


@cli.command()
def status() -> None:
    """Show current Jireh configuration and status."""
    config = load_config()
    console.print(Panel("[bold]Jireh System Status[/]", border_style="green"))
    console.print(f"  Live mode: {config.get('apply', {}).get('live_mode', False)}")
    console.print(f"  Apply deadline: {config.get('schedule', {}).get('apply_deadline', '09:15')} IST")
    console.print(f"  Path B threshold: {config.get('scorer', {}).get('path_b_threshold', 72)}/100")
    console.print(f"  Anthropic key set: {'ANTHROPIC_API_KEY' in os.environ}")


@cli.command()
@click.option("--dry-run", is_flag=True, default=False, help="Run without submitting applications")
@click.option("--config", "config_path", default="resources/config/agent_config.yaml")
@click.option("--skills", "skills_path", default="resources/skills/skills_profile.yaml")
def schedule(dry_run: bool, config_path: str, skills_path: str) -> None:
    """Start the Jireh scheduling daemon — runs pipeline daily on the configured schedule."""
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger

    config = load_config(config_path)
    skills = load_skills(skills_path)
    _setup_logging(
        config.get("system", {}).get("log_level", "INFO"),
        config.get("system", {}).get("log_file", "logs/jireh.log"),
    )

    sched_cfg = config.get("schedule", {})
    timezone: str = config.get("system", {}).get("timezone", "Asia/Kolkata")
    scout_start: str = sched_cfg.get("scout_start", "05:00")
    interval_minutes: int = int(sched_cfg.get("scout_interval_minutes", 30))
    deadline: str = sched_cfg.get("apply_deadline", "09:15")

    run_times = _build_schedule_times(scout_start, interval_minutes, deadline)
    if not run_times:
        console.print("[red]No valid schedule slots found — check agent_config.yaml[/]")
        return

    def _run_job() -> None:
        logger.info("Scheduler fired — starting pipeline")
        asyncio.run(run_pipeline(config, skills, dry_run=dry_run))

    scheduler = BlockingScheduler(timezone=timezone)
    for h, m in run_times:
        scheduler.add_job(
            _run_job,
            CronTrigger(hour=h, minute=m, timezone=timezone),
            id=f"jireh_{h:02d}{m:02d}",
            name=f"Jireh {h:02d}:{m:02d} IST",
            misfire_grace_time=300,
            coalesce=True,
        )

    time_labels = "  ".join(f"{h:02d}:{m:02d}" for h, m in run_times)
    next_run_str = _next_run_label(run_times, timezone)

    console.print(
        Panel(
            "[bold gold1]Jireh Scheduler Active[/]\n"
            f"[dim]Timezone : {timezone}[/]\n"
            f"[dim]Runs at  : {time_labels} IST[/]\n"
            f"[dim]Deadline : {deadline} IST — no submissions after this[/]\n"
            f"[dim]Mode     : {'DRY-RUN ⚠' if dry_run else 'LIVE ✓'}[/]\n"
            f"[dim]Next run : {next_run_str}[/]",
            border_style="gold1",
        )
    )

    logger.info(
        "Scheduler armed — %d daily slots, next: %s", len(run_times), next_run_str
    )

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped by user")
        console.print("\n[yellow]Jireh scheduler stopped. He still provides.[/]")


@cli.command()
@click.option("--config", "config_path", default="resources/config/agent_config.yaml")
@click.option("--skills", "skills_path", default="resources/skills/skills_profile.yaml")
def voice(config_path: str, skills_path: str) -> None:
    """Activate Jireh voice interface — press Enter to speak commands."""
    try:
        from agents.voice import JirehVoice
    except ImportError:
        console.print(
            "[red]Voice extras not installed.[/] Run:\n"
            "  pip install -e '.[voice]'\n"
            "  brew install portaudio  (macOS — one time)"
        )
        return

    config = load_config(config_path)
    skills = load_skills(skills_path)
    _setup_logging(
        config.get("system", {}).get("log_level", "INFO"),
        config.get("system", {}).get("log_file", "logs/jireh.log"),
    )

    async def _pipeline(dry_run: bool = True) -> None:
        await run_pipeline(config, skills, dry_run=dry_run)

    voice_agent = JirehVoice(config, _pipeline)
    asyncio.run(voice_agent.run_loop())


@cli.command()
@click.argument("platform")
@click.option("--email", prompt=True)
@click.option("--password", prompt=True, hide_input=True)
def store_creds(platform: str, email: str, password: str) -> None:
    """Store platform credentials in the OS keyring."""
    from agents.vault import JirehVault

    config = load_config()
    vault = JirehVault(config)
    vault.store_credentials(platform, email, password)
    console.print(f"[green]Credentials stored for {platform}[/]")


if __name__ == "__main__":
    cli()