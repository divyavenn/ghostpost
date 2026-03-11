"""
Consumed - Browser automation for Substack posting.

Called by Rust via subprocess. Modules:
    browser: Playwright browser state management
    generate: Generate post content
    post: Post to Substack Notes
"""

from .generate import generate_post, Post
from .post import post_to_substack
from .browser import login_to_substack, get_browser_context

__all__ = [
    "generate_post",
    "Post",
    "post_to_substack",
    "login_to_substack",
    "get_browser_context",
]
