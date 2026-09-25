"""Vercel Serverless Function entrypoint: Triggers daily opportunity ingestion, synthesis, and dispatch."""

import os
import sys
import json
import asyncio
import logging
from urllib.parse import urlparse
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
    logger.info("=" * 80)
    logger.info("🚀 [PIPELINE START] Autonomous Tech Opportunity Aggregator")
    logger.info("Timestamp: %s UTC", start_time.isoformat())
    logger.info("=" * 80)

    # -------------------------------------------------------------------------
    # PHASE 1: Asynchronous Parallel Ingestion
    # -------------------------------------------------------------------------
    t_phase1 = datetime.now(timezone.utc)
    logger.info("[PHASE 1/5: INGESTION] Initiating concurrent collection across 4 sources...")

    ats_task = asyncio.create_task(collect_all_ats_jobs())
    yc_task = asyncio.create_task(fetch_yc_jobs())
    remote_task = asyncio.create_task(collect_remote_feeds())
    linkedin_task = asyncio.create_task(collect_linkedin_guest_jobs())

    collector_results = await asyncio.gather(
        ats_task, yc_task, remote_task, linkedin_task, return_exceptions=True
    )

    all_raw_jobs: List[Dict[str, Any]] = []
    source_names = ["ATS Boards (Greenhouse/Ashby/Lever)", "YC Startups (Algolia/HN)", "Remote Feeds (RemoteOK/Jobicy)", "LinkedIn Guest Search"]
    for idx, res in enumerate(collector_results):
        src = source_names[idx]
        if isinstance(res, list):
            logger.info("  ✓ %s: %d opportunities collected", src, len(res))
            all_raw_jobs.extend(res)
        elif isinstance(res, Exception):
            logger.error("  ✗ %s FAILED with error: %s", src, res, exc_info=True)

    elapsed_p1 = (datetime.now(timezone.utc) - t_phase1).total_seconds()
    logger.info("[PHASE 1/5: INGESTION] Complete in %.2fs. Total raw opportunities: %d", elapsed_p1, len(all_raw_jobs))
    logger.info("-" * 80)

    # -------------------------------------------------------------------------
    # PHASE 2: Pre-Filter & Content Deduplication
    # -------------------------------------------------------------------------
    t_phase2 = datetime.now(timezone.utc)
    logger.info("[PHASE 2/5: DEDUP & FILTER] Filtering scams and normalizing hashes...")

    dedup_seen = set()
    filtered_jobs: List[Dict[str, Any]] = []
    scam_count = 0
    missing_fields_count = 0

    for raw in all_raw_jobs:
        company = raw.get("company_name", "").strip()
        title = raw.get("job_title", "").strip()
        desc = raw.get("description", "")

        if not company or not title:
            missing_fields_count += 1
            continue

        if is_scam(title, desc):
            scam_count += 1
            continue

        key = compute_dedup_hash(company, title)
        if key in dedup_seen:
            continue
        dedup_seen.add(key)
        filtered_jobs.append(raw)

    elapsed_p2 = (datetime.now(timezone.utc) - t_phase2).total_seconds()
    dup_count = len(all_raw_jobs) - len(filtered_jobs) - scam_count - missing_fields_count
    logger.info("  ✓ Scam / exploitative listings purged: %d", scam_count)
    logger.info("  ✓ Duplicates purged: %d", dup_count)
    logger.info("  ✓ Retained unique roles: %d (from %d raw)", len(filtered_jobs), len(all_raw_jobs))
    logger.info("[PHASE 2/5: DEDUP & FILTER] Complete in %.2fs", elapsed_p2)
    logger.info("-" * 80)

    # -------------------------------------------------------------------------
    # PHASE 3: Link Liveness & Closure Verification
    # -------------------------------------------------------------------------
    t_phase3 = datetime.now(timezone.utc)
    logger.info("[PHASE 3/5: LIVENESS] Concurrently verifying real-time URL status for %d roles...", len(filtered_jobs))

    active_jobs: List[Dict[str, Any]] = await filter_active_opportunities(filtered_jobs)
    elapsed_p3 = (datetime.now(timezone.utc) - t_phase3).total_seconds()
    closed_count = len(filtered_jobs) - len(active_jobs)
    logger.info("  ✓ Active verified live: %d", len(active_jobs))
    logger.info("  ✗ Expired / closed purged: %d", closed_count)
    logger.info("[PHASE 3/5: LIVENESS] Complete in %.2fs", elapsed_p3)
    logger.info("-" * 80)

    # -------------------------------------------------------------------------
    # PHASE 4: AI Extraction & Seniority Tiering
    # -------------------------------------------------------------------------
    t_phase4 = datetime.now(timezone.utc)
    logger.info("[PHASE 4/5: AI TIERING] Processing %d opportunities through Gemini 3 Flash cascade...", len(active_jobs))

    enriched_records: List[OpportunityRecord] = await enrich_opportunities_with_gemini(active_jobs)
    elapsed_p4 = (datetime.now(timezone.utc) - t_phase4).total_seconds()

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

    logger.info("  📊 Seniority Tier Distribution:")
    logger.info("     • 🎓 Internships:           %d", tier_counts["Internship"])
    logger.info("     • 🚀 Freshers (0-2 YOE):    %d", tier_counts["Fresher / 0-2 YOE"])
    logger.info("     • ⚡ Mid-Level (2-5 YOE):   %d", tier_counts["Mid-Level (2-5 YOE)"])
    logger.info("     • 🏆 Senior/Staff (5+ YOE): %d", tier_counts["Senior / Staff / Lead (5+ YOE)"])
    logger.info("[PHASE 4/5: AI TIERING] Complete in %.2fs. Total enriched: %d", elapsed_p4, len(enriched_records))
    logger.info("-" * 80)

    # -------------------------------------------------------------------------
    # PHASE 5: In-Memory Excel Build & Telegram Dispatch
    # -------------------------------------------------------------------------
    t_phase5 = datetime.now(timezone.utc)
    logger.info("[PHASE 5/5: WORKBOOK & DISPATCH] Building 4-tab styled spreadsheet in-memory...")

    excel_buffer = build_excel_workbook(enriched_records)
    buffer_size = excel_buffer.getbuffer().nbytes
    logger.info("  ✓ Generated Excel spreadsheet (%d bytes / %.2f KB)", buffer_size, buffer_size / 1024)

    logger.info("  🚀 Dispatching to Telegram community channel...")
    dispatched = await dispatch_telegram_document(excel_buffer, enriched_records)

    local_file_path = None
    if dispatched:
        logger.info("  ✓ Telegram broadcast confirmed successful! Cleaning local temp files...")
        for fname in os.listdir(PROJECT_ROOT):
            if fname.endswith(".xlsx") and "Opportunities" in fname:
                try:
                    fpath = os.path.join(PROJECT_ROOT, fname)
                    os.remove(fpath)
                    logger.info("    - Removed local temp file: %s", fname)
                except Exception as exc:
                    logger.debug("    - Could not remove %s: %s", fname, exc)
    else:
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        local_filename = f"TechyUpdates_Opportunities_{date_str}.xlsx"
        local_file_path = os.path.join(PROJECT_ROOT, local_filename)
        try:
            excel_buffer.seek(0)
            with open(local_file_path, "wb") as f:
                f.write(excel_buffer.getvalue())
            logger.info("  ℹ️ Local Excel backup saved: %s", local_file_path)
        except Exception as exc:
            logger.error("  ✗ Could not write local Excel backup: %s", exc, exc_info=True)
            local_file_path = None

    elapsed_p5 = (datetime.now(timezone.utc) - t_phase5).total_seconds()
    total_elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()

    logger.info("[PHASE 5/5: WORKBOOK & DISPATCH] Complete in %.2fs", elapsed_p5)
    logger.info("=" * 80)
    logger.info("✅ [PIPELINE FINISHED] Execution completed in %.2fs (%.1f mins)", total_elapsed, total_elapsed / 60)
    logger.info("Summary: %d raw ➔ %d deduped ➔ %d live active ➔ %d enriched ➔ Telegram: %s",
                len(all_raw_jobs), len(filtered_jobs), len(active_jobs), len(enriched_records), dispatched)
    logger.info("=" * 80)

    result_payload = {
        "status": "success",
        "timestamp": start_time.isoformat(),
        "elapsed_seconds": round(total_elapsed, 2),
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
        parsed_path = urlparse(self.path).path.rstrip("/")
        if parsed_path in ("/api/health", "/health", ""):
            self._send_response_json(200, {
                "status": "healthy",
                "service": "techyupdates-careers-engine",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return

        # For pipeline triggers (/api/trigger, etc.), verify authentication
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
