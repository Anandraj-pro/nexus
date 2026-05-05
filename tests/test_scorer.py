"""Unit tests for jireh-scorer — uses mocked Ollama responses to avoid model dependency."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from agents.scout import JobPosting
from agents.scorer import JirehScorer, ScoredJob, _extract_json

# ─── _enforce_path tests ──────────────────────────────────────────────────────

def test_enforce_path_above_path_b_threshold():
    scorer = JirehScorer(CONFIG, SAMPLE_SKILLS)
    assert scorer._enforce_path(72) == "path_b"
    assert scorer._enforce_path(90) == "path_b"
    assert scorer._enforce_path(100) == "path_b"


def test_enforce_path_between_thresholds():
    scorer = JirehScorer(CONFIG, SAMPLE_SKILLS)
    assert scorer._enforce_path(60) == "path_a"
    assert scorer._enforce_path(71) == "path_a"


def test_enforce_path_below_both_thresholds():
    scorer = JirehScorer(CONFIG, SAMPLE_SKILLS)
    assert scorer._enforce_path(0) == "skip"
    assert scorer._enforce_path(34) == "skip"
    assert scorer._enforce_path(59) == "skip"


# ─── Fixtures ─────────────────────────────────────────────────────────────────

SAMPLE_POSTING = JobPosting(
    job_id="test_001",
    title="Senior QA Manager",
    company="FinPay Technologies",
    location="Hyderabad",
    url="https://example.com/job/123",
    platform="linkedin",
    description=(
        "We are looking for a Senior QA Manager with 10+ years in test automation, "
        "CI/CD pipeline ownership, and leading QA teams in fintech environments. "
        "Strong expertise in Python, Selenium, and API testing required. "
        "Must have experience with payment platforms and PCI-DSS compliance."
    ),
)

SAMPLE_SKILLS = {
    "leadership": {"qa_org_building": 9, "strategy": 9},
    "automation": {"selenium": 9, "playwright": 8, "pytest": 9},
    "languages": {"python": 8, "java": 7, "sql": 8},
    "domains": {"fintech": 9, "enterprise_saas": 8},
}

MOCK_SCORE_RESPONSE = {
    "total_score": 88,
    "breakdown": {
        "experience_match": 90,
        "skills_match": 92,
        "domain_match": 88,
        "seniority_match": 82,
    },
    "matched_skills": ["Python", "Selenium", "pytest", "CI/CD", "fintech"],
    "missing_skills": [],
    "path_recommendation": "path_b",
    "reasoning": "Strong match on automation skills and fintech domain experience.",
}

CONFIG = {
    "llm": {"scorer_model": "llama3.2"},
    "scorer": {"path_b_threshold": 72, "path_a_threshold": 60},
}


# ─── _extract_json tests ───────────────────────────────────────────────────────

def test_extract_json_plain():
    raw = '{"total_score": 85, "path_recommendation": "path_b"}'
    assert json.loads(_extract_json(raw))["total_score"] == 85


def test_extract_json_strips_markdown_fence():
    raw = '```json\n{"total_score": 72}\n```'
    assert json.loads(_extract_json(raw))["total_score"] == 72


def test_extract_json_strips_unnamed_fence():
    raw = "```\n{\"key\": \"value\"}\n```"
    assert json.loads(_extract_json(raw))["key"] == "value"


def test_extract_json_with_surrounding_text():
    raw = 'Here is your score:\n{"total_score": 60}\nEnd of response.'
    assert json.loads(_extract_json(raw))["total_score"] == 60


# ─── JirehScorer.score tests ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_score_returns_scored_job():
    scorer = JirehScorer(CONFIG, SAMPLE_SKILLS)
    raw_response = json.dumps(MOCK_SCORE_RESPONSE)

    with patch("agents.scorer._ollama_chat", return_value=raw_response):
        result = await scorer.score(SAMPLE_POSTING)

    assert isinstance(result, ScoredJob)
    assert result.total_score == 88
    assert result.path_recommendation == "path_b"
    assert "Python" in result.matched_skills


@pytest.mark.asyncio
async def test_score_handles_json_decode_error():
    scorer = JirehScorer(CONFIG, SAMPLE_SKILLS)

    with patch("agents.scorer._ollama_chat", return_value="not valid json at all"):
        result = await scorer.score(SAMPLE_POSTING)

    assert result.path_recommendation == "skip"
    assert result.total_score == 0


@pytest.mark.asyncio
async def test_score_handles_missing_key():
    scorer = JirehScorer(CONFIG, SAMPLE_SKILLS)
    incomplete = '{"total_score": 80}'  # missing required keys

    with patch("agents.scorer._ollama_chat", return_value=incomplete):
        result = await scorer.score(SAMPLE_POSTING)

    assert result.path_recommendation == "skip"


# ─── JirehScorer.score_batch tests ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_score_batch_filters_skips():
    scorer = JirehScorer(CONFIG, SAMPLE_SKILLS)

    skip_response = {**MOCK_SCORE_RESPONSE, "total_score": 30, "path_recommendation": "skip"}
    responses = [json.dumps(MOCK_SCORE_RESPONSE), json.dumps(skip_response)]

    call_count = 0

    def fake_ollama(model, messages):
        nonlocal call_count
        r = responses[call_count]
        call_count += 1
        return r

    postings = [SAMPLE_POSTING, SAMPLE_POSTING]

    with patch("agents.scorer._ollama_chat", side_effect=fake_ollama):
        results = await scorer.score_batch(postings)

    assert len(results) == 1
    assert results[0].path_recommendation == "path_b"


@pytest.mark.asyncio
async def test_score_batch_sorted_by_score_descending():
    scorer = JirehScorer(CONFIG, SAMPLE_SKILLS)

    high = {**MOCK_SCORE_RESPONSE, "total_score": 90, "path_recommendation": "path_b"}
    low = {**MOCK_SCORE_RESPONSE, "total_score": 65, "path_recommendation": "path_a"}
    responses = [json.dumps(low), json.dumps(high)]

    call_count = 0

    def fake_ollama(model, messages):
        nonlocal call_count
        r = responses[call_count]
        call_count += 1
        return r

    other_posting = JobPosting(
        job_id="test_002",
        title="QA Manager",
        company="AnotherCo",
        location="Remote",
        url="https://example.com/job/456",
        platform="linkedin",
    )
    postings = [SAMPLE_POSTING, other_posting]

    with patch("agents.scorer._ollama_chat", side_effect=fake_ollama):
        results = await scorer.score_batch(postings)

    assert len(results) == 2
    assert results[0].total_score > results[1].total_score
