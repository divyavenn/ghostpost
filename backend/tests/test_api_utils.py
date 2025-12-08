"""
Tests for rate_limiter.py - rate limiting, retry logic, and parallel execution.
"""
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.twitter.rate_limiter import (
    FunctionResponse,
    RateLimitConfig,
    RateLimiter,
    call_api,
    rate_limiter,
    TWITTER_SEARCH,
    TWITTER_TWEET_LOOKUP,
    LLM_OBELISK,
)


# =============================================================================
# RateLimitConfig Tests
# =============================================================================

class TestRateLimitConfig:
    """Test RateLimitConfig dataclass."""

    def test_min_interval_calculation(self):
        """Test that min_interval is calculated correctly."""
        # 60 requests per 15 minutes = 15 seconds between requests
        config = RateLimitConfig(requests_per_window=60, window_seconds=900)
        assert config.min_interval == 15.0

        # 300 requests per 15 minutes = 3 seconds between requests
        config = RateLimitConfig(requests_per_window=300, window_seconds=900)
        assert config.min_interval == 3.0

        # 100 requests per 24 hours
        config = RateLimitConfig(requests_per_window=100, window_seconds=86400)
        assert config.min_interval == 864.0

    def test_default_values(self):
        """Test default values are set correctly."""
        config = RateLimitConfig(requests_per_window=60)
        assert config.window_seconds == 900  # 15 minutes
        assert config.name == ""
        assert config.max_retries == 3
        assert config.base_delay == 1.0


# =============================================================================
# RateLimiter Tests
# =============================================================================

class TestRateLimiter:
    """Test RateLimiter class."""

    def test_add_bucket(self):
        """Test adding buckets to rate limiter."""
        limiter = RateLimiter()
        config = RateLimitConfig(60, name="test")
        limiter.add_bucket("test_bucket", config)

        assert "test_bucket" in limiter._configs
        assert "test_bucket" in limiter._locks
        assert limiter._last_request_times["test_bucket"] == 0

    @pytest.mark.asyncio
    async def test_wait_if_needed_no_config(self):
        """Test wait_if_needed returns immediately for unconfigured bucket."""
        limiter = RateLimiter()
        start = time.time()
        await limiter.wait_if_needed("nonexistent_bucket")
        elapsed = time.time() - start
        assert elapsed < 0.1  # Should return immediately

    @pytest.mark.asyncio
    async def test_wait_if_needed_first_request(self):
        """Test first request doesn't wait."""
        limiter = RateLimiter()
        limiter.add_bucket("test", RateLimitConfig(60, window_seconds=900))

        start = time.time()
        await limiter.wait_if_needed("test")
        elapsed = time.time() - start

        assert elapsed < 0.1  # First request should not wait

    @pytest.mark.asyncio
    async def test_wait_if_needed_respects_interval(self):
        """Test that subsequent requests wait for min_interval."""
        limiter = RateLimiter()
        # 10 requests per second = 0.1s interval
        limiter.add_bucket("test", RateLimitConfig(10, window_seconds=1))

        # First request
        await limiter.wait_if_needed("test", quiet=True)

        # Second request should wait ~0.1s
        start = time.time()
        await limiter.wait_if_needed("test", quiet=True)
        elapsed = time.time() - start

        assert elapsed >= 0.08  # Should wait close to 0.1s (with some tolerance)

    @pytest.mark.asyncio
    async def test_different_buckets_independent(self):
        """Test that different buckets don't affect each other's timing."""
        limiter = RateLimiter()
        # Slow bucket: 1 request per second
        limiter.add_bucket("slow", RateLimitConfig(1, window_seconds=1))
        # Fast bucket: 100 requests per second
        limiter.add_bucket("fast", RateLimitConfig(100, window_seconds=1))

        # Make request to slow bucket
        await limiter.wait_if_needed("slow", quiet=True)

        # Fast bucket should not be affected - should return immediately
        start = time.time()
        await limiter.wait_if_needed("fast", quiet=True)
        elapsed = time.time() - start

        assert elapsed < 0.05  # Fast bucket should not wait

    @pytest.mark.asyncio
    async def test_update_last_request(self):
        """Test update_last_request updates timestamp."""
        limiter = RateLimiter()
        limiter.add_bucket("test", RateLimitConfig(60))

        before = limiter._last_request_times["test"]
        limiter.update_last_request("test")
        after = limiter._last_request_times["test"]

        assert after > before


# =============================================================================
# Retry Logic Tests
# =============================================================================

class TestRetryLogic:
    """Test retry functionality."""

    @pytest.mark.asyncio
    async def test_call_with_retry_success_first_try(self):
        """Test successful call on first try."""
        limiter = RateLimiter()
        limiter.add_bucket("test", RateLimitConfig(100, window_seconds=1))

        call_count = 0

        async def mock_call():
            nonlocal call_count
            call_count += 1
            return FunctionResponse(success=True, data={"result": "ok"})

        result = await limiter.call_with_retry(mock_call, "test")

        assert result.success
        assert result.data == {"result": "ok"}
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_call_with_retry_retries_on_server_error(self):
        """Test that server errors (5xx) are retried."""
        limiter = RateLimiter()
        limiter.add_bucket("test", RateLimitConfig(100, window_seconds=1, max_retries=2, base_delay=0.01))

        call_count = 0

        async def mock_call():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return FunctionResponse(success=False, status_code=500, error_message="Server error", retryable=True)
            return FunctionResponse(success=True, data={"result": "ok"})

        result = await limiter.call_with_retry(mock_call, "test")

        assert result.success
        assert call_count == 3  # 2 failures + 1 success

    @pytest.mark.asyncio
    async def test_call_with_retry_no_retry_on_client_error(self):
        """Test that client errors (4xx) are not retried."""
        limiter = RateLimiter()
        limiter.add_bucket("test", RateLimitConfig(100, window_seconds=1, max_retries=3))

        call_count = 0

        async def mock_call():
            nonlocal call_count
            call_count += 1
            return FunctionResponse(success=False, status_code=400, error_message="Bad request", retryable=False)

        with patch("backend.twitter.rate_limiter.error") as mock_error:
            result = await limiter.call_with_retry(mock_call, "test")

        assert not result.success
        assert call_count == 1  # Should not retry
        # Error message gets wrapped in "Failed after X attempts" format
        assert "Bad request" in result.error_message

    @pytest.mark.asyncio
    async def test_call_with_retry_max_retries_exhausted(self):
        """Test behavior when max retries are exhausted."""
        limiter = RateLimiter()
        limiter.add_bucket("test", RateLimitConfig(100, window_seconds=1, max_retries=2, base_delay=0.01))

        call_count = 0

        async def mock_call():
            nonlocal call_count
            call_count += 1
            return FunctionResponse(success=False, status_code=500, error_message="Server error", retryable=True)

        with patch("backend.twitter.rate_limiter.error") as mock_error:
            result = await limiter.call_with_retry(mock_call, "test", username="test_user")

        assert not result.success
        assert call_count == 3  # Initial + 2 retries
        assert "Failed after 3 attempts" in result.error_message

        # Verify error was logged
        mock_error.assert_called_once()
        call_args = mock_error.call_args
        assert "test_user" in str(call_args)

    @pytest.mark.asyncio
    async def test_call_with_retry_handles_exceptions(self):
        """Test that exceptions are caught and retried."""
        limiter = RateLimiter()
        limiter.add_bucket("test", RateLimitConfig(100, window_seconds=1, max_retries=1, base_delay=0.01))

        call_count = 0

        async def mock_call():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Network error")
            return FunctionResponse(success=True, data="ok")

        result = await limiter.call_with_retry(mock_call, "test")

        assert result.success
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_call_with_retry_429_with_reset_header(self):
        """Test handling of 429 with rate limit reset header."""
        limiter = RateLimiter()
        limiter.add_bucket("test", RateLimitConfig(100, window_seconds=1, max_retries=2, base_delay=0.01))

        call_count = 0
        # Set reset time to 0.1 seconds from now
        reset_time = int(time.time()) + 1

        async def mock_call():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return FunctionResponse(
                    success=False,
                    status_code=429,
                    error_message="Rate limited",
                    rate_limit_reset=reset_time,
                    retryable=True
                )
            return FunctionResponse(success=True, data="ok")

        with patch.object(limiter, "wait_for_reset", new_callable=AsyncMock) as mock_wait:
            result = await limiter.call_with_retry(mock_call, "test")

        assert result.success
        assert call_count == 2
        mock_wait.assert_called_once_with(reset_time, "test")


# =============================================================================
# call_api Integration Tests
# =============================================================================

class TestCallApi:
    """Test call_api function with mocked HTTP responses."""

    @pytest.mark.asyncio
    async def test_call_api_success(self):
        """Test successful API call."""
        import requests as req_lib

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "success"}
        mock_response.headers = {}

        with patch.object(req_lib, "request", return_value=mock_response):
            result = await call_api(
                method="GET",
                url="https://api.example.com/test",
                bucket=LLM_OBELISK,
            )

        assert result.success
        assert result.data == {"data": "success"}
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_call_api_retry_on_failure(self):
        """Test that call_api retries on server errors."""
        import requests as req_lib

        call_count = 0

        def create_response(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_response = MagicMock()
            if call_count < 3:
                mock_response.status_code = 500
                mock_response.text = "Internal Server Error"
                mock_response.headers = {}
            else:
                mock_response.status_code = 200
                mock_response.json.return_value = {"data": "success"}
                mock_response.headers = {}
            return mock_response

        # Use a test bucket with fast retry
        test_limiter = RateLimiter()
        test_limiter.add_bucket("fast_test", RateLimitConfig(1000, window_seconds=1, max_retries=3, base_delay=0.01))

        with patch.object(req_lib, "request", side_effect=create_response):
            with patch("backend.twitter.rate_limiter.rate_limiter", test_limiter):
                result = await call_api(
                    method="GET",
                    url="https://api.example.com/test",
                    bucket="fast_test",
                )

        assert result.success
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_call_api_logs_error_after_max_retries(self):
        """Test that error is logged after max retries exhausted."""
        import requests as req_lib

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.headers = {}

        # Use a test bucket with limited retries
        test_limiter = RateLimiter()
        test_limiter.add_bucket("fail_test", RateLimitConfig(1000, window_seconds=1, max_retries=2, base_delay=0.01))

        with patch.object(req_lib, "request", return_value=mock_response):
            with patch("backend.twitter.rate_limiter.rate_limiter", test_limiter):
                with patch("backend.twitter.rate_limiter.error") as mock_error:
                    result = await call_api(
                        method="GET",
                        url="https://api.invalid.com/fail",
                        bucket="fail_test",
                        username="test_user",
                    )

        assert not result.success
        assert "Failed after 3 attempts" in result.error_message

        # Verify error was logged
        mock_error.assert_called_once()
        error_call = mock_error.call_args
        assert "test_user" in str(error_call)

    @pytest.mark.asyncio
    async def test_call_api_handles_timeout(self):
        """Test that timeouts are handled and retried."""
        import requests as req_lib

        call_count = 0

        def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise req_lib.exceptions.Timeout("Request timed out")
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": "success"}
            mock_response.headers = {}
            return mock_response

        test_limiter = RateLimiter()
        test_limiter.add_bucket("timeout_test", RateLimitConfig(1000, window_seconds=1, max_retries=2, base_delay=0.01))

        with patch.object(req_lib, "request", side_effect=mock_request):
            with patch("backend.twitter.rate_limiter.rate_limiter", test_limiter):
                result = await call_api(
                    method="GET",
                    url="https://api.example.com/slow",
                    bucket="timeout_test",
                )

        assert result.success
        assert call_count == 2


# =============================================================================
# Parallel Execution Tests
# =============================================================================

class TestParallelExecution:
    """Test that requests in different buckets execute in parallel."""

    @pytest.mark.asyncio
    async def test_different_buckets_run_in_parallel(self):
        """Test that requests to different buckets don't block each other."""
        limiter = RateLimiter()
        # Slow bucket: 1 request per 2 seconds
        limiter.add_bucket("slow", RateLimitConfig(1, window_seconds=2, max_retries=0))
        # Fast bucket: 100 requests per second
        limiter.add_bucket("fast", RateLimitConfig(100, window_seconds=1, max_retries=0))

        execution_times = {"slow": [], "fast": []}

        async def slow_call():
            execution_times["slow"].append(time.time())
            return FunctionResponse(success=True, data="slow")

        async def fast_call():
            execution_times["fast"].append(time.time())
            return FunctionResponse(success=True, data="fast")

        # Make first request to slow bucket to set its last_request_time
        await limiter.call_with_retry(slow_call, "slow")

        # Now run slow and fast requests concurrently
        start_time = time.time()

        results = await asyncio.gather(
            limiter.call_with_retry(slow_call, "slow"),  # Should wait ~2s
            limiter.call_with_retry(fast_call, "fast"),  # Should be immediate
            limiter.call_with_retry(fast_call, "fast"),  # Should be immediate
        )

        total_time = time.time() - start_time

        # All should succeed
        assert all(r.success for r in results)

        # Fast requests should have happened much sooner than slow
        # (within the first 0.1s, while slow waits for 2s)
        fast_times = execution_times["fast"]
        slow_times = execution_times["slow"]

        # The fast requests should complete before the slow request's wait is done
        # (slow request waits ~2s, fast requests should be nearly instant)
        assert len(fast_times) == 2
        assert len(slow_times) == 2  # Initial + the one in gather

        # Fast requests should start within 0.5s of start
        for ft in fast_times:
            assert ft - start_time < 0.5

    @pytest.mark.asyncio
    async def test_same_bucket_requests_are_serialized(self):
        """Test that requests to the same bucket wait for each other."""
        limiter = RateLimiter()
        # 2 requests per second = 0.5s between requests
        limiter.add_bucket("serial", RateLimitConfig(2, window_seconds=1, max_retries=0))

        execution_times = []

        async def tracked_call():
            execution_times.append(time.time())
            return FunctionResponse(success=True)

        # Make initial request
        await limiter.call_with_retry(tracked_call, "serial")

        # Make 3 more requests concurrently to the same bucket
        start_time = time.time()
        await asyncio.gather(
            limiter.call_with_retry(tracked_call, "serial"),
            limiter.call_with_retry(tracked_call, "serial"),
            limiter.call_with_retry(tracked_call, "serial"),
        )
        total_time = time.time() - start_time

        # Should take at least 1.5s (3 requests * 0.5s interval)
        # But allow some tolerance
        assert total_time >= 1.0  # At least 1 second for 3 requests with 0.5s spacing

    @pytest.mark.asyncio
    async def test_real_parallel_http_calls_different_buckets(self):
        """Test actual parallel execution with mocked HTTP calls."""
        import requests as req_lib

        call_times = {"bucket_a": [], "bucket_b": []}

        def mock_request(*args, **kwargs):
            # Record when each request was made
            url = kwargs.get("url", "")
            bucket = "bucket_a" if "bucket_a" in url else "bucket_b"
            call_times[bucket].append(time.time())
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"bucket": bucket}
            mock_response.headers = {}
            return mock_response

        # Create test buckets with different rates
        test_limiter = RateLimiter()
        test_limiter.add_bucket("bucket_a", RateLimitConfig(100, window_seconds=1, max_retries=0))
        test_limiter.add_bucket("bucket_b", RateLimitConfig(100, window_seconds=1, max_retries=0))

        with patch.object(req_lib, "request", side_effect=mock_request):
            with patch("backend.twitter.rate_limiter.rate_limiter", test_limiter):
                start = time.time()

                # Make parallel calls to different buckets
                results = await asyncio.gather(
                    call_api("GET", "https://api.example.com/bucket_a", "bucket_a"),
                    call_api("GET", "https://api.example.com/bucket_b", "bucket_b"),
                )

                elapsed = time.time() - start

        # Both should succeed
        assert all(r.success for r in results)

        # Both requests should have been made
        assert len(call_times["bucket_a"]) == 1
        assert len(call_times["bucket_b"]) == 1

        # Both requests should have started nearly simultaneously
        # (within 0.2s of each other - allowing for some async overhead)
        time_diff = abs(call_times["bucket_a"][0] - call_times["bucket_b"][0])
        assert time_diff < 0.2, f"Requests should start together, but diff was {time_diff}s"


# =============================================================================
# Global Rate Limiter Configuration Tests
# =============================================================================

class TestGlobalRateLimiter:
    """Test the pre-configured global rate limiter."""

    def test_twitter_buckets_configured(self):
        """Test that Twitter API buckets are configured."""
        assert TWITTER_SEARCH in rate_limiter._configs
        assert TWITTER_TWEET_LOOKUP in rate_limiter._configs

        search_config = rate_limiter._configs[TWITTER_SEARCH]
        assert search_config.requests_per_window == 60
        assert search_config.min_interval == 15.0  # 900/60

        tweet_config = rate_limiter._configs[TWITTER_TWEET_LOOKUP]
        assert tweet_config.requests_per_window == 300
        assert tweet_config.min_interval == 3.0  # 900/300

    def test_llm_bucket_configured(self):
        """Test that LLM bucket is configured."""
        assert LLM_OBELISK in rate_limiter._configs

        llm_config = rate_limiter._configs[LLM_OBELISK]
        assert llm_config.requests_per_window == 60
        assert llm_config.window_seconds == 60  # 1 minute
        assert llm_config.base_delay == 2.0  # Longer delay for LLM


# =============================================================================
# FunctionResponse Tests
# =============================================================================

class TestFunctionResponse:
    """Test FunctionResponse dataclass."""

    def test_success_response(self):
        """Test creating a success response."""
        response = FunctionResponse(success=True, data={"key": "value"}, status_code=200)
        assert response.success
        assert response.data == {"key": "value"}
        assert response.status_code == 200
        assert response.error_message is None

    def test_error_response(self):
        """Test creating an error response."""
        response = FunctionResponse(
            success=False,
            status_code=500,
            error_message="Server error",
            retryable=True
        )
        assert not response.success
        assert response.status_code == 500
        assert response.error_message == "Server error"
        assert response.retryable

    def test_rate_limit_response(self):
        """Test creating a rate limit response with reset time."""
        reset_time = int(time.time()) + 300
        response = FunctionResponse(
            success=False,
            status_code=429,
            error_message="Rate limited",
            rate_limit_reset=reset_time,
            retryable=True
        )
        assert response.status_code == 429
        assert response.rate_limit_reset == reset_time
