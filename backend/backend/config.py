"""
Central configuration for the application.
All configuration variables should be defined here.
"""
import os
from pathlib import Path

import dotenv

# Load .env file from backend/ directory (one level up from backend/backend/)
dotenv.load_dotenv(Path(__file__).resolve().parent.parent / '.env')


def _get_int_env(name: str, default: int) -> int:
    """Read an integer env var with safe fallback."""
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default

# =============================================================================
# PATHS
# =============================================================================
BACKEND_DIR = Path(__file__).resolve().parent
CACHE_DIR = BACKEND_DIR.parent / "cache"
ARCHIVE_DIR = CACHE_DIR / "archive"

# File paths
BROWSER_STATE_FILE = CACHE_DIR / "storage_state.json"
TOKEN_FILE = CACHE_DIR / "tokens.json"
USER_INFO_FILE = CACHE_DIR / "user_info.json"

SHOW_BROWSER = False

# Debug: Log prompts sent to LLM to text files
LOG_PROMPTS = os.getenv("LOG_PROMPTS", "false").lower() == "true"
PROMPTS_LOG_DIR = CACHE_DIR / "prompts"

# Session timeout for browser sessions (seconds)
SESSION_TIMEOUT = 300

# =============================================================================
# TOKEN AND SESSION MANAGEMENT
# =============================================================================
# Buffer time for token expiration checks (seconds)
TOKEN_EXPIRY_BUFFER_SECONDS = 60
# Session validation timeout (milliseconds)
SESSION_VALIDATION_TIMEOUT_MS = 10000
# Cookie validity check buffer (seconds)
COOKIE_VALIDITY_BUFFER_SECONDS = 60

# =============================================================================
# TWITTER API CONFIGURATION
# =============================================================================
# Twitter OAuth credentials (from environment variables)
TWITTER_CLIENT_ID = os.getenv("TWITTER_CLIENT_ID")
TWITTER_CLIENT_SECRET = os.getenv("TWITTER_CLIENT_SECRET")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# Twitter API endpoints
TWITTER_API_BASE_URL = "https://api.x.com/2"
TWITTER_API_V2_BASE = "https://api.twitter.com/2"

# Twitter bearer token for API requests
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN", r"AAAAAAAAAAAAAAAAAAAAAJHRxQEAAAAAB%2F567wfymD1OQyW8C4MXhUX8t4c%3DZn9FSzsz31UhfpTQN10YRMHQHRuMqsGYjPFYFxUJXVezuuZuPi")

# Auth cookie name
AUTH_COOKIE = "auth_token"

# =============================================================================
# BROWSERBASE CONFIGURATION
# =============================================================================
BROWSERBASE_API_KEY = os.getenv("BROWSERBASE_API_KEY")
BROWSERBASE_PROJECT_ID = os.getenv("BROWSERBASE_PROJECT_ID")

# Whether to use Browserbase for scraping instead of local browser
# Can be overridden by USE_BROWSERBASE_FOR_SCRAPING environment variable
USE_BROWSERBASE_FOR_SCRAPING = False

# =============================================================================
# AI/LLM CONFIGURATION
# =============================================================================
OBELISK_KEY = os.getenv("OBELISK_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME")

# =============================================================================
# SUPABASE CONFIGURATION
# =============================================================================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")
SUPABASE_JWT_KEY = os.getenv("SUPABASE_JWT_KEY")  # From Supabase Dashboard > Settings > API > JWT Signing Key

# =============================================================================
# STRIPE BILLING CONFIGURATION
# =============================================================================
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
STRIPE_PAID_PRICE_ID = os.getenv("STRIPE_PAID_PRICE_ID")  # Price ID for $30/month paid tier
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# =============================================================================
# EMAIL CONFIGURATION
# =============================================================================
# Email settings for developer notifications
DEV_EMAIL = os.getenv("DEV_EMAIL")
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = _get_int_env("SMTP_PORT", 587)
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

# =============================================================================
# SCRAPING CONFIGURATION
# =============================================================================
# Default maximum tweets to retrieve per user or query
DEFAULT_MAX_TWEETS_RETRIEVE = 30

# Maximum age of tweets to scrape and retain (in hours)
# Used for:
# - Filtering tweets during scraping
# - Cleaning up old cached tweets
# - Purging old seen_tweets entries
MAX_TWEET_AGE_HOURS = 48

# Minimum impressions threshold for tweet discovery
MIN_IMPRESSIONS_FOR_DISCOVERY = 2000
MIN_IMPRESSIONS_FOR_TIMELINE = 0  # No threshold for user's own timeline

# Default Twitter credentials for scraping (if needed)
# Note: These should ideally come from environment variables
DEFAULT_TWITTER_USERNAME = "proudlurker"
DEFAULT_TWITTER_PASSWORD = r"JXJ-pfd3bdv*myu0whb"

# Default search queries (can be overridden per user)
DEFAULT_QUERIES = [
    "cursor pointer bug",
]

# Default usernames to scrape (can be overridden per user)
DEFAULT_USERNAMES = ["divya_venn"]

# Test user for unit tests (must have saved browser state)
TEST_USER = "divya_venn"

# =============================================================================
# MONITORING STATE CONFIGURATION
# =============================================================================
# Thresholds for tweet monitoring state transitions
ACTIVE_MAX_AGE_HOURS = 12      # After this, tweet becomes "warm"
WARM_MAX_AGE_DAYS = 3          # After this + inactivity, tweet becomes "cold"
INACTIVITY_TO_COLD_HOURS = 24  # No activity for this long -> "cold"
HARDCUTOFF_COLD_DAYS = 7       # Beyond this age, always treat as "cold"

# Activity threshold for promotion back to "active"
ACTIVITY_PROMOTION_THRESHOLD = 5  # New replies needed to promote to "active"

# =============================================================================
# DATE FORMAT CONSTANTS
# =============================================================================
# Twitter API v2 date format (ISO 8601)
TWITTER_API_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
# Twitter v1 API legacy date format
TWITTER_LEGACY_DATE_FORMAT = "%a %b %d %H:%M:%S %z %Y"
