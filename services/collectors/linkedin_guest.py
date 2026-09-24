"""Rate-aware, polite LinkedIn Guest API collector with circuit breaker."""

import logging
from typing import List, Dict, Any
from urllib.parse import urlencode
from bs4 import BeautifulSoup
import httpx

from config.targets import LINKEDIN_GUEST_CONFIG, REQUEST_TIMEOUT_SECONDS
from services.collectors import is_tech_role, is_scam

logger = logging.getLogger("nexus.collectors.linkedin")

# Global circuit breaker flag in memory during a single execution run
_CIRCUIT_BROKEN = False


def reset_circuit_breaker():
    """Reset circuit breaker state (useful in testing)."""
    global _CIRCUIT_BROKEN
    _CIRCUIT_BROKEN = False


async def collect_linkedin_guest_jobs() -> List[Dict[str, Any]]:
    """Fetch recent India and remote technical jobs from LinkedIn Guest API without auth."""
    global _CIRCUIT_BROKEN
    if _CIRCUIT_BROKEN:
        logger.warning("LinkedIn circuit breaker is OPEN. Skipping LinkedIn guest collector.")
        return []

    results: List[Dict[str, Any]] = []
    base_url = LINKEDIN_GUEST_CONFIG["base_url"]
    time_filter = LINKEDIN_GUEST_CONFIG["time_filter"]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
    }

    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        for q in LINKEDIN_GUEST_CONFIG["queries"]:
            if _CIRCUIT_BROKEN:
                break

            params = {
                "keywords": q["keywords"],
                "location": q["location"],
                "f_TPR": time_filter,
                "start": 0,
            }

            request_url = f"{base_url}?{urlencode(params)}"

            try:
                resp = await client.get(request_url, timeout=REQUEST_TIMEOUT_SECONDS)

                # Circuit breaker check: abort immediately on 429 (Too Many Requests) or 403
                if resp.status_code == 429:
                    logger.warning(
                        "LinkedIn returned HTTP 429 (Rate Limit). Tripping circuit breaker immediately."
                    )
                    _CIRCUIT_BROKEN = True
                    break

                if resp.status_code != 200:
                    logger.warning("LinkedIn guest query returned status %d", resp.status_code)
                    continue

                html_content = resp.text
                soup = BeautifulSoup(html_content, "html.parser")
                cards = soup.select("li, .job-search-card, .base-card")

                for card in cards:
                    title_elem = card.select_one(".base-search-card__title, h3")
                    if not title_elem:
                        continue
                    title = title_elem.get_text(strip=True)
                    if not title or not is_tech_role(title):
                        continue

                    company_elem = card.select_one(
                        ".base-search-card__subtitle, .job-search-card__company-name, h4"
                    )
                    company = company_elem.get_text(strip=True) if company_elem else "MNC / Tech Employer"

                    loc_elem = card.select_one(".job-search-card__location")
                    location = loc_elem.get_text(strip=True) if loc_elem else q["location"]

                    link_elem = card.select_one("a.base-card__full-link, a")
                    apply_url = ""
                    if link_elem and link_elem.get("href"):
                        apply_url = link_elem["href"].split("?")[0]  # Strip tracking query params

                    if not apply_url:
                        continue

                    time_elem = card.select_one("time")
                    published_at = time_elem.get("datetime") if time_elem else None

                    if is_scam(title):
                        continue

                    results.append({
                        "company_name": company,
                        "job_title": title,
                        "location": location,
                        "apply_url": apply_url,
                        "platform": "LinkedIn",
                        "description": "",
                        "published_at": published_at,
                        "raw_salary": None,
                    })

            except httpx.TimeoutException:
                logger.warning("LinkedIn request timed out for query: %s", q)
                # Polite fallback: don't break circuit for single timeout, but move on
            except Exception as exc:
                logger.warning("Error querying LinkedIn guest endpoint: %s", exc)

    return results
