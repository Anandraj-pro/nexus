"""Unit tests for jireh-tailor — uses mocked Ollama responses."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from agents.scorer import ScoredJob
from agents.scout import JobPosting
from agents.tailor import JirehTailor, TailoredApplication, _extract_json

# ─── Fixtures ─────────────────────────────────────────────────────────────────

SAMPLE_POSTING = JobPosting(
    job_id="tailor_001",
    title="QA Automation Lead",
    company="Acme Corp",
    location="Hyderabad",
    url="https://example.com/job/tailor_001",
    platform="linkedin",
    description="We need a QA lead with Selenium, pytest, and CI/CD experience.",
)

SAMPLE_SCORED_JOB = ScoredJob(
    posting=SAMPLE_POSTING,
    total_score=85,
    breakdown={"skills_match": 90, "experience_match": 80, "domain_match": 85, "seniority_match": 82},
    matched_skills=["Selenium", "pytest", "CI/CD"],
    missing_skills=["Appium"],
    path_recommendation="path_b",
    reasoning="Strong automation skill match.",
)

MOCK_TAILOR_RESPONSE = {
    "tailored_resume": "# Tailored Resume\n\nExperienced QA lead with Selenium...",
    "cover_letter": "Dear Hiring Manager,\n\nI bring 17 years of QA leadership.",
    "key_changes": ["Led with Selenium experience", "Highlighted CI/CD ownership"],
}


def _cfg(tmp_path: Path, template_text: str = "") -> dict:
    template_a = tmp_path / "base_a.md"
    template_b = tmp_path / "base_b.md"
    template_a.write_text(template_text)
    template_b.write_text(template_text)
    return {
        "llm": {"tailor_model": "llama3.1:8b"},
        "tailor": {
            "output_dir": str(tmp_path),
            "resume_template_path_a": str(template_a),
            "resume_template_path_b": str(template_b),
        },
    }


# ─── _extract_json ─────────────────────────────────────────────────────────────

def test_extract_json_plain():
    raw = '{"tailored_resume": "r", "cover_letter": "c"}'
    assert json.loads(_extract_json(raw))["tailored_resume"] == "r"


def test_extract_json_strips_fence():
    raw = '```json\n{"tailored_resume": "r"}\n```'
    assert json.loads(_extract_json(raw))["tailored_resume"] == "r"


def test_extract_json_with_preamble():
    raw = 'Here is the result:\n{"tailored_resume": "ok", "cover_letter": "ok"}\nDone.'
    assert json.loads(_extract_json(raw))["tailored_resume"] == "ok"


# ─── JirehTailor.tailor ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tailor_returns_tailored_application(tmp_path: Path):
    tailor = JirehTailor(_cfg(tmp_path))
    with patch("agents.tailor._ollama_chat", return_value=json.dumps(MOCK_TAILOR_RESPONSE)):
        result = await tailor.tailor(SAMPLE_SCORED_JOB)

    assert isinstance(result, TailoredApplication)
    assert "Tailored Resume" in result.tailored_resume
    assert "Hiring Manager" in result.cover_letter
    assert len(result.key_changes) == 2


@pytest.mark.asyncio
async def test_tailor_saves_resume_and_cover_to_disk(tmp_path: Path):
    tailor = JirehTailor(_cfg(tmp_path))
    with patch("agents.tailor._ollama_chat", return_value=json.dumps(MOCK_TAILOR_RESPONSE)):
        result = await tailor.tailor(SAMPLE_SCORED_JOB)

    assert result.output_path is not None
    assert result.output_path.exists()
    cover = result.output_path.with_name(result.output_path.name.replace("_resume.md", "_cover.md"))
    assert cover.exists()


@pytest.mark.asyncio
async def test_tailor_fallback_on_json_decode_error(tmp_path: Path):
    tailor = JirehTailor(_cfg(tmp_path, template_text="# Base Resume"))
    with patch("agents.tailor._ollama_chat", return_value="not valid json at all"):
        result = await tailor.tailor(SAMPLE_SCORED_JOB)

    assert "Tailoring failed" in result.key_changes[0]
    assert result.tailored_resume == "# Base Resume"
    assert result.cover_letter == ""


@pytest.mark.asyncio
async def test_tailor_fallback_on_missing_required_key(tmp_path: Path):
    tailor = JirehTailor(_cfg(tmp_path))
    incomplete = '{"tailored_resume": "ok"}'  # missing cover_letter key
    with patch("agents.tailor._ollama_chat", return_value=incomplete):
        result = await tailor.tailor(SAMPLE_SCORED_JOB)

    assert "Tailoring failed" in result.key_changes[0]


@pytest.mark.asyncio
async def test_tailor_key_changes_defaults_to_empty_list(tmp_path: Path):
    tailor = JirehTailor(_cfg(tmp_path))
    response = {**MOCK_TAILOR_RESPONSE}
    del response["key_changes"]
    with patch("agents.tailor._ollama_chat", return_value=json.dumps(response)):
        result = await tailor.tailor(SAMPLE_SCORED_JOB)

    assert result.key_changes == []


# ─── JirehTailor.tailor_batch ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tailor_batch_returns_one_result_per_job(tmp_path: Path):
    tailor = JirehTailor(_cfg(tmp_path))
    with patch("agents.tailor._ollama_chat", return_value=json.dumps(MOCK_TAILOR_RESPONSE)):
        results = await tailor.tailor_batch([SAMPLE_SCORED_JOB, SAMPLE_SCORED_JOB])

    assert len(results) == 2
    assert all(isinstance(r, TailoredApplication) for r in results)


@pytest.mark.asyncio
async def test_tailor_batch_empty_input(tmp_path: Path):
    tailor = JirehTailor(_cfg(tmp_path))
    results = await tailor.tailor_batch([])
    assert results == []