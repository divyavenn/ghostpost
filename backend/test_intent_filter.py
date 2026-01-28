"""
Test intent filtering with DIVYA model to see what responses we're getting.
"""
import asyncio
from backend.utlils.llm import ask_llm

async def test_intent_filter():
    """Test the DIVYA model with actual intent filter prompts."""

    # User's actual intent from user_info.json
    intent = "i'm a writer looking to promote my substack on philosophy, relationships, self-help, high agency, psychology, and culture."

    # Examples from their intent_filter_examples
    examples_context = """

[EXAMPLES OF POSTS THE USER HAS REPLIED TO (sorted by engagement)]
1. @PhilOfLife_: Your mental health is worth way MORE than a relationship.
2. @selentelechia: I love my little kids, they are such treasures

can't believe we rolled the dice three times and got such sparkly beautiful personalities every time
3. @hollowearthterf: I think its crazy that men insist their actions have nothing to do with their character, a standard they of course only apply to themselves and never to women
4. @PhilOfLife_: The problem today is people don't cherish good people. They use them.
[END EXAMPLES]
"""

    # Test tweets - these should match the intent
    test_cases = [
        {
            "text": "Philosophy isn't about finding THE answer - it's about learning to live with uncertainty while still choosing meaning.",
            "handle": "test_philosophical"
        },
        {
            "text": "Your relationship patterns repeat because you're trying to fix childhood wounds with adult romance. Therapy helps.",
            "handle": "test_psychology"
        },
        {
            "text": "Just finished writing my latest newsletter on stoicism and modern life. Link in bio!",
            "handle": "test_substack"
        },
        {
            "text": "The crypto market is crashing hard today. Down 15% across the board.",
            "handle": "test_crypto"
        }
    ]

    system_prompt = "You are a content relevance evaluator. Answer only YES or NO."

    print("="*80)
    print("Testing DIVYA Model Intent Filtering")
    print("="*80)
    print(f"\nUser Intent: {intent}")
    print(f"\n{examples_context}")

    for i, test_case in enumerate(test_cases, 1):
        tweet_text = test_case["text"]
        tweet_handle = test_case["handle"]

        prompt = f"""User intent: "{intent}"
{examples_context}
    Tweet text: "{tweet_text}"
    Tweet author: @{tweet_handle}

    Could this tweet potentially be relevant to the user's intent? Consider:
    - Does it relate to the topics they're interested in?
    - Could it lead to valuable conversations?
    - Is there any connection to their stated interests?
    - Is it similar to the examples of posts they've replied to before?

    Answer with only "YES" or "NO"."""

        print(f"\n{'-'*80}")
        print(f"Test Case {i}:")
        print(f"Tweet: {tweet_text}")
        print(f"Author: @{tweet_handle}")

        response = await ask_llm(
            system_prompt=system_prompt,
            user_prompt=prompt,
            model="chatgpt-4o",
            username="divya_venn",
            prompt_type="INTENT FILTER TEST"
        )

        if "error" in response:
            print(f"❌ Error: {response['error']}")
        else:
            message = response['message'].strip().upper()
            matches = "YES" in message
            print(f"Response: {response['message']}")
            print(f"Parsed Result: {'✅ PASSED' if matches else '❌ FILTERED'}")

if __name__ == "__main__":
    asyncio.run(test_intent_filter())
