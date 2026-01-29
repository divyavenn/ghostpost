"""
Quick test script to verify DIVYA model integration with OpenAI.
"""
import asyncio
from backend.utlils.llm import ask_llm

async def test_divya_model():
    """Test the DIVYA fine-tuned model."""

    print("Testing DIVYA fine-tuned model integration...")
    print("=" * 80)

    system_prompt = "You are a helpful AI assistant that generates engaging Twitter replies."
    user_prompt = "Generate a short, witty reply to this tweet: 'Just deployed my first app to production!'"

    print(f"\nSystem Prompt: {system_prompt}")
    print(f"\nUser Prompt: {user_prompt}")
    print("\n" + "=" * 80)
    print("Calling DIVYA model...\n")

    response = await ask_llm(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model="chatgpt-4o",  # This will be overridden by DIVYA_MODEL_NAME
        username="test_user",
        prompt_type="TEST"
    )

    print("\n" + "=" * 80)
    print("RESPONSE:")
    print("=" * 80)

    if "error" in response:
        print(f"❌ Error: {response['error']}")
        if "raw" in response:
            print(f"\nRaw response: {response['raw']}")
        return False
    else:
        print(f"✅ Success!")
        print(f"\nGenerated Reply:\n{response['message']}")
        return True

if __name__ == "__main__":
    success = asyncio.run(test_divya_model())
    exit(0 if success else 1)
