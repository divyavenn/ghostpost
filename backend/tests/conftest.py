"""
Shared pytest fixtures for backend tests.
"""

import pytest
import pytest_asyncio
from playwright.async_api import async_playwright

from backend.config import TEST_USER


@pytest_asyncio.fixture
async def browser_context():
    """
    Shared browser context with TEST_USER cookies loaded.

    Use this fixture for any test that needs authenticated Twitter access.
    """
    from backend.utlils.utils import read_browser_state

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # Try to load saved browser state for TEST_USER
        ctx = None
        try:
            result = await read_browser_state(browser, TEST_USER)
            if result:
                _, ctx = result
        except Exception:
            pass

        # Fall back to empty context if no cookies loaded
        if ctx is None:
            ctx = await browser.new_context()

        yield ctx

        await ctx.close()
        await browser.close()


@pytest.fixture
def test_user():
    """Return the configured TEST_USER."""
    return TEST_USER
