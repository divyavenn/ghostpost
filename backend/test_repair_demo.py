#!/usr/bin/env python3
"""
Demo script to show how repair_user_data.py works with invalid data.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from backend.data_validation import User
from pydantic import ValidationError

# Test data with missing fields
test_users = [
    {
        "handle": "incomplete_user",
        "username": "incomplete_user",
        "account_type": "trial",
        "relevant_accounts": {},
        "queries": []
        # Missing: email, profile_pic_url, follower_count, etc. (but they're optional)
    },
    {
        "handle": "valid_user",
        "username": "valid_user",
        "email": "valid@example.com",
        "profile_pic_url": "https://example.com/pic.jpg",
        "follower_count": 100,
        "account_type": "premium",
        "models": ["gpt-4"],
        "relevant_accounts": {"user1": True},
        "queries": ["AI news"],
        "max_tweets_retrieve": 30,
        "number_of_generations": 2,
        "scrapes_left": 50,
        "posts_left": 25
    }
]

print("=" * 60)
print("REPAIR TOOL DEMO - Testing User Validation")
print("=" * 60)

for idx, user_data in enumerate(test_users):
    handle = user_data.get('handle', f'User #{idx + 1}')
    print(f"\nUser {idx + 1}: {handle}")
    print("-" * 60)
    print("Data:", json.dumps(user_data, indent=2))
    print()

    try:
        user = User(**user_data)
        print(f"✅ Valid! All required fields present.")
    except ValidationError as e:
        print(f"❌ Validation errors found:")
        for error in e.errors():
            field = error['loc'][0] if error['loc'] else 'unknown'
            print(f"  - {field}: {error['msg']}")
        print()
        print("💡 Run 'python repair_user_data.py' to fix these issues interactively!")

print("\n" + "=" * 60)
print("To repair your actual user_info.json, run:")
print("  python repair_user_data.py")
print("=" * 60)
