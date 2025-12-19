"""Manually trigger intent filter examples update for a user."""
import sys
from pathlib import Path

# Add backend to path
BACKEND_DIR = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from backend.twitter.monitoring import _update_intent_filter_examples
from backend.utlils.utils import read_user_info


def update_intent_examples(username: str):
    """Update intent filter examples for a user."""
    print(f"Updating intent filter examples for @{username}...")

    user_info = read_user_info(username)
    if not user_info:
        print(f"❌ User {username} not found")
        return

    print(f"Current intent_filter_examples: {len(user_info.get('intent_filter_examples', []))}")

    # Update examples
    _update_intent_filter_examples(username, limit=5)

    # Read updated
    user_info = read_user_info(username)
    updated_examples = user_info.get('intent_filter_examples', [])

    print(f"Updated intent_filter_examples: {len(updated_examples)}")
    print("\nExamples:")
    for idx, example in enumerate(updated_examples, 1):
        author = example.get('author', '')
        text_preview = example.get('text', '')[:80]
        print(f"  {idx}. @{author}: {text_preview}...")

    print("\n✅ Done!")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/update_intent_examples.py <username>")
        print("Example: python scripts/update_intent_examples.py divya_venn")
        sys.exit(1)

    username = sys.argv[1]
    update_intent_examples(username)
