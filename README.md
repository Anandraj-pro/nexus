# Nexus — Autonomous Job Hunt Agent

> *Connects your skills to the right openings — automatically.*

Nexus is a fully autonomous job-hunting pipeline that runs every morning and applies to the right roles before you wake up. Point it at your skills profile and resume, set your target roles, and let it work.

---

> New user? Follow the **[Setup Runbook](docs/runbook.md)** — from zero to first run in ~20 minutes.

## How It Works

```
orchestrator.py
    │
    ├── nexus-scout    → scrapes Naukri, Greenhouse, Lever, Indeed
    ├── nexus-scorer   → scores each job 0–100 using local Ollama (free)
    ├── nexus-tailor   → selects the right resume template per path
    ├── nexus-apply    → submits applications via Playwright automation
    ├── nexus-reporter → sends daily digest via Telegram + Gmail
    └── nexus-vault    → manages credentials (OS keyring + .env fallback)
```

**Two career paths — entirely score-driven:**
- **Path A** (score ≥ 60) — high-value roles queued for your review; never auto-submitted
- **Path B** (score ≥ 72) — strong matches auto-submitted before the 9:15 AM deadline

---

## Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com/download) installed and running locally
- Playwright browsers installed
- Telegram bot (optional, for morning digests)

---

## Installation

```bash
# 1. Clone and enter the project
git clone https://github.com/Anandraj-pro/nexus.git
cd nexus

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Mac/Linux
# .venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -e ".[dev]"

# 4. Install Playwright browsers (one-time)
playwright install chromium

# 5. Pull the Ollama model (one-time — only the scorer uses it)
ollama pull llama3.2
```

---

## First-Time Setup

Run the interactive wizard — it generates your `.env`, skills profile, career paths, and agent config:

```bash
python orchestrator.py init
```

Then:
1. Edit `resources/skills/skills_profile.yaml` — rate your skills 1–10
2. Replace `resources/resumes/resume_path_a.md` and `resume_path_b.md` with your actual resumes

---

## Manual Configuration

### Environment variables

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Key variables:

```env
NAUKRI_EMAIL=you@email.com
NAUKRI_PASSWORD=your_password

TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

CANDIDATE_NAME=Your Full Name
CANDIDATE_EMAIL=you@email.com
CANDIDATE_PHONE=+91XXXXXXXXXX
```

**Getting your Telegram bot:** open Telegram → `@BotFather` → `/newbot` → copy the token. Then visit `https://api.telegram.org/bot<TOKEN>/getUpdates` after messaging your bot to find your chat ID.

### Agent config

`resources/config/agent_config.yaml` controls all behaviour. Key flags:

| Setting | Default | Description |
|---|---|---|
| `apply.live_mode` | `false` | Set `true` to enable real submissions |
| `scorer.path_b_threshold` | `72` | Minimum score for auto-apply |
| `scorer.path_a_threshold` | `60` | Minimum score for human-review queue |
| `schedule.apply_deadline` | `09:15` | Hard cutoff — no submissions after this |

---

## Usage

```bash
# First-time setup
python orchestrator.py init

# Dry run — scouts, scores, and logs everything. No submissions.
python orchestrator.py run --dry-run

# Full run — submits Path B applications if live_mode: true
python orchestrator.py run

# Run as daemon — wakes every 30 min from 5:00 AM to 9:00 AM IST
python orchestrator.py schedule

# Check system status
python orchestrator.py status

# Store platform credentials in OS keyring
python orchestrator.py store-creds naukri

# Voice interface (requires: pip install -e ".[voice]")
python orchestrator.py voice
```

---

## Daily Schedule (IST)

| Time | Action |
|---|---|
| 05:00 | Scout wakes up, begins scraping |
| 05:00–09:00 | Score → Tailor → Apply loop runs every 30 min |
| 09:15 | Hard deadline — no more submissions |
| 09:30 | Daily digest sent via Telegram / Gmail |

---

## Safety Defaults

- `apply.live_mode: false` is the default — Nexus logs everything without submitting until you opt in
- Path A roles (Director/VP) are **always** queued for human review, even with `live_mode: true`
- The 9:15 AM deadline guard is enforced in `orchestrator.py` — override with `--ignore-deadline` for testing only
- Credentials never touch disk in plaintext — OS keyring is the primary backend
- Deduplication via SQLite fingerprints means you'll never apply to the same job twice across runs

---

## Testing

```bash
# Run all tests (no live services needed — LLM and browser are mocked)
pytest tests/ -v

# With coverage
pytest tests/ --cov=agents --cov-report=term-missing

# Lint and format
ruff check .
ruff format .
```

---

## Project Structure

```
nexus/
├── agents/
│   ├── scout.py         — job discovery (scraping + deduplication)
│   ├── scorer.py        — Ollama-powered fit scoring
│   ├── tailor.py        — resume template selection per path
│   ├── apply.py         — Playwright-based application submission
│   ├── reporter.py      — Telegram + Gmail digest builder
│   ├── vault.py         — credential and session management
│   ├── voice.py         — voice interface (optional)
│   ├── db.py            — SQLite deduplication store
│   └── init_wizard.py   — interactive first-time setup
├── resources/
│   ├── config/          — agent_config.yaml, career_paths.yaml
│   ├── skills/          — skills_profile.yaml (your skills rated 1–10)
│   ├── resumes/         — base templates + tailored output
│   └── platforms/       — platform URL registry
├── tests/               — pytest suite (no live services required)
├── db/                  — SQLite store (gitignored)
├── logs/                — runtime logs (gitignored)
├── orchestrator.py      — CLI entry point and pipeline coordinator
├── pyproject.toml       — dependencies and tooling config
└── .env.example         — environment variable template
```

---

## Extending Nexus

**Add a new job platform (scout):**
Implement `async def _fetch_<platform>() -> list[JobPosting]` and register it:
```python
scout.register_adapter("myplatform", _fetch_myplatform)
```

**Add a new apply adapter:**
Implement `async def _apply_<platform>(self, job, app)` in `agents/apply.py` — it's dispatched automatically via `getattr`.

**Add a new notification channel:**
Extend `NexusReporter` in `agents/reporter.py` and add the channel name to `reporter.channels` in `agent_config.yaml`.

---

## License

MIT
