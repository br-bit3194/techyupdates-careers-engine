"""Telegram community dispatcher for broadcasting synthesized Excel workbooks with markdown summaries."""

import os
import io
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import httpx

from services.ai_extractor import OpportunityRecord

logger = logging.getLogger("nexus.telegram")


def generate_executive_caption(opportunities: List[OpportunityRecord]) -> str:
    """Generate executive summary and top 4 highlights across seniority tiers."""
    now_str = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")

    by_tier: Dict[str, List[OpportunityRecord]] = {
        "Internship": [],
        "Fresher / 0-2 YOE": [],
        "Mid-Level (2-5 YOE)": [],
        "Senior / Staff / Lead (5+ YOE)": [],
    }

    for opp in opportunities:
        if opp.seniority_tier in by_tier:
            by_tier[opp.seniority_tier].append(opp)
        else:
            by_tier["Mid-Level (2-5 YOE)"].append(opp)

    c_intern = len(by_tier["Internship"])
    c_fresher = len(by_tier["Fresher / 0-2 YOE"])
    c_mid = len(by_tier["Mid-Level (2-5 YOE)"])
    c_senior = len(by_tier["Senior / Staff / Lead (5+ YOE)"])
    total = len(opportunities)

    # Pick 1 top highlight per tier if available
    highlights = []

    if by_tier["Internship"]:
        top = by_tier["Internship"][0]
        highlights.append(f"• 🎓 *{top.company_name}* — {top.job_title} ({top.location})")

    if by_tier["Fresher / 0-2 YOE"]:
        top = by_tier["Fresher / 0-2 YOE"][0]
        sal = f" | {top.salary_package}" if top.salary_package != "Not Disclosed" else ""
        highlights.append(f"• 🚀 *{top.company_name}* — {top.job_title} ({top.location}{sal})")

    if by_tier["Mid-Level (2-5 YOE)"]:
        top = by_tier["Mid-Level (2-5 YOE)"][0]
        tech = ", ".join(top.core_tech_stack[:3])
        highlights.append(f"• ⚡ *{top.company_name}* — {top.job_title} ({tech})")

    if by_tier["Senior / Staff / Lead (5+ YOE)"]:
        top = by_tier["Senior / Staff / Lead (5+ YOE)"][0]
        highlights.append(f"• 🏆 *{top.company_name}* — {top.job_title} ({top.technical_domain})")

    highlights_str = "\n".join(highlights) if highlights else "• Fresh opportunities compiled in workbook."

    caption = (
        f"⚡ *TechyUpdates Daily Opportunity Synthesizer*\n"
        f"📅 *Timestamp:* `{now_str}`\n"
        f"🎯 *Active Roles Ingested:* *{total}*\n\n"
        f"📊 *Seniority Breakdown:*\n"
        f"  🎓 *Internships:* {c_intern}\n"
        f"  🚀 *Freshers (0–2 YOE):* {c_fresher}\n"
        f"  ⚡ *Mid-Level (2–5 YOE):* {c_mid}\n"
        f"  🏆 *Senior & Staff (5+ YOE):* {c_senior}\n\n"
        f"🔥 *Top Tier Highlights:*\n"
        f"{highlights_str}\n\n"
        f"📁 *Attached:* 4-tab structured workbook with verified direct application links."
    )
    return caption


async def dispatch_telegram_document(
    excel_buffer: io.BytesIO,
    opportunities: List[OpportunityRecord],
    bot_token: Optional[str] = None,
    channel_id: Optional[str] = None,
    filename: Optional[str] = None,
) -> bool:
    """Send generated .xlsx workbook to Telegram community channel."""
    token = (bot_token or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (channel_id or os.getenv("TELEGRAM_COMMUNITY_CHANNEL_ID") or "").strip()

    # Treat empty or template placeholders as unconfigured
    is_placeholder = (
        not token
        or not chat_id
        or "your_" in token.lower()
        or token.startswith("1234567890:")
        or chat_id == "-1001234567890"
    )

    if is_placeholder:
        logger.warning(
            "Telegram credentials not configured or set to placeholder. Skipping Telegram broadcast."
        )
        return False

    date_tag = datetime.now(timezone.utc).strftime("%Y%m%d")
    out_filename = filename or f"TechyUpdates_Opportunities_{date_tag}.xlsx"
    caption = generate_executive_caption(opportunities)

    api_url = f"https://api.telegram.org/bot{token}/sendDocument"

    # Rewind buffer
    excel_buffer.seek(0)
    file_bytes = excel_buffer.getvalue()

    files = {
        "document": (
            out_filename,
            file_bytes,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    data = {
        "chat_id": chat_id,
        "caption": caption,
        "parse_mode": "Markdown",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(api_url, data=data, files=files)
            if resp.status_code == 200:
                logger.info("Successfully dispatched workbook to Telegram channel %s", chat_id)
                return True
            else:
                logger.error(
                    "Telegram API returned %d: %s", resp.status_code, resp.text[:300]
                )
                return False
    except Exception as exc:
        logger.error("Failed dispatching document to Telegram: %s", exc)
        return False


async def send_telegram_alert(
    message: str,
    bot_token: Optional[str] = None,
    channel_id: Optional[str] = None,
) -> bool:
    """Send an urgent error/status alert text message to the Telegram channel."""
    token = (bot_token or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (channel_id or os.getenv("TELEGRAM_COMMUNITY_CHANNEL_ID") or "").strip()

    is_placeholder = (
        not token
        or not chat_id
        or "your_" in token.lower()
        or token.startswith("1234567890:")
        or chat_id == "-1001234567890"
    )

    if is_placeholder:
        logger.warning("Telegram credentials not configured. Skipping alert dispatch.")
        return False

    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message[:4000],  # Telegram max message length is 4096 chars
        "parse_mode": "HTML",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(api_url, json=payload)
            if resp.status_code == 200:
                logger.info("Successfully dispatched alert to Telegram channel %s", chat_id)
                return True
            else:
                logger.error("Telegram alert failed (%d): %s", resp.status_code, resp.text[:200])
                return False
    except Exception as exc:
        logger.error("Failed sending Telegram alert: %s", exc)
        return False
