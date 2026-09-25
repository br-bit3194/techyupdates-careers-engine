"""Collectors package for NexusCareers: Aggregates opportunities from multiple ATSs, feeds, and guest APIs."""

import hashlib
import re
from typing import Dict, Any
from config.targets import TECHNICAL_ROLE_KEYWORDS, SCAM_BLACKLIST_KEYWORDS


def normalize_string(val: str) -> str:
    """Normalize a string by lowercasing, stripping, and reducing whitespace."""
    if not val:
        return ""
    val = val.lower().strip()
    return re.sub(r"\s+", " ", val)


def compute_dedup_hash(company_name: str, job_title: str) -> str:
    """Compute MD5 hash key: MD5(normalize(company_name) + "_" + normalize(job_title))."""
    norm_company = normalize_string(company_name)
    norm_title = normalize_string(job_title)
    signature = f"{norm_company}_{norm_title}"
    return hashlib.md5(signature.encode("utf-8")).hexdigest()


def is_tech_role(job_title: str) -> bool:
    """Check if the title matches target technical engineering/AI roles."""
    title_lower = job_title.lower()
    return any(keyword in title_lower for keyword in TECHNICAL_ROLE_KEYWORDS)


def is_scam(title: str, description: str = "") -> bool:
    """Check if title or description triggers anti-scam heuristics."""
    content = f"{title} {description}".lower()
    return any(scam_phrase in content for scam_phrase in SCAM_BLACKLIST_KEYWORDS)


from services.collectors.enterprise_early_careers import collect_enterprise_early_careers

