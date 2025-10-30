"""
Central configuration for the application.
All configuration variables should be defined here.
"""
import os
from pathlib import Path
import dotenv

# Load .env file from backend/ directory (one level up from backend/backend/)
dotenv.load_dotenv(Path(__file__).resolve().parent.parent / '.env')

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

# Session timeout for browser sessions (seconds)
SESSION_TIMEOUT = 300

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
TWITTER_BEARER_TOKEN = os.getenv(
    "TWITTER_BEARER_TOKEN",
    r"AAAAAAAAAAAAAAAAAAAAAJHRxQEAAAAAB%2F567wfymD1OQyW8C4MXhUX8t4c%3DZn9FSzsz31UhfpTQN10YRMHQHRuMqsGYjPFYFxUJXVezuuZuPi"
)

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

# =============================================================================
# EMAIL CONFIGURATION
# =============================================================================
# Email settings for developer notifications
DEV_EMAIL = os.getenv("DEV_EMAIL")
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

# =============================================================================
# SCRAPING CONFIGURATION
# =============================================================================
# Default maximum tweets to retrieve per user or query
DEFAULT_MAX_TWEETS_RETRIEVE = 30

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
