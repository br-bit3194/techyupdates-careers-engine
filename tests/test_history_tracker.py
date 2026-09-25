"""Unit tests for HistoryTracker, URL canonicalization, and TTL cleanup."""

import os
import json
import tempfile
import pytest
from datetime import datetime, timezone, timedelta
from services.history_tracker import (
    HistoryTracker,
    normalize_job_url,
    normalize_job_key,
)
from services.ai_extractor import OpportunityRecord


def test_normalize_job_url_strips_tracking():
    """Verify that URL canonicalization removes tracking params and trailing slashes."""
    dirty_url = "https://jobs.ashbyhq.com/anthropic/12345/?utm_source=linkedin&utm_medium=feed&ref=job_board&gh_src=custom#section"
    clean_url = normalize_job_url(dirty_url)
    assert clean_url == "https://jobs.ashbyhq.com/anthropic/12345"

    dirty_url2 = "https://boards.greenhouse.io/stripe/jobs/9876/?trk=public_jobs&utm_campaign=daily&source=telegram/"
    clean_url2 = normalize_job_url(dirty_url2)
    assert clean_url2 == "https://boards.greenhouse.io/stripe/jobs/9876"


def test_normalize_job_key_fuzzy_matching():
    """Verify company suffix stripping and title normalization for dual-key matching."""
    key1 = normalize_job_key("Anthropic, Inc.", "Software Engineer (Full-Stack)")
    key2 = normalize_job_key("anthropic inc", "software engineer full stack")
    key3 = normalize_job_key("Anthropic LLC", "Software Engineer - Full Stack")

    assert key1 == key2 == key3


def test_history_tracker_record_and_duplicate_detection():
    """Verify that recorded jobs are detected as duplicates by both URL and company+title."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        tracker = HistoryTracker(filepath=tmp_path)
        assert tracker.is_duplicate("Google", "SWE Intern", "https://careers.google.com/jobs/1") is False

        # Record a test record
        record = OpportunityRecord(
            company_name="Google",
            job_title="SWE Intern",
            seniority_tier="Internship",
            technical_domain="Backend & Distributed Systems",
            location="Remote",
            workplace_type="Remote",
            salary_package="Competitive",
            platform="Google Careers",
            apply_url="https://careers.google.com/jobs/1?utm_source=telegram",
            why_it_matters="Google internship.",
        )

        added = tracker.record_dispatched([record])
        assert added == 1

        # Test duplicate by URL with different tracking query
        assert tracker.is_duplicate(
            "Different Company",
            "Different Title",
            "https://careers.google.com/jobs/1?ref=email",
        ) is True

        # Test duplicate by company + title with different URL
        assert tracker.is_duplicate(
            "Google Inc",
            "SWE Intern",
            "https://other-mirror.com/job",
        ) is True

        # Non-duplicate
        assert tracker.is_duplicate(
            "Microsoft",
            "SWE Intern",
            "https://careers.microsoft.com/jobs/2",
        ) is False

        # Save and reload from disk
        tracker.save()
        tracker2 = HistoryTracker(filepath=tmp_path)
        assert tracker2.is_duplicate("Google", "SWE Intern", "https://careers.google.com/jobs/1") is True
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_history_tracker_ttl_cleanup():
    """Verify that entries older than 30 days are automatically purged."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        now = datetime.now(timezone.utc)
        old_date = (now - timedelta(days=35)).isoformat()
        recent_date = (now - timedelta(days=5)).isoformat()

        fake_data = {
            "version": 1,
            "last_updated": recent_date,
            "sent_urls": {
                "https://old-job.com/1": {"company": "Old Corp", "title": "Old Dev", "last_sent": old_date},
                "https://recent-job.com/2": {"company": "New Corp", "title": "New Dev", "last_sent": recent_date},
            },
            "sent_keys": {
                "old corp:::old dev": {"company": "Old Corp", "title": "Old Dev", "last_sent": old_date},
                "new corp:::new dev": {"company": "New Corp", "title": "New Dev", "last_sent": recent_date},
            },
        }
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(fake_data, f)

        tracker = HistoryTracker(filepath=tmp_path)
        assert len(tracker.sent_urls) == 2

        purged = tracker.cleanup_expired(retention_days=30)
        assert purged == 1
        assert "https://old-job.com/1" not in tracker.sent_urls
        assert "https://recent-job.com/2" in tracker.sent_urls
        assert "old corp:::old dev" not in tracker.sent_keys
        assert "new corp:::new dev" in tracker.sent_keys
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
