"""
Centralized rate limiter + retry layer for API calls or any function.


API rate limits only apply to same kinds of request. So searches + user lookups in Twitter 
can happen in parallel, even though two searches need to be spaced out.
Also, obviously requests to different servers don't need to wait on each other.

The solution to this is having "buckets." Requests in a bucket are spaced out according 
to the bucket's rate, but requests in different buckets can happen at the same time.

Also, if a request fails, this takes care of retrying according to the following rules:
    - 429 (rate limit): waits for x-rate-limit-reset header or exponential backoff
    - 5xx (server error): retries with exponential backoff
    - 401/4xx (client error): fails immediately (not retryable)
    - After max retries: logs error via error() function
Usage:
    from backend.twitter.rate_limiter import call_api, LLM_OBELISK, TWITTER_SEARCH

    # HTTP request with rate limiting and retry
    response = await call_api(
        method="POST",
        url="https://api.example.com/endpoint",
        bucket=LLM_OBELISK,
        headers={"Authorization": "Bearer ..."},
        json_data={"prompt": "hello"},
        username="user123"
    )

    if response.success:
        data = response.data
    else:
        print(f"Failed: {response.error_message}")

Configured buckets:
    - TWITTER_* buckets: No local throttling - Twitter API enforces limits via 429
    - LLM_OBELISK: 60 req/min (time throttled) - Now using OpenAI with DIVYA fine-tuned model
    - LLM_GEMINI: 60 req/min (time throttled)
    - LLM_CLAUDE: 60 req/min (time throttled)


"""
import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from backend.utlils.utils import error, notify

T = TypeVar("T")


@dataclass
class RateLimitConfig:
    """Configuration for a rate limit bucket."""
    window_seconds: int = 15 * 60  # 15 minutes default
    requests_per_window: int | None = None  # Optional: if set, enforces time-based throttling
    name: str = ""  # Display name for logging
    max_retries: int = 3  # Default max retries for this bucket
    base_delay: float = 1.0  # Base delay for exponential backoff
    # Optional quota tracking (for cumulative limits like daily post caps)
    user_quota_per_window: int | None = None  # Max requests per user in window (e.g., 100 posts/day)
    app_quota_per_window: int | None = None   # Max requests for entire app in window (e.g., 1667 posts/day)

    @property
    def min_interval(self) -> float:
        """
        Minimum seconds between requests.

        If requests_per_window is None, returns 0 (no time throttling).
        Otherwise, enforces time-based spacing.
        """
        if self.requests_per_window is None:
            return 0  # No time throttling
        return self.window_seconds / self.requests_per_window


@dataclass
class FunctionResponse:
    """Wrapper for function responses to handle both success and failure cases."""
    success: bool
    data: Any = None
    status_code: int | None = None
    error_message: str | None = None
    rate_limit_reset: int | None = None  # Unix timestamp for 429 responses
    retryable: bool = True  # Whether this error can be retried


class RateLimiter:
    """
    Generic rate limiter supporting multiple independent buckets.

    Each bucket has its own rate limit - requests to different buckets
    can happen simultaneously without affecting each other.

    Usage:
        limiter = RateLimiter()
        limiter.add_bucket("search", RateLimitConfig(60, name="search"))
        limiter.add_bucket("tweets", RateLimitConfig(300, name="tweets"))

        await limiter.wait_if_needed("search")
        # make request...
        limiter.update_last_request("search")
    """

    def __init__(self):
        self._configs: dict[str, RateLimitConfig] = {}
        self._last_request_times: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._rate_limit_reset_times: dict[str, int] = {}  # Track when rate limits reset
        # Quota tracking: store timestamps of requests in sliding window
        self._user_request_history: dict[str, dict[str, list[float]]] = {}  # {bucket: {username: [timestamps]}}
        self._app_request_history: dict[str, list[float]] = {}  # {bucket: [timestamps]}

    def add_bucket(self, bucket: str, config: RateLimitConfig):
        """Add a rate limit bucket."""
        self._configs[bucket] = config
        self._last_request_times[bucket] = 0
        self._locks[bucket] = asyncio.Lock()
        # Initialize quota tracking if enabled
        if config.user_quota_per_window is not None:
            self._user_request_history[bucket] = {}
        if config.app_quota_per_window is not None:
            self._app_request_history[bucket] = []

    def _cleanup_old_requests(self, bucket: str, window_seconds: int):
        """Remove request timestamps older than the window."""
        now = time.time()
        cutoff = now - window_seconds

        # Clean up user request history
        if bucket in self._user_request_history:
            for username in list(self._user_request_history[bucket].keys()):
                # Filter out old timestamps
                self._user_request_history[bucket][username] = [
                    ts for ts in self._user_request_history[bucket][username] if ts > cutoff
                ]
                # Remove empty user entries
                if not self._user_request_history[bucket][username]:
                    del self._user_request_history[bucket][username]

        # Clean up app request history
        if bucket in self._app_request_history:
            self._app_request_history[bucket] = [
                ts for ts in self._app_request_history[bucket] if ts > cutoff
            ]

    def _check_quota(self, bucket: str, username: str | None) -> tuple[bool, str | None, int | None]:
        """
        Check if request would exceed per-user or per-app quota.

        Returns:
            (can_proceed, error_message, reset_timestamp)
            reset_timestamp is when the oldest request expires (quota will be available)
        """
        config = self._configs.get(bucket)
        if not config:
            return True, None, None

        # Clean up old requests first
        self._cleanup_old_requests(bucket, config.window_seconds)

        # Check per-user quota
        if config.user_quota_per_window is not None and username:
            if bucket in self._user_request_history:
                user_requests = self._user_request_history[bucket].get(username, [])
                if len(user_requests) >= config.user_quota_per_window:
                    # Calculate when oldest request will expire
                    oldest_request = min(user_requests)
                    reset_time = int(oldest_request + config.window_seconds)
                    return False, f"User {username} has exceeded quota: {len(user_requests)}/{config.user_quota_per_window} in {config.window_seconds}s window", reset_time

        # Check per-app quota
        if config.app_quota_per_window is not None:
            if bucket in self._app_request_history:
                app_requests = self._app_request_history[bucket]
                if len(app_requests) >= config.app_quota_per_window:
                    # Calculate when oldest request will expire
                    oldest_request = min(app_requests)
                    reset_time = int(oldest_request + config.window_seconds)
                    return False, f"App has exceeded quota: {len(app_requests)}/{config.app_quota_per_window} in {config.window_seconds}s window", reset_time

        return True, None, None

    def _record_request(self, bucket: str, username: str | None):
        """Record a request for quota tracking."""
        now = time.time()
        config = self._configs.get(bucket)
        if not config:
            return

        # Record for per-user quota
        if config.user_quota_per_window is not None and username:
            if bucket in self._user_request_history:
                if username not in self._user_request_history[bucket]:
                    self._user_request_history[bucket][username] = []
                self._user_request_history[bucket][username].append(now)

        # Record for per-app quota
        if config.app_quota_per_window is not None:
            if bucket in self._app_request_history:
                self._app_request_history[bucket].append(now)

    async def wait_if_needed(self, bucket: str, username: str | None = None, quiet: bool = False, max_quota_wait: int = 300):
        """
        Wait if we need to respect the rate limit for this bucket.

        Args:
            bucket: The bucket name
            username: Username for per-user quota tracking (optional)
            quiet: If True, don't log the wait message
            max_quota_wait: Maximum seconds to wait for quota to become available (default: 5 minutes)
        """
        if bucket not in self._configs:
            return  # No rate limit configured for this bucket

        config = self._configs[bucket]
        min_interval = config.min_interval
        display_name = config.name or bucket

        async with self._locks[bucket]:
            # Check per-user and per-app quotas
            can_proceed, quota_error, quota_reset_time = self._check_quota(bucket, username)
            if not can_proceed and quota_reset_time:
                now = time.time()
                wait_time = quota_reset_time - now

                if wait_time <= max_quota_wait:
                    # Wait time is reasonable - wait until quota available
                    if not quiet:
                        notify(f"⏳ LOCAL quota limit reached ({display_name}): {quota_error}")
                        notify(f"   Waiting {wait_time:.0f}s ({wait_time/60:.1f}min) until quota window resets...")
                    await asyncio.sleep(wait_time)
                    # After waiting, clean up and continue (quota should be available now)
                    self._cleanup_old_requests(bucket, config.window_seconds)
                else:
                    # Wait time is too long - set reset time and raise exception
                    # The retry logic will handle this with wait_for_reset
                    self._rate_limit_reset_times[bucket] = quota_reset_time
                    notify(f"⚠️ LOCAL quota limit reached ({display_name}): {quota_error}")
                    notify(f"   Wait time too long ({wait_time/3600:.1f} hours) - will retry after window resets")
                    from backend.utlils.utils import error
                    error(f"{quota_error} - reset in {wait_time:.0f}s", status_code=429,
                          function_name="wait_if_needed", username=username or "unknown", critical=False)
                    raise Exception(f"{quota_error} - quota resets in {wait_time/3600:.1f} hours")

            now = time.time()

            # Check if we're in a rate-limited state (from a 429 response or quota exceeded)
            if bucket in self._rate_limit_reset_times:
                reset_time = self._rate_limit_reset_times[bucket]
                if now < reset_time:
                    # Still rate limited - wait until reset
                    wait_time = reset_time - now
                    if not quiet:
                        notify(f"⚠️ Twitter API 429 response ({display_name}): waiting {wait_time:.0f}s ({wait_time/60:.1f}min) until reset...")
                    await asyncio.sleep(wait_time)
                # Clear the reset time after waiting (or if it's already expired)
                self._rate_limit_reset_times.pop(bucket, None)

            # Also enforce minimum interval between requests
            elapsed = now - self._last_request_times[bucket]
            if elapsed < min_interval:
                wait_time = min_interval - elapsed
                if not quiet:
                    notify(f"⏳ Rate limiting ({display_name}): waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)

            self._last_request_times[bucket] = time.time()

            # Record this request for quota tracking
            self._record_request(bucket, username)

    def update_last_request(self, bucket: str):
        """Update the last request timestamp for a bucket."""
        if bucket in self._last_request_times:
            self._last_request_times[bucket] = time.time()

    async def wait_for_reset(self, reset_timestamp: int, bucket: str):
        """
        Wait until the rate limit resets (from 429 response header).

        Args:
            reset_timestamp: Unix timestamp when the rate limit resets
            bucket: The bucket that was rate limited
        """
        display_name = self._configs.get(bucket, RateLimitConfig(0)).name or bucket
        now = int(time.time())
        wait_seconds = max(1, reset_timestamp - now + 1)  # +1 for safety

        # Store the reset time so other concurrent calls know we're rate limited
        # Acquire lock briefly to set the shared state
        async with self._locks[bucket]:
            self._rate_limit_reset_times[bucket] = reset_timestamp

        notify(f"⚠️ Rate limited ({display_name}). Waiting {wait_seconds}s ({wait_seconds // 60}min) before retry...")
        await asyncio.sleep(wait_seconds)

        # Clear the reset time after waiting
        # Acquire lock again to modify shared state
        async with self._locks[bucket]:
            self._rate_limit_reset_times.pop(bucket, None)
            self._last_request_times[bucket] = time.time()

    async def call_with_retry(
        self,
        api_call: Callable[[], FunctionResponse],
        bucket: str,
        max_retries: int | None = None,
        username: str = "unknown",
        quiet: bool = False,
    ) -> FunctionResponse:
        """
        Execute an API call with rate limiting and retry logic.

        Args:
            api_call: Async callable that returns FunctionResponse
            bucket: Rate limit bucket name
            max_retries: Override default max retries for this bucket
            username: Username for error logging
            quiet: If True, don't log rate limit waits

        Returns:
            FunctionResponse with success/failure status
        """
        config = self._configs.get(bucket)
        if not config:
            # No rate limit configured, just execute the call
            return await api_call()

        retries = max_retries if max_retries is not None else config.max_retries
        display_name = config.name or bucket
        base_delay = config.base_delay
        last_error: str | None = None

        for attempt in range(retries + 1):
            # Wait for rate limit before making request
            await self.wait_if_needed(bucket, username=username, quiet=quiet)

            try:
                response = await api_call()

                if response.success:
                    return response

                # Handle rate limit (429) specially
                if response.status_code == 429:
                    if response.rate_limit_reset and attempt < retries:
                        await self.wait_for_reset(response.rate_limit_reset, bucket)
                        continue
                    elif attempt < retries:
                        # No reset time, use exponential backoff
                        wait_time = base_delay * (2 ** attempt)
                        notify(f"⚠️ Rate limited ({display_name}), retrying in {wait_time:.1f}s...")
                        await asyncio.sleep(wait_time)
                        continue

                # Handle other retryable errors
                if response.retryable and attempt < retries:
                    wait_time = base_delay * (2 ** attempt)
                    notify(f"⚠️ API error ({display_name}): {response.error_message}, retrying in {wait_time:.1f}s...")
                    await asyncio.sleep(wait_time)
                    last_error = response.error_message
                    continue

                # Non-retryable error or out of retries
                last_error = response.error_message
                break

            except Exception as e:
                last_error = str(e)
                if attempt < retries:
                    wait_time = base_delay * (2 ** attempt)
                    notify(f"⚠️ Exception ({display_name}): {e}, retrying in {wait_time:.1f}s...")
                    await asyncio.sleep(wait_time)
                    continue
                break

        # All retries exhausted - log error
        error(
            f"API call failed after {retries + 1} attempts ({display_name}): {last_error}",
            status_code=500,
            function_name="call_with_retry",
            username=username,
            critical=False
        )

        return FunctionResponse(
            success=False,
            error_message=f"Failed after {retries + 1} attempts: {last_error}",
            retryable=False
        )


# =============================================================================
# Bucket name constants
# =============================================================================

# Twitter API buckets
TWITTER_SEARCH = "twitter_search"
TWITTER_TWEET_LOOKUP = "twitter_tweet_lookup"
TWITTER_HOME_TIMELINE = "twitter_home_timeline"
TWITTER_USER_TIMELINE = "twitter_user_timeline"
TWITTER_USER_MENTIONS = "twitter_user_mentions"
TWITTER_USER_LOOKUP = "twitter_user_lookup"
TWITTER_POST = "twitter_post"

# LLM API buckets
LLM_OBELISK = "llm_obelisk"
LLM_GEMINI = "llm_gemini"
LLM_CLAUDE = "llm_claude"


def create_rate_limiter() -> RateLimiter:
    """Create a rate limiter pre-configured for all API endpoints.

    Rate limits from X API Basic tier (https://docs.x.com/x-api/fundamentals/rate-limits):
    Per User Auth (OAuth):
    - Search (GET /2/tweets/search/recent): 60 req / 15 min
    - Tweet Lookup (GET /2/tweets): 15 req / 15 min
    - User Timeline (GET /2/users/:id/tweets): 5 req / 15 min
    - Home Timeline (GET /2/users/:id/timelines/reverse_chronological): 5 req / 15 min
    - User Mentions (GET /2/users/:id/mentions): 10 req / 15 min
    - User Lookup (GET /2/users/by/username/:username): 100 req / 24 hours
    - Post Tweet (POST /2/tweets): 100 req / 24 hours per user, 1667 req / 24 hours per app

    Uses quota tracking to enforce both per-user and per-app limits.
    """
    limiter = RateLimiter()

    # Twitter API - Throttled endpoints (per 15-minute window) - Basic Tier
    # Using quota tracking to enforce limits
    limiter.add_bucket(TWITTER_SEARCH, RateLimitConfig(
        window_seconds=15 * 60,
        name="Twitter Search",
        user_quota_per_window=60,   # 60 requests per user per 15 min
        app_quota_per_window=60     # 60 requests per app per 15 min
    ))
    limiter.add_bucket(TWITTER_TWEET_LOOKUP, RateLimitConfig(
        window_seconds=15 * 60,
        name="Twitter Tweet Lookup",
        user_quota_per_window=15,   # 15 requests per user per 15 min
        app_quota_per_window=15     # 15 requests per app per 15 min
    ))
    limiter.add_bucket(TWITTER_HOME_TIMELINE, RateLimitConfig(
        window_seconds=15 * 60,
        name="Twitter Home Timeline",
        user_quota_per_window=5,    # 5 requests per user per 15 min
        app_quota_per_window=None   # No per-app limit documented
    ))
    limiter.add_bucket(TWITTER_USER_TIMELINE, RateLimitConfig(
        window_seconds=15 * 60,
        name="Twitter User Timeline",
        user_quota_per_window=5,    # 5 requests per user per 15 min
        app_quota_per_window=10     # 10 requests per app per 15 min
    ))
    limiter.add_bucket(TWITTER_USER_MENTIONS, RateLimitConfig(
        window_seconds=15 * 60,
        name="Twitter User Mentions",
        user_quota_per_window=10,   # 10 requests per user per 15 min
        app_quota_per_window=15     # 15 requests per app per 15 min
    ))

    # Twitter API - Daily quota endpoints - Basic Tier
    # Using quota tracking to enforce limits
    limiter.add_bucket(TWITTER_USER_LOOKUP, RateLimitConfig(
        window_seconds=24 * 60 * 60,  # 24 hour window
        name="Twitter User Lookup",
        user_quota_per_window=100,  # 100 requests per user per 24 hours
        app_quota_per_window=500    # 500 requests per app per 24 hours
    ))

    # Post Tweet - uses quota tracking for per-user and per-app limits
    # Basic tier: 100 posts/24hr per user, 1667 posts/24hr per app
    limiter.add_bucket(TWITTER_POST, RateLimitConfig(
        window_seconds=24 * 60 * 60,  # 24 hour window
        name="Twitter Post",
        max_retries=2,
        user_quota_per_window=100,   # 100 posts per user per 24 hours
        app_quota_per_window=1667    # 1667 posts per app per 24 hours
    ))

    # LLM API endpoints (generous limits - adjust as needed)
    # Using time-based throttling for LLMs (no quota tracking needed)
    limiter.add_bucket(LLM_OBELISK, RateLimitConfig(
        window_seconds=60,  # 1 minute window
        requests_per_window=60,  # 60 requests per minute
        name="OpenAI (DIVYA) LLM",
        max_retries=0,  # No retries - fail fast and fallback to Claude
        base_delay=2.0  # Longer base delay for LLM calls
    ))
    limiter.add_bucket(LLM_GEMINI, RateLimitConfig(
        window_seconds=60,  # 1 minute window
        requests_per_window=60,  # 60 requests per minute
        name="Gemini LLM",
        max_retries=3,
        base_delay=2.0  # Longer base delay for LLM calls
    ))
    limiter.add_bucket(LLM_CLAUDE, RateLimitConfig(
        window_seconds=60,  # 1 minute window
        requests_per_window=60,  # 60 requests per minute
        name="Claude LLM",
        max_retries=3,
        base_delay=2.0  # Longer base delay for LLM calls
    ))

    return limiter


# Global rate limiter instance (use for all API calls)
rate_limiter = create_rate_limiter()

# Backwards compatibility alias
twitter_rate_limiter = rate_limiter


# =============================================================================
# Backwards compatibility - EndpointType enum (deprecated, use bucket strings)
# =============================================================================

class EndpointType:
    """Backwards compatibility - use TWITTER_* bucket constants instead."""
    SEARCH = TWITTER_SEARCH
    TWEET_LOOKUP = TWITTER_TWEET_LOOKUP
    USER_LOOKUP = TWITTER_USER_LOOKUP
    HOME_TIMELINE = TWITTER_HOME_TIMELINE
    USER_TIMELINE = TWITTER_USER_TIMELINE
    USER_MENTIONS = TWITTER_USER_MENTIONS


# =============================================================================
# Helper functions for common patterns
# =============================================================================

async def call_api(
    method: str,
    url: str,
    bucket: str,
    headers: dict | None = None,
    params: dict | None = None,
    json_data: dict | None = None,
    data: dict | None = None,
    timeout: int = 30,
    username: str = "unknown",
    max_retries: int | None = None,
) -> FunctionResponse:
    """
    Make an HTTP request with rate limiting and retry logic.

    This is a convenience function that wraps requests library calls.

    Args:
        method: HTTP method (GET, POST, DELETE, etc.)
        url: Request URL
        bucket: Rate limit bucket name
        headers: Request headers
        params: Query parameters
        json_data: JSON body data
        data: Form data
        timeout: Request timeout in seconds
        username: Username for error logging
        max_retries: Override default max retries

    Returns:
        FunctionResponse with success status and data
    """
    import requests

    async def do_request() -> FunctionResponse:
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_data,
                data=data,
                timeout=timeout
            )

            # Check for rate limit
            if response.status_code == 429:
                reset_time = response.headers.get("x-rate-limit-reset")
                return FunctionResponse(
                    success=False,
                    status_code=429,
                    error_message="Rate limited",
                    rate_limit_reset=int(reset_time) if reset_time else None,
                    retryable=True
                )

            # Check for auth errors (not retryable)
            if response.status_code == 401:
                return FunctionResponse(
                    success=False,
                    status_code=401,
                    error_message="Authentication required",
                    retryable=False
                )

            # Check for other client errors (not retryable)
            if 400 <= response.status_code < 500:
                return FunctionResponse(
                    success=False,
                    status_code=response.status_code,
                    error_message=response.text,
                    retryable=False
                )

            # Server errors are retryable
            if response.status_code >= 500:
                return FunctionResponse(
                    success=False,
                    status_code=response.status_code,
                    error_message=response.text,
                    retryable=True
                )

            # Success
            try:
                response_data = response.json()
            except Exception:
                response_data = response.text

            return FunctionResponse(
                success=True,
                data=response_data,
                status_code=response.status_code
            )

        except requests.exceptions.Timeout:
            return FunctionResponse(
                success=False,
                error_message="Request timed out",
                retryable=True
            )
        except requests.exceptions.ConnectionError as e:
            return FunctionResponse(
                success=False,
                error_message=f"Connection error: {e}",
                retryable=True
            )
        except requests.exceptions.RequestException as e:
            return FunctionResponse(
                success=False,
                error_message=f"Request error: {e}",
                retryable=True
            )

    return await rate_limiter.call_with_retry(
        do_request,
        bucket=bucket,
        max_retries=max_retries,
        username=username
    )


