"""
Shared browser state management for Playwright.

Handles persistent browser context with saved cookies/auth state.
"""

import os
from pathlib import Path
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
from contextlib import contextmanager

# Default path for browser state (cookies, localStorage, etc.)
DEFAULT_STATE_PATH = Path.home() / ".consumed" / "browser_state.json"


def get_state_path() -> Path:
    """Get browser state file path from env or default."""
    state_path = Path(os.getenv("BROWSER_STATE_PATH", DEFAULT_STATE_PATH))
    state_path.parent.mkdir(parents=True, exist_ok=True)
    return state_path


@contextmanager
def get_browser_context(headless: bool = True):
    """
    Get a browser context with persistent state.

    Usage:
        with get_browser_context() as (browser, context, page):
            page.goto("https://substack.com")
            # ... do stuff

    State is automatically saved on exit.
    """
    state_path = get_state_path()

    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=headless)

        # Load existing state if available
        if state_path.exists():
            context = browser.new_context(storage_state=str(state_path))
        else:
            context = browser.new_context()

        page = context.new_page()

        try:
            yield browser, context, page
        finally:
            # Save state for next time
            context.storage_state(path=str(state_path))
            context.close()
            browser.close()


def login_to_substack(headless: bool = False):
    """
    Interactive login to Substack to save credentials.

    Run this once with headless=False to manually log in.
    Your session will be saved for future automated use.
    """
    print("Opening browser for Substack login...")
    print("Please log in manually. The browser will close after you're done.")
    print("Press Enter in this terminal when you've finished logging in.")

    with get_browser_context(headless=headless) as (browser, context, page):
        page.goto("https://substack.com/sign-in")

        # Wait for user to log in
        input("\nPress Enter after you've logged in to Substack...")

        # Verify login
        page.goto("https://substack.com/home")
        if "sign-in" not in page.url:
            print("Login successful! State saved.")
        else:
            print("Warning: Login may not have completed.")

    print(f"Browser state saved to: {get_state_path()}")


if __name__ == "__main__":
    # Run this file directly to do initial Substack login
    login_to_substack(headless=False)
