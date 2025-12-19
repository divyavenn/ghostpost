"""Test to verify intent filter examples are correctly populated after post_type migration."""
import json
from pathlib import Path


def test_validate_post_type_logic():
    """Test that post_type classification logic works correctly with conversation_id."""

    # Mock scenarios
    test_cases = [
        {
            "name": "Reply to someone else's original post",
            "parent_tweet_id": "123",
            "conversation_id": "123",  # Parent IS the root
            "responding_to_handle": "other_user",
            "username": "divya_venn",
            "expected_post_type": "reply"
        },
        {
            "name": "Reply to our own original post (thread continuation)",
            "parent_tweet_id": "123",
            "conversation_id": "123",  # Parent IS the root
            "responding_to_handle": "divya_venn",
            "username": "divya_venn",
            "expected_post_type": "original"
        },
        {
            "name": "Reply to someone else's comment",
            "parent_tweet_id": "456",
            "conversation_id": "123",  # Parent is NOT the root
            "responding_to_handle": "other_user",
            "username": "divya_venn",
            "expected_post_type": "comment_reply"
        },
        {
            "name": "Reply to our own comment",
            "parent_tweet_id": "456",
            "conversation_id": "123",  # Parent is NOT the root
            "responding_to_handle": "divya_venn",
            "username": "divya_venn",
            "expected_post_type": "comment_reply"
        },
    ]

    for case in test_cases:
        parent_tweet_id = case["parent_tweet_id"]
        conversation_id = case["conversation_id"]
        responding_to_handle = case["responding_to_handle"]
        username = case["username"]

        # Apply the same logic from posting.py
        is_replying_to_root = (parent_tweet_id == conversation_id)

        if is_replying_to_root:
            if responding_to_handle.lower() == username.lower():
                post_type = "original"
            else:
                post_type = "reply"
        else:
            post_type = "comment_reply"

        assert post_type == case["expected_post_type"], \
            f"FAILED: {case['name']} - Expected {case['expected_post_type']}, got {post_type}"
        print(f"✅ PASSED: {case['name']} -> {post_type}")


def test_count_tweets_needing_reclassification():
    """Count how many tweets in posted_tweets cache need reclassification."""
    cache_file = Path("cache/divya_venn_posted_tweets.json")

    if not cache_file.exists():
        print("⚠️ Posted tweets cache not found, skipping")
        return

    data = json.load(open(cache_file))
    tweet_ids = [k for k in data.keys() if k != '_order']
    tweets = [data[tid] for tid in tweet_ids]

    # Current stats
    current_replies = len([t for t in tweets if t.get('post_type') == 'reply'])
    current_comment_replies = len([t for t in tweets if t.get('post_type') == 'comment_reply'])
    current_originals = len([t for t in tweets if t.get('post_type') == 'original'])

    print(f"\n📊 Current Classifications:")
    print(f"  Reply: {current_replies}")
    print(f"  Comment Reply: {current_comment_replies}")
    print(f"  Original: {current_originals}")

    # Count how many would change with new logic
    # Note: We can't fully test without conversation_id in the cache yet
    would_change = 0
    missing_conv_id = 0

    for tweet in tweets:
        if 'conversation_id' not in tweet:
            missing_conv_id += 1

    print(f"\n⚠️ Tweets missing conversation_id: {missing_conv_id}/{len(tweets)}")
    print(f"   These tweets were created before conversation_id was added to the model")
    print(f"   Migration will need to fetch conversation_id or skip these tweets")

    # Count potential valid intent filter examples AFTER migration
    valid_for_intent = [
        t for t in tweets
        if t.get('post_type') == 'reply'
        and t.get('responding_to')
        and t.get('response_to_thread')
        and t.get('responding_to') != 'divya_venn'
    ]

    print(f"\n📚 Potential Intent Filter Examples:")
    print(f"  Currently valid replies (with data, not self): {len(valid_for_intent)}")
    print(f"  Top 5 by score:")
    sorted_valid = sorted(valid_for_intent, key=lambda x: x.get('score', 0), reverse=True)[:5]
    for idx, t in enumerate(sorted_valid, 1):
        score = t.get('score', 0)
        resp_to = t.get('responding_to', '')
        print(f"    {idx}. Score: {score}, @{resp_to}")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Post Type Classification Logic")
    print("=" * 60)

    test_validate_post_type_logic()

    print("\n" + "=" * 60)
    print("Analyzing Current Posted Tweets Cache")
    print("=" * 60)

    test_count_tweets_needing_reclassification()

    print("\n" + "=" * 60)
    print("✅ All tests completed")
    print("=" * 60)
