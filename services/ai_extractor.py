"""AI Extraction & Categorization Engine using Gemini Flash and Pydantic."""

import os
import json
import logging
import re
import asyncio
from datetime import datetime, timezone
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("nexus.ai_extractor")


class OpportunityRecord(BaseModel):
    """Structured contract for normalized opportunity records."""
    company_name: str
    job_title: str
    seniority_tier: Literal[
        "Internship",
        "Fresher / 0-2 YOE",
        "Mid-Level (2-5 YOE)",
        "Senior / Staff / Lead (5+ YOE)",
    ]
    technical_domain: Literal[
        "GenAI / LLM / Agentic Systems",
        "Core ML / Deep Learning / Vision / NLP",
        "Backend & Distributed Systems",
        "Full-Stack / Infrastructure / DevOps",
    ]
    min_exp_years: Optional[int] = None
    max_exp_years: Optional[int] = None
    location: str
    workplace_type: Literal["Remote", "Hybrid", "On-site"]
    salary_package: str = Field(
        description="Normalized CTC (e.g. ₹15-25 LPA, $120k-$150k, or 'Not Disclosed')"
    )
    platform: str
    apply_url: str
    posted_date: Optional[str] = Field(
        default=None,
        description="Formatted job posting date (e.g. '24 Sep 2026', '2026-09-24', or 'Recent')"
    )
    core_tech_stack: List[str] = Field(default_factory=list)
    why_it_matters: str = Field(
        description="1-line crisp reason highlighting why this role is high signal"
    )


class OpportunitiesBatch(BaseModel):
    items: List[OpportunityRecord]


def fallback_classify_record(raw: Dict[str, Any]) -> OpportunityRecord:
    """Intelligent rule-based fallback when Gemini API key is absent or unreachable."""
    title = raw.get("job_title", "").strip()
    company = raw.get("company_name", "Tech Startup").strip()
    location = raw.get("location", "Remote").strip()
    platform = raw.get("platform", "Direct ATS")
    apply_url = raw.get("apply_url", "")
    desc = raw.get("description", "").lower()
    t_lower = title.lower()

    # 1. Seniority Tier Detection
    if any(k in t_lower for k in ["intern", "internship", "fellow", "fellowship", "trainee", "student", "apprentice", "apprenticeship", "co-op", "campus"]):
        seniority_tier = "Internship"
        min_exp, max_exp = 0, 0
    elif any(k in t_lower for k in ["staff", "principal", "lead", "architect", "head of", "director", "senior", "sr.", "sr "]):
        seniority_tier = "Senior / Staff / Lead (5+ YOE)"
        min_exp, max_exp = 5, 10
    elif any(k in t_lower for k in ["junior", "jr.", "jr ", "associate", "entry", "graduate", "new grad", "fresher", "sde 1", "sde-1", "sde i", "sde-i", "l3", "get", "trainee engineer", "early career"]):
        seniority_tier = "Fresher / 0-2 YOE"
        min_exp, max_exp = 0, 2
    else:
        # Default mid-level if no specific senior/junior keyword
        seniority_tier = "Mid-Level (2-5 YOE)"
        min_exp, max_exp = 2, 5

    # 2. Technical Domain Detection
    if any(k in t_lower for k in ["genai", "llm", "agent", "prompt", "rag", "langchain", "llama", "gpt"]):
        technical_domain = "GenAI / LLM / Agentic Systems"
    elif any(k in t_lower for k in ["ml", "machine learning", "deep learning", "cv", "computer vision", "nlp", "data scientist", "ai"]):
        technical_domain = "Core ML / Deep Learning / Vision / NLP"
    elif any(k in t_lower for k in ["frontend", "front-end", "fullstack", "full-stack", "react", "next.js", "devops", "sre", "cloud", "infra", "kubernetes"]):
        technical_domain = "Full-Stack / Infrastructure / DevOps"
    else:
        technical_domain = "Backend & Distributed Systems"

    # 3. Workplace Type
    loc_lower = location.lower()
    if "remote" in loc_lower or "anywhere" in loc_lower:
        workplace_type = "Remote"
    elif "hybrid" in loc_lower:
        workplace_type = "Hybrid"
    else:
        workplace_type = "On-site"

    # 4. Salary Package Normalization
    raw_salary = raw.get("raw_salary")
    if raw_salary:
        salary_package = raw_salary
    else:
        salary_package = "Not Disclosed"

    # 5. Core Tech Stack Extraction from Title & Desc
    known_techs = [
        "Python", "FastAPI", "Go", "Golang", "Rust", "Java", "TypeScript",
        "React", "Next.js", "Docker", "Kubernetes", "Kafka", "PostgreSQL",
        "Redis", "PyTorch", "TensorFlow", "AWS", "GCP", "LLMs", "RAG"
    ]
    detected_tech = []
    combined_text = f"{title} {desc}"
    for tech in known_techs:
        if re.search(rf"\b{re.escape(tech)}\b", combined_text, re.IGNORECASE):
            detected_tech.append(tech)
    if not detected_tech:
        detected_tech = ["Python", "Cloud Architecture"]

    # 6. Why it matters crisp summary
    why = f"High-impact {technical_domain.split('/')[0].strip()} role at {company} ({workplace_type})."

    # 7. Formatted Posted Date
    raw_pub = raw.get("published_at")
    posted_date = "Recent"
    if raw_pub:
        try:
            clean_ts = str(raw_pub).replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_ts)
            posted_date = dt.strftime("%d %b %Y")
        except Exception:
            posted_date = str(raw_pub)[:10]

    return OpportunityRecord(
        company_name=company,
        job_title=title,
        seniority_tier=seniority_tier,
        technical_domain=technical_domain,
        min_exp_years=min_exp,
        max_exp_years=max_exp,
        location=location or "Remote",
        workplace_type=workplace_type,
        salary_package=salary_package,
        platform=platform,
        apply_url=apply_url,
        posted_date=posted_date,
        core_tech_stack=detected_tech[:5],
        why_it_matters=why,
    )


async def enrich_opportunities_with_gemini(
    raw_jobs: List[Dict[str, Any]],
    api_key: Optional[str] = None,
    batch_size: int = 50,
    model_name: Optional[str] = None,
) -> List[OpportunityRecord]:
    """Normalize and enrich raw job listings using Gemini Flash with rate-limit pacing."""
    if not raw_jobs:
        return []

    gemini_key = api_key or os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        logger.info("GEMINI_API_KEY not set. Using intelligent rule-based classifier.")
        return [fallback_classify_record(job) for job in raw_jobs]

    chosen_model = model_name or os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=gemini_key)
    except Exception as exc:
        logger.warning("Failed initializing google-genai client: %s. Using fallback.", exc)
        return [fallback_classify_record(job) for job in raw_jobs]

    enriched_records: List[OpportunityRecord] = []
    quota_exhausted = False

    # Process in larger batches to minimize total API requests
    total_batches = (len(raw_jobs) + batch_size - 1) // batch_size
    logger.info("Processing %d opportunities in %d batches (batch_size=%d)...", len(raw_jobs), total_batches, batch_size)

    for i in range(0, len(raw_jobs), batch_size):
        chunk = raw_jobs[i : i + batch_size]
        batch_idx = (i // batch_size) + 1

        # If quota was previously exhausted, bypass remaining LLM calls directly to fallback
        if quota_exhausted:
            logger.info("Batch %d/%d: Quota exhausted, using local rule-based classifier.", batch_idx, total_batches)
            enriched_records.extend([fallback_classify_record(j) for j in chunk])
            continue

        prompt = f"""You are an elite Senior Staff Tech Recruiter and AI Systems Engineer.
Normalize and classify the following {len(chunk)} tech job opportunities into structured JSON.

COMMUNITY AUDIENCE & TIER BALANCE:
Our community serves professionals across all career stages — from college interns and freshers to mid-level and senior/staff leads. Ensure accurate, unbiased categorization across all 4 tiers:
- 🎓 'Internship': Interns, campus fellows, students, apprentices, or co-op roles (0 YOE).
- 🚀 'Fresher / 0-2 YOE': 0-2 YOE, SDE-1, Graduate Engineer Trainee (GET), New Grad, Associate, or Junior engineering roles.
- ⚡ 'Mid-Level (2-5 YOE)': 2-5 YOE, SDE-2, Systems Engineers, independent ICs.
- 🏆 'Senior / Staff / Lead (5+ YOE)': 5+ YOE, Senior (SDE-3), Staff, Principal, Lead, Architect.

For each opportunity:
1. 'seniority_tier': Exactly one of ["Internship", "Fresher / 0-2 YOE", "Mid-Level (2-5 YOE)", "Senior / Staff / Lead (5+ YOE)"].
   - Internships: interns, campus fellows, students, apprentices, 0 YOE.
   - Fresher / 0-2 YOE: SDE-1, Junior, Associate, Graduate Engineer Trainee (GET), New Grad, 0-2 YOE.
   - Mid-Level (2-5 YOE): SDE-2, Systems Engineers, independent IC ownership, 2-5 YOE.
   - Senior / Staff / Lead (5+ YOE): Senior (SDE-3), Staff, Principal, Lead, Architect, 5+ YOE.
2. 'technical_domain': Exactly one of ["GenAI / LLM / Agentic Systems", "Core ML / Deep Learning / Vision / NLP", "Backend & Distributed Systems", "Full-Stack / Infrastructure / DevOps"].
3. 'min_exp_years' and 'max_exp_years': integers or null.
4. 'workplace_type': Exactly one of ["Remote", "Hybrid", "On-site"].
5. 'salary_package': Normalized CTC string (e.g. ₹15-25 LPA, $120k-$150k, or 'Not Disclosed').
6. 'core_tech_stack': Array of 2 to 5 primary technologies.
7. 'why_it_matters': Exactly 1 crisp, high-signal line on why this role is attractive to candidates.
8. 'posted_date': Formatted date when the role was posted (e.g. '24 Sep 2026' or 'Recent') derived from 'published_at'.
9. Maintain the original 'company_name', 'job_title', 'location', 'platform', and 'apply_url'.

Raw job data to process:
{json.dumps(chunk, indent=2)}
"""

        success = False
        batch_error_logs: List[str] = []
        max_retries = 3

        # Modern Gemini 3 production models (Lite prioritized for highest speed and quota efficiency)
        model_hierarchy = ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.8-flash"]
        candidate_models = [chosen_model]
        for m in model_hierarchy:
            if m not in candidate_models:
                candidate_models.append(m)

        t_batch_start = datetime.now(timezone.utc)

        for attempt in range(1, max_retries + 1):
            model_idx = min(attempt - 1, len(candidate_models) - 1)
            current_model = candidate_models[model_idx]
            try:
                logger.info(
                    "  [AI Batch %d/%d] Attempt %d/%d ➔ Calling %s (%d roles)...",
                    batch_idx, total_batches, attempt, max_retries, current_model, len(chunk)
                )
                response = client.models.generate_content(
                    model=current_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=OpportunitiesBatch,
                        temperature=0.1,
                    ),
                )

                if response.text:
                    batch_data = OpportunitiesBatch.model_validate_json(response.text)
                    enriched_records.extend(batch_data.items)
                    success = True
                    batch_elapsed = (datetime.now(timezone.utc) - t_batch_start).total_seconds()
                    logger.info(
                        "  ✓ [AI Batch %d/%d] SUCCESS in %.2fs — Classified %d opportunities. Pacing delay: 3.0s...",
                        batch_idx, total_batches, batch_elapsed, len(batch_data.items)
                    )
                    await asyncio.sleep(3.0)
                    break
                else:
                    raise ValueError("Empty response text from Gemini")

            except Exception as exc:
                err_msg = str(exc)
                logger.warning(
                    "  ✗ [AI Batch %d/%d] Attempt %d/%d failed on %s: %s",
                    batch_idx, total_batches, attempt, max_retries, current_model, err_msg
                )
                batch_error_logs.append(f"Attempt {attempt}/{max_retries} ({current_model}): {err_msg}")

                if "RESOURCE_EXHAUSTED" in err_msg:
                    # Exponential backoff or rapid model cascade
                    backoff_delay = 2.0
                else:
                    backoff_delay = float(2 ** attempt)

                if attempt < max_retries:
                    logger.info("  🔄 [AI Batch %d/%d] Cascading to next model in %.1fs...", batch_idx, total_batches, backoff_delay)
                    await asyncio.sleep(backoff_delay)
                else:
                    logger.warning(
                        "  ✗ [AI Batch %d/%d] Gemini quota reached. Activating intelligent rule-based classifier.",
                        batch_idx, total_batches
                    )
                    if any("RESOURCE_EXHAUSTED" in log for log in batch_error_logs):
                        quota_exhausted = True
                        logger.info("  ⚡ Quota exhausted across models; remaining batches will use instant rule-based classifier.")

        if not success:
            # Fallback to local heuristic classifier so pipeline completes smoothly without delay
            enriched_records.extend([fallback_classify_record(j) for j in chunk])

    return enriched_records
