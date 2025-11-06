#!/usr/bin/env python3
"""
Cookie Import Helper Script

This script helps you import Twitter cookies from your browser into the backend.

Usage:
1. Install browser extension (EditThisCookie or Cookie-Editor)
2. Export cookies for x.com to a JSON file
3. Run: python import_cookies.py cookies.json your_twitter_handle
"""

import json
import sys
import requests


def import_cookies(cookies_file: str,
                   username: str,
                   backend_url: str = "http://localhost:8000"):
    """Import cookies from JSON file to backend."""

    # Read cookies from file
    try:
        with open(cookies_file, 'r') as f:
            cookies = json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: File '{cookies_file}' not found")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"❌ Error: '{cookies_file}' is not valid JSON")
        sys.exit(1)

    # Validate cookies format
    if not isinstance(cookies, list):
        print("❌ Error: Cookies must be a JSON array")
        sys.exit(1)

    # Filter for x.com/twitter.com cookies only
    twitter_cookies = [
        c for c in cookies if '.x.com' in c.get('domain', '')
        or '.twitter.com' in c.get('domain', '')
    ]

    if not twitter_cookies:
        print("⚠️  Warning: No Twitter/X cookies found in file")
        print("   Make sure you exported cookies for x.com or twitter.com")
        sys.exit(1)

    # Check for critical cookies
    cookie_names = [c.get('name') for c in twitter_cookies]
    critical_cookies = ['auth_token', 'ct0']
    missing = [c for c in critical_cookies if c not in cookie_names]

    if missing:
        print(f"⚠️  Warning: Missing critical cookies: {', '.join(missing)}")
        print("   You may not be logged in or the export is incomplete")

    # Send to backend
    print(f"📤 Importing {len(twitter_cookies)} cookies for @{username}...")

    try:
        response = requests.post(
            f"{backend_url}/api/auth/twitter/import-cookies",
            json={
                "username": username,
                "cookies": twitter_cookies
            },
            timeout=10)
        response.raise_for_status()

        result = response.json()
        print(f"✅ {result['message']}")
        print(f"   Imported {result['cookies_count']} cookies")

    except requests.exceptions.ConnectionError:
        print(f"❌ Error: Could not connect to backend at {backend_url}")
        print("   Make sure the backend is running (docker compose up)")
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        print(f"❌ Error: Backend returned error: {e.response.status_code}")
        print(f"   {e.response.text}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(
            "Usage: python import_cookies.py <cookies_file.json> <twitter_handle>"
        )
        print()
        print("Example:")
        print("  python import_cookies.py cookies.json divya_venn")
        print()
        print("Steps:")
        print("1. Install EditThisCookie or Cookie-Editor browser extension")
        print("2. Log into Twitter/X in your browser")
        print("3. Click extension → Export → Save as cookies.json")
        print("4. Run this script with the file and your Twitter handle")
        sys.exit(1)

    cookies_file = sys.argv[1]
    username = sys.argv[2]

    import_cookies(cookies_file, username)
