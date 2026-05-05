"""Unit tests for jireh-reporter — pure logic, no network calls."""

from __future__ import annotations

from datetime import date

import pytest

from agents.apply import ApplyStatus, ApplicationResult
from agents.reporter import DigestReport, JirehReporter
from agents.scorer import ScoredJob
from agents.scout import JobPosting
from agents.tailor import TailoredApplication

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_result(
    status: ApplyStatus,
    title: str = "QA Manager",
    score: int = 80,
    url: str = "https://example.com/job/1",
    platform: str = "linkedin",
) -> ApplicationResult:
    posting = JobPosting(
        job_id="rep_001",
        title=title,
        company="Acme",
        location="Hyderabad",
        url=url,
        platform=platform,
    )
    scored = ScoredJob(
        posting=posting,
        total_score=score,
        breakdown={},
        matched_skills=[],
        missing_skills=[],
        path_recommendation="path_b" if score >= 72 else "path_a",
        reasoning="",
    )
    app = TailoredApplication(
        scored_job=scored,
        tailored_resume="# Resume",
        cover_letter="Cover",
        key_changes=[],
    )
    return ApplicationResult(application=app, status=status, platform=platform)


CONFIG = {"reporter": {"channels": ["telegram"]}}
REPORTER = JirehReporter(CONFIG)


# ─── build_digest ─────────────────────────────────────────────────────────────

def test_build_digest_partitions_all_statuses():
    results = [
        _make_result(ApplyStatus.QUEUED_FOR_HUMAN),
        _make_result(ApplyStatus.SUBMITTED),
        _make_result(ApplyStatus.DRY_RUN),
        _make_result(ApplyStatus.SKIPPED_CAPTCHA),
        _make_result(ApplyStatus.FAILED),
    ]
    digest = REPORTER.build_digest(results, total_scouted=20, total_scored=5)
    assert len(digest.path_a_queued) == 1
    assert len(digest.path_b_applied) == 1
    assert len(digest.path_b_dry_run) == 1
    assert len(digest.skipped_captcha) == 1
    assert len(digest.failed) == 1


def test_build_digest_empty_results():
    digest = REPORTER.build_digest([], total_scouted=0, total_scored=0)
    assert digest.path_a_queued == []
    assert digest.path_b_applied == []
    assert digest.total_scouted == 0


def test_build_digest_uses_today_by_default():
    digest = REPORTER.build_digest([], 0, 0)
    assert digest.date == date.today()


def test_build_digest_scripture_is_deterministic_for_same_date():
    d = date(2025, 3, 15)
    digest1 = REPORTER.build_digest([], 0, 0, run_date=d)
    digest2 = REPORTER.build_digest([], 0, 0, run_date=d)
    assert digest1.scripture == digest2.scripture


def test_build_digest_scripture_varies_across_week():
    scriptures = {
        REPORTER.build_digest([], 0, 0, run_date=date(2025, 1, i)).scripture
        for i in range(1, 8)
    }
    assert len(scriptures) > 1


def test_build_digest_totals_match_inputs():
    digest = REPORTER.build_digest([], total_scouted=42, total_scored=7)
    assert digest.total_scouted == 42
    assert digest.total_scored == 7


# ─── render_telegram ──────────────────────────────────────────────────────────

def test_render_telegram_always_includes_scripture():
    digest = REPORTER.build_digest([], 5, 2, run_date=date(2025, 6, 1))
    text = REPORTER.render_telegram(digest)
    assert digest.scripture in text


def test_render_telegram_closing_line_always_present():
    digest = REPORTER.build_digest([], 0, 0)
    text = REPORTER.render_telegram(digest)
    assert "He goes before you" in text


def test_render_telegram_dry_run_label_present():
    digest = REPORTER.build_digest([_make_result(ApplyStatus.DRY_RUN)], 10, 1)
    text = REPORTER.render_telegram(digest)
    assert "dry run" in text.lower() or "Dry Run" in text


def test_render_telegram_path_a_includes_job_url():
    digest = REPORTER.build_digest(
        [_make_result(ApplyStatus.QUEUED_FOR_HUMAN, url="https://example.com/job/99")],
        10, 1,
    )
    text = REPORTER.render_telegram(digest)
    assert "https://example.com/job/99" in text


def test_render_telegram_submitted_shows_checkmark():
    digest = REPORTER.build_digest([_make_result(ApplyStatus.SUBMITTED)], 10, 1)
    text = REPORTER.render_telegram(digest)
    assert "✓" in text


def test_render_telegram_no_path_a_section_when_empty():
    digest = REPORTER.build_digest([_make_result(ApplyStatus.SUBMITTED)], 1, 1)
    text = REPORTER.render_telegram(digest)
    assert "Needs Your Review" not in text


def test_render_telegram_captcha_flagged():
    digest = REPORTER.build_digest([_make_result(ApplyStatus.SKIPPED_CAPTCHA)], 1, 1)
    text = REPORTER.render_telegram(digest)
    assert "CAPTCHA" in text or "Manual" in text