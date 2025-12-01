"""
Custom exceptions for the backend.
"""


class ScrapingError(Exception):
    """Base exception for scraping errors."""
    pass


class CaptchaError(ScrapingError):
    """Raised when a captcha is detected during scraping."""
    pass


class RateLimitError(ScrapingError):
    """Raised when rate limiting is detected during scraping."""
    pass


class BotDetectionError(ScrapingError):
    """Raised when bot detection is triggered during scraping."""
    pass
