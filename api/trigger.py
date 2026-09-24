"""Vercel Serverless Function entrypoint: Triggers daily opportunity ingestion, synthesis, and dispatch."""

import os
import sys
import json
import asyncio
import logging
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from typing import Dict, Any, List

# Ensure project root is in sys.path for Vercel's Python runtime
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv()

from services.collectors import compute_dedup_hash, is_scam
from services.collectors.ats_boards import collect_all_ats_jobs
from services.collectors.yc_algolia import fetch_yc_jobs
from services.collectors.remote_feeds import collect_remote_feeds
from services.collectors.linkedin_guest import collect_linkedin_guest_jobs
from services.collectors.liveness_verifier import filter_active_opportunities
from services.ai_extractor import enrich_opportunities_with_gemini, OpportunityRecord
from services.excel_builder import build_excel_workbook
from services.telegram_notifier import dispatch_telegram_document

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("nexus.trigger")


async def run_pipeline() -> Dict[str, Any]:
    """Execute complete ingestion, AI enrichment, Excel generation, and Telegram broadcast pipeline."""
    start_time = datetime.now(timezone.utc)
    logger.info("Starting NexusCareers Opportunity Pipeline...")

    # Step 1: Asynchronous parallel collection across all sources
    ats_task = asyncio.create_task(collect_all_ats_jobs())
    yc_task = asyncio.create_task(fetch_yc_jobs())
    remote_task = asyncio.create_task(collect_remote_feeds())
    linkedin_task = asyncio.create_task(collect_linkedin_guest_jobs())

    collector_results = await asyncio.gather(
        ats_task, yc_task, remote_task, linkedin_task, return_exceptions=True
    )

    all_raw_jobs: List[Dict[str, Any]] = []
    source_names = ["ATS", "YC", "RemoteFeeds", "LinkedIn"]
    for idx, res in enumerate(collector_results):
        src = source_names[idx]
        if isinstance(res, list):
            logger.info("Collected %d raw opportunities from %s", len(res), src)
            all_raw_jobs.extend(res)
        elif isinstance(res, Exception):
            logger.error("Collector %s failed with exception: %s", src, res)

    # Step 2: Pre-Filter & Deduplication Engine
    dedup_seen = set()
    filtered_jobs: List[Dict[str, Any]] = []

    for raw in all_raw_jobs:
        company = raw.get("company_name", "").strip()
        title = raw.get("job_title", "").strip()
        desc = raw.get("description", "")

        if not company or not title:
            continue

        if is_scam(title, desc):
            continue

        key = compute_dedup_hash(company, title)
        if key in dedup_seen:
            continue
        dedup_seen.add(key)
        filtered_jobs.append(raw)

    logger.info(
        "Deduplication complete: %d raw reduced to %d unique roles",
        len(all_raw_jobs),
        len(filtered_jobs),
    )

    # Step 3: Active Status & Expiration Verification
    active_jobs: List[Dict[str, Any]] = await filter_active_opportunities(filtered_jobs)
    logger.info("Retained %d live opportunities after expiration checks", len(active_jobs))

    # Step 4: AI Extraction & Tiering Engine
    enriched_records: List[OpportunityRecord] = await enrich_opportunities_with_gemini(active_jobs)
    logger.info("Enriched %d opportunities with AI tiering", len(enriched_records))

    # Tally seniority tiers
    tier_counts = {
        "Internship": 0,
        "Fresher / 0-2 YOE": 0,
        "Mid-Level (2-5 YOE)": 0,
        "Senior / Staff / Lead (5+ YOE)": 0,
    }
    for opp in enriched_records:
        if opp.seniority_tier in tier_counts:
            tier_counts[opp.seniority_tier] += 1
        else:
            tier_counts["Mid-Level (2-5 YOE)"] += 1

    # Step 4: Excel Workbook Generation (in-memory)
    excel_buffer = build_excel_workbook(enriched_records)
    logger.info("Generated in-memory Excel workbook (%d bytes)", excel_buffer.getbuffer().nbytes)

    # Step 5: Telegram Dispatch Layer
    dispatched = await dispatch_telegram_document(excel_buffer, enriched_records)

    local_file_path = None
    if dispatched:
        logger.info("Successfully dispatched to Telegram! Cleaning up any local .xlsx files...")
        # User requirement: Clear local Excel files after successfully broadcasting to Telegram
        for fname in os.listdir(PROJECT_ROOT):
            if fname.endswith(".xlsx") and "Opportunities" in fname:
                try:
                    fpath = os.path.join(PROJECT_ROOT, fname)
                    os.remove(fpath)
                    logger.info("Cleaned up local file after Telegram dispatch: %s", fname)
                except Exception as exc:
                    logger.debug("Could not remove %s: %s", fname, exc)
    else:
        # Fallback: Save locally only if Telegram dispatch is unconfigured or failed
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        local_filename = f"TechyUpdates_Opportunities_{date_str}.xlsx"
        local_file_path = os.path.join(PROJECT_ROOT, local_filename)
        try:
            excel_buffer.seek(0)
            with open(local_file_path, "wb") as f:
                f.write(excel_buffer.getvalue())
            logger.info("Saved local Excel spreadsheet: %s (Telegram not dispatched)", local_file_path)
        except Exception as exc:
            logger.warning("Could not write local Excel file: %s", exc)
            local_file_path = None

    elapsed_seconds = (datetime.now(timezone.utc) - start_time).total_seconds()

    result_payload = {
        "status": "success",
        "timestamp": start_time.isoformat(),
        "elapsed_seconds": round(elapsed_seconds, 2),
        "total_raw": len(all_raw_jobs),
        "total_deduped": len(filtered_jobs),
        "total_active_live": len(active_jobs),
        "seniority_distribution": tier_counts,
        "telegram_dispatched": dispatched,
    }
    if local_file_path:
        result_payload["local_file_saved"] = local_file_path

    return result_payload


def authenticate_request(headers: Dict[str, str]) -> bool:
    """Verify Bearer token against CRON_SECRET environment variable."""
    expected_secret = os.getenv("CRON_SECRET")
    if not expected_secret:
        # In development/local mode when no secret is configured, allow execution
        logger.warning("CRON_SECRET environment variable not set. Permitting request in dev mode.")
        return True

    auth_header = headers.get("Authorization") or headers.get("authorization")
    if not auth_header:
        return False

    parts = auth_header.split(" ")
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1] == expected_secret

    return False


class handler(BaseHTTPRequestHandler):
    """Vercel Python Serverless HTTP Request Handler."""

    def _send_response_json(self, status_code: int, data: Dict[str, Any]):
        response_bytes = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response_bytes)))
        self.end_headers()
        self.wfile.write(response_bytes)

    def do_GET(self):
        """Handle Vercel Cron GET invocation or health check."""
        # Convert headers to dict
        headers_dict = {k: v for k, v in self.headers.items()}

        if not authenticate_request(headers_dict):
            self._send_response_json(401, {"error": "Unauthorized: Invalid or missing Bearer token"})
            return

        try:
            result = asyncio.run(run_pipeline())
            self._send_response_json(200, result)
        except Exception as exc:
            logger.exception("Pipeline failed: %s", exc)
            self._send_response_json(500, {"error": "Pipeline execution failed", "details": str(exc)})

    def do_POST(self):
        """Handle manual webhook POST trigger."""
        headers_dict = {k: v for k, v in self.headers.items()}

        if not authenticate_request(headers_dict):
            self._send_response_json(401, {"error": "Unauthorized: Invalid or missing Bearer token"})
            return

        try:
            result = asyncio.run(run_pipeline())
            self._send_response_json(200, result)
        except Exception as exc:
            logger.exception("Pipeline failed: %s", exc)
            self._send_response_json(500, {"error": "Pipeline execution failed", "details": str(exc)})


if __name__ == "__main__":
    # Allows local CLI run: python api/trigger.py
    logger.info("Executing pipeline directly via CLI...")
    result = asyncio.run(run_pipeline())
    print("\n--- Pipeline Result ---")
    print(json.dumps(result, indent=2))
