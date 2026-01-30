"""
Bread Account Context Manager

Manages browser sessions for bread (burner) Twitter accounts used for automated scraping.
Creates persistent browser contexts that are reused throughout a job's lifecycle.
"""
import random
from typing import Any

from playwright.async_api import Browser, BrowserContext, Playwright, async_playwright

from backend.browser_management.context import cleanup_browser_resources
from backend.twitter.bread_accounts import BREAD_ACCOUNTS
from backend.utlils.utils import notify, read_browser_state


class BreadAccountContext:
    """
    Context manager for bread account browser automation.

    Creates and manages a persistent Playwright browser + context for the entire
    job lifecycle. Handles account selection, session restoration, auto-login,
    and account rotation on failure.

    Usage:
        async with BreadAccountContext("username") as bread_ctx:
            # bread_ctx.context is the Playwright browser context
            await some_scraping_function(ctx=bread_ctx.context, ...)
    """

    def __init__(self, username: str, force_account: tuple[str, str] | None = None):
        """
        Initialize bread account context for a user.

        Args:
            username: The actual user's username (for data routing, not authentication)
            force_account: Optional (username, password) tuple to use specific account
                          (allocated by bread account manager)
        """
        self.user_username = username      # User for data routing
        self.force_account = force_account # Forced account from manager (if any)
        self.bread_username: str | None = None         # Selected bread account username
        self.bread_password: str | None = None         # Selected bread account password
        self.playwright: Playwright | None = None      # Playwright instance
        self.browser: Browser | None = None            # Browser instance
        self.context: BrowserContext | None = None     # Browser context (passed to scraping functions)
        self.attempted_accounts: set[str] = set()      # Track failed accounts

    async def __aenter__(self):
        """
        Enter context manager - select bread account and create browser session.

        Returns:
            self (with initialized browser context)
        """
        # 1. Random selection from BREAD_ACCOUNTS
        await self._select_bread_account()

        # 2. Launch Playwright browser (headless for production)
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,  # Headless mode for production
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
            ]
        )

        # 3. Try to restore saved browser state
        await self._ensure_bread_session()

        notify(f"🍞 Bread account context ready: {self.bread_username} (for user {self.user_username})")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Exit context manager - cleanup browser resources.
        """
        notify(f"🧹 Cleaning up bread account browser session: {self.bread_username}")
        await cleanup_browser_resources(self.playwright, self.browser, self.context)

    async def _select_bread_account(self):
        """Select bread account - use forced account if provided, otherwise random."""
        # Use forced account from manager if provided
        if self.force_account:
            self.bread_username = self.force_account[0]
            self.bread_password = self.force_account[1]
            self.attempted_accounts.add(self.bread_username)
            notify(f"🎯 [Bread Context] Using allocated account: {self.bread_username}")
            return

        # Fallback: Random selection (for backward compatibility)
        if not BREAD_ACCOUNTS:
            from backend.utlils.utils import error
            error("No bread accounts configured", status_code=500, function_name="_select_bread_account", critical=True)
            raise RuntimeError("No bread accounts available")

        # Filter out already attempted accounts
        available_accounts = [
            acc for acc in BREAD_ACCOUNTS
            if acc[0] not in self.attempted_accounts
        ]

        if not available_accounts:
            # All accounts have been tried
            from backend.utlils.utils import error
            error(
                f"All {len(BREAD_ACCOUNTS)} bread accounts failed",
                status_code=500,
                function_name="_select_bread_account",
                username=self.user_username,
                critical=False
            )
            from backend.utlils.email import message_devs
            message_devs(
                f"❌ CRITICAL: All {len(BREAD_ACCOUNTS)} bread accounts failed\n"
                f"User: {self.user_username}\n"
                f"Action: Check account status and credentials"
            )
            raise RuntimeError(f"All {len(BREAD_ACCOUNTS)} bread accounts exhausted")

        # Random selection from available accounts
        selected = random.choice(available_accounts)
        self.bread_username = selected[0]
        self.bread_password = selected[1]
        self.attempted_accounts.add(self.bread_username)

        notify(f"🎲 Selected bread account: {self.bread_username}")

    async def _ensure_bread_session(self):
        """
        Ensure bread account has valid browser session.
        Attempts to restore from saved state. Raises error if no valid session exists.
        """
        # Try to restore saved session
        result = await read_browser_state(self.browser, self.bread_username, account_type="bread")

        if result:
            # Session exists and is valid
            _, self.context = result
            notify(f"✅ Restored existing session for bread account: {self.bread_username}")
            return

        # No valid session - require manual login
        from backend.utlils.utils import error
        from backend.utlils.email import message_devs

        error_msg = (
            f"❌ No valid session for bread account: {self.bread_username}\n"
            f"   Automated login is disabled to prevent Twitter blocks.\n"
            f"   Please run: python backend/manual_bread_login.py\n"
            f"   This will open a browser where you can manually log in all bread accounts."
        )

        notify(error_msg)
        error(error_msg, status_code=500, function_name="_ensure_bread_session", username=self.user_username, critical=True)
        message_devs(f"🔐 {error_msg}")

        raise RuntimeError(error_msg)

    # REMOVED: Automated login is disabled to prevent Twitter blocks.
    # Use manual_bread_login.py script instead to log in bread accounts.
    #
    # async def _login_bread_account(self):
    # async def _rotate_to_next_bread_account(self):
