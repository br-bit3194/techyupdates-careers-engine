# NexusCareers: Autonomous Daily Opportunity Synthesizer & Community Aggregator

[![Daily Pipeline](https://github.com/br-bit3194/techyupdates-careers-engine/actions/workflows/daily_pipeline.yml/badge.svg)](https://github.com/br-bit3194/techyupdates-careers-engine/actions/workflows/daily_pipeline.yml)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue?logo=python)](https://python.org)
[![Gemini 3 Series](https://img.shields.io/badge/Google-Gemini%203%20Series-orange?logo=google)](https://ai.google.dev)
[![OpenPyXL](https://img.shields.io/badge/openpyxl-4--tier%20Spreadsheet-green)](https://openpyxl.readthedocs.io)
[![Vercel Ready](https://img.shields.io/badge/Vercel-Serverless%20%26%20Cron-black?logo=vercel)](https://vercel.com)

An enterprise-grade, autonomous opportunity ingestion engine built for **GitHub Actions** and **Vercel Serverless**. NexusCareers triggers automatically every single day at **7:00 AM IST (01:30 UTC)** via GitHub Actions (with optional Vercel Cron at **7:45 PM IST / 14:15 UTC**), pulls active technical roles posted within the past 24 hours from premier ATS platforms and feeds, verifies URL liveness, enriches and classifies the dataset using Google Gemini 3 series, formats a 4-tier color-coded Excel workbook (`.xlsx`) with 11 rich columns entirely in-memory, and broadcasts it to a Telegram community channel without IP bans or credential leakage.

---

## 🏗️ System Architecture

```
                  ┌────────────────────────────────────────────────────────┐
                  │ Trigger Layer                                          │
                  │ - GitHub Actions Cron (Daily @ 01:30 UTC / 7:00 AM IST)│
                  │ - GitHub 1-Click Manual: workflow_dispatch             │
                  │ - Vercel Cron (Daily @ 14:15 UTC / 7:45 PM IST)        │
                  │ - Liveness Probe: GET /api/health (200 OK)             │
                  │ - Webhook / Manual POST /api/trigger                   │
                  └──────────────────────────┬─────────────────────────────┘
                                             │
                                             ▼
                  ┌────────────────────────────────────────────────────────┐
                  │ Ingestion Controller (api/trigger.py)                  │
                  │ Auth: Bearer CRON_SECRET or Header secret              │
                  └──────────────────────────┬─────────────────────────────┘
                                             │
                                             ▼
 ┌──────────────────────────────────────────────────────────────────────────────┐
 │ Asynchronous Multi-Source Collector (Parallel httpx)                         │
 │                                                                              │
 │ [Tier 1: Direct ATS]          [Tier 2: Startups & Feeds]  [Tier 3: Guest API]│
 │ Greenhouse / Lever /          YC Algolia & Official HN    LinkedIn Guest API │
 │ Ashby Public Endpoints        RemoteOK & Jobicy Feeds     (Circuit Breaker)  │
 └───────────────────────────────────────┬──────────────────────────────────────┘
                                         │
                                         ▼
                  ┌────────────────────────────────────────────────────────┐
                  │ Pre-Filter & Deduplication Engine                      │
                  │ - Freshness: < 24 Hours                                │
                  │ - Deduplication: MD5(company + title)                  │
                  │ - Anti-Scam Heuristics Filter                          │
                  │ - Liveness Fast-Path & Link Closure Verifier           │
                  └──────────────────────────┬─────────────────────────────┘
                                             │
                                             ▼
                  ┌────────────────────────────────────────────────────────┐
                  │ AI Extraction Engine (Gemini 3 Series)                 │
                  │ - Batch size 50, 5.0s pacing (~10 RPM)                 │
                  │ - 3.5 Flash ➡️ 3.8 Flash ➡️ 3.5 Flash-Lite             │
                  │ - 3 Retries Max with Exp Backoff (2s, 4s)              │
                  │ - Fallback: Local Rule-Based Regex Engine              │
                  └──────────────────────────┬─────────────────────────────┘
                                             │
                                             ▼
                  ┌────────────────────────────────────────────────────────┐
                  │ Excel Engine (openpyxl in-memory)                      │
                  │ - 4 Tab Workbook with 11 Columns & Active Hyperlinks   │
                  │ - Posted Date, Tech Stack, CTC, & Why Apply?           │
                  └──────────────────────────┬─────────────────────────────┘
                                             │
                                             ▼
                  ┌────────────────────────────────────────────────────────┐
                  │ Dispatch & Artifact Layer                              │
                  │ - Telegram Bot API (sendDocument + Humanized Caption)  │
                  │ - GitHub Actions Artifact Storage (30-day retention)   │
                  │ - Local disk preservation fallback                     │
                  └────────────────────────────────────────────────────────┘
```

---

## 🌐 Data Ingestion: Platforms & Extraction Mechanics

NexusCareers ingests opportunities exclusively from **unauthenticated, legitimate public sources** across 4 distinct tiers:

### 1. The Platforms We Gather From

| Ingestion Tier | Access Mechanism | Target Employers & Scope | Examples |
|---|---|---|---|
| **Tier 1: Direct Company ATS** | Official public REST APIs | Top AI scaleups, unicorns, and university hiring leaders | • **Greenhouse:** Anthropic, Scale AI, Stripe, Figma, Databricks, Cloudflare, Discord, Gusto, Reddit, Airbnb, Dropbox, Duolingo, Affirm, Coinbase, Robinhood, Datadog, Airtable, Anduril.<br>• **Ashby:** Cursor, Perplexity, Ramp, Benchling, Linear, Poolside, Replit, Modal, Cohere, Runway.<br>• **Lever:** Mistral AI, Spotify, Palantir. |
| **Tier 2: Y Combinator Startups** | Algolia search & Official Hacker News Jobs API | Early-stage, high-growth YC-backed AI startups | • QuestDB (YC S20), Zep AI (YC W24), Lingo.dev (YC F24), SubImage (YC W25), Kyber (YC W23). |
| **Tier 3: Remote Portals** | Public JSON & RSS Feeds | Global remote AI and Software Engineering roles | • RemoteOK & Jobicy (Canonical, Mozilla, Binance, Kraken, ElevenLabs). |
| **Tier 4: LinkedIn Guest API** | Polite unauthenticated search (`f_TPR=r86400`) | MNCs, GCCs, and Indian tech hubs across all experience tiers | • Wells Fargo, Siemens, Grab, FactSet, Caterpillar, Accenture. |

---

### 2. HOW We Gather the Data (Technical Safeguards)

* **⚡ Concurrent Async I/O (`httpx` + `asyncio`):** All 30+ company endpoints and search queries are queried **simultaneously in parallel**, finishing in **~8 to 10 seconds** instead of minutes.
* **🚫 Zero Headless Browsers:** No heavy frameworks (Playwright/Selenium) that cause out-of-memory errors or gateway timeouts (`504`) on serverless runners.
* **🔒 100% Account Safety:** No authenticated session cookies (`li_at`) are ever used. You never risk personal account bans because everything hits unauthenticated public endpoints.
* **🛡️ Circuit Breakers:** Every network request has an **8.0-second timeout**. If LinkedIn returns `HTTP 429` (rate limit) or an external server hangs, the circuit breaker instantly trips and the pipeline moves on without getting stuck.
* **🔍 Fast-Path Liveness Verification:** Direct ATS roles from Greenhouse/Ashby/Lever are verified at origin, while third-party and remote postings undergo parallel HTTP status and closure phrase checks to eliminate broken or expired job links.

---

### 3. What Data Points We Extract per Opportunity (11 Columns)

For every single opportunity, the pipeline normalizes, classifies, and enriches **11 distinct data points**:

1. **Company** (e.g. `Databricks`, `Coinbase`, `Anthropic`, `Perplexity`)
2. **Role Title** (e.g. `Software Engineering Intern, AI/ML`, `Member of Technical Staff`)
3. **Domain** (`GenAI/LLM`, `Core ML`, `Backend & Distributed`, `Full-Stack & DevOps`)
4. **Experience** (e.g. `0-0 yrs`, `0-2 yrs`, `2-5 yrs`, `5+ yrs`)
5. **Workplace** (`Remote`, `Hybrid`, `On-site`)
6. **Location** (e.g. `Bengaluru, India`, `San Francisco, CA`, `Remote / Global`)
7. **Salary / CTC** (Normalized: e.g. `₹15-25 LPA`, `$140k-$165k`, or `Not Disclosed`)
8. **Tech Stack** (e.g. `Python, PyTorch, Kubernetes, Kafka, React`)
9. **Posted Date** (e.g. `2026-09-25`, `14 hours ago`, or `Recent (<24h)`)
10. **Why Apply?** (1-line crisp reason highlighting why this role is attractive)
11. **Direct Apply Link** (Clickable `=HYPERLINK("...", "Apply Direct ↗")` formula pointing directly to the company portal)

---

## ⚡ Endpoints & Cloud Architecture

### 1. `GET /api/health` (Uptime & Liveness Probe)
- **Unauthenticated & Fast (< 50ms)**: Returns an immediate `200 OK` JSON response:
  ```json
  {
    "status": "healthy",
    "service": "techyupdates-careers-engine",
    "timestamp": "2026-09-25T01:30:00.000000+00:00"
  }
  ```
- Use this endpoint for uptime monitors (UptimeRobot, BetterUptime) or quick health checks without triggering AI or scraping.

### 2. `GET /api/trigger` or `POST /api/trigger` (Full Pipeline Engine)
The **Trigger** is the master execution handler for the pipeline.

### 🔄 Execution Flow When Triggered
1. **Security Authentication:** Verifies the `Authorization: Bearer <CRON_SECRET>` or `x-cron-secret` token. If missing or invalid, immediately returns `401 Unauthorized`. (CLI dry-run bypasses auth if executed locally).
2. **Parallel Collection:** Concurrently queries Greenhouse, Ashby, Lever, Y Combinator, RemoteOK, Jobicy, and LinkedIn Guest APIs (~5-8 seconds).
3. **Filtering & Deduplication:** Discards roles older than 24 hours, catches scam keywords, and removes cross-platform duplicates using MD5 signatures.
4. **Liveness Verification:** Validates that posting URLs are active and not closed/expired before passing to AI.
5. **AI Tiering & Synthesis (Gemini 3):** Processes listings in batches of 50 with safe pacing (~10 RPM, well below Google's 15 RPM free tier cap). If Google experiences a demand spike, it retries up to 3 times with exponential backoff (2s, 4s) across `gemini-3.5-flash` ➡️ `gemini-3.8-flash` ➡️ `gemini-3.5-flash-lite`, and gracefully falls back to the local rule-based classifier if quota is exhausted.
6. **Excel Generation:** Constructs a styled, 4-tab `.xlsx` spreadsheet in-memory (`io.BytesIO`) with custom theme colors, zebra rows, auto-filters, and active `=HYPERLINK()` formulas.
7. **Community Broadcast:** Dispatches the workbook and humanized executive summary directly to your Telegram channel via `multipart/form-data`.
8. **Artifact Archiving & Local Fallback:** Saves a copy of the spreadsheet (`TechyUpdates_Opportunities_YYYYMMDD.xlsx`) locally and uploads it as a GitHub Actions workflow artifact.

---

## 🕒 Automation Schedules & Cron Configuration

### 1. GitHub Actions Workflow (Primary & Recommended)
Defined in [`.github/workflows/daily_pipeline.yml`](file:///d:/TechyUpdates/job_finder/.github/workflows/daily_pipeline.yml):
* **Schedule:** `30 1 * * *` (Every single day at **7:00 AM IST / 01:30 UTC**)
* **Manual Trigger:** Supports 1-click execution via **workflow_dispatch** button in the GitHub Actions tab.
* **Artifacts:** Automatically uploads generated workbooks for 30-day retention under the Actions run summary.

### 2. Vercel Cron (Optional Secondary Serverless Trigger)
Defined in [`vercel.json`](file:///d:/TechyUpdates/job_finder/vercel.json):
* **Schedule:** `15 14 * * *` (Every single day at **7:45 PM IST / 14:15 UTC**)

### 📋 Time Conversion Cheat Sheet

| Target Run Time (IST) | Equivalent UTC Time | Cron Expression (`schedule`) |
|---|---|---|
| **7:00 AM IST** *(GitHub Actions Default)* | **01:30 UTC** | `30 1 * * *` |
| **8:00 AM IST** | 02:30 UTC | `30 2 * * *` |
| **10:00 AM IST** | 04:30 UTC | `30 4 * * *` |
| **1:00 PM IST** | 07:30 UTC | `30 7 * * *` |
| **6:00 PM IST** | 12:30 UTC | `30 12 * * *` |
| **7:45 PM IST** *(Vercel Cron Default)* | **14:15 UTC** | `15 14 * * *` |
| **8:00 PM IST** | 14:30 UTC | `30 14 * * *` |
| **10:00 PM IST** | 16:30 UTC | `30 16 * * *` |

---

## 🎯 Roles & Technical Domains Covered

NexusCareers focuses exclusively on **Software Engineering, AI/ML, and Technical Infrastructure** opportunities:

### 1. The 4 Seniority Tiers (Tabs)

| Tab Name | Experience | Target Roles & Audience | Real Examples from Ingestion |
|---|---|---|---|
| **`🎓 Internships`** | **0 YOE** | Pre-final & final year students, summer/winter interns, campus fellows | • **Databricks:** *Software Engineering Intern (Winter)*<br>• **Figma:** *Data Engineer Intern*<br>• **Ramp:** *Software Engineering Intern, Frontend* |
| **`🚀 Freshers (0-2 YOE)`** | **0–2 YOE** | New Grads, SDE-1, Associate Engineers, Junior AI/ML Developers, GETs | • **Perplexity:** *Member of Technical Staff (Early Career)*<br>• **Scale AI:** *Software Engineer - New Grad*<br>• **Canonical:** *Junior Linux Kernel Engineer - Ubuntu* |
| **`⚡ Mid-Level (2-5 YOE)`** | **2–5 YOE** | SDE-2, Systems Engineers, Core ICs, Backend Engineers | • **Palantir:** *Forward Deployed Software Engineer*<br>• **Binance:** *Backend Engineer (Java) - Trading*<br>• **Modal:** *Analytics Engineer* |
| **`🏆 Senior & Staff (5+ YOE)`** | **5+ YOE** | Senior (SDE-3), Staff+, Principal Engineers, AI Architects, Leads | • **Anthropic:** *Applied AI Architect*<br>• **Anthropic:** *Staff+ Software Engineer, Access Programs*<br>• **Discord:** *Senior Systems Engineer* |

### 2. The 4 Technical Domains

* **🤖 GenAI / LLM / Agentic Systems:** RAG architectures, Agentic workflows, LiteLLM, prompt evaluation, vector search, model fine-tuning, AI product engineers.
* **🔬 Core ML / Deep Learning / Vision / NLP:** PyTorch, TensorFlow, classical statistical learning, model training pipelines, computer vision, data science.
* **⚙️ Backend & Distributed Systems:** Python, FastAPI, Go, Java, Rust, microservices, Kafka, Redis, low-latency APIs, databases, distributed caching.
* **🌐 Full-Stack / Infrastructure / DevOps:** Next.js/React + Backend, Docker, Kubernetes, GCP/AWS cloud architectures, SRE, Linux systems.

### 3. What Gets Discarded (Filtered Out)
* **Non-technical roles:** Sales, HR, Marketing, Operations, Graphic Design, Customer Support.
* **Exploitative scams:** Listings requiring "registration fees", "training deposits", "unpaid test assignments", or MLM schemes.
* **Stale listings:** Postings older than 24 hours.

---

## 📁 Project Structure

```text
job_finder/
├── .github/
│   └── workflows/
│       └── daily_pipeline.yml   # Automated daily GitHub Actions workflow (7:00 AM IST)
├── api/
│   ├── health.py                # Dedicated ultra-fast (<50ms) liveness probe
│   └── trigger.py               # Master pipeline execution entrypoint & CLI runner
├── services/
│   ├── collectors/
│   │   ├── __init__.py          # Dedup hash, tech filters, anti-scam checks
│   │   ├── ats_boards.py        # Greenhouse, Lever, Ashby async fetchers
│   │   ├── yc_algolia.py        # Y Combinator Algolia & HN jobs fallback
│   │   ├── remote_feeds.py      # RemoteOK, Jobicy RSS/JSON
│   │   ├── linkedin_guest.py    # Polite guest scraper with circuit breaker
│   │   └── liveness_verifier.py # HTTP status & expiration phrase verifier
│   ├── ai_extractor.py          # Gemini 3 cascade (3.5 / 3.8 / Flash-Lite) & fallback
│   ├── excel_builder.py         # 11-column, 4-tab openpyxl workbook generator
│   └── telegram_notifier.py     # Community broadcaster & humanized caption builder
├── config/
│   ├── __init__.py
│   └── targets.py               # Verified target slugs, keywords, scam blacklist
├── tests/
│   └── test_pipeline.py         # Complete unit and integration test suite
├── requirements.txt             # Dependency definitions
├── pyproject.toml               # PEP 621 metadata & Vercel Python entrypoint
├── vercel.json                  # Serverless function & cron definitions
├── pytest.ini                   # Pytest configuration
├── .env.example                 # Template for environment variables
├── TELEGRAM_SETUP.md            # Step-by-step 3-minute Telegram bot setup manual
└── README.md                    # Setup and deployment manual
```

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.11 or 3.12
- Git

### 2. Environment Setup

```bash
# Clone the repository
git clone https://github.com/br-bit3194/techyupdates-careers-engine.git
cd techyupdates-careers-engine

# Create and activate virtual environment
python -m venv .venv

# On Windows PowerShell:
.\.venv\Scripts\Activate.ps1

# On Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install pytest
```

### 3. Configure Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Configure your secrets in `.env`:
```ini
# Generate a random 32-character token for cron authentication
CRON_SECRET=your_super_secret_32_char_token

# Google AI Studio key (supports Gemini 3 Series)
GEMINI_API_KEY=AIzaSy...

# Optional: defaults to gemini-3.5-flash with automatic gemini-3.8-flash / gemini-3.5-flash-lite fallback
GEMINI_MODEL=gemini-3.5-flash

# Telegram Bot Token (from @BotFather)
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# Telegram Community Channel ID (e.g., -100xxxxxxxxxx or @your_channel)
TELEGRAM_COMMUNITY_CHANNEL_ID=-100xxxxxxxxxx
```

> **Detailed Bot Setup Manual**: For full step-by-step instructions on setting up your bot and getting your channel ID in 3 minutes, see [**`TELEGRAM_SETUP.md`**](file:///d:/TechyUpdates/job_finder/TELEGRAM_SETUP.md).

> **Note**: If Telegram credentials are not configured, the pipeline automatically saves the generated Excel file directly to your local workspace (`TechyUpdates_Opportunities_YYYYMMDD.xlsx`).

---

## 🧪 Testing & Local Execution

### Run Unit Tests
```bash
pytest -v
```

### Run Pipeline Directly (CLI Dry Run)
```bash
python api/trigger.py
```

This will run all collectors in parallel, deduplicate listings, verify URL liveness, enrich the dataset using Google Gemini 3 series, build the 11-column 4-tab Excel spreadsheet, and broadcast/save it.

---

## ☁️ Production Deployment

### Option A: GitHub Actions (Recommended)
1. Go to your GitHub repository ➔ **Settings** ➔ **Secrets and variables** ➔ **Actions**.
2. Add the following **Repository Secrets**:
   - `GEMINI_API_KEY`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_COMMUNITY_CHANNEL_ID`
   - `CRON_SECRET`
   - `GEMINI_MODEL` (Optional, defaults to `gemini-3.5-flash-lite` or `gemini-3.5-flash`)
3. The workflow will run automatically every morning at **7:00 AM IST (01:30 UTC)**. You can also trigger it manually anytime by going to **Actions** ➔ **TechyUpdates Opportunity Pipeline** ➔ **Run workflow**.

---

### Option B: Vercel Serverless & Cron

#### Step 1: Deploy with Vercel CLI
```bash
npm install -g vercel
vercel
```

#### Step 2: Configure Environment Variables in Vercel Dashboard
In your Vercel Project Settings ➔ **Environment Variables**, add:
- `CRON_SECRET`
- `GEMINI_API_KEY`
- `GEMINI_MODEL`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_COMMUNITY_CHANNEL_ID`

> **IMPORTANT (Deployment Protection):** In your Vercel Project Settings ➔ **Deployment Protection**, ensure **Vercel Authentication** is set to **Disabled** so that external cron triggers, uptime robots, and webhooks can access the endpoints without being intercepted by an SSO login wall.

#### Step 3: Manual Trigger Verification (cURL)
You can trigger the pipeline manually at any time using:

```bash
curl -X POST https://your-project.vercel.app/api/trigger \
  -H "Authorization: Bearer your_super_secret_32_char_token"
```

---

## 📄 License
MIT License.
