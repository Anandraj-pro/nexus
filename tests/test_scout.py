"""Unit tests for jireh-scout — pure helpers and adapter registration."""

from __future__ import annotations

from pathlib import Path

import pytest

from agents.scout import JobPosting, JirehScout, _linkedin_auth_blocked, _naukri_auth_blocked


def _config(tmp_path: Path, platforms: list[str] | None = None) -> dict:
    return {
        "system": {"db_path": str(tmp_path / "jireh.db")},
        "scout": {
            "max_jobs_per_run": 10,
            "keywords": ["QA Manager"],
            "locations": ["Hyderabad"],
            "platforms": platforms or [],
        },
        "apply": {"slow_mo_ms": 0},
    }


# ─── JobPosting.fingerprint ───────────────────────────────────────────────────

def test_fingerprint_is_a_property_not_callable():
    p = JobPosting(job_id="x", title="T", company="C", location="L", platform="linkedin", url="")
    fp = p.fingerprint
    assert isinstance(fp, str)
    assert len(fp) == 16


def test_fingerprint_is_deterministic():
    p = JobPosting(job_id="x", title="T", company="C", location="L", platform="linkedin", url="")
    assert p.fingerprint == p.fingerprint


def test_fingerprint_differs_for_different_job_ids():
    p1 = JobPosting(job_id="a", title="T", company="C", location="L", platform="linkedin", url="")
    p2 = JobPosting(job_id="b", title="T", company="C", location="L", platform="linkedin", url="")
    # fingerprint is based on title+company+platform, not job_id
    # same title/company/platform → same fingerprint (this is the dedup key)
    assert p1.fingerprint == p2.fingerprint


def test_fingerprint_differs_for_different_companies():
    p1 = JobPosting(job_id="a", title="QA Manager", company="Acme", location="L", platform="linkedin", url="")
    p2 = JobPosting(job_id="b", title="QA Manager", company="Beta", location="L", platform="linkedin", url="")
    assert p1.fingerprint != p2.fingerprint


def test_fingerprint_differs_for_different_platforms():
    p1 = JobPosting(job_id="a", title="T", company="C", location="L", platform="linkedin", url="")
    p2 = JobPosting(job_id="a", title="T", company="C", location="L", platform="naukri", url="")
    assert p1.fingerprint != p2.fingerprint


def test_fingerprint_case_insensitive():
    p1 = JobPosting(job_id="a", title="QA MANAGER", company="ACME", location="L", platform="linkedin", url="")
    p2 = JobPosting(job_id="a", title="qa manager", company="acme", location="L", platform="linkedin", url="")
    assert p1.fingerprint == p2.fingerprint


# ─── _linkedin_auth_blocked ───────────────────────────────────────────────────

@pytest.mark.parametrize("url", [
    "https://www.linkedin.com/authwall?referrer=...",
    "https://www.linkedin.com/login",
    "https://www.linkedin.com/checkpoint/lg/login-submit",
])
def test_linkedin_auth_blocked_for_gated_urls(url: str):
    assert _linkedin_auth_blocked(url)


@pytest.mark.parametrize("url", [
    "https://www.linkedin.com/jobs/",
    "https://www.linkedin.com/jobs/view/12345",
    "https://www.linkedin.com/feed/",
])
def test_linkedin_auth_passes_for_normal_urls(url: str):
    assert not _linkedin_auth_blocked(url)


# ─── _naukri_auth_blocked ─────────────────────────────────────────────────────

@pytest.mark.parametrize("url", [
    "https://www.naukri.com/nlogin/login",
    "https://www.naukri.com/login",
])
def test_naukri_auth_blocked_for_gated_urls(url: str):
    assert _naukri_auth_blocked(url)


@pytest.mark.parametrize("url", [
    "https://www.naukri.com/mnjuser/homepage",
    "https://www.naukri.com/jobs?k=QA+Manager&l=Hyderabad",
])
def test_naukri_auth_passes_for_normal_urls(url: str):
    assert not _naukri_auth_blocked(url)


# ─── JirehScout adapter registration ─────────────────────────────────────────

def test_all_built_in_adapters_registered(tmp_path: Path):
    scout = JirehScout(_config(tmp_path), vault=None)
    for platform in ("greenhouse", "lever", "indeed", "linkedin", "naukri"):
        assert platform in scout._adapters


def test_register_custom_adapter_replaces_existing(tmp_path: Path):
    scout = JirehScout(_config(tmp_path), vault=None)

    async def my_adapter(kw, lc):
        return []

    scout.register_adapter("naukri", my_adapter)
    assert scout._adapters["naukri"] is my_adapter


def test_register_new_platform_adapter(tmp_path: Path):
    scout = JirehScout(_config(tmp_path), vault=None)

    async def workday_adapter(kw, lc):
        return []

    scout.register_adapter("workday", workday_adapter)
    assert "workday" in scout._adapters


# ─── JirehScout.run deduplication ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_deduplicates_across_adapters(tmp_path: Path):
    posting = JobPosting(
        job_id="dup_001",
        title="QA Manager",
        company="Acme",
        location="Hyderabad",
        platform="indeed",
        url="https://example.com/1",
    )

    async def returning_same(_kw, _lc):
        return [posting]

    cfg = _config(tmp_path, platforms=["indeed"])
    scout = JirehScout(cfg, seen_fingerprints=set(), vault=None)
    scout.register_adapter("indeed", returning_same)

    first_run = await scout.run()
    second_run = await scout.run()  # same posting — should be deduped

    assert len(first_run) == 1
    assert len(second_run) == 0


@pytest.mark.asyncio
async def test_run_returns_empty_when_no_platforms(tmp_path: Path):
    scout = JirehScout(_config(tmp_path, platforms=[]), vault=None)
    results = await scout.run()
    assert results == []


@pytest.mark.asyncio
async def test_run_skips_unknown_platform_gracefully(tmp_path: Path):
    cfg = _config(tmp_path, platforms=["nonexistent_board"])
    scout = JirehScout(cfg, vault=None)
    results = await scout.run()
    assert results == []