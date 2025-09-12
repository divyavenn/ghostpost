from playwright.async_api import async_playwright
import asyncio

async def demo():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://example.org")
        print(await page.title())
        await browser.close()

asyncio.run(demo())