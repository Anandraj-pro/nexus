"""jireh-scout — discovers new job postings across all configured platforms."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from agents.db import DEFAULT_DB_PATH, init_db, load_seen_fingerprints, save_seen_jobs

if TYPE_CHECKING:
    from agents.vault import JirehVault

logger = logging.getLogger(__name__)


@dataclass
class JobPosting:
    """Canonical job posting record produced by jireh-scout."""

    job_id: str
    title: str
    company: str
    location: str
    platform: str
    url: str
    description: str = ""
    posted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    raw_data: dict[str, Any] = field(default_factory=dict)

    @property
    def fingerprint(self) -> str:
        """Stable ID for deduplication — title + company + platform."""
        key = f"{self.title.lower()}|{self.company.lower()}|{self.platform}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]


class JirehScout:
    """
    Discovers fresh job postings and returns a deduplicated list of JobPosting objects.

    Platform adapters are registered via `register_adapter`. Each adapter is a
    callable(keywords, locations) -> list[JobPosting].
    """

    def __init__(
        self,
        config: dict[str, Any],
        seen_fingerprints: set[str] | None = None,
        db_path: Path | None = None,
        vault: JirehVault | None = None,
    ):
        self.config = config
        self._vault = vault
        self._db_path = db_path or Path(
            config.get("system", {}).get("db_path", str(DEFAULT_DB_PATH))
        )
        init_db(self._db_path)
        self._seen: set[str] = (
            seen_fingerprints if seen_fingerprints is not None
            else load_seen_fingerprints(self._db_path)
        )
        self._adapters: dict[str, Any] = {}
        self._register_built_in_adapters()

    def _register_built_in_adapters(self) -> None:
        self._adapters["greenhouse"] = self._fetch_greenhouse
        self._adapters["lever"] = self._fetch_lever
        self._adapters["indeed"] = self._fetch_indeed_html
        # Playwright imports happen inside each method — safe to register here.
        self._adapters["linkedin"] = self._fetch_linkedin
        self._adapters["naukri"] = self._fetch_naukri

    def register_adapter(self, platform: str, fn: Any) -> None:
        self._adapters[platform] = fn

    async def run(self) -> list[JobPosting]:
        """Execute all enabled platform adapters and return new postings."""
        scout_cfg = self.config.get("scout", {})
        keywords: list[str] = scout_cfg.get("keywords", [])
        locations: list[str] = scout_cfg.get("locations", [])
        platforms: list[str] = scout_cfg.get("platforms", [])

        all_postings: list[JobPosting] = []

        for platform in platforms:
            adapter = self._adapters.get(platform)
            if adapter is None:
                logger.warning("No adapter registered for platform: %s", platform)
                continue
            try:
                logger.info("Scout → fetching from %s", platform)
                postings = await adapter(keywords, locations)
                new = [p for p in postings if p.fingerprint not in self._seen]
                self._seen.update(p.fingerprint for p in new)
                save_seen_jobs(new, self._db_path)
                logger.info("Scout ← %s: %d new / %d total", platform, len(new), len(postings))
                all_postings.extend(new)
            except Exception:
                logger.exception("Scout failed on platform: %s", platform)

        return all_postings

    # ── Built-in adapters ────────────────────────────────────────────────────

    async def _fetch_greenhouse(self, keywords: list[str], locations: list[str]) -> list[JobPosting]:
        """Fetches from Greenhouse public board API (no auth required)."""
        # Greenhouse has no global search API — extend with target company board IDs.
        return []

    async def _fetch_lever(self, keywords: list[str], locations: list[str]) -> list[JobPosting]:
        """Fetches from Lever public postings API."""
        # Lever has per-company public endpoints — extend with target company IDs.
        return []

    async def _fetch_indeed_html(
        self, keywords: list[str], locations: list[str]
    ) -> list[JobPosting]:
        """Indeed job scrape via Playwright (bypasses 403 bot-detection on plain HTTP)."""
        from playwright.async_api import async_playwright

        postings: list[JobPosting] = []

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            )
            page = await context.new_page()

            for keyword in keywords[:3]:
                for location in locations[:2]:
                    url = (
                        f"https://in.indeed.com/jobs"
                        f"?q={keyword.replace(' ', '+')}&l={location.replace(' ', '+')}&fromage=1"
                    )
                    try:
                        await page.goto(url, timeout=20_000, wait_until="domcontentloaded")
                        await page.wait_for_timeout(2000)
                        html = await page.content()
                        soup = BeautifulSoup(html, "html.parser")
                        for card in soup.select("[data-jk]"):
                            jk = card.get("data-jk", "")
                            title_el = card.select_one("h2.jobTitle span, h2.jobTitle a span")
                            company_el = card.select_one(
                                "[data-testid='company-name'], .companyName"
                            )
                            desc_el = card.select_one(".job-snippet, [data-testid='jobsnippet']")
                            posting = JobPosting(
                                job_id=f"indeed_{jk}",
                                title=title_el.get_text(strip=True) if title_el else "",
                                company=company_el.get_text(strip=True) if company_el else "",
                                location=location,
                                description=desc_el.get_text(strip=True) if desc_el else "",
                                platform="indeed",
                                url=f"https://in.indeed.com/viewjob?jk={jk}",
                            )
                            if posting.title:
                                postings.append(posting)
                        logger.info(
                            "Indeed: %d cards for '%s' / '%s'",
                            len([p for p in postings if p.location == location]),
                            keyword,
                            location,
                        )
                    except Exception:
                        logger.exception("Indeed fetch failed for %s / %s", keyword, location)

            await browser.close()
        return postings

    # ── Playwright adapters ──────────────────────────────────────────────────

    async def _fetch_linkedin(
        self, keywords: list[str], locations: list[str]
    ) -> list[JobPosting]:
        """
        LinkedIn job search via Playwright.

        First run: opens a visible browser so you can log in manually.
        Subsequent runs: loads saved session cookies and runs headless.
        Session is cleared automatically if LinkedIn rejects it.
        """
        from playwright.async_api import TimeoutError as PWTimeout
        from playwright.async_api import async_playwright

        scout_cfg = self.config.get("scout", {})
        apply_cfg = self.config.get("apply", {})
        max_jobs: int = scout_cfg.get("max_jobs_per_run", 100)
        slow_mo: int = apply_cfg.get("slow_mo_ms", 50)

        postings: list[JobPosting] = []
        saved_cookies = self._vault.load_session("linkedin") if self._vault else None
        headless = bool(saved_cookies)

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=headless, slow_mo=slow_mo)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            )

            if saved_cookies:
                await context.add_cookies(saved_cookies)

            page = await context.new_page()

            try:
                if not saved_cookies:
                    await self._linkedin_manual_login(page, context)
                    if self._vault:
                        cookies = await context.cookies()
                        self._vault.save_session("linkedin", cookies)
                        logger.info("LinkedIn: session saved — next run will be headless")

                # Verify the session is still valid
                await page.goto("https://www.linkedin.com/jobs/", timeout=30000)
                await page.wait_for_timeout(2000)

                if _linkedin_auth_blocked(page.url):
                    logger.warning("LinkedIn: session expired — clearing; re-login required next run")
                    if self._vault:
                        self._vault.clear_session("linkedin")
                    return []

                postings = await self._linkedin_scrape_jobs(
                    page, keywords, locations, max_jobs
                )

            except PWTimeout:
                logger.warning("LinkedIn: timeout — returning %d collected so far", len(postings))
            except Exception:
                logger.exception("LinkedIn: unexpected error")
            finally:
                await browser.close()

        return postings

    async def _linkedin_manual_login(self, page: Any, context: Any) -> None:
        """Open LinkedIn login page and wait up to 2 minutes for manual sign-in."""
        from playwright.async_api import TimeoutError as PWTimeout

        await page.goto("https://www.linkedin.com/login", timeout=30000)
        logger.info(
            "LinkedIn: browser opened — please log in within 2 minutes. "
            "Jireh will continue automatically once you reach your feed."
        )
        try:
            # Wait for redirect to feed or any authenticated page
            await page.wait_for_url("**/feed/**", timeout=120_000)
        except PWTimeout:
            # Fallback: check if we're on any authenticated page
            if "login" in page.url or "authwall" in page.url:
                raise RuntimeError("LinkedIn login not completed within timeout")

    async def _linkedin_scrape_jobs(
        self,
        page: Any,
        keywords: list[str],
        locations: list[str],
        max_jobs: int,
    ) -> list[JobPosting]:
        """Iterate keyword × location pairs and collect job postings."""
        from playwright.async_api import TimeoutError as PWTimeout

        postings: list[JobPosting] = []

        for keyword in keywords:
            if len(postings) >= max_jobs:
                break
            for location in locations:
                if len(postings) >= max_jobs:
                    break

                search_url = (
                    "https://www.linkedin.com/jobs/search/"
                    f"?keywords={quote_plus(keyword)}"
                    f"&location={quote_plus(location)}"
                    "&f_TPR=r86400"   # posted in last 24 hours
                    "&sortBy=DD"      # most recent first
                )

                try:
                    await page.goto(search_url, timeout=30000)
                    await page.wait_for_timeout(2500)

                    if _linkedin_auth_blocked(page.url):
                        logger.warning("LinkedIn: auth blocked mid-scrape — stopping")
                        return postings

                    cards = await page.query_selector_all(
                        "li.jobs-search-results__list-item"
                    )
                    if not cards:
                        cards = await page.query_selector_all(".job-card-container")

                    logger.info(
                        "LinkedIn: %d cards for '%s' / '%s'", len(cards), keyword, location
                    )

                    for card in cards:
                        if len(postings) >= max_jobs:
                            break
                        posting = await self._parse_linkedin_card(page, card, location)
                        if posting:
                            postings.append(posting)

                except PWTimeout:
                    logger.warning(
                        "LinkedIn: timeout on '%s' / '%s' — continuing", keyword, location
                    )
                except Exception:
                    logger.exception(
                        "LinkedIn: error on '%s' / '%s'", keyword, location
                    )

        return postings

    async def _parse_linkedin_card(
        self, page: Any, card: Any, fallback_location: str
    ) -> JobPosting | None:
        """Click a job card, wait for the side panel, and extract all fields."""
        from playwright.async_api import TimeoutError as PWTimeout

        try:
            await card.click()
            await page.wait_for_timeout(1500)

            title = await _text(card, [
                ".job-card-list__title",
                ".job-card-container__link",
                "h3",
            ])
            company = await _text(card, [
                ".job-card-container__primary-description",
                ".job-card-container__company-name",
                ".artdeco-entity-lockup__subtitle",
            ])
            location = await _text(card, [
                ".job-card-container__metadata-item",
                ".job-card-container__metadata-wrapper",
            ]) or fallback_location

            href = ""
            for sel in [
                "a.job-card-container__link",
                "a.job-card-list__title",
                "a[href*='/jobs/view/']",
            ]:
                el = await card.query_selector(sel)
                if el:
                    href = await el.get_attribute("href") or ""
                    break

            job_url = ""
            if href:
                job_url = (
                    f"https://www.linkedin.com{href.split('?')[0]}"
                    if href.startswith("/")
                    else href.split("?")[0]
                )

            # Description from the detail panel that loads after clicking the card
            description = ""
            try:
                desc_el = await page.wait_for_selector(
                    ".jobs-description__content, .jobs-box__html-content",
                    timeout=5000,
                )
                if desc_el:
                    description = (await desc_el.inner_text()).strip()
            except PWTimeout:
                pass

            if not title:
                return None

            job_id = (
                f"linkedin_{job_url.rstrip('/').split('/')[-1]}"
                if job_url
                else f"linkedin_{abs(hash(title + company))}"
            )

            return JobPosting(
                job_id=job_id,
                title=title,
                company=company,
                location=location,
                platform="linkedin",
                url=job_url,
                description=description,
            )

        except Exception:
            logger.debug("LinkedIn: failed to parse card", exc_info=True)
            return None

    async def _fetch_naukri(
        self, keywords: list[str], locations: list[str]
    ) -> list[JobPosting]:
        """Naukri job search via Playwright. Session-cookie backed, headless after first login."""
        from playwright.async_api import TimeoutError as PWTimeout
        from playwright.async_api import async_playwright

        scout_cfg = self.config.get("scout", {})
        apply_cfg = self.config.get("apply", {})
        max_jobs: int = scout_cfg.get("max_jobs_per_run", 100)
        slow_mo: int = apply_cfg.get("slow_mo_ms", 50)

        postings: list[JobPosting] = []
        saved_cookies = self._vault.load_session("naukri") if self._vault else None
        headless = bool(saved_cookies)

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=headless, slow_mo=slow_mo)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            )
            if saved_cookies:
                await context.add_cookies(saved_cookies)

            page = await context.new_page()

            try:
                if not saved_cookies:
                    await self._naukri_manual_login(page, context)
                    if self._vault:
                        cookies = await context.cookies()
                        self._vault.save_session("naukri", cookies)
                        logger.info("Naukri: session saved — next run will be headless")

                await page.goto("https://www.naukri.com/mnjuser/homepage", timeout=30000)
                await page.wait_for_timeout(2000)

                if _naukri_auth_blocked(page.url):
                    logger.warning("Naukri: session expired — clearing; re-login required next run")
                    if self._vault:
                        self._vault.clear_session("naukri")
                    return []

                for keyword in keywords:
                    if len(postings) >= max_jobs:
                        break
                    for location in locations:
                        if len(postings) >= max_jobs:
                            break
                        batch = await self._naukri_scrape_jobs(
                            page, keyword, location, max_jobs - len(postings)
                        )
                        postings.extend(batch)
                        logger.info(
                            "Naukri: %d jobs collected for '%s' / '%s'",
                            len(batch), keyword, location,
                        )

            except PWTimeout:
                logger.warning("Naukri: timeout — returning %d collected so far", len(postings))
            except Exception:
                logger.exception("Naukri: unexpected error")
            finally:
                await browser.close()

        return postings

    async def _naukri_manual_login(self, page: Any, context: Any) -> None:  # noqa: ARG002
        """Open Naukri login page and wait up to 5 minutes for manual sign-in."""
        from playwright.async_api import TimeoutError as PWTimeout

        await page.goto("https://www.naukri.com/nlogin/login", timeout=30000)

        # Try auto-fill credentials if available
        import os
        email = os.getenv("NAUKRI_EMAIL", "")
        password = os.getenv("NAUKRI_PASSWORD", "")
        if email and password:
            try:
                await page.fill("input[type='text'][placeholder*='mail'], #usernameField", email)
                await page.fill("input[type='password'], #passwordField", password)
                await page.click("button[type='submit'], .loginButton")
                logger.info("Naukri: auto-fill credentials attempted")
            except Exception:
                logger.info("Naukri: auto-fill failed — waiting for manual login")

        logger.info(
            "Naukri: browser opened — please log in within 5 minutes. "
            "Jireh will continue automatically once you reach your homepage."
        )
        try:
            await page.wait_for_url("**/mnjuser/homepage**", timeout=300_000)
        except PWTimeout:
            if any(t in page.url for t in ("nlogin", "login")):
                raise RuntimeError("Naukri login not completed within timeout")

    async def _naukri_scrape_jobs(
        self,
        page: Any,
        keyword: str,
        location: str,
        limit: int,
    ) -> list[JobPosting]:
        """Search one keyword × location pair on Naukri and return job postings."""
        from playwright.async_api import TimeoutError as PWTimeout

        kw = keyword.replace(" ", "+")
        loc = location.replace(" ", "+")
        url = f"https://www.naukri.com/jobs?k={kw}&l={loc}&experience=10"

        try:
            await page.goto(url, timeout=30000)
            await page.wait_for_timeout(2000)
        except PWTimeout:
            logger.warning("Naukri: timeout loading search for %s / %s", keyword, location)
            return []

        try:
            await page.wait_for_selector(
                ".srp-jobtuple-wrapper, article.jobTuple, .cust-job-tuple",
                timeout=10_000,
            )
        except PWTimeout:
            logger.warning("Naukri: no job cards for '%s' / '%s'", keyword, location)
            return []

        cards = await page.query_selector_all(
            ".srp-jobtuple-wrapper, article.jobTuple, .cust-job-tuple"
        )
        postings: list[JobPosting] = []
        for card in cards[:limit]:
            posting = await self._parse_naukri_card(card, location)
            if posting:
                postings.append(posting)
        return postings

    async def _parse_naukri_card(self, card: Any, fallback_location: str) -> JobPosting | None:
        """Extract a JobPosting from a single Naukri search-result card."""
        try:
            title = await _text(card, ["a.title", ".jobTupleHeader a", "h2 a"])
            if not title:
                return None

            company = await _text(card, ["a.comp-name", ".comp-name", ".subTitle"])
            location = (
                await _text(card, [".loc span", ".locWdth", ".location span"])
                or fallback_location
            )

            href = ""
            for sel in ["a.title[href]", ".jobTupleHeader a[href]", "h2 a[href]"]:
                el = await card.query_selector(sel)
                if el:
                    href = await el.get_attribute("href") or ""
                    break

            job_url = href.split("?")[0] if href else ""

            # Naukri job URLs end with a numeric ID: ...job-listings-...-12345678
            last_segment = job_url.rstrip("/").split("-")[-1]
            job_id = (
                f"naukri_{last_segment}"
                if last_segment.isdigit()
                else f"naukri_{abs(hash(title + company))}"
            )

            description = await _text(card, [".job-description", ".job-desc", ".jd-desc"])

            return JobPosting(
                job_id=job_id,
                title=title,
                company=company,
                location=location,
                platform="naukri",
                url=job_url,
                description=description,
            )
        except Exception:
            logger.debug("Naukri: failed to parse card", exc_info=True)
            return None


# ── Helpers ──────────────────────────────────────────────────────────────────

def _linkedin_auth_blocked(url: str) -> bool:
    return any(token in url for token in ("authwall", "/login", "checkpoint"))


def _naukri_auth_blocked(url: str) -> bool:
    return any(token in url for token in ("nlogin", "/login", "error"))


async def _text(element: Any, selectors: list[str]) -> str:
    """Try each selector in order; return first non-empty inner text."""
    for sel in selectors:
        el = await element.query_selector(sel)
        if el:
            text = (await el.inner_text()).strip()
            if text:
                return text
    return ""