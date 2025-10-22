"""Custom exceptions for FloodMe backend."""


class BotDetectionError(Exception):
    """
    Raised when bot detection is encountered during scraping.

    This can include:
    - CAPTCHA challenges
    - Rate limiting errors (429)
    - Account suspensions
    - IP blocks
    - "Unusual activity" warnings
    """
    pass


class RateLimitError(BotDetectionError):
    """Raised when rate limiting (429) is encountered."""
    pass


class CaptchaError(BotDetectionError):
    """Raised when CAPTCHA challenge is detected."""
    pass


class AccountSuspendedError(BotDetectionError):
    """Raised when account is suspended or locked."""
    pass
