"""Persistent Cross-Run Deduplication & History Tracker for Tech Opportunities.

Tracks previously broadcasted opportunities in `data/sent_history.json` to prevent
spamming identical job alerts across daily cron executions. Features dual-key matching
(canonical URL and normalized company/title) and automatic 30-day TTL cleanup.
"""

import os
import re
import json
import logging
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
from typing import Dict, Any, List, Optional, Union

logger = logging.getLogger("nexus.history")

# Default history storage location relative to project root
DEFAULT_HISTORY_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "sent_history.json",
)

# Common tracking / referrer query parameters to strip
TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "ref",
    "source",
    "gh_src",
    "lever-source",
    "ashby_jid",
    "trackingId",
    "refId",
    "position",
    "pageNum",
    "trk",
    "fbclid",
    "gclid",
    "subId",
    "session",
    "sid",
}

# Corporate legal suffixes to strip for fuzzy company matching
COMPANY_SUFFIX_REGEX = re.compile(
    r"\b(inc\.?|llc\.?|ltd\.?|limited\.?|corp\.?|corporation\.?|technologies|software|solutions|services|group|holdings|pvt\.?|private)\b",
    re.IGNORECASE,
)


def normalize_job_url(url: str) -> str:
    """Normalize a URL to its canonical form by stripping tracking query params and trailing slashes."""
    if not url:
        return ""
    try:
        parsed = urlparse(url.strip())
        scheme = parsed.scheme.lower() or "https"
        netloc = parsed.netloc.lower()

        # Filter out tracking query parameters
        clean_query_pairs = []
        if parsed.query:
            for k, v in parse_qsl(parsed.query, keep_blank_values=False):
                if k.lower() not in TRACKING_PARAMS and not k.lower().startswith("utm_"):
                    clean_query_pairs.append((k, v))
        clean_query = urlencode(sorted(clean_query_pairs))

        # Normalize path by removing duplicate or trailing slashes (except root '/')
        path = parsed.path.rstrip("/")
        if not path:
            path = "/"

        canonical = urlunparse((scheme, netloc, path, "", clean_query, ""))
        return canonical
    except Exception:
        return url.strip().rstrip("/")


def normalize_job_key(company: str, title: str) -> str:
    """Normalize company name and job title into a standard key for dual-key matching."""
    comp = company or ""
    tit = title or ""

    # Strip corporate suffixes from company name
    comp_clean = COMPANY_SUFFIX_REGEX.sub("", comp)
    comp_clean = re.sub(r"[^\w\s]", "", comp_clean).lower()
    comp_clean = re.sub(r"\s+", " ", comp_clean).strip()

    # Clean job title
    tit_clean = re.sub(r"[^\w\s]", " ", tit).lower()
    tit_clean = re.sub(r"\s+", " ", tit_clean).strip()

    return f"{comp_clean}:::{tit_clean}"


class HistoryTracker:
    """Persistent history tracking store to ensure cross-run uniqueness."""

    def __init__(self, filepath: Optional[str] = None):
        self.filepath = filepath or DEFAULT_HISTORY_FILE
        self.sent_urls: Dict[str, Dict[str, Any]] = {}
        self.sent_keys: Dict[str, Dict[str, Any]] = {}
        self.last_updated: Optional[str] = None
        self._load()

    def _load(self) -> None:
        """Load history data from JSON store if present."""
        if not os.path.exists(self.filepath):
            logger.info("No prior history file found at %s. Starting fresh tracker.", self.filepath)
            return

        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.last_updated = data.get("last_updated")
            self.sent_urls = data.get("sent_urls", {})
            self.sent_keys = data.get("sent_keys", {})
            logger.info(
                "Loaded history tracker: %d canonical URLs, %d title keys (last updated: %s)",
                len(self.sent_urls),
                len(self.sent_keys),
                self.last_updated or "N/A",
            )
        except Exception as exc:
            logger.warning("Could not read history store (%s): %s. Re-initializing empty.", self.filepath, exc)
            self.sent_urls = {}
            self.sent_keys = {}

    def is_duplicate(self, company: str, title: str, apply_url: str) -> bool:
        """Check if an opportunity was already sent in recent history by URL or Title+Company."""
        # 1. Check canonical apply URL
        canon_url = normalize_job_url(apply_url)
        if canon_url and canon_url in self.sent_urls:
            return True

        # 2. Check normalized company and title key
        key = normalize_job_key(company, title)
        if key and key in self.sent_keys:
            return True

        return False

    def record_dispatched(self, opportunities: List[Union[Dict[str, Any], Any]]) -> int:
        """Record dispatched opportunities into the history database."""
        now_iso = datetime.now(timezone.utc).isoformat()
        added = 0

        for opp in opportunities:
            # Support both dicts and Pydantic OpportunityRecord models
            if isinstance(opp, dict):
                company = opp.get("company_name", "").strip()
                title = opp.get("job_title", "").strip()
                url = opp.get("apply_url", "").strip()
            else:
                company = getattr(opp, "company_name", "").strip()
                title = getattr(opp, "job_title", "").strip()
                url = getattr(opp, "apply_url", "").strip()

            if not company or not title:
                continue

            canon_url = normalize_job_url(url)
            key = normalize_job_key(company, title)

            entry_payload = {
                "company": company,
                "title": title,
                "url": url,
                "last_sent": now_iso,
            }

            if canon_url:
                if canon_url not in self.sent_urls:
                    entry_payload["first_seen"] = now_iso
                    added += 1
                self.sent_urls[canon_url] = entry_payload

            if key:
                self.sent_keys[key] = entry_payload

        self.last_updated = now_iso
        logger.info("Recorded %d new opportunities into history (Total URLs: %d, Keys: %d)",
                    added, len(self.sent_urls), len(self.sent_keys))
        return added

    def cleanup_expired(self, retention_days: int = 30) -> int:
        """Purge entries older than the retention threshold to prevent file bloat."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=retention_days)
        purged = 0

        # Purge URLs
        urls_to_remove = []
        for url, meta in self.sent_urls.items():
            sent_str = meta.get("last_sent") or meta.get("first_seen")
            if sent_str:
                try:
                    sent_dt = datetime.fromisoformat(sent_str.replace("Z", "+00:00"))
                    if sent_dt < cutoff:
                        urls_to_remove.append(url)
                except Exception:
                    pass

        for url in urls_to_remove:
            del self.sent_urls[url]
            purged += 1

        # Purge Keys
        keys_to_remove = []
        for key, meta in self.sent_keys.items():
            sent_str = meta.get("last_sent") or meta.get("first_seen")
            if sent_str:
                try:
                    sent_dt = datetime.fromisoformat(sent_str.replace("Z", "+00:00"))
                    if sent_dt < cutoff:
                        keys_to_remove.append(key)
                except Exception:
                    pass

        for key in keys_to_remove:
            del self.sent_keys[key]

        if purged > 0:
            logger.info("History cleanup: Purged %d entries older than %d days.", purged, retention_days)
        return purged

    def save(self) -> None:
        """Serialize history store to JSON file."""
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        payload = {
            "version": 1,
            "last_updated": self.last_updated or datetime.now(timezone.utc).isoformat(),
            "total_sent_urls": len(self.sent_urls),
            "total_sent_keys": len(self.sent_keys),
            "sent_urls": self.sent_urls,
            "sent_keys": self.sent_keys,
        }
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            logger.info("Persisted history tracker to %s (%d URLs, %d keys)", self.filepath, len(self.sent_urls), len(self.sent_keys))
        except Exception as exc:
            logger.error("Failed saving history file %s: %s", self.filepath, exc, exc_info=True)
