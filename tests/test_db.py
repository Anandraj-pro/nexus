"""Tests for agents/db.py — sqlite3 seen-jobs persistence."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from agents.db import init_db, load_seen_fingerprints, save_seen_jobs
from agents.scout import JobPosting


def _make_posting(job_id: str, title: str = "QE Manager", company: str = "Acme") -> JobPosting:
    return JobPosting(
        job_id=job_id,
        title=title,
        company=company,
        location="Hyderabad",
        platform="indeed",
        url=f"https://example.com/{job_id}",
    )


# ── init_db ───────────────────────────────────────────────────────────────────

def test_init_db_creates_file_and_table(tmp_path: Path) -> None:
    db = tmp_path / "test.db"
    init_db(db)
    assert db.exists()
    with sqlite3.connect(db) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "seen_jobs" in tables


def test_init_db_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "test.db"
    init_db(db)
    init_db(db)  # second call must not raise


def test_init_db_creates_parent_dirs(tmp_path: Path) -> None:
    db = tmp_path / "nested" / "deep" / "jireh.db"
    init_db(db)
    assert db.exists()


# ── load_seen_fingerprints ────────────────────────────────────────────────────

def test_load_returns_empty_set_when_db_missing(tmp_path: Path) -> None:
    result = load_seen_fingerprints(tmp_path / "nonexistent.db")
    assert result == set()


def test_load_returns_empty_set_on_fresh_db(tmp_path: Path) -> None:
    db = tmp_path / "test.db"
    init_db(db)
    assert load_seen_fingerprints(db) == set()


def test_load_returns_persisted_fingerprints(tmp_path: Path) -> None:
    db = tmp_path / "test.db"
    init_db(db)
    postings = [_make_posting("job_001"), _make_posting("job_002")]
    save_seen_jobs(postings, db)
    loaded = load_seen_fingerprints(db)
    assert loaded == {p.fingerprint for p in postings}


# ── save_seen_jobs ────────────────────────────────────────────────────────────

def test_save_persists_all_fields(tmp_path: Path) -> None:
    db = tmp_path / "test.db"
    init_db(db)
    posting = _make_posting("job_001", title="Senior QE Manager", company="FinPay")
    save_seen_jobs([posting], db)
    with sqlite3.connect(db) as conn:
        row = conn.execute(
            "SELECT job_id, title, company, platform FROM seen_jobs WHERE fingerprint = ?",
            (posting.fingerprint,),
        ).fetchone()
    assert row == ("job_001", "Senior QE Manager", "FinPay", "indeed")


def test_save_empty_list_is_noop(tmp_path: Path) -> None:
    db = tmp_path / "test.db"
    init_db(db)
    save_seen_jobs([], db)
    assert load_seen_fingerprints(db) == set()


def test_save_duplicate_fingerprint_does_not_raise(tmp_path: Path) -> None:
    db = tmp_path / "test.db"
    init_db(db)
    posting = _make_posting("job_001")
    save_seen_jobs([posting], db)
    save_seen_jobs([posting], db)  # INSERT OR IGNORE — must not raise
    assert len(load_seen_fingerprints(db)) == 1


# ── cross-run deduplication ───────────────────────────────────────────────────

def test_cross_run_deduplication(tmp_path: Path) -> None:
    """Simulates two pipeline runs: second run must see 0 new jobs."""
    db = tmp_path / "test.db"
    init_db(db)

    postings = [_make_posting(f"job_{i:03d}") for i in range(5)]

    # Run 1: all are new
    seen = load_seen_fingerprints(db)
    new_run1 = [p for p in postings if p.fingerprint not in seen]
    save_seen_jobs(new_run1, db)
    assert len(new_run1) == 5

    # Run 2: all already seen
    seen = load_seen_fingerprints(db)
    new_run2 = [p for p in postings if p.fingerprint not in seen]
    assert len(new_run2) == 0