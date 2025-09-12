"""
Production-ready Playwright configuration
"""
import os
from playwright.async_api import async_playwright, Browser, BrowserContext
from typing import Optional

class ProductionPlaywrightManager:
    """Manages Playwright instances for production use"""
    
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.playwright = None
    
    async def start_browser(self, headless: bool = True):
        """Start browser with production-optimized settings"""
        self.playwright = await async_playwright().start()
        
        # Production browser launch options
        browser_args = [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--disable-gpu',
            '--disable-background-timer-throttling',
            '--disable-backgrounding-occluded-windows',
            '--disable-renderer-backgrounding',
            '--disable-features=TranslateUI',
            '--disable-ipc-flooding-protection',
            '--disable-extensions',
            '--disable-default-apps',
            '--disable-sync',
            '--disable-translate',
            '--hide-scrollbars',
            '--mute-audio',
            '--no-default-browser-check',
            '--no-pings',
            '--password-store=basic',
            '--use-mock-keychain',
            '--disable-blink-features=AutomationControlled',
            '--disable-features=VizDisplayCompositor'
        ]
        
        # Add user agent to avoid detection
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=browser_args,
            slow_mo=100,  # Add small delay to appear more human
        )
        
        # Create context with production settings
        self.context = await self.browser.new_context(
            user_agent=user_agent,
            viewport={'width': 1920, 'height': 1080},
            locale='en-US',
            timezone_id='America/New_York',
            # Disable images and CSS for faster loading (optional)
            # java_script_enabled=True,
            # accept_downloads=False,
            # has_touch=False,
            # is_mobile=False,
            # device_scale_factor=1,
            # screen={'width': 1920, 'height': 1080},
            # no_viewport=False,
            # ignore_https_errors=True,
            # bypass_csp=True,
            # user_data_dir=None,
            # permissions=[],
            # geolocation=None,
            # color_scheme='light',
            # reduced_motion='no-preference',
            # forced_colors='none',
            extra_http_headers={
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
        )
        
        return self.context
    
    async def close(self):
        """Clean up browser resources"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def __aenter__(self):
        await self.start_browser()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

# Global instance for reuse
playwright_manager = ProductionPlaywrightManager()

# Environment-specific settings
def get_playwright_config():
    """Get Playwright configuration based on environment"""
    is_production = os.getenv('ENVIRONMENT', 'development') == 'production'
    
    return {
        'headless': is_production,
        'slow_mo': 0 if is_production else 100,
        'timeout': 30000 if is_production else 60000,
        'user_data_dir': None if is_production else './browser_data',
        'downloads_path': '/tmp/downloads' if is_production else './downloads',
    }
