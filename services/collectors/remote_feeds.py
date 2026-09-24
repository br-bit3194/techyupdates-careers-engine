"""Remote job feeds collector (RemoteOK and Jobicy public APIs)."""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
import httpx

from config.targets import REMOTE_FEEDS, REQUEST_TIMEOUT_SECONDS, FRESHNESS_WINDOW_SECONDS
from services.collectors import is_tech_role, is_scam

logger = logging.getLogger("nexus.collectors.remote")


async def fetch_remoteok_jobs(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """Fetch recent engineering and AI jobs from RemoteOK public JSON API."""
    url = REMOTE_FEEDS["remoteok"]
    results: List[Dict[str, Any]] = []
    try:
        resp = await client.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        if resp.status_code != 200:
            logger.warning("RemoteOK returned status %d", resp.status_code)
            return results

        data = resp.json()
        if not isinstance(data, list):
            return results

        cutoff = datetime.now(timezone.utc) - timedelta(seconds=FRESHNESS_WINDOW_SECONDS)

        # First item in RemoteOK is usually API disclaimer metadata
        for item in data:
            if not isinstance(item, dict) or not item.get("id"):
                continue

            position = item.get("position", "")
            if not is_tech_role(position):
                continue

            # Date parsing
            date_str = item.get("date")
            pub_date = None
            if date_str:
                try:
                    pub_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                except Exception:
                    pass

            if pub_date and pub_date < cutoff:
                continue

            company = item.get("company", "Remote Company")
            description = item.get("description", "")

            if is_scam(position, description):
                continue

            apply_url = item.get("url") or f"https://remoteok.com/l/{item.get('id')}"

            # Salary extraction
            sal_min = item.get("salary_min")
            sal_max = item.get("salary_max")
            raw_salary = None
            if sal_min and sal_max:
                raw_salary = f"${sal_min:,} - ${sal_max:,}"

            results.append({
                "company_name": company,
                "job_title": position,
                "location": item.get("location") or "Remote / Global",
                "apply_url": apply_url,
                "platform": "RemoteOK",
                "description": description[:1000] if description else "",
                "published_at": pub_date.isoformat() if pub_date else None,
                "raw_salary": raw_salary,
            })
    except Exception as exc:
        logger.warning("Failed fetching RemoteOK feed: %s", exc)

    return results


async def fetch_jobicy_jobs(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """Fetch recent engineering and AI jobs from Jobicy public API."""
    url = REMOTE_FEEDS["jobicy"]
    results: List[Dict[str, Any]] = []
    try:
        resp = await client.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        if resp.status_code != 200:
            logger.warning("Jobicy returned status %d", resp.status_code)
            return results

        data = resp.json()
        jobs = data.get("jobs", [])
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=FRESHNESS_WINDOW_SECONDS)

        for job in jobs:
            title = job.get("jobTitle", "")
            if not is_tech_role(title):
                continue

            pub_date_str = job.get("pubDate")
            pub_date = None
            if pub_date_str:
                try:
                    # Jobicy date format: e.g. "2026-09-24 10:00:00"
                    pub_date = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00"))
                except Exception:
                    pass

            if pub_date and pub_date < cutoff:
                continue

            company = job.get("companyName", "Tech Company")
            description = job.get("jobDescription", "")

            if is_scam(title, description):
                continue

            sal_min = job.get("annualSalaryMin")
            sal_max = job.get("annualSalaryMax")
            currency = job.get("salaryCurrency", "USD")
            raw_salary = None
            if sal_min and sal_max:
                raw_salary = f"{currency} {sal_min:,} - {sal_max:,}"

            results.append({
                "company_name": company,
                "job_title": title,
                "location": job.get("jobGeo") or "Remote",
                "apply_url": job.get("url") or "",
                "platform": "Jobicy",
                "description": description[:1000] if description else "",
                "published_at": pub_date.isoformat() if pub_date else None,
                "raw_salary": raw_salary,
            })
    except Exception as exc:
        logger.warning("Failed fetching Jobicy feed: %s", exc)

    return results


async def collect_remote_feeds() -> List[Dict[str, Any]]:
    """Collect from all remote portals with polite User-Agent."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
    }
    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        remoteok_jobs = await fetch_remoteok_jobs(client)
        jobicy_jobs = await fetch_jobicy_jobs(client)
        return remoteok_jobs + jobicy_jobs
