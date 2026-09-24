"""Y Combinator Work at a Startup Algolia public query collector."""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
import httpx

from config.targets import YC_ALGOLIA_CONFIG, REQUEST_TIMEOUT_SECONDS, FRESHNESS_WINDOW_SECONDS
from services.collectors import is_tech_role, is_scam

logger = logging.getLogger("nexus.collectors.yc")


async def fetch_yc_hn_jobs() -> List[Dict[str, Any]]:
    """Fallback collector using Y Combinator's official Hacker News Jobs API."""
    results: List[Dict[str, Any]] = []
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            resp = await client.get("https://hacker-news.firebaseio.com/v0/jobstories.json")
            if resp.status_code != 200:
                return results

            story_ids = resp.json()[:15]  # Top 15 recent YC job postings
            tasks = [
                client.get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json")
                for sid in story_ids
            ]
            item_resps = await asyncio.gather(*tasks, return_exceptions=True)

            cutoff = datetime.now(timezone.utc) - timedelta(seconds=FRESHNESS_WINDOW_SECONDS * 2)

            for item_resp in item_resps:
                if isinstance(item_resp, Exception) or item_resp.status_code != 200:
                    continue
                item = item_resp.json()
                if not item or item.get("type") != "job":
                    continue

                raw_title = item.get("title", "")
                if not is_tech_role(raw_title) or is_scam(raw_title):
                    continue

                # Parse company name e.g. "QuestDB (YC S20) Is Hiring a..."
                company_name = "YC Startup"
                job_title = raw_title
                if "is hiring" in raw_title.lower():
                    parts = raw_title.lower().split("is hiring", 1)
                    company_name = raw_title[: len(parts[0])].strip()
                    job_title = raw_title[len(parts[0]) + len("is hiring") :].strip()
                    if job_title.lower().startswith("a "):
                        job_title = job_title[2:].strip()
                    elif job_title.lower().startswith("an "):
                        job_title = job_title[3:].strip()
                elif "(" in raw_title and ")" in raw_title:
                    company_name = raw_title.split("(")[0].strip()

                time_val = item.get("time")
                pub_dt = (
                    datetime.fromtimestamp(time_val, tz=timezone.utc)
                    if time_val
                    else None
                )

                apply_url = item.get("url") or f"https://news.ycombinator.com/item?id={item.get('id')}"

                results.append({
                    "company_name": company_name or "YC Startup",
                    "job_title": job_title or raw_title,
                    "location": "Global / Remote",
                    "apply_url": apply_url,
                    "platform": "YC Work at a Startup",
                    "description": "",
                    "published_at": pub_dt.isoformat() if pub_dt else None,
                    "raw_salary": None,
                })
    except Exception as exc:
        logger.warning("YC HN jobs fallback error: %s", exc)

    return results


async def fetch_yc_jobs() -> List[Dict[str, Any]]:
    """Query Y Combinator Work at a Startup via Algolia public search API, falling back to YC HN feed."""
    url = YC_ALGOLIA_CONFIG["url"]
    headers = {
        "x-algolia-application-id": YC_ALGOLIA_CONFIG["app_id"],
        "x-algolia-api-key": YC_ALGOLIA_CONFIG["api_key"],
        "Content-Type": "application/json",
        "User-Agent": "NexusCareers-Aggregator/1.0",
    }
    payload = {
        "query": "Software Engineer AI",
        "hitsPerPage": 50,
        "facetFilters": [],
    }

    results: List[Dict[str, Any]] = []
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                hits = data.get("hits", [])
                cutoff = datetime.now(timezone.utc) - timedelta(seconds=FRESHNESS_WINDOW_SECONDS)

                for hit in hits:
                    title = hit.get("title") or hit.get("role") or ""
                    if not is_tech_role(title):
                        continue

                    company_name = hit.get("company_name") or hit.get("companyName") or "YC Startup"
                    desc = hit.get("description") or ""

                    if is_scam(title, desc):
                        continue

                    created_at_val = hit.get("created_at") or hit.get("createdAt")
                    created_dt = None
                    if created_at_val:
                        try:
                            if isinstance(created_at_val, (int, float)):
                                created_dt = datetime.fromtimestamp(created_at_val, tz=timezone.utc)
                            elif isinstance(created_at_val, str):
                                created_dt = datetime.fromisoformat(created_at_val.replace("Z", "+00:00"))
                        except Exception:
                            pass

                    if created_dt and created_dt < cutoff:
                        continue

                    job_id = hit.get("id") or hit.get("objectID")
                    slug = hit.get("company_slug") or hit.get("companySlug") or ""
                    apply_url = hit.get("apply_url") or hit.get("applyUrl")
                    if not apply_url:
                        if job_id:
                            apply_url = f"https://www.workatastartup.com/jobs/{job_id}"
                        elif slug:
                            apply_url = f"https://www.workatastartup.com/companies/{slug}"
                        else:
                            apply_url = "https://www.workatastartup.com"

                    location = hit.get("location") or "Remote"
                    if hit.get("remote") in (True, "Yes", "true"):
                        location = f"{location} (Remote)"

                    salary_min = hit.get("salary_min") or hit.get("min_salary")
                    salary_max = hit.get("salary_max") or hit.get("max_salary")
                    raw_salary = None
                    if salary_min or salary_max:
                        raw_salary = f"${salary_min or 0}k - ${salary_max or 0}k"

                    results.append({
                        "company_name": company_name,
                        "job_title": title,
                        "location": location,
                        "apply_url": apply_url,
                        "platform": "YC Work at a Startup",
                        "description": desc[:1000] if desc else "",
                        "published_at": created_dt.isoformat() if created_dt else None,
                        "raw_salary": raw_salary,
                    })
    except Exception as exc:
        logger.info("YC Algolia query not accessible (%s), activating YC official feed fallback.", exc)

    if not results:
        results = await fetch_yc_hn_jobs()

    return results

