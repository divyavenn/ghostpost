"""
Unified date parsing utilities for Twitter dates and timestamps.
"""

from datetime import datetime

try:
    from datetime import UTC
except ImportError:
    # Python <3.11 compatibility
    from datetime import timezone

    UTC = timezone.utc

from backend.config import TWITTER_API_DATE_FORMAT, TWITTER_LEGACY_DATE_FORMAT


def parse_twitter_date(date_str: str) -> datetime:
    """
    Parse Twitter date in any supported format.

    Tries formats in this order:
    1. ISO 8601 (Twitter API v2): "2024-01-15T10:30:45.000Z"
    2. Legacy Twitter v1: "Mon Jan 15 10:30:45 +0000 2024"

    Args:
        date_str: Date string from Twitter API

    Returns:
        datetime object (UTC timezone aware)
    """
    if not date_str:
        return now_utc()

    # Try ISO 8601 (Twitter API v2)
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        pass

    # Try Twitter API v2 format with explicit parsing
    try:
        return datetime.strptime(date_str, TWITTER_API_DATE_FORMAT).replace(
            tzinfo=UTC
        )
    except (ValueError, AttributeError):
        pass

    # Try Twitter v1 format
    try:
        return datetime.strptime(date_str, TWITTER_LEGACY_DATE_FORMAT)
    except (ValueError, AttributeError):
        pass

    # Fallback to now
    return now_utc()


def now_utc() -> datetime:
    """
    Get current UTC time.

    Replaces deprecated datetime.utcnow() with timezone-aware alternative.

    Returns:
        Current datetime in UTC timezone
    """
    return datetime.now(UTC)


def utc_iso_string() -> str:
    """
    Get current UTC time as ISO string with Z suffix.

    Returns ISO 8601 format: "2024-01-15T10:30:45.123456Z"

    Returns:
        ISO 8601 formatted timestamp string
    """
    return now_utc().isoformat() + "Z"


def timestamp_to_datetime(timestamp: float) -> datetime:
    """
    Convert Unix timestamp to timezone-aware datetime.

    Args:
        timestamp: Unix timestamp (seconds since epoch)

    Returns:
        datetime object (UTC timezone aware)
    """
    return datetime.fromtimestamp(timestamp, tz=UTC)
