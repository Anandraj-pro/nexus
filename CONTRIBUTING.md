# Contributing to Nexus

Thanks for your interest. This guide covers everything you need to open a quality pull request.

---

## Development setup

```bash
git clone https://github.com/Anandraj-pro/nexus.git
cd nexus
python -m venv .venv
source .venv/bin/activate        # Mac/Linux
# .venv\Scripts\activate         # Windows
pip install -e ".[dev]"
playwright install chromium
ollama pull llama3.2
```

Copy `.env.example` to `.env` and fill in at minimum a Naukri account for manual testing. All automated tests run fully offline — no live credentials needed for `pytest`.

---

## Before you start

- **Check existing issues** before opening a new one — your idea may already be tracked.
- **Open an issue first** for any non-trivial change (new platform, new feature, architecture change) so the approach can be agreed before you spend time on it.
- **Bug fixes and docs** can go straight to a PR.

---

## Code style

Nexus uses Ruff for linting and formatting, and Mypy for type checking.

```bash
ruff check .       # lint
ruff format .      # format
mypy agents/       # type check
```

All three must pass cleanly before opening a PR. Key rules:

- Line length: 100 characters
- Target: Python 3.11+
- Type annotations on all public functions
- No comments explaining *what* the code does — only *why* if it's non-obvious

Run checks together:

```bash
ruff check . && ruff format . && mypy agents/
```

---

## Testing

Every change needs tests. Run the full suite with:

```bash
pytest tests/ -v
pytest tests/ --cov=agents --cov-report=term-missing   # with coverage
```

**Rules:**
- New agent behaviour → new test in the corresponding `tests/test_<agent>.py`
- New platform adapter → mock the HTTP/Playwright calls; do not hit live services
- Tests must pass with no running Ollama, no live credentials, no network
- Use `tmp_path` fixtures for anything that writes to disk
- Mock `agents.scorer._ollama_chat` for scorer tests (see existing tests for the pattern)

---

## Adding a new job platform (Scout)

1. Implement an async fetch function in `agents/scout.py`:

```python
async def _fetch_myplatform(keywords: list[str], locations: list[str]) -> list[JobPosting]:
    ...
```

2. Register it in `_register_built_in_adapters()`:

```python
self.register_adapter("myplatform", self._fetch_myplatform)
```

3. Add the platform name to the `platforms` list in `resources/config/agent_config.yaml`.

4. Add tests in `tests/test_scout.py` — mock all HTTP/browser calls.

> **LinkedIn is intentionally excluded.** Do not add LinkedIn scout or apply adapters — account ban risk is too high. This is a firm decision, not up for discussion in PRs.

---

## Adding a new apply adapter

Apply adapters are dispatched automatically by name via `getattr`. To add support for a new platform:

1. Add a method to `NexusApply` in `agents/apply.py`:

```python
async def _apply_myplatform(self, job: ScoredJob, app: TailoredApplication) -> ApplicationResult:
    ...
```

2. The method must return an `ApplicationResult` with an `ApplyStatus` value.

3. Add tests in `tests/test_apply.py` — mock all Playwright calls.

---

## Adding a new notification channel

1. Add a send method to `NexusReporter` in `agents/reporter.py`:

```python
async def _send_myservice(self, digest: str) -> None:
    ...
```

2. Add the channel name to `reporter.channels` dispatch logic.

3. Add the new channel to `reporter.channels` in `agent_config.yaml`.

4. Document any required env vars in `.env.example`.

---

## Commit messages

Follow this format:

```
Short summary in imperative mood (max 72 chars)

Optional longer explanation — the *why*, not the *what*.
What constraint drove this? What alternative was ruled out?
```

Examples:
```
Add Lever apply adapter with form-fill support
Fix scorer JSON repair failing on nested quotes
Skip jobs with no description instead of scoring them zero
```

---

## Pull request checklist

Before opening a PR, confirm:

- [ ] `ruff check .` passes with no errors
- [ ] `ruff format .` produces no changes
- [ ] `mypy agents/` passes
- [ ] `pytest tests/ -v` — all tests pass
- [ ] New behaviour has corresponding tests
- [ ] `.env.example` updated if new env vars were added
- [ ] `README.md` or `docs/runbook.md` updated if user-facing behaviour changed

---

## What we won't accept

- LinkedIn Playwright automation (account ban risk — see `docs/runbook.md`)
- LLM-based resume tailoring per job (tested and found no measurable ATS benefit — adds latency for nothing)
- Features that require paid external APIs (Nexus is intentionally zero API-cost)
- Breaking changes to the `JobPosting → ScoredJob → TailoredApplication → ApplicationResult` pipeline dataclasses without a migration path

---

## Questions

Open a GitHub issue with the `question` label.
