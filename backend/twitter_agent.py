"""
Twitter Agent Module
Integrates with existing Playwright and API code to provide a unified interface
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path

# Import existing modules
from playwright.async_api import async_playwright, Browser, BrowserContext
from headless_fetch import collect_from_page
from backend.headless_login import log_in
from better_fetch import get_home
from post_takes import post_take, post_take_as_reply
from main import ask_model


@dataclass
class Tweet:
    """Represents a tweet with engagement metrics"""
    id: str
    author: str
    content: str
    engagement: int
    timestamp: datetime
    url: str = ""
    likes: int = 0
    retweets: int = 0
    replies: int = 0


@dataclass
class CommentOpportunity:
    """Represents an opportunity to comment on a tweet"""
    tweet: Tweet
    relevance_score: float
    comment_suggestion: str
    priority: float


class TwitterAgent:
    """Main Twitter automation agent"""
    
    def __init__(self):
        # Rate limiting
        self.comments_today = 0
        self.comments_this_hour = 0
        self.last_comment_time = None
        self.max_comments_per_hour = 5
        self.max_comments_per_day = 50
        
        # Configuration
        self.target_accounts = ["divya_venn", "witkowski_cam"]
        
        # Browser state
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.playwright = None
        
        # State
        self.is_logged_in = False
        self.session_id = None
    
    async def start_browser(self, headless: bool = True):
        """Start Playwright browser"""
        self.playwright = await async_playwright().start()
        
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
        
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=browser_args,
            slow_mo=100,
        )
        
        self.context = await self.browser.new_context(
            user_agent=user_agent,
            viewport={'width': 1920, 'height': 1080},
            locale='en-US',
            timezone_id='America/New_York',
            extra_http_headers={
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
        )
    
    async def login_to_twitter(self) -> bool:
        """Login to Twitter using existing login module"""
        try:
            if not self.browser:
                await self.start_browser(headless=True)
            
            # Use existing login functionality
            self.browser, self.context = await get_home(browser=self.browser)
            self.is_logged_in = True
            return True
        except Exception as e:
            print(f"Login failed: {e}")
            return False
    
    async def navigate_to_user(self, username: str) -> bool:
        """Navigate to a user's profile"""
        try:
            if not self.context:
                return False
            
            page = await self.context.new_page()
            url = f"https://x.com/{username}"
            await page.goto(url, wait_until="domcontentloaded")
            await page.close()
            return True
        except Exception as e:
            print(f"Failed to navigate to @{username}: {e}")
            return False
    
    async def extract_tweets(self, limit: int = 5) -> List[Tweet]:
        """Extract tweets from current page using existing headless_fetch"""
        try:
            if not self.context:
                return []
            
            # Use existing tweet extraction
            tweets_data = await collect_from_page(self.context, "https://x.com/home", None, max_scrolls=3)
            
            tweets = []
            for tweet_id, tweet_data in list(tweets_data.items())[:limit]:
                try:
                    # Parse created_at timestamp
                    created_at_str = tweet_data.get('created_at', '')
                    if created_at_str:
                        # Parse Twitter's date format
                        try:
                            timestamp = datetime.strptime(created_at_str, "%a %b %d %H:%M:%S %z %Y")
                        except:
                            timestamp = datetime.now()
                    else:
                        timestamp = datetime.now()
                    
                    # Calculate engagement score
                    likes = tweet_data.get('likes', 0)
                    retweets = tweet_data.get('retweets', 0)
                    replies = tweet_data.get('replies', 0)
                    engagement = likes + (retweets * 2) + replies
                    
                    tweet = Tweet(
                        id=tweet_id,
                        author=tweet_data.get('username', 'unknown'),
                        content=tweet_data.get('text', ''),
                        engagement=engagement,
                        timestamp=timestamp,
                        url=tweet_data.get('url', ''),
                        likes=likes,
                        retweets=retweets,
                        replies=replies
                    )
                    tweets.append(tweet)
                except Exception as e:
                    print(f"Error parsing tweet {tweet_id}: {e}")
                    continue
            
            return tweets
        except Exception as e:
            print(f"Error extracting tweets: {e}")
            return []
    
    async def evaluate_tweet_for_commenting(self, tweet: Tweet) -> CommentOpportunity:
        """Evaluate if a tweet is worth commenting on"""
        try:
            # Simple relevance scoring based on engagement and content
            relevance_score = 0.0
            
            # Base score from engagement
            if tweet.engagement > 100:
                relevance_score += 0.4
            elif tweet.engagement > 50:
                relevance_score += 0.3
            elif tweet.engagement > 10:
                relevance_score += 0.2
            else:
                relevance_score += 0.1
            
            # Content analysis (simple keyword matching)
            content_lower = tweet.content.lower()
            interesting_keywords = [
                'ai', 'artificial intelligence', 'machine learning', 'tech',
                'startup', 'entrepreneur', 'building', 'product', 'design',
                'coding', 'programming', 'software', 'development'
            ]
            
            for keyword in interesting_keywords:
                if keyword in content_lower:
                    relevance_score += 0.1
                    break
            
            # Generate comment suggestion using existing AI
            comment_suggestion = ""
            if relevance_score > 0.3:
                try:
                    response = ask_model(tweet.content)
                    comment_suggestion = response.get('message', '')
                except Exception as e:
                    print(f"Error generating comment: {e}")
                    comment_suggestion = "Interesting point!"
            
            # Calculate priority (combination of relevance and engagement)
            priority = relevance_score * (1 + (tweet.engagement / 1000))
            
            return CommentOpportunity(
                tweet=tweet,
                relevance_score=relevance_score,
                comment_suggestion=comment_suggestion,
                priority=priority
            )
        except Exception as e:
            print(f"Error evaluating tweet: {e}")
            return CommentOpportunity(
                tweet=tweet,
                relevance_score=0.0,
                comment_suggestion="",
                priority=0.0
            )
    
    def can_comment(self) -> bool:
        """Check if we can post a comment based on rate limits"""
        now = datetime.now()
        
        # Reset daily counter if it's a new day
        if self.last_comment_time and now.date() > self.last_comment_time.date():
            self.comments_today = 0
        
        # Reset hourly counter if it's been more than an hour
        if self.last_comment_time and now - self.last_comment_time > timedelta(hours=1):
            self.comments_this_hour = 0
        
        # Check limits
        if self.comments_today >= self.max_comments_per_day:
            return False
        
        if self.comments_this_hour >= self.max_comments_per_hour:
            return False
        
        return True
    
    async def post_comment(self, opportunity: CommentOpportunity) -> bool:
        """Post a comment using existing post_takes functionality"""
        try:
            if not self.can_comment():
                return False
            
            # Use existing posting functionality
            tweet_data = {
                "id": opportunity.tweet.id,
                "thread": [opportunity.tweet.content]
            }
            
            result = post_take_as_reply("", tweet_data)
            
            # Update counters
            self.comments_today += 1
            self.comments_this_hour += 1
            self.last_comment_time = datetime.now()
            
            return True
        except Exception as e:
            print(f"Error posting comment: {e}")
            return False
    
    async def close(self):
        """Clean up browser resources"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    def __del__(self):
        """Cleanup on deletion"""
        if self.browser or self.playwright:
            asyncio.create_task(self.close())
