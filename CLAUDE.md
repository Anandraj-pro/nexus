# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

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

## Project: Jireh — Autonomous Job Hunt Agent

Jireh is an autonomous job-hunt pipeline that runs every morning before 9:15 AM IST. It scrapes job boards, scores each posting against a skills profile using a local LLM (Ollama), tailors the resume and cover letter per job, submits Path B applications automatically, and sends a daily digest via Telegram/email.

`main.py` is an unused PyCharm placeholder. The real entry point is `orchestrator.py`.

### Commands

```bash
# Install (with dev extras)
pip install -e ".[dev]"

# Install Playwright browsers (one-time)
playwright install chromium

# Pull Ollama models (one-time)
ollama pull llama3.2
ollama pull llama3.1:8b

# Run pipeline (dry-run, safe — no submissions)
python orchestrator.py run --dry-run

# Run pipeline (live — submits Path B if live_mode: true in agent_config.yaml)
python orchestrator.py run

# Check status / config
python orchestrator.py status

# Store platform credentials in OS keyring
python orchestrator.py store-creds linkedin
python orchestrator.py store-creds naukri

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
```

`orchestrator.py` drives the pipeline as a single `async def run_pipeline()`. Agent classes are imported lazily inside that function to avoid Playwright being imported at module level.

**Two career paths:**
- **Path A** (score ≥ 60): Director/VP roles — always `QUEUED_FOR_HUMAN`, never auto-submitted even with `live_mode: true`.
- **Path B** (score ≥ 72): Senior QE Manager roles — auto-submitted via Playwright before the 9:15 IST deadline.

**LLM usage:** Both `JirehScorer` and `JirehTailor` call Ollama's blocking `ollama.chat()` inside `asyncio.to_thread()` to keep the async pipeline non-blocking. Scorer uses `llama3.2`; tailor uses `llama3.1:8b`. Both return structured JSON extracted via `_extract_json()` which strips markdown fences.

**Platform adapters:** `JirehScout` uses a registry pattern; built-in adapters for Greenhouse, Lever, and Indeed HTML are registered in `_register_built_in_adapters()`. LinkedIn and Naukri (Playwright-based) are registered separately. `JirehApply` dispatches to `_apply_<platform>()` methods — most are stubs and the primary area for extension.

**Credentials:** `JirehVault` reads from OS keyring first, falls back to `.env`. Browser sessions (cookies) are persisted as JSON in `resources/credentials/sessions/`.

**Configuration:**
- `resources/config/agent_config.yaml` — all agent behaviour; critical flag is `apply.live_mode: false` (default).
- `resources/skills/skills_profile.yaml` — skills rated 1–10; fed directly to the scorer LLM prompt.
- `resources/resumes/resume_path_a.md` and `resume_path_b.md` — base templates for tailoring.
- `.env` (from `.env.example`) — secrets: platform credentials, Telegram token, Gmail OAuth paths.

**Safety invariants:**
- `apply.live_mode: false` is the default — the pipeline logs everything without submitting.
- The 9:15 AM IST deadline guard in `orchestrator.py::_past_deadline()` is checked before the apply phase.
- Path A jobs bypass the apply logic unconditionally.

**Testing:** Tests mock `agents.scorer._ollama_chat` (the module-level function) directly, so no running Ollama instance is needed.
