"""Active job URL & closure verification engine to purge expired and dead postings."""

import asyncio
import logging
from typing import List, Dict, Any
import httpx

logger = logging.getLogger("nexus.liveness")

# Comprehensive closure markers found on expired job portal pages & ATS platforms
CLOSURE_MARKERS = [
    "no longer accepting applications",
    "this job is closed",
    "job posting has expired",
    "position has been filled",
    "this position is no longer available",
    "application deadline has passed",
    "this role has been closed",
    "job is no longer open",
    "requisition has been closed",
    "this job has expired",
    "posting is no longer active",
    "this vacancy is no longer available",
    "this job opportunity is closed",
    "applications are closed",
    "we are no longer taking applications",
    "this listing has expired",
    "page not found",
    "oops! this job is no longer available",
    "the job you are looking for is no longer open",
    "job requisition closed",
    "this requisition is not open",
]


async def is_job_active(client: httpx.AsyncClient, job: Dict[str, Any], semaphore: asyncio.Semaphore) -> bool:
    """Verify that an opportunity link is live, not 404, and not marked as closed."""
    url = job.get("apply_url")
    if not url:
        return False

    platform = job.get("platform", "")

    async with semaphore:
        try:
            # Standard browser headers to avoid anti-bot 403s on landing pages
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/128.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }

            # Fast GET request with redirect following
            resp = await client.get(url, headers=headers, timeout=5.0)

            # Drop definite 404 or 410 dead links
            if resp.status_code in (404, 410):
                logger.debug(
                    "Dropping expired job (HTTP %d): %s - %s",
                    resp.status_code,
                    job.get("company_name"),
                    job.get("job_title"),
                )
                return False

            if resp.status_code == 200:
                # Check the first 12KB of HTML for explicit closure markers
                text_sample = resp.text[:12288].lower()
                for marker in CLOSURE_MARKERS:
                    if marker in text_sample:
                        logger.info(
                            "Dropping closed role ('%s'): %s - %s",
                            marker,
                            job.get("company_name"),
                            job.get("job_title"),
                        )
                        return False

            return True
        except httpx.TimeoutException:
            # If target server is slow or throttling, retain verified direct ATS / careers endpoints
            return platform in (
                "Greenhouse",
                "Ashby",
                "Lever",
                "YC Work at a Startup",
                "Google Careers",
                "Microsoft Careers",
                "Amazon Jobs",
                "Uber Careers",
                "Adobe Careers",
                "Cisco Careers",
                "TCS NextStep",
                "Infosys Careers",
                "Stripe Careers",
            )
        except Exception:
            # On network/DNS errors, keep rather than false-positive purge
            return True


async def filter_active_opportunities(jobs: List[Dict[str, Any]], concurrency: int = 15) -> List[Dict[str, Any]]:
    """Concurrently check all job application links and purge expired / dead postings."""
    if not jobs:
        return []

    logger.info("Verifying active status for %d opportunities across job portals...", len(jobs))
    semaphore = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(follow_redirects=True) as client:
        tasks = [is_job_active(client, job, semaphore) for job in jobs]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        active_jobs: List[Dict[str, Any]] = []
        expired_count = 0

        for idx, is_active in enumerate(results):
            if is_active is True:
                active_jobs.append(jobs[idx])
            else:
                expired_count += 1

        logger.info(
            "Liveness check complete: %d active retained, %d expired/closed purged.",
            len(active_jobs),
            expired_count,
        )
        return active_jobs
