# PRD: Jireh Web Dashboard

**Version:** 1.0  
**Author:** Ananda Raju Pandiri  
**Date:** 2026-04-29  
**Status:** Draft

---

## 1. Problem Statement

The Jireh pipeline currently operates headlessly — it scouts, scores, tailors, and auto-applies without any interactive surface. Two problems have converged to make this untenable:

1. **LinkedIn blacklist risk.** Auto-applying at volume via Playwright triggers LinkedIn's bot detection. Continued auto-apply against LinkedIn threatens the profile itself, which is the primary sourcing channel.
2. **No visibility.** The only output today is a Telegram/email digest. There is no way to see job details, review tailored documents, or take action without digging into log files or the SQLite DB.

The dashboard solves both: it replaces auto-apply with a human-in-the-loop review surface, and it gives full pipeline visibility in a browser tab.

---

## 2. Goals

| # | Goal | Metric |
|---|------|--------|
| G1 | Anand can see all qualified jobs from today's scan in under 30 seconds | Time from opening browser to reading first job row |
| G2 | Anand can trigger a pipeline scan without touching the terminal | "Run Scan" button works end to end |
| G3 | Every job's apply status is visible at a glance | Status column accurate for all pipeline outcomes |
| G4 | Tailored resume and cover letter are readable and downloadable per job | Document viewer renders markdown; PDF download works |
| G5 | The dashboard does not break the existing CLI pipeline | `orchestrator.py run` still works unchanged |

---

## 3. Non-Goals (Out of Scope)

- Cloud hosting, authentication, or multi-user access. This runs exclusively on localhost.
- Editing the tailored resume or cover letter in-browser. Read-only display only.
- Triggering individual pipeline stages independently (score-only, tailor-only, etc.). The whole pipeline runs as one unit.
- Mobile/tablet layout. Desktop browser only.
- Real-time streaming of pipeline output. Polling is sufficient.
- Naukri auto-apply via the dashboard. This is a manual-only surface.
- Modifying `agent_config.yaml` from the UI.
- Any form of user accounts, sessions, or login.

---

## 4. User Stories

### Scan & Review

**US-01** — As Anand, I want to click "Run Scan" so that the pipeline runs without opening a terminal.

**US-02** — As Anand, I want to see a table of all jobs discovered today so that I can decide which ones to pursue.

**US-03** — As Anand, I want to filter jobs by Path (A/B), Status, and score range so that I can quickly isolate the best matches.

**US-04** — As Anand, I want to click a job row and open its original posting URL in a new tab so that I can read the full JD before applying.

**US-05** — As Anand, I want to see the LLM's score breakdown (experience_match, skills_match, domain_match, seniority_match) and reasoning so that I understand why a job scored as it did.

### Apply Actions

**US-06** — As Anand, I want to mark a job as "Applied Manually" after I've submitted it myself so that the status reflects reality.

**US-07** — As Anand, I want to mark a job as "Not Interested" so that it is hidden from the active list without being deleted.

**US-08** — As Anand, I want to see which Path B jobs were auto-applied by the pipeline, with confirmation IDs where available.

### Documents

**US-09** — As Anand, I want to read the tailored resume for any job, rendered as formatted text, so that I can review it before applying.

**US-10** — As Anand, I want to read the tailored cover letter for any job.

**US-11** — As Anand, I want to download the PDF version of the resume for any job so that I can upload it to an external application form.

### Dashboard & History

**US-12** — As Anand, I want to see pipeline stats for today (scouted / qualified / auto-applied / manual pending / skipped) at a glance.

**US-13** — As Anand, I want to see pipeline run history for the last 7 days so that I can track overall activity.

---

## 5. Screens & Features

### Screen 1 — Job Board (`/`)

This is the default landing page and the primary daily workspace.

**Header bar**
- Title: "Jireh — Job Board"
- Date selector (defaults to today)
- "Run Scan" button — POST `/api/pipeline/run` (dry_run toggle via config; button disabled and shows spinner while a run is in progress)
- Pipeline status indicator: idle / running / last run timestamp

**Filter bar**
- Path filter: All | Path A | Path B
- Status filter: All | Pending | Applied | Auto-Applied | Not Interested
- Score range slider: 0–100 (defaults to 60–100)
- Platform filter: All | LinkedIn | Naukri | Indeed | Greenhouse | Lever

**Job table columns**

| Column | Source | Notes |
|--------|--------|-------|
| Title | `seen_jobs.title` / `applications.title` | Clickable — opens job URL in new tab |
| Company | `applications.company` | |
| Score | `applications.score` | Color-coded: green >= 80, yellow 60–79, orange < 60 |
| Path | `applications.path` | Badge: "A" (blue) or "B" (green) |
| Platform | `applications.platform` | Icon + text |
| Status | `applications.user_status` | See status enum below |
| Documents | — | Icon links to resume/cover letter if tailored |
| Actions | — | "Applied" button, "Not Interested" button |

**Status values (user-visible)**

| Value | Meaning |
|-------|---------|
| Auto-Applied | Pipeline submitted via Playwright (`SUBMITTED`) |
| Queued — Path A | Director/VP role waiting for Anand to apply (`QUEUED_FOR_HUMAN`) |
| Needs Manual Apply | External site — no Easy Apply available (`EXTERNAL_APPLY`) |
| Applied Manually | Anand marked as applied |
| Not Interested | Anand dismissed |
| Dry Run | Pipeline ran in dry-run mode |
| Failed | Apply attempt failed |

**Row expansion**
Clicking the expand icon on a row shows:
- Score breakdown table (experience_match, skills_match, domain_match, seniority_match)
- LLM reasoning sentence
- Matched skills list
- Missing skills list

**Pagination / sort**
- Default sort: score descending
- 25 rows per page

---

### Screen 2 — Apply Status Dashboard (`/status`)

**Stats bar (today)**
- Scouted | Qualified | Auto-Applied | Manual Pending | Skipped
- Each stat is a number in a card

**Auto-Applied section**
- List of Path B jobs the pipeline submitted
- Columns: Title | Company | Score | Platform | Confirmation ID | Timestamp
- Empty state: "No auto-applications today"

**Needs Manual Application section**
- All jobs with status `EXTERNAL_APPLY` or `QUEUED_FOR_HUMAN` and not yet marked Applied Manually
- Columns: Title | Company | Score | Path | Direct Link | Documents
- Direct Link opens the job URL in a new tab

**Pipeline Run History**
- Table of the last 7 pipeline runs
- Columns: Date | Scouted | Qualified | Auto-Applied | Manual Pending | Duration | Trigger (scheduled / manual)

---

### Screen 3 — Tailored Documents (`/jobs/<job_id>/documents`)

Reached by clicking the document icon in the Job Board table.

**Header**
- Job title, company, score, path badge
- Link back to job board

**Resume tab**
- Tailored resume rendered as HTML from markdown (use `markdown` library already in the project)
- "Download PDF" button — serves the pre-generated PDF from `resources/resumes/tailored/`
- If PDF not generated: "Download Markdown" button

**Cover Letter tab**
- Tailored cover letter rendered as HTML from markdown

**Key Changes section**
- Bulleted list of `key_changes` from the tailor output — explains what the LLM changed and why

---

## 6. Data Model Changes

### Existing tables (unchanged)

`seen_jobs` — fingerprint deduplication only. No changes needed.

### New table: `applications`

```sql
CREATE TABLE IF NOT EXISTS applications (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          TEXT NOT NULL,          -- matches seen_jobs.job_id
    fingerprint     TEXT NOT NULL,          -- matches seen_jobs.fingerprint
    run_id          INTEGER NOT NULL REFERENCES pipeline_runs(id),

    -- Job metadata (denormalised for query convenience)
    title           TEXT NOT NULL,
    company         TEXT NOT NULL,
    location        TEXT,
    platform        TEXT NOT NULL,
    url             TEXT NOT NULL,

    -- Scorer output
    score           INTEGER NOT NULL,
    path            TEXT NOT NULL,          -- 'path_a' | 'path_b'
    score_breakdown TEXT,                   -- JSON: {"experience_match": 25, ...}
    matched_skills  TEXT,                   -- JSON array
    missing_skills  TEXT,                   -- JSON array
    reasoning       TEXT,

    -- Apply outcome (from pipeline)
    pipeline_status TEXT NOT NULL,          -- ApplyStatus enum value
    confirmation_id TEXT DEFAULT '',

    -- User action (from dashboard)
    user_status     TEXT NOT NULL DEFAULT 'pending',
    -- 'pending' | 'applied_manually' | 'not_interested'
    user_notes      TEXT DEFAULT '',
    applied_at      TEXT,                   -- ISO timestamp if manually applied

    -- Document paths
    resume_md_path  TEXT DEFAULT '',
    cover_md_path   TEXT DEFAULT '',
    pdf_path        TEXT DEFAULT '',

    -- Timestamps
    discovered_at   TEXT NOT NULL,
    updated_at      TEXT NOT NULL,

    UNIQUE(job_id, run_id)
);
```

### New table: `pipeline_runs`

```sql
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at      TEXT NOT NULL,          -- ISO timestamp
    finished_at     TEXT,
    trigger         TEXT NOT NULL DEFAULT 'scheduled',  -- 'scheduled' | 'manual'
    status          TEXT NOT NULL DEFAULT 'running',    -- 'running' | 'completed' | 'failed'
    total_scouted   INTEGER DEFAULT 0,
    total_qualified INTEGER DEFAULT 0,
    total_applied   INTEGER DEFAULT 0,
    total_manual    INTEGER DEFAULT 0,
    total_skipped   INTEGER DEFAULT 0,
    error_message   TEXT DEFAULT ''
);
```

### Migration approach

Add a `migrate_db()` function to `agents/db.py` that runs `CREATE TABLE IF NOT EXISTS` for both new tables. Call it from `init_db()`. No breaking change to existing schema — `seen_jobs` is untouched.

---

## 7. API Endpoints

All endpoints return JSON unless noted. No authentication.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Serve Job Board HTML |
| GET | `/status` | Serve Apply Status Dashboard HTML |
| GET | `/jobs/<job_id>/documents` | Serve Documents page HTML |
| GET | `/api/jobs` | List jobs; query params: `date`, `path`, `status`, `platform`, `min_score`, `max_score`, `page`, `per_page` |
| PATCH | `/api/jobs/<job_id>/status` | Update user_status (`applied_manually` or `not_interested`) |
| POST | `/api/pipeline/run` | Trigger pipeline run; body: `{"dry_run": bool}` |
| GET | `/api/pipeline/status` | Return current run status and last run summary |
| GET | `/api/pipeline/runs` | Return last 7 run records |
| GET | `/api/stats/today` | Return today's stat card numbers |
| GET | `/api/jobs/<job_id>/resume.md` | Return raw markdown text |
| GET | `/api/jobs/<job_id>/cover.md` | Return raw markdown text |
| GET | `/api/jobs/<job_id>/resume.pdf` | Serve PDF file (Content-Type: application/pdf) |

---

## 8. Technical Architecture

### Server

- **Framework:** FastAPI with Jinja2 templates
  - FastAPI is already an indirect dependency via `langgraph`; adds no new dependency
  - Jinja2 is FastAPI's standard template engine
  - Serve on `localhost:5000` (or configurable port)
- **ASGI server:** `uvicorn` (standard FastAPI runtime, single additional dependency)
- **Entry point:** `dashboard.py` at project root — separate process from `orchestrator.py`

```
python dashboard.py
# or
python dashboard.py --port 5000
```

### Frontend

- Plain HTML + Jinja2 templates — no build step, no npm
- Vanilla JavaScript for:
  - Score range slider
  - Row expansion (fetch score breakdown from API)
  - Polling pipeline status every 3 seconds during a run
  - PATCH calls for user status updates
- CSS: single `static/style.css` — no framework, functional > pretty
- Markdown rendering: Python-side using `markdown` library (already installed), not JS

### Pipeline integration

The dashboard triggers the pipeline by calling `asyncio.run(run_pipeline(...))` in a background thread via `concurrent.futures.ThreadPoolExecutor`. This keeps the FastAPI event loop free while the pipeline (which itself uses `asyncio`) runs in its own loop in a worker thread.

The pipeline's existing `ApplicationResult` objects get written to the `applications` table by a new thin wrapper in `agents/db.py` — `save_application_results()`. The pipeline code itself (`orchestrator.py`, `agents/*.py`) is not modified.

### Static files

```
dashboard/
  static/
    style.css
    app.js
  templates/
    base.html
    job_board.html
    status.html
    documents.html
```

---

## 9. New Dependencies

| Package | Purpose | Already present? |
|---------|---------|-----------------|
| `fastapi` | Web framework | No — add to `pyproject.toml` |
| `uvicorn` | ASGI server | No — add to `pyproject.toml` |
| `jinja2` | HTML templates | No (but fastapi depends on it) — add explicitly |
| `markdown` | Render tailored docs to HTML | Yes (`markdown>=3.5.0`) |
| `python-multipart` | FastAPI form parsing | No — add (required by FastAPI for form endpoints) |

All other logic reuses existing agents and `agents/db.py`.

---

## 10. File Structure

New files added to the project:

```
dashboard.py                          -- entry point (FastAPI app + uvicorn start)
dashboard/
  __init__.py
  routes/
    __init__.py
    jobs.py                           -- /api/jobs endpoints
    pipeline.py                       -- /api/pipeline endpoints
    documents.py                      -- document serve endpoints
    pages.py                          -- HTML page routes
  static/
    style.css
    app.js
  templates/
    base.html
    job_board.html
    status.html
    documents.html
agents/db.py                          -- add migrate_db(), save_application_results(),
                                         save_pipeline_run(), update_pipeline_run()
```

Existing files modified:
- `agents/db.py` — add new functions and table DDL (no existing function changes)
- `pyproject.toml` — add fastapi, uvicorn, jinja2, python-multipart to dependencies

---

## 11. Running Alongside the Scheduler

The dashboard and the scheduler are independent processes:

```bash
# Terminal 1 — pipeline scheduler (existing)
python orchestrator.py schedule

# Terminal 2 — web dashboard (new)
python dashboard.py
```

There is no inter-process communication. Both processes access the same `db/jireh.db` SQLite file. SQLite's WAL mode handles concurrent readers/writers safely. The dashboard writes only to `applications` and `pipeline_runs` (via `save_application_results()`); the scheduler writes only to `seen_jobs`. The only shared write path is the `pipeline_runs` table when the dashboard triggers a manual run — this is an acceptable single-writer scenario since the manual run creates its own run record.

---

## 12. Safety Constraints

The existing safety invariants from `orchestrator.py` must be preserved:

1. `apply.live_mode: false` in `agent_config.yaml` must continue to suppress submissions. The dashboard "Run Scan" button reads this config — it does not expose a separate live-mode toggle.
2. The 9:15 AM IST deadline guard (`_past_deadline()`) remains active for dashboard-triggered runs unless `ignore_deadline=True` is explicitly set in config. The dashboard does not expose this flag.
3. Path A jobs (`QUEUED_FOR_HUMAN`) are never auto-submitted, even from dashboard-triggered runs.
4. The dashboard has no ability to submit applications directly — it opens job URLs in the browser and lets Anand apply manually.

---

## 13. Success Metrics

| Metric | Target |
|--------|--------|
| Time from opening browser to reading today's job list | Under 30 seconds |
| All pipeline `ApplicationResult` statuses correctly reflected in dashboard | 100% accuracy |
| "Run Scan" button triggers pipeline and displays results on completion | Works end to end |
| PDF download works for all tailored applications that have a PDF on disk | 100% of cases |
| `orchestrator.py run --dry-run` still passes all existing tests unchanged | All tests green |
| Dashboard process startup time | Under 3 seconds |

---

## 14. Open Questions

1. **Score threshold display:** Should the Job Board show jobs below the path_a threshold (score < 60) in a "rejected" section, or only show qualified jobs? Current pipeline drops sub-threshold jobs before they reach `TailoredApplication`. Showing them requires persisting `ScoredJob` data for all postings, not just qualified ones.

2. **Scan frequency:** The "Run Scan" button triggers the full pipeline. Should there be a "Scout only" mode that populates the job table without tailoring or applying — faster for browsing before committing to tailoring compute?

3. **Browser notification:** Should the dashboard send a browser notification (Web Notifications API) when a triggered pipeline scan completes?

4. **Tailored document regeneration:** If Anand edits `skills_profile.yaml` and wants a re-tailored resume for an existing job, should there be a "Re-tailor" button per job?

---

## 15. Implementation Order

Suggested sequence to deliver value incrementally:

1. **DB migration** — add `pipeline_runs` and `applications` tables; add `save_application_results()` to `agents/db.py`; wire into `orchestrator.py::run_pipeline()` (5 lines)
2. **FastAPI skeleton** — `dashboard.py`, static files, base template, single `/` route returning empty table
3. **Job Board** — `/api/jobs` endpoint, table rendering, filters, row expansion
4. **Apply Status Dashboard** — `/status` route, stats cards, run history
5. **Document viewer** — `/jobs/<job_id>/documents`, markdown render, PDF download
6. **Pipeline trigger** — `POST /api/pipeline/run`, background thread execution, status polling
7. **User actions** — `PATCH /api/jobs/<job_id>/status` for "Applied Manually" and "Not Interested"
