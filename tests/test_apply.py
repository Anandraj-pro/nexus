"""Unit tests for jireh-apply — pure-logic paths that need no Playwright."""

from __future__ import annotations

from datetime import datetime

import pytest

from agents.apply import ApplyStatus, ApplicationResult, JirehApply
from agents.scorer import ScoredJob
from agents.scout import JobPosting
from agents.tailor import TailoredApplication

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_app(path: str = "path_b", platform: str = "linkedin") -> TailoredApplication:
    posting = JobPosting(
        job_id="apply_001",
        title="QA Manager",
        company="Acme",
        location="Hyderabad",
        url="https://example.com/job/1",
        platform=platform,
    )
    scored = ScoredJob(
        posting=posting,
        total_score=85,
        breakdown={},
        matched_skills=[],
        missing_skills=[],
        path_recommendation=path,
        reasoning="",
    )
    return TailoredApplication(
        scored_job=scored,
        tailored_resume="# Resume",
        cover_letter="Dear Hiring Manager,",
        key_changes=[],
    )


DRY_CONFIG = {
    "apply": {
        "live_mode": False,
        "headless": True,
        "slow_mo_ms": 0,
        "timeout_ms": 5000,
        "retry_attempts": 1,
        "on_captcha": "skip_and_flag",
    },
    "vault": {},
}

LIVE_CONFIG = {**DRY_CONFIG, "apply": {**DRY_CONFIG["apply"], "live_mode": True}}


# ─── Path A — always queued regardless of live_mode ───────────────────────────

@pytest.mark.asyncio
async def test_path_a_queued_in_dry_run():
    result = await JirehApply(DRY_CONFIG).apply(_make_app(path="path_a"))
    assert result.status == ApplyStatus.QUEUED_FOR_HUMAN


@pytest.mark.asyncio
async def test_path_a_queued_in_live_mode():
    result = await JirehApply(LIVE_CONFIG).apply(_make_app(path="path_a"))
    assert result.status == ApplyStatus.QUEUED_FOR_HUMAN


@pytest.mark.asyncio
async def test_path_a_platform_propagated():
    result = await JirehApply(DRY_CONFIG).apply(_make_app(path="path_a", platform="naukri"))
    assert result.platform == "naukri"


# ─── Dry-run mode (path_b, live_mode=False) ───────────────────────────────────

@pytest.mark.asyncio
async def test_dry_run_returns_dry_run_status():
    result = await JirehApply(DRY_CONFIG).apply(_make_app(path="path_b"))
    assert result.status == ApplyStatus.DRY_RUN


@pytest.mark.asyncio
async def test_dry_run_platform_set_correctly():
    result = await JirehApply(DRY_CONFIG).apply(_make_app(path="path_b", platform="naukri"))
    assert result.platform == "naukri"
    assert result.status == ApplyStatus.DRY_RUN


# ─── apply_batch ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_batch_returns_one_result_per_app():
    apps = [_make_app("path_a"), _make_app("path_b"), _make_app("path_a")]
    results = await JirehApply(DRY_CONFIG).apply_batch(apps)
    assert len(results) == 3


@pytest.mark.asyncio
async def test_batch_correct_statuses():
    apps = [_make_app("path_a"), _make_app("path_b")]
    results = await JirehApply(DRY_CONFIG).apply_batch(apps)
    assert results[0].status == ApplyStatus.QUEUED_FOR_HUMAN
    assert results[1].status == ApplyStatus.DRY_RUN


@pytest.mark.asyncio
async def test_batch_empty_input():
    results = await JirehApply(DRY_CONFIG).apply_batch([])
    assert results == []


# ─── ApplicationResult defaults ───────────────────────────────────────────────

def test_result_timestamp_is_set():
    result = ApplicationResult(application=_make_app(), status=ApplyStatus.DRY_RUN)
    assert isinstance(result.timestamp, datetime)


def test_result_error_and_confirmation_default_to_empty():
    result = ApplicationResult(application=_make_app(), status=ApplyStatus.FAILED)
    assert result.error == ""
    assert result.confirmation_id == ""