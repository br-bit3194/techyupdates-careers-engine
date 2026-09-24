"""ATS Collectors for Greenhouse, Lever, and Ashby unauthenticated public endpoints."""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
import httpx

from config.targets import (
    ATS_TARGETS,
    FRESHNESS_WINDOW_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
)
from services.collectors import is_tech_role, is_scam

logger = logging.getLogger("nexus.collectors.ats")


def _is_recent(dt: Optional[datetime], window_seconds: int = FRESHNESS_WINDOW_SECONDS) -> bool:
    """Check if datetime is within the freshness window (defaults to 24h)."""
    if dt is None:
        # If no timestamp is provided by the ATS, assume active posting
        return True
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (now - dt) <= timedelta(seconds=window_seconds)


def _parse_iso_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO formatted timestamp strings."""
    if not date_str:
        return None
    try:
        # Normalize trailing Z
        normalized = date_str.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except Exception:
        return None


async def fetch_greenhouse_jobs(
    client: httpx.AsyncClient, slug: str
) -> List[Dict[str, Any]]:
    """Fetch active jobs from Greenhouse public board API."""
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=false"
    results: List[Dict[str, Any]] = []
    try:
        resp = await client.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        if resp.status_code != 200:
            logger.warning("Greenhouse %s returned status %d", slug, resp.status_code)
            return results

        data = resp.json()
        jobs = data.get("jobs", [])
        for job in jobs:
            title = job.get("title", "")
            if not is_tech_role(title):
                continue

            updated_at_str = job.get("updated_at")
            updated_at = _parse_iso_date(updated_at_str)
            if not _is_recent(updated_at):
                continue

            if is_scam(title):
                continue

            location_data = job.get("location", {})
            location_str = (
                location_data.get("name", "Remote")
                if isinstance(location_data, dict)
                else "Remote"
            )

            results.append({
                "company_name": slug.capitalize(),
                "job_title": title,
                "location": location_str or "Remote",
                "apply_url": job.get("absolute_url", ""),
                "platform": "Greenhouse",
                "description": "",
                "published_at": updated_at.isoformat() if updated_at else None,
                "raw_salary": None,
            })
    except Exception as exc:
        logger.warning("Failed fetching Greenhouse for %s: %s", slug, exc)
    return results


async def fetch_lever_jobs(
    client: httpx.AsyncClient, slug: str
) -> List[Dict[str, Any]]:
    """Fetch active jobs from Lever public postings API."""
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    results: List[Dict[str, Any]] = []
    try:
        resp = await client.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        if resp.status_code != 200:
            logger.warning("Lever %s returned status %d", slug, resp.status_code)
            return results

        jobs = resp.json()
        if not isinstance(jobs, list):
            return results

        for job in jobs:
            title = job.get("text", "")
            if not is_tech_role(title):
                continue

            # Lever createdAt is in milliseconds
            created_at_ms = job.get("createdAt")
            created_at = None
            if created_at_ms:
                try:
                    created_at = datetime.fromtimestamp(created_at_ms / 1000.0, tz=timezone.utc)
                except Exception:
                    pass

            if not _is_recent(created_at):
                continue

            categories = job.get("categories", {})
            location = categories.get("location") or "Remote"
            description = job.get("descriptionPlain", "")

            if is_scam(title, description):
                continue

            results.append({
                "company_name": slug.capitalize(),
                "job_title": title,
                "location": location,
                "apply_url": job.get("hostedUrl", ""),
                "platform": "Lever",
                "description": description[:1000] if description else "",
                "published_at": created_at.isoformat() if created_at else None,
                "raw_salary": None,
            })
    except Exception as exc:
        logger.warning("Failed fetching Lever for %s: %s", slug, exc)
    return results


async def fetch_ashby_jobs(
    client: httpx.AsyncClient, slug: str
) -> List[Dict[str, Any]]:
    """Fetch active jobs from Ashby public job-board API."""
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    results: List[Dict[str, Any]] = []
    try:
        resp = await client.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        if resp.status_code != 200:
            logger.warning("Ashby %s returned status %d", slug, resp.status_code)
            return results

        data = resp.json()
        jobs = data.get("jobs", [])
        for job in jobs:
            title = job.get("title", "")
            if not is_tech_role(title):
                continue

            published_at_str = job.get("publishedAt")
            published_at = _parse_iso_date(published_at_str)
            if not _is_recent(published_at):
                continue

            location = job.get("location") or "Remote"
            job_url = job.get("jobUrl") or f"https://jobs.ashbyhq.com/{slug}/{job.get('id')}"

            if is_scam(title):
                continue

            results.append({
                "company_name": slug.capitalize(),
                "job_title": title,
                "location": location,
                "apply_url": job_url,
                "platform": "Ashby",
                "description": "",
                "published_at": published_at.isoformat() if published_at else None,
                "raw_salary": None,
            })
    except Exception as exc:
        logger.warning("Failed fetching Ashby for %s: %s", slug, exc)
    return results


async def collect_all_ats_jobs() -> List[Dict[str, Any]]:
    """Parallel collector across Greenhouse, Lever, and Ashby targets."""
    headers = {
        "User-Agent": "NexusCareers-Aggregator/1.0 (+https://github.com/TechyUpdates/job_finder)"
    }
    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        tasks = []

        for slug in ATS_TARGETS.get("greenhouse", []):
            tasks.append(fetch_greenhouse_jobs(client, slug))

        for slug in ATS_TARGETS.get("lever", []):
            tasks.append(fetch_lever_jobs(client, slug))

        for slug in ATS_TARGETS.get("ashby", []):
            tasks.append(fetch_ashby_jobs(client, slug))

        gathered = await asyncio.gather(*tasks, return_exceptions=True)

        all_jobs: List[Dict[str, Any]] = []
        for result in gathered:
            if isinstance(result, list):
                all_jobs.extend(result)
            elif isinstance(result, Exception):
                logger.warning("ATS fetch task raised exception: %s", result)

        return all_jobs
