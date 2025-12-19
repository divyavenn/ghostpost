"""Test HTML entity decoding in tweet text."""
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.browser_automation.twitter.api import _get_full_text


def test_html_entities_in_text():
    """Test that HTML entities are decoded in regular text field."""
    tweet = {
        "text": "&gt; Pick a skill\n&gt; Learn the skill\n&lt; Test &amp; more",
        "note_tweet": {}
    }

    result = _get_full_text(tweet)

    assert ">" in result, f"Expected '>' but got: {result}"
    assert "<" in result, f"Expected '<' but got: {result}"
    assert "&" in result and "&amp;" not in result, f"Expected '&' without '&amp;' but got: {result}"
    assert "&gt;" not in result, f"Should not contain '&gt;' but got: {result}"

    print("✅ Regular text HTML entity decoding works")
    print(f"   Decoded: {result[:50]}...")


def test_html_entities_in_note_tweet():
    """Test that HTML entities are decoded in note_tweet field (long tweets)."""
    tweet = {
        "text": "short truncated",
        "note_tweet": {
            "text": "&gt; This is a long tweet\n&gt; With multiple lines\n&amp; special chars"
        }
    }

    result = _get_full_text(tweet)

    assert ">" in result, f"Expected '>' but got: {result}"
    assert "&" in result and "&amp;" not in result, f"Expected '&' without '&amp;' but got: {result}"
    assert "&gt;" not in result, f"Should not contain '&gt;' but got: {result}"
    assert "short truncated" not in result, f"Should use note_tweet, not regular text"

    print("✅ Long tweet (note_tweet) HTML entity decoding works")
    print(f"   Decoded: {result[:50]}...")


def test_no_html_entities():
    """Test that normal text without entities is unchanged."""
    tweet = {
        "text": "> Already normal text\n< No encoding needed",
        "note_tweet": {}
    }

    result = _get_full_text(tweet)

    assert result == "> Already normal text\n< No encoding needed"

    print("✅ Normal text without entities works")


def test_mixed_html_entities():
    """Test various HTML entities."""
    tweet = {
        "text": "&quot;Quote&quot; &apos;apostrophe&apos; &nbsp;space",
        "note_tweet": {}
    }

    result = _get_full_text(tweet)

    assert '"Quote"' in result, f"Expected quotes but got: {result}"
    assert "'" in result or "'" in result, f"Expected apostrophe but got: {result}"
    assert "&quot;" not in result, f"Should not contain '&quot;' but got: {result}"

    print("✅ Mixed HTML entities decoding works")
    print(f"   Decoded: {result}")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing HTML Entity Decoding in Tweet Text")
    print("=" * 60)

    test_html_entities_in_text()
    test_html_entities_in_note_tweet()
    test_no_html_entities()
    test_mixed_html_entities()

    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)
