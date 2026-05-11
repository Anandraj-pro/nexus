# Nexus — Autonomous Job Hunt Agent

Any user runs `python orchestrator.py init` to generate personal config, then the pipeline runs unattended every morning before a configurable deadline. Entry point is `orchestrator.py` (`main.py` is an unused PyCharm stub).

## Efficiency tips

- **Long sessions:** run `/compact` to compress history before token use grows
- **Multi-step changes:** use plan mode — type your request and select "Plan" to review before execution
- **Research tasks:** Claude spawns sub-agents for codebase exploration; don't re-read files already searched

## Commands

```bash
pip install -e ".[dev]"                          # install (build backend: setuptools.build_meta)
playwright install chromium                      # one-time browser setup
ollama pull llama3.2                             # one-time model pull (scorer only)

python orchestrator.py init                      # first-time interactive setup
python orchestrator.py run --dry-run             # safe run — no submissions
python orchestrator.py run                       # live run (requires live_mode: true)
python orchestrator.py run --ignore-deadline     # bypass 9:15 IST guard (testing only)
python orchestrator.py schedule                  # daemon: every 30 min, 5:00–9:00 AM IST
python orchestrator.py status                    # check config and live_mode flag
python orchestrator.py store-creds naukri        # store credentials in OS keyring
python orchestrator.py voice                     # voice interface (pip install -e ".[voice]")

pytest tests/ -v                                 # all tests (no live services needed)
pytest tests/ --cov=agents --cov-report=term-missing
ruff check . && ruff format .
mypy agents/
```

Ruff: line-length 100, Python 3.11. `asyncio_mode = "auto"` — `@pytest.mark.asyncio` is optional.

## Architecture

```
JobPosting → ScoredJob → TailoredApplication → ApplicationResult
   scout        scorer         tailor                 apply
                                                        ↓
                                                  NexusReporter
```

`orchestrator.py` runs `async def run_pipeline()`. Agents imported lazily to prevent Playwright loading at module level.

**Two paths (score-driven only — LLM path_recommendation field is ignored):**
- **Path A** (≥ 60): Director/VP — always `QUEUED_FOR_HUMAN`, never auto-submitted. Max 3/day.
- **Path B** (≥ 72): Senior QE Manager — auto-submitted before 9:15 IST deadline. Max 15/day.

**LLM:** Only `NexusScorer` uses Ollama (`llama3.2`). Tailor copies base resume as-is (no per-job rewriting — ATS scores the raw resume). Scorer uses `asyncio.to_thread()` for blocking `ollama.chat()`. JSON repaired via `_extract_json()` + `_escape_json_strings()`; parse failure returns score=0.

**Scout adapters:** Registry pattern. Built-ins: Greenhouse, Lever, Indeed (HTML), Naukri (Playwright). **LinkedIn disabled** (account ban risk). Add platforms via `scout.register_adapter(name, async_fn)`.

**Apply adapters:** Dispatched via `getattr(_apply_<platform>)`. Naukri most complete. LinkedIn adapter exists but is never called.

**Deduplication:** `sha256(title|company|platform)[:16]` stored in SQLite. Highest-scoring instance kept per fingerprint across runs.

**Sessions:** Naukri cookies saved to `resources/credentials/sessions/`. First run opens visible browser for manual login; subsequent runs are headless. Re-prompts on auth failure.

**Config files:**
- `resources/config/agent_config.yaml` — all behaviour; `apply.live_mode: false` is the critical safety flag
- `resources/config/career_paths.yaml` — per-path thresholds, scoring signal keywords
- `resources/skills/skills_profile.yaml` — skills rated 1–10, fed into scorer prompt
- `resources/resumes/resume_path_a.md` / `resume_path_b.md` — base templates

## Safety invariants

- `apply.live_mode: false` default — logs everything, submits nothing
- Path A bypasses apply unconditionally regardless of `live_mode`
- 9:15 AM IST deadline enforced in `_past_deadline()` — override only with `--ignore-deadline`
- Dry-run marks all results `ApplyStatus.DRY_RUN` — airtight, no submissions
- Credentials: OS keyring primary, `.env` fallback; never plaintext on disk

## Testing

Mocks `agents.scorer._ollama_chat` directly — no Ollama needed. Playwright mocked similarly. DB tests use `tmp_path` for isolated SQLite. All tests run offline.
