# Nexus — New User Setup Runbook

This guide walks you from zero to your first automated job application run.
Total setup time: ~20 minutes.

---

## Prerequisites

Install these before starting:

| Tool | Version | Download |
|---|---|---|
| Python | 3.11 or newer | https://python.org/downloads |
| Git | any | https://git-scm.com |
| Ollama | latest | https://ollama.com/download |

Verify everything is working:

```bash
python --version      # should print 3.11.x or newer
git --version
ollama --version
```

> **Windows note:** Use PowerShell or Command Prompt. If `python` is not found, try `python3` or check that Python was added to PATH during installation.

---

## Step 1 — Clone and Install

```bash
# Clone the repo
git clone https://github.com/Anandraj-pro/nexus.git
cd nexus

# Create a virtual environment
python -m venv .venv

# Activate it
source .venv/bin/activate        # Mac / Linux
.venv\Scripts\activate           # Windows PowerShell

# Install Nexus and all dependencies
pip install -e ".[dev]"

# Install the Playwright browser (one-time)
playwright install chromium

# Pull the Ollama model used by the scorer (one-time, ~2 GB)
ollama pull llama3.2
```

---

## Step 2 — Run the Setup Wizard

```bash
python orchestrator.py init
```

The wizard walks you through 5 steps and generates all config files. Here is what it asks:

### Step 1 of 5 — About you
- Full name, email, phone (with country code e.g. `+91XXXXXXXXXX`)
- Current job title (default: `Senior QE Manager`)
- Your location (default: `Hyderabad, India`)
- Years of QA/QE experience
- Job search locations (e.g. `Hyderabad, Remote, Bangalore`)

### Step 2 of 5 — Target roles
- **Path B titles** — roles Nexus will auto-apply to (e.g. `Senior QE Manager, QA Manager, Lead QE`)
- **Path B score threshold** — minimum fit score to auto-apply (default: `72`)
- **Path A titles** — stretch roles Nexus queues for your manual review (e.g. `Director of QA, Head of Quality`)
- **Path A score threshold** — minimum score to queue (default: `60`)
- Search keywords — auto-populated from your titles, you can add more

### Step 3 of 5 — Notifications
- Telegram Bot Token and Chat ID (see [Setting up Telegram](#setting-up-telegram) below)
- Gmail sender / recipient address (see [Setting up Gmail](#setting-up-gmail-optional) below)
- You can leave both blank to skip and add them to `.env` later

### Step 4 of 5 — Platform credentials
- Naukri email and password
- LinkedIn is intentionally disabled (account ban risk)

### Step 5 of 5 — Schedule
- Timezone (default: `Asia/Kolkata`)
- Pipeline start time (default: `05:00`)
- Apply deadline — no submissions after this time (default: `09:15`)

### What the wizard creates

| File | Description |
|---|---|
| `.env` | All secrets and credentials |
| `resources/skills/skills_profile.yaml` | Your skills rated 1–10 |
| `resources/config/career_paths.yaml` | Path A / Path B role targets |
| `resources/config/agent_config.yaml` | All agent settings |
| `resources/resumes/resume_path_a.md` | Resume stub (if not already present) |
| `resources/resumes/resume_path_b.md` | Resume stub (if not already present) |

---

## Step 3 — Tune Your Skills Profile

Open `resources/skills/skills_profile.yaml` and update the ratings (1–10) to reflect your actual proficiency:

```yaml
qa_engineering:
  test_automation:
    rating: 9          # change this to your honest self-assessment
    keywords: ["automation architecture", "test framework"]
  api_testing:
    rating: 8
    ...
```

**Why this matters:** The scorer compares your skill ratings against every job's requirements. Inflated scores produce bad matches; honest scores produce good ones.

---

## Step 4 — Add Your Resumes

Replace the stub files with your actual resumes in Markdown format:

- `resources/resumes/resume_path_b.md` — your primary track resume (Senior Manager / Lead QE roles)
- `resources/resumes/resume_path_a.md` — your stretch resume (Director / VP / Head of roles)

**Format tips:**
- Use plain Markdown with `##` section headings
- Include measurable achievements ("Reduced release defect rate by 40%")
- Match your keywords to the scoring signals in `career_paths.yaml`
- ATS systems score the raw text, so keep formatting simple

---

## Step 5 — Setting up Telegram

Telegram sends your daily digest — a summary of every job found, scored, and applied to.

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow the prompts — choose any name and username
3. BotFather gives you a token like `7123456789:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` — copy it
4. Search for **@userinfobot** and send any message — it replies with your Chat ID
5. Add both to your `.env`:

```env
TELEGRAM_BOT_TOKEN=7123456789:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TELEGRAM_CHAT_ID=123456789
```

Test it:

```bash
python orchestrator.py status
```

If Telegram is configured correctly, the status output will confirm it.

---

## Step 6 — Setting up Gmail (optional)

Gmail sends a formatted HTML digest alongside the Telegram message.

1. Go to [Google Cloud Console](https://console.cloud.google.com) → create a project (or use an existing one)
2. Enable the **Gmail API**
3. Go to **Credentials** → **Create Credentials** → **OAuth 2.0 Client ID** → Desktop app
4. Download the JSON file and save it as `resources/credentials/gmail_credentials.json`
5. Add to `.env`:

```env
GMAIL_SENDER=you@gmail.com
GMAIL_RECIPIENT=you@gmail.com
GMAIL_CREDENTIALS_PATH=resources/credentials/gmail_credentials.json
GMAIL_TOKEN_PATH=resources/credentials/gmail_token.json
```

On first run with Gmail enabled, a browser window opens for you to authorise access. The token is saved to `gmail_token.json` and reused on all future runs.

---

## Step 7 — Store Credentials Securely

If you entered Naukri credentials in the wizard, they are in `.env` as plaintext. Store them in your OS keyring instead:

```bash
python orchestrator.py store-creds naukri
```

Nexus reads from the keyring first and falls back to `.env`. The keyring is the safer option.

---

## Step 8 — Verify the Setup

```bash
python orchestrator.py status
```

Expected output:

```
Nexus System Status
  Live mode:        False   ✓
  Apply deadline:   09:15 IST
  Path B threshold: 72/100
  ...
```

`Live mode: False` is correct — this means Nexus will log everything but not submit anything yet.

---

## Step 9 — First Dry Run

Run the full pipeline without submitting any applications:

```bash
python orchestrator.py run --dry-run
```

This scouts jobs, scores them, selects resumes, and logs what would have been applied — completely safe. Check the output and the daily digest to confirm everything looks right.

---

## Step 10 — Go Live

Once you are happy with the dry run results:

1. Open `resources/config/agent_config.yaml`
2. Change the live mode flag:

```yaml
apply:
  live_mode: true    # was false
```

3. Run the pipeline:

```bash
python orchestrator.py run
```

Nexus will now auto-submit Path B applications before your configured deadline.

> **Path A roles are never auto-submitted**, even with `live_mode: true`. They always land in your review queue.

---

## Step 11 — Run as a Daily Daemon

Start the scheduler so Nexus runs automatically every morning:

```bash
python orchestrator.py schedule
```

The daemon wakes at your configured start time (default 05:00), runs the full pipeline, repeats every 30 minutes until the apply deadline (default 09:15), then sends your digest and goes back to sleep.

To run this persistently on a server or always-on machine, wrap it in a system service or use `nohup`:

```bash
nohup python orchestrator.py schedule > logs/daemon.log 2>&1 &
```

---

## Configuration Reference

| File | What to edit |
|---|---|
| `.env` | Credentials, API tokens, candidate contact info |
| `resources/skills/skills_profile.yaml` | Your skill ratings (1–10) |
| `resources/resumes/resume_path_b.md` | Primary track resume |
| `resources/resumes/resume_path_a.md` | Stretch roles resume |
| `resources/config/agent_config.yaml` | Schedule, thresholds, `live_mode`, platforms |
| `resources/config/career_paths.yaml` | Target titles, scoring signals |

---

## Troubleshooting

**`ModuleNotFoundError`**
You are not in the virtual environment. Run `.venv\Scripts\activate` (Windows) or `source .venv/bin/activate` (Mac/Linux) and try again.

**`ollama: command not found` or scorer fails**
Ollama is not running. Start it with `ollama serve` in a separate terminal, or install it from https://ollama.com/download.

**`llama3.2` model not found**
Run `ollama pull llama3.2` to download the model.

**Naukri login keeps re-opening the browser**
The session cookie has expired. Delete `resources/credentials/sessions/naukri_session.json` and log in again on the next run.

**No jobs found**
Check `resources/config/agent_config.yaml` → `scout.keywords` — make sure the keywords match real job titles on your target platforms.

**All jobs score below threshold**
Review `resources/skills/skills_profile.yaml` — ratings may be too conservative, or the keywords in `career_paths.yaml` may not match the job descriptions being returned.

**Pipeline runs after 09:15 and skips apply phase**
This is by design — the deadline guard prevents late submissions. Use `--ignore-deadline` to override during testing:
```bash
python orchestrator.py run --ignore-deadline
```
