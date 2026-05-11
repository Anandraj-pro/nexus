"""nexus-db — sqlite3 persistence for seen job fingerprints."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agents.scout import JobPosting

DEFAULT_DB_PATH = Path("db/nexus.db")


def init_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    """Create the database and seen_jobs table if they don't exist."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS seen_jobs (
                fingerprint   TEXT PRIMARY KEY,
                job_id        TEXT,
                title         TEXT,
                company       TEXT,
                location      TEXT DEFAULT '',
                platform      TEXT,
                url           TEXT DEFAULT '',
                first_seen_at TEXT
            )
        """)
        # Migrate existing DBs that predate the url / location columns
        for col, default in (("url", "''"), ("location", "''")):
            try:
                conn.execute(f"ALTER TABLE seen_jobs ADD COLUMN {col} TEXT DEFAULT {default}")
            except sqlite3.OperationalError:
                pass  # column already exists


def load_seen_fingerprints(db_path: Path = DEFAULT_DB_PATH) -> set[str]:
    """Return all fingerprints previously stored in the DB."""
    if not db_path.exists():
        return set()
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT fingerprint FROM seen_jobs").fetchall()
    return {row[0] for row in rows}


def save_seen_jobs(postings: list[JobPosting], db_path: Path = DEFAULT_DB_PATH) -> None:
    """Persist a batch of new job postings so they are skipped on future runs."""
    if not postings:
        return
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            """
            INSERT OR IGNORE INTO seen_jobs
                (fingerprint, job_id, title, company, location, platform, url, first_seen_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (p.fingerprint, p.job_id, p.title, p.company,
                 p.location, p.platform, p.url, now)
                for p in postings
            ],
        )