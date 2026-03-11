"""
Module 3: Post to Substack Notes using saved browser state.

Uses Playwright with persistent cookies to post without re-authenticating.
"""

import time
from typing import Optional
from .browser import get_browser_context
from .generate import Post


def post_to_substack(
    post: Post,
    headless: bool = True,
    dry_run: bool = False,
) -> bool:
    """
    Post content to Substack Notes.

    Args:
        post: The Post object containing content to publish
        headless: Run browser in headless mode
        dry_run: If True, don't actually post (for testing)

    Returns:
        True if successful
    """
    if dry_run:
        print("DRY RUN - Would post:")
        print("-" * 40)
        print(post.content)
        print("-" * 40)
        return True

    with get_browser_context(headless=headless) as (browser, context, page):
        # Go to Substack Notes
        page.goto("https://substack.com/home")
        time.sleep(2)

        # Check if logged in
        if "sign-in" in page.url:
            raise RuntimeError(
                "Not logged in to Substack. Run 'python -m consumed.browser' first to log in."
            )

        # Click on the "New Note" button/area
        # Substack's UI: look for the compose area
        try:
            # Try to find the compose box
            compose_selectors = [
                '[data-testid="new-note-button"]',
                'button:has-text("New note")',
                '[placeholder*="new note"]',
                '.compose-box',
                'div[contenteditable="true"]',
            ]

            compose_box = None
            for selector in compose_selectors:
                try:
                    compose_box = page.wait_for_selector(selector, timeout=5000)
                    if compose_box:
                        break
                except:
                    continue

            if not compose_box:
                # Navigate directly to notes compose
                page.goto("https://substack.com/notes")
                time.sleep(2)
                compose_box = page.wait_for_selector(
                    'div[contenteditable="true"]', timeout=10000
                )

            # Click to focus
            compose_box.click()
            time.sleep(0.5)

            # Type the content
            # Using keyboard.type for more reliable input
            page.keyboard.type(post.content)
            time.sleep(0.5)

            # Find and click the post button
            post_button_selectors = [
                'button:has-text("Post")',
                '[data-testid="post-button"]',
                'button[type="submit"]',
            ]

            for selector in post_button_selectors:
                try:
                    post_button = page.wait_for_selector(selector, timeout=3000)
                    if post_button and post_button.is_enabled():
                        post_button.click()
                        time.sleep(2)
                        print(f"Posted to Substack Notes: {post.title}")
                        return True
                except:
                    continue

            raise RuntimeError("Could not find post button")

        except Exception as e:
            # Take screenshot for debugging
            screenshot_path = "/tmp/substack_error.png"
            page.screenshot(path=screenshot_path)
            raise RuntimeError(
                f"Failed to post to Substack: {e}. Screenshot saved to {screenshot_path}"
            )


def post_url_to_substack(
    url: str,
    quote: Optional[str] = None,
    thoughts: Optional[str] = None,
    headless: bool = True,
    dry_run: bool = False,
) -> bool:
    """
    Convenience function: log URL, generate post, and publish to Substack.

    Args:
        url: URL to share
        quote: Optional quote from the content
        thoughts: Optional commentary
        headless: Run browser in headless mode
        dry_run: If True, don't actually post

    Returns:
        True if successful
    """
    from .log import add_to_log
    from .generate import generate_post

    # Step 1: Log the URL
    print(f"Logging: {url}")
    entry = add_to_log(url)
    print(f"Logged: {entry.title}")

    # Step 2: Generate post
    post = generate_post(entry, include_quote=quote, include_thoughts=thoughts)
    print(f"Generated post ({len(post.content)} chars)")

    # Step 3: Post to Substack
    return post_to_substack(post, headless=headless, dry_run=dry_run)


def post_to_twitter(
    text: str,
    image_path: Optional[str] = None,
) -> dict:
    """
    Post content to Twitter/X using the API.

    Requires environment variables:
        TWITTER_API_KEY
        TWITTER_API_SECRET
        TWITTER_ACCESS_TOKEN
        TWITTER_ACCESS_SECRET

    Args:
        text: The text content to post
        image_path: Optional local path to image to attach

    Returns:
        dict with tweet data including 'id' and 'text'
    """
    import tweepy
    import os

    # Get credentials from environment
    api_key = os.environ.get("TWITTER_API_KEY")
    api_secret = os.environ.get("TWITTER_API_SECRET")
    access_token = os.environ.get("TWITTER_ACCESS_TOKEN")
    access_secret = os.environ.get("TWITTER_ACCESS_SECRET")

    if not all([api_key, api_secret, access_token, access_secret]):
        raise ValueError(
            "Missing Twitter API credentials. Set TWITTER_API_KEY, TWITTER_API_SECRET, "
            "TWITTER_ACCESS_TOKEN, and TWITTER_ACCESS_SECRET environment variables."
        )

    # Create client for Twitter API v2
    client = tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_secret,
    )

    media_ids = None

    # Upload image if provided
    if image_path:
        # Need v1.1 API for media upload
        auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_secret)
        api_v1 = tweepy.API(auth)
        media = api_v1.media_upload(image_path)
        media_ids = [media.media_id]

    # Post tweet
    response = client.create_tweet(text=text, media_ids=media_ids)

    print(f"Posted to Twitter! Tweet ID: {response.data['id']}")
    return response.data


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m consumed.post <url> [--dry-run] [--twitter]")
        sys.exit(1)

    url = sys.argv[1]
    dry_run = "--dry-run" in sys.argv
    use_twitter = "--twitter" in sys.argv

    if use_twitter:
        post_to_twitter(f"Check this out: {url}")
    else:
        post_url_to_substack(url, dry_run=dry_run, headless=False)
