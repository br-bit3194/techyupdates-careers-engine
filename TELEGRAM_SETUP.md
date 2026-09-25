# 🤖 Telegram Bot & Channel Setup Guide for TechyUpdates

This step-by-step manual guides you through creating a free, 100% ban-proof Telegram Bot and connecting it to your Telegram Community Channel or Group to receive the daily **TechyUpdates Opportunities Digest** (`.xlsx` workbook + executive highlights).

---

## ⏱️ Estimated Setup Time: ~3 Minutes

---

## 📋 Table of Contents
1. [Step 1: Create Your Bot via @BotFather](#step-1-create-your-bot-via-botfather)
2. [Step 2: Create Your Telegram Channel or Group](#step-2-create-your-telegram-channel-or-group)
3. [Step 3: Make Your Bot an Administrator](#step-3-make-your-bot-an-administrator)
4. [Step 4: Retrieve Your Channel Chat ID](#step-4-retrieve-your-channel-chat-id)
5. [Step 5: Configure Environment Variables](#step-5-configure-environment-variables)
6. [Step 6: Send a Test Verification Broadcast](#step-6-send-a-test-verification-broadcast)
7. [❓ Common Troubleshooting & Gotchas](#-common-troubleshooting--gotchas)

---

## Step 1: Create Your Bot via @BotFather

Telegram's **@BotFather** is the official tool provided by Telegram to create and manage bots.

1. Open Telegram on your phone or desktop.
2. In the global search bar, type: **`@BotFather`**
   *(Look for the verified account with the blue checkmark).*
3. Click **Start** (or type `/start`).
4. Type and send:
   ```text
   /newbot
   ```
5. **Set a Display Name:**
   Choose what users see in chat (e.g. `TechyUpdates Job Alerts` or `NexusCareers Bot`).
6. **Choose a Username:**
   This must be unique globally and **must end in `bot`** (e.g. `techyupdates_jobs_bot` or `techy_careers_bot`).
7. **Copy Your Bot Token:**
   BotFather will reply with a congratulatory message containing your **HTTP API Token**:
   ```text
   Use this token to access the HTTP API:
   7849201948:AAH1b_x849kdJsd83nd8s-2ksd0s
   ```
   > [!IMPORTANT]
   > Keep this token secret. This is your `TELEGRAM_BOT_TOKEN`.

---

## Step 2: Create Your Telegram Channel or Group

You can broadcast the daily Excel sheet to either a **Channel** (recommended) or a **Group**.

### Channel vs. Group: Which should you choose?
* **Channel (Recommended):** Best for announcements and daily job digests. Only admins (and your bot) can post; subscribers receive clean, clutter-free files without spam.
* **Group:** Best if you want community members to chat and discuss opportunities below the postings.

### How to Create:
1. In Telegram, click the **Pen / New Message icon**.
2. Select **New Channel** (or **New Group**).
3. Set your Channel name (e.g. `TechyUpdates | Tech Jobs & Internships`).
4. Add an optional description and profile avatar.
5. Choose **Public** or **Private**:
   * **Public:** Anyone can find it and join via a custom handle (e.g. `t.me/techyupdates_jobs`).
   * **Private:** Accessible only via an invite link.

---

## Step 3: Make Your Bot an Administrator

> [!CAUTION]
> A Telegram bot **cannot** send documents or messages into a channel unless it has been explicitly granted **Administrator** permissions.

1. Open your newly created Telegram Channel.
2. Click the Channel Name at the top header ➡️ Click **Edit** (pencil icon on mobile, or "Manage Channel" on desktop).
3. Select **Administrators** ➡️ Click **Add Admin**.
4. Search for your bot using its exact username (e.g. `@techyupdates_jobs_bot`).
5. In the permissions list, ensure **"Post Messages"** (or "Manage Posts") is toggled **ON**.
6. Click **Done / Save**.

---

## Step 4: Retrieve Your Channel Chat ID

Your bot needs the unique numeric ID of your channel to send files to it.

### Method A: If Your Channel is Public (Simplest)
If your channel has a public link/handle (e.g. `t.me/techyupdates_jobs`), your Channel ID is simply:
```ini
TELEGRAM_COMMUNITY_CHANNEL_ID=@techyupdates_jobs
```

---

### Method B: For Private Channels (Standard Numeric ID)
Private channels use a negative 13-digit numeric ID starting with `-100`.

1. In Telegram, search for the helper bot: **`@JsonDumpBot`** or **`@getmyid_bot`**.
2. Click **Start**.
3. Go to your Job Channel, write any temporary message (e.g. *"Hello"*), and **Forward** that message to `@JsonDumpBot`.
4. The helper bot will immediately output a JSON block. Look for the `forward_from_chat` object:
   ```json
   "forward_from_chat": {
     "id": -1002345678901,
     "title": "TechyUpdates | Tech Jobs & Internships",
     "type": "channel"
   }
   ```
5. Copy the ID including the minus sign and `-100`:
   👉 **`-1002345678901`**

---

## Step 5: Configure Environment Variables

### 1. In Your Local Workspace (`.env`)
Open your local [`.env`](file:///d:/TechyUpdates/job_finder/.env) file and update the values:

```ini
# Telegram Bot Token (obtained from @BotFather in Step 1)
TELEGRAM_BOT_TOKEN=7849201948:AAH1b_x849kdJsd83nd8s-2ksd0s

# Telegram Channel ID (obtained in Step 4)
TELEGRAM_COMMUNITY_CHANNEL_ID=-1002345678901
```

### 2. In GitHub Actions (Recommended for Daily Automated Broadcasts)
If using GitHub Actions for scheduled runs:
1. Go to your repository on GitHub ➔ **Settings** ➔ **Secrets and variables** ➔ **Actions**.
2. Add the following **Repository Secrets**:
   * **`TELEGRAM_BOT_TOKEN`** = `<your_bot_token>`
   * **`TELEGRAM_COMMUNITY_CHANNEL_ID`** = `<your_channel_id>`
   * **`GEMINI_API_KEY`** = `<your_gemini_api_key>`
   * **`CRON_SECRET`** = `<your_32_character_secret>`

### 3. In Vercel Project Settings (If Using Vercel Serverless)
When deploying to Vercel:
1. Open your project on the [Vercel Dashboard](https://vercel.com/dashboard).
2. Go to **Settings** ➔ **Environment Variables**.
3. Add `TELEGRAM_BOT_TOKEN`, `TELEGRAM_COMMUNITY_CHANNEL_ID`, `GEMINI_API_KEY`, and `CRON_SECRET`.

---

## Step 6: Send a Test Verification Broadcast

Once your `.env` (or GitHub Secrets) has both credentials, you can immediately test the bot:

### Run the Pipeline Locally:
```powershell
# In PowerShell:
.\.venv\Scripts\python.exe api/trigger.py
```

### Or Trigger via GitHub Actions:
Go to **GitHub Actions** ➔ **TechyUpdates Opportunity Pipeline** ➔ Click **Run workflow**.

### Expected Telegram Output in Your Channel:
Your channel will instantly receive:
1. 📁 **Attached Document:** `TechyUpdates_Opportunities_YYYYMMDD.xlsx` (a styled 11-column 4-tab workbook containing Internships, Freshers, Mid-Level, and Senior roles).
2. 📝 **Formatted Humanized Caption:**
   ```text
   👋 Hey Tech Fam! Here is your daily TechyUpdates job drop! 🚀

   📅 Date: 25 Sep 2026
   ✨ We scoured and verified 102 fresh tech openings across top product companies, high-growth startups & YC founders.

   🎯 What's inside today's drop:
     🎓 Internships & College Grads: 25
     🌱 Freshers & Entry-Level (0–2 YOE): 30
     💻 Mid-Level Engineers (2–5 YOE): 27
     🚀 Senior, Staff & Leads (5+ YOE): 20

   🔥 Today's Top Picks:
   • 🎓 Databricks — Software Engineering Intern (AI/ML) (Bengaluru, India)
   • 🌱 Coinbase — Associate Software Engineer (Remote • ₹20-28 LPA)
   • 💻 Palantir — Forward Deployed Software Engineer [Python, Go, Spark]
   • 🚀 Anthropic — Applied AI Architect (GenAI/LLM)

   📂 Attached Excel file: 4 categorized tabs with direct 1-click apply links.
   💡 Pro-tip: Filter by your preferred tech stack & apply early. Best of luck with your prep! 🌟
   ```

---

## ❓ Common Troubleshooting & Gotchas

| Issue / Error | Root Cause | How to Fix |
|---|---|---|
| **`HTTP 401 Unauthorized`** | The `TELEGRAM_BOT_TOKEN` is incorrect or contains extra spaces. | Re-copy the token directly from your chat with `@BotFather`. |
| **`HTTP 400 Bad Request: chat not found`** | The `TELEGRAM_COMMUNITY_CHANNEL_ID` is wrong or missing the `-100` prefix. | Ensure private channel IDs look like `-100xxxxxxxxxx`. For public channels, ensure you include `@` (e.g. `@my_channel`). |
| **`HTTP 403 Forbidden: bot is not a member of the channel`** | The bot was created, but not added to the channel as an Admin. | Go to your Channel Settings ➡️ Administrators ➡️ Add your bot as Admin with **"Post Messages"** permission enabled. |
| **`HTTP 400: file must be non-empty`** | The `.xlsx` buffer was empty or corrupted. | The pipeline uses `io.BytesIO` in-memory. Ensure `build_excel_workbook` generated rows before calling dispatch. |

---

### 🎉 Congratulations!
Your autonomous **TechyUpdates Daily Opportunity Engine** is now fully wired to broadcast curated spreadsheets directly to your community every single day at **7:00 AM IST (01:30 UTC)**.

