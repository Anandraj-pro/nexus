"""nexus-scorer — scores job postings 0-100 against the skills profile using Ollama/Llama."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Any

import ollama

from agents.scout import JobPosting

logger = logging.getLogger(__name__)

def _build_scorer_prompt(experience_years: int) -> str:
    return (
        "You are nexus-scorer, an expert QA career advisor. Evaluate how well a job description\n"
        "matches a candidate's skills profile and return a structured score.\n\n"
        "Scoring criteria (weights sum to 1.0):\n"
        f"  - experience_match (0.30): does the required YoE align with candidate's {experience_years} years?\n"
        "  - skills_match (0.35): how many key technical/leadership skills match?\n"
        "  - domain_match (0.20): does the industry/domain align with candidate preferences?\n"
        "  - seniority_match (0.15): is the role level appropriate for the candidate's seniority?\n\n"
        "Return ONLY a valid JSON object — no markdown, no code fences, no explanation:\n"
        '{"total_score": <int 0-100>, "breakdown": {"experience_match": <int>, "skills_match": <int>, '
        '"domain_match": <int>, "seniority_match": <int>}, "matched_skills": [<str>, ...], '
        '"missing_skills": [<str>, ...], "path_recommendation": "path_a"|"path_b"|"skip", "reasoning": "<one sentence>"}\n\n'
        "path_a = stretch / senior track (score >= path_a_threshold, queued for human approval)\n"
        "path_b = primary track (score >= path_b_threshold, auto-applied immediately)\n"
        "skip   = poor fit or below minimum threshold — do not apply\n"
    )


def _escape_json_strings(text: str) -> str:
    """Escape literal newlines/tabs inside JSON string values (LLM output repair)."""
    result = []
    in_string = False
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and in_string:
            result.append(ch)
            if i + 1 < len(text):
                result.append(text[i + 1])
            i += 2
            continue
        if ch == '"':
            in_string = not in_string
            result.append(ch)
        elif in_string and ch == "\n":
            result.append("\\n")
        elif in_string and ch == "\r":
            result.append("\\r")
        elif in_string and ch == "\t":
            result.append("\\t")
        else:
            result.append(ch)
        i += 1
    return "".join(result)


def _extract_json(text: str) -> str:
    """Strip markdown code fences and extract the first JSON object found."""
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text)
    start = text.find("{")
    if start == -1:
        return text
    try:
        _, end = json.JSONDecoder(strict=False).raw_decode(text, start)
        return text[start:end]
    except json.JSONDecodeError:
        pass
    try:
        repaired = _escape_json_strings(text[start:])
        _, end = json.JSONDecoder(strict=False).raw_decode(repaired, 0)
        return repaired[:end]
    except json.JSONDecodeError:
        return text[start:]


_NON_QE_TITLE_SIGNALS = frozenset([
    "sales", "marketer", "marketing", "lead generation",
    "growth executive", "business development",
])


def _ollama_chat(model: str, messages: list[dict]) -> str:
    response = ollama.chat(model=model, messages=messages)
    return response["message"]["content"]


@dataclass
class ScoredJob:
    posting: JobPosting
    total_score: int
    breakdown: dict[str, int]
    matched_skills: list[str]
    missing_skills: list[str]
    path_recommendation: str  # "path_a" | "path_b" | "skip"
    reasoning: str


class NexusScorer:
    """
    Scores each JobPosting against the candidate's skills profile using Ollama/Llama.

    Uses llama3.2 locally — zero API cost.
    Runs the blocking ollama.chat() in a thread pool so the async pipeline stays non-blocking.
    """

    def __init__(self, config: dict[str, Any], skills_profile: dict[str, Any]):
        self.config = config
        self.skills_profile = skills_profile
        llm_cfg = config.get("llm", {})
        self._model = llm_cfg.get("scorer_model", "llama3.2")
        self._path_b_threshold = config.get("scorer", {}).get("path_b_threshold", 72)
        self._path_a_threshold = config.get("scorer", {}).get("path_a_threshold", 60)
        self._skills_text = json.dumps(skills_profile, indent=2)
        experience_years = skills_profile.get("profile", {}).get("experience_years", 10)
        self._system_prompt = _build_scorer_prompt(experience_years)

    def _enforce_path(self, score: int) -> str:
        """Config thresholds are the final authority — LLM recommendation is ignored for routing."""
        if score >= self._path_b_threshold:
            return "path_b"
        if score >= self._path_a_threshold:
            return "path_a"
        return "skip"

    async def score(self, posting: JobPosting) -> ScoredJob:
        """Score a single job posting against the candidate's profile."""
        user_content = (
            f"CANDIDATE SKILLS PROFILE:\n{self._skills_text}\n\n"
            f"JOB TITLE: {posting.title}\n"
            f"COMPANY: {posting.company}\n"
            f"LOCATION: {posting.location}\n\n"
            f"JOB DESCRIPTION:\n{posting.description[:3000]}"
        )

        messages = [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": user_content},
        ]

        try:
            raw = await asyncio.to_thread(_ollama_chat, self._model, messages)
            data = json.loads(_extract_json(raw))
            score = data["total_score"]

            return ScoredJob(
                posting=posting,
                total_score=score,
                breakdown=data["breakdown"],
                matched_skills=data.get("matched_skills", []),
                missing_skills=data.get("missing_skills", []),
                path_recommendation=self._enforce_path(score),
                reasoning=data["reasoning"],
            )

        except (json.JSONDecodeError, KeyError) as exc:
            logger.exception("Scorer failed for %s @ %s: %s", posting.title, posting.company, exc)
            return ScoredJob(
                posting=posting,
                total_score=0,
                breakdown={},
                matched_skills=[],
                missing_skills=[],
                path_recommendation="skip",
                reasoning=f"Scoring failed: {exc}",
            )

    async def score_batch(self, postings: list[JobPosting]) -> list[ScoredJob]:
        """Score all postings; return only those above threshold, sorted by score."""
        results: list[ScoredJob] = []
        for posting in postings:
            title_lower = posting.title.lower()
            if any(sig in title_lower for sig in _NON_QE_TITLE_SIGNALS):
                logger.info("Pre-filter skip (irrelevant title): %s @ %s", posting.title, posting.company)
                continue
            scored = await self.score(posting)
            logger.info(
                "Scored [%d/100] %s @ %s → %s",
                scored.total_score,
                posting.title,
                posting.company,
                scored.path_recommendation,
            )
            if scored.path_recommendation != "skip":
                results.append(scored)

        # Deduplicate by URL — same job can appear across multiple keyword searches.
        # Keep the highest-scoring instance so the tailor only processes it once.
        seen_urls: dict[str, ScoredJob] = {}
        for job in results:
            url = job.posting.url
            if url not in seen_urls or job.total_score > seen_urls[url].total_score:
                seen_urls[url] = job
        deduped = list(seen_urls.values())
        if len(deduped) < len(results):
            logger.info("URL dedup: %d → %d jobs", len(results), len(deduped))

        deduped.sort(key=lambda s: s.total_score, reverse=True)
        return deduped