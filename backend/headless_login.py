from pathlib import Path
from playwright.async_api import async_playwright

STATE_FILE = Path("storage_state.json")
print(Path.cwd())


async def log_in(username: str, password: str, browser=None):
    async with async_playwright() as p:
        if browser is None:
            browser = await p.chromium.launch(headless=False)
        ctx     = await browser.new_context()
        page    = await ctx.new_page()

        await page.goto("https://x.com/i/flow/login?lang=en")
        await page.fill('input[name="text"]', username)
        await page.press('input[name="text"]', 'Enter')
        await page.fill('input[name="password"]', password)
        await page.press('input[name="password"]', 'Enter')
        await page.wait_for_url("https://x.com/home", timeout=20_000)

        # **important**: save *this* context’s state
        await ctx.storage_state(path=STATE_FILE)
        print("✅  storage_state.json written")
        return browser, ctx
         
if __name__ == "__main__":
    import os
    import dotenv
    dotenv.load_dotenv()

    username = os.getenv("TWITTER_USERNAME")
    password = os.getenv("TWITTER_PASSWORD")
    import asyncio
    asyncio.run(log_in(username, password))
    print("Login completed. Check storage_state.json for session details.")