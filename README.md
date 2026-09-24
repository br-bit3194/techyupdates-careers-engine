# NexusCareers: Autonomous Daily Opportunity Synthesizer & Community Aggregator

[![Vercel Cron](https://img.shields.io/badge/Vercel-Cron%20Schedule%2014%3A30%20UTC-black?logo=vercel)](https://vercel.com)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue?logo=python)](https://python.org)
[![Gemini 3.5 Flash](https://img.shields.io/badge/Google-Gemini%203.5%20Flash-orange?logo=google)](https://ai.google.dev)
[![OpenPyXL](https://img.shields.io/badge/openpyxl-4--tier%20Spreadsheet-green)](https://openpyxl.readthedocs.io)

An enterprise-grade, serverless opportunity ingestion engine built for Vercel. NexusCareers triggers automatically every single day at **8:00 PM IST (14:30 UTC)**, pulls active technical roles posted within the past 24 hours from premier ATS platforms and feeds, enriches and classifies the dataset using Google Gemini, formats a 4-tier color-coded Excel workbook (`.xlsx`) entirely in-memory, and broadcasts it to a Telegram community channel without IP bans or credential leakage.

---

## 🏗️ System Architecture

```
                  ┌────────────────────────────────────────┐
                  │ Trigger Layer                          │
                  │ - Vercel Cron (Daily @ 14:30 UTC)      │
                  │ - Webhook / Manual POST /api/trigger   │
                  └──────────────────┬─────────────────────┘
                                     │
                                     ▼
                  ┌────────────────────────────────────────┐
                  │ Ingestion Controller (api/trigger.py)  │
                  │ Auth: Bearer CRON_SECRET               │
                  └──────────────────┬─────────────────────┘
                                     │
                                     ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │ Asynchronous Multi-Source Collector (Parallel httpx)                   │
 │                                                                        │
 │ [Tier 1: Direct ATS]    [Tier 2: Startups & Feeds]  [Tier 3: Guest API]│
 │ Greenhouse / Lever /    YC Algolia & Official HN    LinkedIn Guest API │
 │ Ashby Public Endpoints  RemoteOK & Jobicy Feeds     (Rate-limited)     │
 └───────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
                  ┌────────────────────────────────────────┐
                  │ Pre-Filter & Deduplication Engine      │
                  │ - Freshness: < 24 Hours                │
                  │ - Deduplication: MD5(company + title)  │
                  │ - Anti-Scam Heuristics Filter          │
                  └──────────────────┬─────────────────────┘
                                     │
                                     ▼
                  ┌────────────────────────────────────────┐
                  │ AI Extraction Engine (Gemini Flash)    │
                  │ - Schema Extraction & Structured JSON  │
                  │ - 4-Tier Seniority Classification      │
                  └──────────────────┬─────────────────────┘
                                     │
                                     ▼
                  ┌────────────────────────────────────────┐
                  │ Excel Engine (openpyxl in-memory)      │
                  │ - 4 Tab Workbook with Clickable Links  │
                  └──────────────────┬─────────────────────┘
                                     │
                                     ▼
                  ┌────────────────────────────────────────┐
                  │ Dispatch Layer                         │
                  │ Telegram Bot API (sendDocument)        │
                  └────────────────────────────────────────┘
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
* **🚫 Zero Headless Browsers:** No heavy frameworks (Playwright/Selenium) that cause out-of-memory errors or gateway timeouts (`504`) on Vercel serverless.
* **🔒 100% Account Safety:** No authenticated session cookies (`li_at`) are ever used. You never risk personal account bans because everything hits unauthenticated public endpoints.
* **🛡️ Circuit Breakers:** Every network request has an **8.0-second timeout**. If LinkedIn returns `HTTP 429` (rate limit) or an external server hangs, the circuit breaker instantly trips and the pipeline moves on without getting stuck.

---

### 3. What Data Points We Extract per Opportunity

For every single opportunity, the pipeline normalizes and enriches the following 10 data points:
1. **Company Name** (e.g. `Databricks`, `Coinbase`, `Anthropic`)
2. **Role Title** (e.g. `Software Engineering Intern, AI/ML`)
3. **Seniority Tier** (`🎓 Internships`, `🚀 Freshers (0-2 YOE)`, `⚡ Mid-Level (2-5 YOE)`, `🏆 Senior & Staff (5+ YOE)`)
4. **Technical Domain** (`GenAI/LLM`, `Core ML`, `Backend & Distributed`, `Full-Stack & DevOps`)
5. **Experience Level** (e.g. `0-0 yrs`, `0-2 yrs`, `3-5 yrs`, `5+ yrs`)
6. **Workplace Type** (`Remote`, `Hybrid`, `On-site`)
7. **Location** (e.g. `Bengaluru, India`, `San Francisco, CA`, `Remote / Global`)
8. **Salary / CTC** (Normalized: e.g. `₹15-25 LPA`, `$140k-$165k`, or `Not Disclosed`)
9. **Core Tech Stack** (e.g. `Python, PyTorch, Kubernetes, Kafka`)
10. **Why Apply?** (1-line crisp reason highlighting why this role is attractive)
11. **Direct Apply Link** (Clickable `=HYPERLINK("...", "Apply Direct ↗")` formula pointing directly to the company portal)

---

## ⚡ Understanding the "Trigger" (`api/trigger.py`)

The **Trigger** is the serverless API endpoint that acts as the master **starter switch** for the entire pipeline.

### 🌐 How It Works in Vercel
When deployed to Vercel, the file `api/trigger.py` automatically binds to the public route:
```text
https://your-project.vercel.app/api/trigger
```

### 🔄 Execution Flow When Triggered
When an HTTP request hits `/api/trigger`:
1. **Security Authentication:** Verifies the `Authorization: Bearer <CRON_SECRET>` token. If missing or invalid, immediately returns `401 Unauthorized`.
2. **Parallel Collection:** Concurrently queries Greenhouse, Ashby, Lever, Y Combinator, RemoteOK, Jobicy, and LinkedIn Guest APIs.
3. **Filtering & Deduplication:** Strictly discards roles older than 24 hours, catches scam keywords, and removes cross-platform duplicates using MD5 signatures.
4. **AI Enrichment:** Sends deduplicated postings to **Gemini 3.5 Flash** to classify seniority tiers, technical domains, extracted tech stacks, and high-signal summaries.
5. **Excel Generation:** Constructs a styled, 4-tab `.xlsx` spreadsheet in-memory (`io.BytesIO`) with custom theme colors and active `=HYPERLINK()` formulas.
6. **Community Broadcast:** Dispatches the workbook and executive summary directly to your Telegram channel via `multipart/form-data`.
7. **Local Fallback:** If Telegram credentials are omitted, it automatically writes a copy of the spreadsheet to your local directory (e.g. `NexusCareers_Opportunities_YYYYMMDD.xlsx`).

### 🎮 The 3 Ways to Trigger It
* **1. Automatic Vercel Cron:** Automatically triggered daily at **8:00 PM IST (14:30 UTC)** by Vercel's built-in cloud scheduler.
* **2. On-Demand Webhook / cURL:** Manually trigger the pipeline anytime without waiting for the scheduled time:
  ```bash
  curl -X POST https://your-project.vercel.app/api/trigger \
    -H "Authorization: Bearer your_cron_secret"
  ```
* **3. Local CLI Execution:** Run directly on your machine:
  ```bash
  python api/trigger.py
  ```

---

## 🕒 Setting Vercel Cron at a Particular Time

Vercel Cron expressions use standard 5-part POSIX syntax inside `vercel.json`:
```text
 ┌───────────── Minute (0 - 59)
 │ ┌─────────── Hour in UTC (0 - 23)
 │ │ ┌───────── Day of month (1 - 31)
 │ │ │ ┌─────── Month (1 - 12)
 │ │ │ │ ┌───── Day of week (0 - 6, 0=Sunday)
 │ │ │ │ │
 * * * * *
```

> **CRITICAL RULE:** Vercel Cron **always evaluates in UTC (Coordinated Universal Time)**.

### 📐 IST to UTC Conversion Formula
$$\text{UTC Time} = \text{Target IST Time} - \text{5 hours 30 minutes}$$

### 📋 Time Conversion Cheat Sheet

| Target Run Time (IST) | Equivalent UTC Time | `vercel.json` Schedule Expression |
|---|---|---|
| **8:00 AM IST** | 02:30 UTC | `"schedule": "30 2 * * *"` |
| **10:00 AM IST** | 04:30 UTC | `"schedule": "30 4 * * *"` |
| **1:00 PM IST** | 07:30 UTC | `"schedule": "30 7 * * *"` |
| **6:00 PM IST** | 12:30 UTC | `"schedule": "30 12 * * *"` |
| **8:00 PM IST** *(Default)* | 14:30 UTC | `"schedule": "30 14 * * *"` |
| **10:00 PM IST** | 16:30 UTC | `"schedule": "30 16 * * *"` |
| **Midnight (12:00 AM IST)** | 18:30 UTC (prev day) | `"schedule": "30 18 * * *"` |

### ⚡ Vercel Plan Execution Limits
* **Hobby (Free Tier):** Allows **1 cron execution per day**. Perfect for running a daily digest (e.g. at 8:00 PM IST).
* **Pro Plan:** Allows unlimited cron executions per day (hourly, every 6 hours, etc.).

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

## 🛡️ 24-Hour Freshness & Verification Guarantee

Every opportunity in the workbook is guaranteed to be active and posted within the **last 24 hours**:

1. **LinkedIn Guest API:** Enforces LinkedIn's native server-side time parameter `f_TPR=r86400` (*Rolling 86,400 seconds = 24 hours*). LinkedIn strictly excludes any posting older than 24 hours.
2. **Direct ATS (Greenhouse, Ashby, Lever):** Evaluates exact UTC timestamps (`updated_at`, `publishedAt`, `createdAt`). The collector calculates `(now - timestamp) <= 24 hours`. Any older posting is dropped. *(For example, at Databricks, out of 884 total open jobs, 864 older jobs were filtered out and only the 20 newly updated/opened within 24 hours were retained!)*
3. **Remote Feeds & YC:** Evaluated against `cutoff = now - 24 hours`.
4. **Legitimacy Level:** Direct ATS and YC roles are 100% direct company openings with zero agency middlemen.

---

## 📁 Project Structure

```text
job_finder/
├── api/
│   └── trigger.py               # Vercel entrypoint handler & local CLI runner
├── services/
│   ├── collectors/
│   │   ├── __init__.py          # Dedup hash, tech filters, anti-scam checks
│   │   ├── ats_boards.py        # Greenhouse, Lever, Ashby async fetchers
│   │   ├── yc_algolia.py        # Y Combinator Algolia & HN jobs fallback
│   │   ├── remote_feeds.py      # RemoteOK, Jobicy RSS/JSON
│   │   └── linkedin_guest.py    # Polite guest scraper with circuit breaker
│   ├── ai_extractor.py          # Gemini 3.5 Flash batch processing & fallback
│   ├── excel_builder.py         # Multi-tab openpyxl workbook generator
│   └── telegram_notifier.py     # Document & message broadcast service
├── config/
│   ├── __init__.py
│   └── targets.py               # Verified target slugs, keywords, scam blacklist
├── tests/
│   └── test_pipeline.py         # Complete unit and integration test suite
├── requirements.txt             # Dependency definitions
├── vercel.json                  # Serverless function & cron definitions
├── pytest.ini                   # Pytest configuration
├── .env.example                 # Template for environment variables
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

# Google AI Studio key (supports Gemini 3.5 Flash)
GEMINI_API_KEY=AIzaSy...

# Optional: defaults to gemini-3.5-flash with automatic gemini-2.5-flash fallback
GEMINI_MODEL=gemini-3.5-flash

# Telegram Bot Token (from @BotFather)
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# Telegram Community Channel ID (e.g., -100xxxxxxxxxx)
TELEGRAM_COMMUNITY_CHANNEL_ID=-100xxxxxxxxxx
```

> **Detailed Bot Setup Manual**: For full step-by-step instructions on setting up your bot and getting your channel ID in 3 minutes, see [**`TELEGRAM_SETUP.md`**](file:///d:/TechyUpdates/job_finder/TELEGRAM_SETUP.md).

> **Note**: If Telegram credentials are not set, the pipeline automatically saves the generated Excel file directly to your local workspace (`TechyUpdates_Opportunities_YYYYMMDD.xlsx`).

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

This will run all collectors in parallel, deduplicate listings, enrich the dataset using Gemini 3.5 Flash, build the 4-tab Excel spreadsheet, and save it locally.

---

## ☁️ Deployment to Vercel

### Step 1: Deploy with Vercel CLI
```bash
# Install Vercel CLI if needed
npm install -g vercel

# Deploy project
vercel
```

### Step 2: Configure Environment Variables in Vercel Dashboard
In the Vercel Project Settings -> **Environment Variables**, add:
- `CRON_SECRET`
- `GEMINI_API_KEY`
- `GEMINI_MODEL` (Optional, defaults to `gemini-3.5-flash`)
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_COMMUNITY_CHANNEL_ID`

### Step 3: Verify Cron Schedule
The project includes `vercel.json` configured with:
```json
{
  "crons": [
    {
      "path": "/api/trigger",
      "schedule": "30 14 * * *"
    }
  ],
  "functions": {
    "api/trigger.py": {
      "maxDuration": 300,
      "memory": 1024
    }
  }
}
```
* **Daily Schedule:** Runs at `14:30 UTC` (8:00 PM IST).
* **Execution Boundary:** `maxDuration: 300` ensures serverless async I/O finishes comfortably.

### Step 4: Manual Trigger Verification (cURL)
You can trigger the pipeline manually at any time using:

```bash
curl -X POST https://your-project.vercel.app/api/trigger \
  -H "Authorization: Bearer your_super_secret_32_char_token"
```

---

## 📄 License
MIT License.
