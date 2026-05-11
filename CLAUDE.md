# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Behavioral guidelines to reduce common LLM coding mistakes.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---

## Project: Nexus — Autonomous Job Hunt Agent

Nexus is a generalized autonomous job-hunt pipeline. Any user can run `python orchestrator.py init` to generate their personal config (skills profile, target roles, credentials) and then run the pipeline unattended every morning before a configurable deadline.

`main.py` is an unused PyCharm placeholder. The real entry point is `orchestrator.py`.

### Commands

```bash
# Install (with dev extras)
pip install -e ".[dev]"

# Install Playwright browsers (one-time)
playwright install chromium

# Pull Ollama model (one-time — only scorer uses LLM)
ollama pull llama3.2

# First-time setup for a new user
python orchestrator.py init

# Run pipeline (dry-run, safe — no submissions)
python orchestrator.py run --dry-run

# Run pipeline (live — submits Path B if live_mode: true in agent_config.yaml)
python orchestrator.py run

# Bypass the 9:15 AM IST deadline guard (testing only)
python orchestrator.py run --ignore-deadline

# Start daemon: runs every 30 min from 5:00 AM to 9:00 AM IST via APScheduler
python orchestrator.py schedule

# Check status / config
python orchestrator.py status

# Store platform credentials in OS keyring
python orchestrator.py store-creds linkedin
python orchestrator.py store-creds naukri

# Activate voice interface (requires: pip install -e ".[voice]")
python orchestrator.py voice

# Run all tests
pytest tests/ -v

# Run a single test
pytest tests/test_scorer.py::test_score_returns_scored_job -v

# Tests with coverage
pytest tests/ --cov=agents --cov-report=term-missing

# Lint
ruff check .

# Format
ruff format .

# Type check
mypy agents/
```

Ruff is configured at line-length 100, targeting Python 3.11. `asyncio_mode = "auto"` is set in `pyproject.toml`, so `@pytest.mark.asyncio` on async test functions is optional.

### Architecture

**Data flow** — typed dataclasses passed through five sequential async stages:

```
JobPosting  →  ScoredJob  →  TailoredApplication  →  ApplicationResult
   scout         scorer           tailor                    apply
                                                              ↓
                                                        NexusReporter (digest)
```

`orchestrator.py` drives the pipeline as a single `async def run_pipeline()`. Agent classes are imported *lazily inside* that function — this prevents Playwright from being imported at module level.

**Two career paths** (thresholds configured in `agent_config.yaml`):
- **Path A** (score ≥ 60): Director/VP roles — always `QUEUED_FOR_HUMAN`, never auto-submitted even with `live_mode: true`. Max 3/day.
- **Path B** (score ≥ 72): Senior QE Manager roles — auto-submitted via Playwright before the 9:15 IST deadline. Max 15/day.

Path routing is **entirely score-driven**. The LLM's `path_recommendation` field in its JSON response is explicitly ignored — only the numeric score is used. This prevents LLM mistakes from bypassing path constraints.

**LLM usage:** Only `NexusScorer` uses Ollama (`llama3.2`) — the tailor no longer calls an LLM (base resume is used as-is; ATS scores the raw resume). Scorer calls the blocking `ollama.chat()` inside `asyncio.to_thread()`. Returns structured JSON extracted via `_extract_json()` with `_escape_json_strings()` repair. On parse failure, a safe default (score=0) is returned. The scorer prompt includes the candidate's `experience_years` from `skills_profile.yaml` dynamically.

**Platform adapters in NexusScout:** Uses a registry pattern — built-in adapters for Greenhouse, Lever, and Indeed HTML are registered in `_register_built_in_adapters()`. Naukri is Playwright-based. **LinkedIn is not in the enabled platforms list** (account ban risk). New platforms: implement `async def _fetch_<platform>() -> list[JobPosting]` and call `scout.register_adapter(platform, fn)`.

**Platform adapters in NexusApply:** Dispatches to `_apply_<platform>()` via `getattr`. Greenhouse and Lever are partially implemented; Naukri has the most practical implementation. **LinkedIn apply adapter exists in code but is not called** (LinkedIn disabled in scout). This is the primary area for extension.

**Deduplication:** Job fingerprint = `sha256(title.lower() | company.lower() | platform)[:16]`. Stored in SQLite (`db/jireh.db`). If the same job appears across multiple keyword searches, only the highest-scoring instance is kept. Fingerprints persist across runs to avoid re-applying.

**Session persistence:** LinkedIn and Naukri cookies are saved as JSON in `resources/credentials/sessions/`. On first run, a visible browser opens and waits for manual login (LinkedIn: 2 min, Naukri: 5 min). Subsequent runs load cookies and run headless. Sessions are cleared and re-prompted if authentication fails mid-scrape.

**Credentials:** `JirehVault` reads from OS keyring first, falls back to `.env`. Candidate identity (`CANDIDATE_NAME`, `CANDIDATE_EMAIL`, `CANDIDATE_PHONE`) is injected into application forms from env vars.

**Configuration:**
- `resources/config/agent_config.yaml` — all agent behaviour; critical flag is `apply.live_mode: false` (default). Also controls LLM models, scheduling times, enabled platforms, and path thresholds.
- `resources/config/career_paths.yaml` — per-path metadata: `human_approval_required`, `max_per_day`, target titles, and scoring signal keywords (strong_positive, mild_positive, strong_negative) used in scorer prompts.
- `resources/skills/skills_profile.yaml` — skills rated 1–10; fed verbatim into the scorer LLM prompt. Keep this curated.
- `resources/resumes/resume_path_a.md` and `resume_path_b.md` — base templates; tailored versions are saved to `resources/resumes/tailored/`.
- `.env` (from `.env.example`) — secrets: platform credentials, Telegram token, Gmail OAuth paths, candidate contact info.

**Safety invariants:**
- `apply.live_mode: false` is the default — the pipeline logs everything without submitting.
- The 9:15 AM IST deadline guard (`_past_deadline()` in `orchestrator.py`) is checked before the apply phase. Override with `--ignore-deadline` for testing only.
- Path A jobs bypass the apply logic unconditionally, regardless of `live_mode`.
- Dry-run mode marks all results `ApplyStatus.DRY_RUN` — completely airtight, no submissions.

**Testing:** Tests mock `agents.scorer._ollama_chat` (the module-level function) directly, so no running Ollama instance is needed. Playwright adapters are mocked similarly. DB tests use `tmp_path` fixtures for isolated SQLite instances. No live services required for `pytest`.

**First-time user setup:** `python orchestrator.py init` runs an interactive wizard (`agents/init_wizard.py`) that generates `.env`, `resources/skills/skills_profile.yaml`, `resources/config/career_paths.yaml`, and `resources/config/agent_config.yaml` from user input. Resume stubs are created if they don't already exist. Users then edit `skills_profile.yaml` to fine-tune skill ratings (1–10) and replace the resume stubs with their actual resumes.