"""nexus-init — interactive onboarding wizard. Generates all config files for a new user."""

from __future__ import annotations

import getpass
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

_SKILLS_TEMPLATE: dict[str, Any] = {
    "leadership": {
        "team_building": {"rating": 7, "keywords": ["team building", "hiring", "QA org"]},
        "strategy": {"rating": 7, "keywords": ["quality strategy", "test strategy", "QA roadmap"]},
        "stakeholder_management": {"rating": 7, "keywords": ["stakeholder", "executive reporting"]},
        "cross_functional": {"rating": 7, "keywords": ["cross-functional", "PM alignment"]},
        "agile_scrum": {"rating": 7, "keywords": ["agile", "scrum", "kanban"]},
    },
    "qa_engineering": {
        "test_automation": {"rating": 7, "keywords": ["automation architecture", "test framework"]},
        "api_testing": {"rating": 7, "keywords": ["API testing", "REST", "Postman"]},
        "ui_automation": {"rating": 7, "keywords": ["UI automation", "Selenium", "Playwright"]},
        "performance_testing": {"rating": 6, "keywords": ["performance testing", "JMeter", "k6"]},
        "shift_left": {"rating": 7, "keywords": ["shift-left", "TDD", "BDD"]},
    },
    "cicd_devops": {
        "cicd_pipeline": {"rating": 7, "keywords": ["CI/CD", "continuous integration"]},
        "github_actions": {"rating": 7, "keywords": ["GitHub Actions"]},
        "docker": {"rating": 6, "keywords": ["Docker", "containerization"]},
        "aws": {"rating": 5, "keywords": ["AWS", "cloud"]},
    },
    "languages": {
        "python": {"rating": 7, "keywords": ["Python", "scripting"]},
        "java": {"rating": 6, "keywords": ["Java", "Maven"]},
        "sql": {"rating": 7, "keywords": ["SQL", "database testing"]},
    },
    "soft_skills": {
        "communication": {"rating": 8, "keywords": ["communication", "presentation"]},
        "mentoring": {"rating": 8, "keywords": ["mentoring", "coaching"]},
    },
}


def run_init_wizard(console: Console) -> None:
    """Walk a new user through setting up Nexus for their profile."""
    console.print(Panel(
        "[bold cyan]Welcome to Nexus Setup[/]\n"
        "This wizard will configure Nexus for your job search.\n"
        "Your data stays local — nothing is sent anywhere.",
        border_style="cyan",
    ))

    # ── Step 1: Candidate info ─────────────────────────────────────────────────
    console.print("\n[bold]Step 1 of 5 — About you[/]")
    name = Prompt.ask("Full name")
    email = Prompt.ask("Email address")
    phone = Prompt.ask("Phone with country code (e.g. +91XXXXXXXXXX)")
    title = Prompt.ask("Current job title", default="Senior QE Manager")
    location = Prompt.ask("Your location", default="Hyderabad, India")
    experience_years = int(Prompt.ask("Years of QA/QE experience", default="10"))
    locations_raw = Prompt.ask("Job search locations (comma-separated)", default=f"{location}, Remote")
    preferred_locations = [loc.strip() for loc in locations_raw.split(",")]

    # ── Step 2: Career paths ───────────────────────────────────────────────────
    console.print("\n[bold]Step 2 of 5 — Target roles[/]")
    console.print("[dim]Path B = auto-apply (primary track). Path A = stretch roles you review before applying.[/]")

    path_b_raw = Prompt.ask("Path B titles (comma-separated)", default="Senior QE Manager, QA Manager, Lead QE")
    path_b_titles = [t.strip() for t in path_b_raw.split(",")]
    path_b_threshold = int(Prompt.ask("Minimum score to auto-apply (0–100)", default="72"))

    path_a_raw = Prompt.ask("Path A titles (comma-separated)", default="Director of QA, Head of Quality")
    path_a_titles = [t.strip() for t in path_a_raw.split(",")]
    path_a_threshold = int(Prompt.ask("Minimum score to queue for review", default="60"))

    default_keywords = (path_b_titles[:3] + path_a_titles[:2])
    keywords_raw = Prompt.ask("Search keywords (comma-separated)", default=", ".join(default_keywords))
    keywords = [k.strip() for k in keywords_raw.split(",")]

    # ── Step 3: Notifications ──────────────────────────────────────────────────
    console.print("\n[bold]Step 3 of 5 — Notifications[/]")
    console.print("[dim]Telegram: create a bot via @BotFather, get your chat ID via @userinfobot.[/]")
    telegram_token = Prompt.ask("Telegram Bot Token (blank to skip)", default="")
    telegram_chat_id = Prompt.ask("Telegram Chat ID (blank to skip)", default="")
    gmail_sender = Prompt.ask("Gmail sender address (blank to skip)", default="")
    gmail_recipient = Prompt.ask("Gmail recipient address", default=email)

    # ── Step 4: Platform credentials ──────────────────────────────────────────
    console.print("\n[bold]Step 4 of 5 — Platform credentials[/]")
    console.print("[dim]Note: LinkedIn is disabled (account ban risk). Naukri, Indeed, Greenhouse, Lever supported.[/]")
    naukri_email = Prompt.ask("Naukri email (blank to skip)", default="")
    naukri_password = getpass.getpass("Naukri password: ") if naukri_email else ""

    # ── Step 5: Schedule ──────────────────────────────────────────────────────
    console.print("\n[bold]Step 5 of 5 — Schedule[/]")
    timezone = Prompt.ask("Your timezone", default="Asia/Kolkata")
    scout_start = Prompt.ask("Pipeline start time (HH:MM, 24h)", default="05:00")
    apply_deadline = Prompt.ask("Apply deadline — no submissions after this (HH:MM, 24h)", default="09:15")

    # ── Write files ───────────────────────────────────────────────────────────
    console.print("\n[dim]Writing configuration files...[/]")

    _write_skills_profile(name, title, location, experience_years, email, preferred_locations)
    _write_career_paths(path_a_titles, path_b_titles, path_a_threshold, path_b_threshold)
    _write_agent_config(timezone, scout_start, apply_deadline, keywords, preferred_locations, experience_years)
    _write_env(email, phone, name, telegram_token, telegram_chat_id, gmail_sender, gmail_recipient,
               naukri_email, naukri_password, timezone, apply_deadline)
    _ensure_resume_stubs(path_a_titles[0] if path_a_titles else "Director", name)

    step = 4 if naukri_email else 3
    console.print(Panel(
        "[bold green]Nexus is configured![/]\n\n"
        "[bold]Next steps:[/]\n"
        "  1. Edit [cyan]resources/skills/skills_profile.yaml[/] — rate your skills 1–10\n"
        "  2. Edit [cyan]resources/resumes/resume_path_a.md[/] — stretch roles resume\n"
        "  3. Edit [cyan]resources/resumes/resume_path_b.md[/] — primary track resume\n"
        + (f"  4. Store Naukri creds:  [cyan]python orchestrator.py store-creds naukri[/]\n"
           if naukri_email else "") +
        f"  {step}. Test the pipeline: [cyan]python orchestrator.py run --dry-run[/]\n\n"
        "Advanced settings: [cyan]resources/config/agent_config.yaml[/]",
        border_style="green",
    ))


# ── File writers ──────────────────────────────────────────────────────────────

def _write_skills_profile(
    name: str,
    title: str,
    location: str,
    experience_years: int,
    email: str,
    preferred_locations: list[str],
) -> None:
    path = Path("resources/skills/skills_profile.yaml")
    path.parent.mkdir(parents=True, exist_ok=True)

    doc: dict[str, Any] = {
        "profile": {
            "name": name,
            "title": title,
            "location": location,
            "experience_years": experience_years,
            "email": email,
        },
        "summary": (
            f"{experience_years}-year QE professional. "
            "Update this summary to reflect your actual background and strengths."
        ),
    }
    doc.update(_SKILLS_TEMPLATE)
    doc["preferences"] = {
        "preferred_locations": preferred_locations,
        "remote_ok": True,
        "relocation_ok": False,
        "notice_period_days": 30,
    }

    with open(path, "w") as f:
        f.write(
            "# ─── Nexus Skills Profile ────────────────────────────────────────────────────\n"
            "# Rate each skill 1–10. The Scorer uses these weights against job requirements.\n"
            "# Run: python orchestrator.py run --dry-run   to test after updating.\n\n"
        )
        yaml.dump(doc, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    print("  ✓ resources/skills/skills_profile.yaml")


def _write_career_paths(
    path_a_titles: list[str],
    path_b_titles: list[str],
    path_a_threshold: int,
    path_b_threshold: int,
) -> None:
    path = Path("resources/config/career_paths.yaml")
    path.parent.mkdir(parents=True, exist_ok=True)

    doc: dict[str, Any] = {
        "paths": {
            "path_a": {
                "name": "Stretch / Senior Track",
                "description": "Roles requiring personal judgment — Nexus queues these for your review",
                "human_approval_required": True,
                "max_per_day": 3,
                "score_threshold": path_a_threshold,
                "resume_variant": "path_a",
                "auto_apply": False,
                "queue_label": "Needs Your Review",
                "target_titles": path_a_titles,
            },
            "path_b": {
                "name": "Primary Track",
                "description": "Strong-fit roles — Nexus applies automatically before the deadline",
                "human_approval_required": False,
                "max_per_day": 15,
                "score_threshold": path_b_threshold,
                "resume_variant": "path_b",
                "auto_apply": True,
                "queue_label": "Auto-Applied",
                "target_titles": path_b_titles,
            },
        },
        "scoring_signals": {
            "strong_positive": [
                "automation architecture", "test framework", "CI/CD",
                "quality strategy", "team building", "shift-left",
            ],
            "mild_positive": ["agile", "scrum", "API testing", "Selenium", "Playwright", "Python"],
            "strong_negative": ["fresher", "0-2 years", "junior", "manual testing only"],
            "mild_negative": ["gaming", "hardware", "embedded systems"],
        },
    }

    with open(path, "w") as f:
        f.write(
            "# ─── Nexus Career Paths ─────────────────────────────────────────────────────\n"
            "# Path A = stretch roles (human review before applying).\n"
            "# Path B = primary track (auto-applied before deadline).\n\n"
        )
        yaml.dump(doc, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    print("  ✓ resources/config/career_paths.yaml")


def _write_agent_config(
    timezone: str,
    scout_start: str,
    apply_deadline: str,
    keywords: list[str],
    locations: list[str],
    experience_years: int,
) -> None:
    path = Path("resources/config/agent_config.yaml")
    path.parent.mkdir(parents=True, exist_ok=True)

    existing: dict[str, Any] = {}
    if path.exists():
        with open(path) as f:
            existing = yaml.safe_load(f) or {}

    existing["system"] = {
        "name": "Nexus",
        "version": "1.0.0",
        "timezone": timezone,
        "log_level": "INFO",
        "log_file": "logs/nexus.log",
        "db_path": "db/nexus.db",
    }
    existing["schedule"] = {
        "scout_start": scout_start,
        "apply_deadline": apply_deadline,
        "scout_interval_minutes": 30,
    }
    existing.setdefault("llm", {}).update({
        "provider": "ollama",
        "base_url": "http://localhost:11434",
        "scorer_model": "llama3.2",
        "temperature": 0.3,
    })
    existing["scout"] = {
        "enabled": True,
        "platforms": ["naukri", "greenhouse", "lever", "indeed"],
        "keywords": keywords,
        "locations": locations,
        "exclude_keywords": ["fresher", "0-2 years", "junior", "associate"],
        "max_jobs_per_run": 100,
        "deduplicate": True,
    }
    existing.setdefault("scorer", {}).update({
        "enabled": True,
        "score_range": [0, 100],
        "path_b_threshold": 72,
        "path_a_threshold": 60,
        "below_threshold_action": "skip",
        "scoring_weights": {
            "experience_match": 0.30,
            "skills_match": 0.35,
            "domain_match": 0.20,
            "seniority_match": 0.15,
        },
    })
    existing.setdefault("tailor", {}).update({
        "enabled": True,
        "resume_template_path_a": "resources/resumes/resume_path_a.md",
        "resume_template_path_b": "resources/resumes/resume_path_b.md",
        "output_dir": "resources/resumes/tailored/",
    })
    existing.setdefault("apply", {}).update({
        "enabled": True,
        "live_mode": False,
        "browser": "chromium",
        "headless": True,
        "slow_mo_ms": 50,
        "timeout_ms": 30000,
        "retry_attempts": 2,
        "on_captcha": "skip_and_flag",
        "candidate_experience_years": experience_years,
    })
    existing["reporter"] = {
        "enabled": True,
        "channels": ["telegram", "email"],
    }
    existing.setdefault("vault", {}).update({
        "credential_backend": "keyring",
        "session_dir": "resources/credentials/sessions/",
    })

    with open(path, "w") as f:
        f.write("# ─── Nexus Agent Configuration ──────────────────────────────────────────────\n\n")
        yaml.dump(existing, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    print("  ✓ resources/config/agent_config.yaml")


def _write_env(
    email: str,
    phone: str,
    name: str,
    telegram_token: str,
    telegram_chat_id: str,
    gmail_sender: str,
    gmail_recipient: str,
    naukri_email: str,
    naukri_password: str,
    timezone: str,
    apply_deadline: str,
) -> None:
    lines = [
        "# ─── Nexus — generated by 'python orchestrator.py init' ─────────────────────",
        "",
        "# ─── Job Platforms ────────────────────────────────────────────────────────────",
        f"NAUKRI_EMAIL={naukri_email}",
        f"NAUKRI_PASSWORD={naukri_password}",
        "",
        "# ─── Notifications ────────────────────────────────────────────────────────────",
        f"TELEGRAM_BOT_TOKEN={telegram_token}",
        f"TELEGRAM_CHAT_ID={telegram_chat_id}",
        f"GMAIL_SENDER={gmail_sender}",
        f"GMAIL_RECIPIENT={gmail_recipient}",
        "GMAIL_CREDENTIALS_PATH=resources/credentials/gmail_credentials.json",
        "GMAIL_TOKEN_PATH=resources/credentials/gmail_token.json",
        "",
        "# ─── Candidate Details (used for Greenhouse / Lever form auto-fill) ───────────",
        f"CANDIDATE_NAME={name}",
        f"CANDIDATE_EMAIL={email}",
        f"CANDIDATE_PHONE={phone}",
        "",
        "# ─── Scheduling ───────────────────────────────────────────────────────────────",
        f"TIMEZONE={timezone}",
        f"APPLY_DEADLINE_IST={apply_deadline}",
        "",
        "# ─── Database ─────────────────────────────────────────────────────────────────",
        "DATABASE_URL=sqlite:///db/nexus.db",
        "",
        "# ─── Logging ──────────────────────────────────────────────────────────────────",
        "LOG_LEVEL=INFO",
        "LOG_FILE=logs/nexus.log",
    ]
    Path(".env").write_text("\n".join(lines) + "\n")
    print("  ✓ .env")


def _ensure_resume_stubs(path_a_label: str, name: str) -> None:
    resumes_dir = Path("resources/resumes")
    resumes_dir.mkdir(parents=True, exist_ok=True)

    for filename, label in [
        ("resume_path_a.md", f"Stretch / Senior Track — {path_a_label}"),
        ("resume_path_b.md", "Primary Track"),
    ]:
        p = resumes_dir / filename
        if not p.exists():
            p.write_text(
                f"# {name}\n\n"
                f"<!-- {label} resume -->\n"
                "<!-- Replace this file with your resume in Markdown format -->\n\n"
                "## Summary\n\nYour summary here.\n\n"
                "## Experience\n\nYour experience here.\n\n"
                "## Skills\n\nYour skills here.\n"
            )
            print(f"  ✓ resources/resumes/{filename} (placeholder created)")
        else:
            print(f"  · resources/resumes/{filename} (already exists — not overwritten)")