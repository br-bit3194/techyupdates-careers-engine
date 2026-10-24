"""NexusCareers configuration: Target companies, ATS endpoints, feeds, and filtering rules."""

from typing import Dict, List, Set

# ATS Targets: Curated top tech companies, AI scaleups, unicorns, and open-source AI leaders
ATS_TARGETS: Dict[str, List[str]] = {
    "ashby": [
        "cursor",
        "perplexity",
        "ramp",
        "benchling",
        "linear",
        "poolside",
        "replit",
        "modal",
        "cohere",
        "runway",
        # Open-Source AI scaleups & unicorn labs
        "fireworks",
        "genesis",
        "livekit",
        "physicalintelligence",
        "nousresearch",
        "primeintellect",
        "inferact",
        "langchain",
        "black-forest-labs",
        "supabase",
        "ollama",
        "sesame",
        "e2b",
        "mastra",
        "thinkingmachines",
        "dust",
        "roboflow",
        "fleek",
        "browserbase",
        "liquid-ai",
        "airbyte",
    ],
    "greenhouse": [
        "anthropic",
        "scaleai",
        "stripe",
        "figma",
        "databricks",
        "cloudflare",
        "discord",
        "gusto",
        "andurilindustries",
        "airtable",
        "reddit",
        "airbnb",
        "dropbox",
        "duolingo",
        "affirm",
        "datadog",
        "coinbase",
        "robinhood",
        # Open-Source AI scaleups
        "veniceai",
        "chainguard",
        "lightningai",
        "togetherai",
    ],
    "lever": [
        "mistral",
        "palantir",
        "spotify",
        "zilliz",
    ],
    "workable": [
        "crewai",
    ],
}

# Canonical display names for companies with non-standard capitalization or brands
COMPANY_DISPLAY_NAMES: Dict[str, str] = {
    # Open-Source AI Companies
    "fireworks": "Fireworks AI",
    "genesis": "Genesis AI",
    "livekit": "LiveKit",
    "physicalintelligence": "Physical Intelligence",
    "veniceai": "Venice.ai",
    "nousresearch": "Nous Research",
    "crewai": "CrewAI",
    "primeintellect": "Prime Intellect",
    "inferact": "Inferact (vLLM)",
    "langchain": "LangChain",
    "black-forest-labs": "Black Forest Labs",
    "supabase": "Supabase",
    "mistral": "Mistral AI",
    "ollama": "Ollama",
    "sesame": "Sesame",
    "e2b": "E2B",
    "mastra": "Mastra",
    "thinkingmachines": "Thinking Machines Lab",
    "dust": "Dust",
    "chainguard": "Chainguard",
    "roboflow": "Roboflow",
    "lightningai": "Lightning AI",
    "zilliz": "Zilliz",
    "togetherai": "Together AI",
    "fleek": "Fleek",
    "browserbase": "Browserbase",
    "liquid-ai": "Liquid AI",
    "airbyte": "Airbyte",
    # Frontier Labs & Enterprise Tech
    "scaleai": "Scale AI",
    "andurilindustries": "Anduril",
    "datadog": "Datadog",
    "cloudflare": "Cloudflare",
    "databricks": "Databricks",
    "benchling": "Benchling",
    "perplexity": "Perplexity",
    "cohere": "Cohere",
    "runway": "Runway",
}

# Y Combinator Work at a Startup - Public Algolia Index Endpoint
YC_ALGOLIA_CONFIG = {
    "app_id": "45BWZJ1S6Q",
    "api_key": "d00609a3cfb57a5ea285f5436ee680cc",
    "index_name": "Job_production",
    "url": "https://45bwzj1s6q-dsn.algolia.net/1/indexes/Job_production/query",
}

# Remote Job Aggregator Feeds
REMOTE_FEEDS = {
    "remoteok": "https://remoteok.com/api",
    "jobicy": "https://jobicy.com/api/v2/remote-jobs?count=50&industry=engineering",
}

# LinkedIn Guest Scraping Endpoint: Balanced across all 4 experience tiers + targeted AI scaleups
LINKEDIN_GUEST_CONFIG = {
    "base_url": "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search",
    "queries": [
        # 1. Internships & Campus
        {"keywords": "Software Engineer Intern", "location": "India"},
        {"keywords": "Software Engineering Intern", "location": "Remote"},
        # 2. Freshers & Early Career (0-2 YOE)
        {"keywords": "Graduate Engineer Trainee", "location": "India"},
        {"keywords": "Associate Software Engineer", "location": "India"},
        {"keywords": "SDE-1", "location": "India"},
        # 3. Mid-Level (2-5 YOE)
        {"keywords": "Software Engineer", "location": "India"},
        {"keywords": "Backend Engineer", "location": "Remote"},
        {"keywords": "Full Stack Engineer", "location": "India"},
        # 4. Senior & Staff (5+ YOE)
        {"keywords": "Senior Software Engineer", "location": "India"},
        {"keywords": "Senior Backend Engineer", "location": "Remote"},
        {"keywords": "Staff Engineer AI", "location": "Remote"},
        # 5. Targeted Open-Source AI Scaleups (without public open ATS REST APIs)
        {"keywords": "Qdrant", "location": "Remote"},
        {"keywords": "Daytona", "location": "Remote"},
        {"keywords": "Arcee AI", "location": "Remote"},
        {"keywords": "DeepInfra", "location": "Remote"},
        {"keywords": "Aiven", "location": "Remote"},
        {"keywords": "ByteFuture", "location": "Remote"},
        {"keywords": "Booster Robotics", "location": "Remote"},
    ],
    # f_TPR=r86400 restricts search to past 24 hours (86400 seconds)
    "time_filter": "r86400",
}

# Positive technical keywords for title filtering
TECHNICAL_ROLE_KEYWORDS: Set[str] = {
    "engineer",
    "developer",
    "software",
    "ai",
    "ml",
    "machine learning",
    "deep learning",
    "computer vision",
    "nlp",
    "genai",
    "llm",
    "agentic",
    "backend",
    "back-end",
    "frontend",
    "front-end",
    "fullstack",
    "full-stack",
    "data engineer",
    "distributed systems",
    "devops",
    "sre",
    "infrastructure",
    "architect",
    "intern",
    "internship",
    "trainee",
    "graduate",
    "get",
    "new grad",
    "fresher",
    "apprentice",
    "apprenticeship",
    "fellow",
    "fellowship",
    "junior",
    "associate",
    "sde-1",
    "sde 1",
    "sde-i",
    "sde i",
    "co-op",
    "campus",
    "entry level",
    "entry-level",
}

# Anti-scam heuristic blacklist (case-insensitive)
SCAM_BLACKLIST_KEYWORDS: List[str] = [
    "registration fee",
    "training deposit",
    "unpaid test assignment",
    "pay upfront",
    "processing fee",
    "security deposit",
    "crypto investment",
    "wire transfer",
    "pyramid scheme",
    "multi-level marketing",
    "buy equipment from us",
    "whatsapp only",
    "telegram only",
]

# Freshness window in seconds (24 hours)
FRESHNESS_WINDOW_SECONDS: int = 86400

# Per-request circuit breaker timeout in seconds
REQUEST_TIMEOUT_SECONDS: float = 8.0
