# Jireh — Autonomous Job Hunt Agent

*Jehovah Jireh: The Lord Will Provide. — Genesis 22:14*

Jireh is a multi-agent system that scouts job postings every morning, scores them against your skills profile, tailors your resume and cover letter per job, and submits applications — all before 9:15 AM IST. Every daily report leads with a scripture. The automation handles the grind; He handles the outcome.

---

## Architecture

```
orchestrator.py
    │
    ├── jireh-scout    → scrapes LinkedIn, Naukri, Greenhouse, Lever, Indeed
    ├── jireh-scorer   → scores each job 0–100 using Ollama/Llama (local, free)
    ├── jireh-tailor   → rewrites resume + cover letter per job via Llama
    ├── jireh-apply    → submits Path B applications via Playwright
    ├── jireh-reporter → sends daily digest via Telegram / email
    └── jireh-vault    → manages credentials (OS keyring + .env fallback)
```

**Two career paths:**
- **Path A** (score ≥ 60) — Director/VP roles, queued for your review before submitting
- **Path B** (score ≥ 72) — Senior QE Manager roles, auto-submitted before the 9:15 AM deadline

---

## Prerequisites

- Python 3.11 or newer
- [Ollama](https://ollama.com/download) installed and running locally
- Playwright browsers installed
- (Optional) Telegram bot for morning digests

---

## Installation

```bash
# 1. Clone and enter the project
git clone <your-repo-url>
cd jireh

# 2. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate      # Mac/Linux
# .venv\Scripts\activate       # Windows

# 3. Install dependencies
pip install -e ".[dev]"

# 4. Install Playwright browsers
playwright install chromium

# 5. Pull the Ollama models (one-time setup)
ollama pull llama3.2       # used by jireh-scorer (fast)
ollama pull llama3.1:8b    # used by jireh-tailor (higher quality)
```

---

## Configuration

### 1. Environment variables

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Minimum required to run:

```env
# Job platforms
LINKEDIN_EMAIL=your@email.com
LINKEDIN_PASSWORD=your_password
NAUKRI_EMAIL=your@email.com
NAUKRI_PASSWORD=your_password

# Telegram digest (optional but recommended)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

**Getting your Telegram bot token:**
1. Open Telegram → search `@BotFather` → send `/newbot`
2. Follow prompts, copy the token into `.env`
3. Send any message to your bot, then visit:
   `https://api.telegram.org/bot<TOKEN>/getUpdates` to find your chat ID

### 2. Skills profile

Edit `resources/skills/skills_profile.yaml` with your actual skills and ratings (1–10). This is what jireh-scorer uses to evaluate every job against you.

### 3. Resume templates

Edit the two base resume templates with your real experience:
- `resources/resumes/resume_path_a.md` — Director/VP track
- `resources/resumes/resume_path_b.md` — Senior QE Manager track

Replace all `[BRACKETED]` placeholders with your actual company names, titles, and metrics.

### 4. Agent config

`resources/config/agent_config.yaml` controls all agent behaviour:
- `apply.live_mode: false` — **default, safe**. No applications are submitted until you set this to `true`.
- `scorer.path_b_threshold: 72` — minimum score for auto-apply
- `scorer.path_a_threshold: 60` — minimum score for human-review queue

---

## Running Jireh

### Dry run (safe — no applications submitted)

```bash
python orchestrator.py run --dry-run
```

### Full run (applications submitted for Path B if `live_mode: true`)

```bash
python orchestrator.py run
```

### Check system status

```bash
python orchestrator.py status
```

### Store platform credentials in OS keyring

```bash
python orchestrator.py store-creds linkedin
python orchestrator.py store-creds naukri
```

---

## Daily Schedule (IST)

| Time  | Action                                      |
|-------|---------------------------------------------|
| 05:00 | jireh-scout wakes up, begins scraping       |
| 05:00–09:00 | Score → Tailor → Apply loop runs    |
| 09:15 | Hard deadline — no more submissions         |
| 09:30 | Daily digest sent via Telegram / email      |

---

## Running Tests

```bash
pytest tests/ -v
```

With coverage:

```bash
pytest tests/ --cov=agents --cov-report=term-missing
```

---

## Safety Defaults

- `apply.live_mode` is `false` by default — Jireh logs everything but submits nothing.
- Path A jobs (Director/VP) are **always** queued for human review, even when `live_mode: true`.
- The 9:15 AM IST deadline guard is enforced in `orchestrator.py` — no submissions after cutoff.
- Credentials never touch disk in plaintext — OS keyring is the primary backend.

---

## Project Structure

```
jireh/
├── agents/
│   ├── scout.py       — job discovery (scraping + deduplication)
│   ├── scorer.py      — Ollama-powered fit scoring
│   ├── tailor.py      — Ollama-powered resume + cover letter tailoring
│   ├── apply.py       — Playwright-based application submission
│   ├── reporter.py    — Telegram + email digest builder
│   └── vault.py       — credential and session management
├── resources/
│   ├── config/        — agent_config.yaml, career_paths.yaml
│   ├── skills/        — skills_profile.yaml
│   ├── resumes/       — base templates + tailored output
│   └── templates/     — cover letter templates
├── tests/             — pytest test suite
├── db/                — SQLite / ChromaDB (gitignored)
├── logs/              — runtime logs (gitignored)
├── orchestrator.py    — CLI entry point and pipeline coordinator
└── .env               — your secrets (never commit this)
```

---

*"A man's heart plans his way, but the Lord directs his steps." — Proverbs 16:9*
