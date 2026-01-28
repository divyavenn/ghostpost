"""
Test OpenAI API key with a standard model.
"""
import asyncio
import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env
load_dotenv(Path(__file__).resolve().parent / '.env')

async def test_api_key():
    """Test the DIVYA_API_KEY with a standard OpenAI model."""
    import httpx

    api_key = os.getenv("DIVYA_API_KEY")

    if not api_key:
        print("❌ DIVYA_API_KEY not found in .env")
        return False

    print(f"API Key found: {api_key[:20]}...{api_key[-10:]}")
    print("\nTesting with gpt-4o-mini (standard model)...")

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say 'Hello!'"}
        ]
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, json=payload, timeout=30.0)

            if response.status_code == 200:
                data = response.json()
                message = data["choices"][0]["message"]["content"]
                print(f"\n✅ API Key works! Response: {message}")
                return True
            else:
                print(f"\n❌ Error {response.status_code}: {response.text}")
                return False
        except Exception as e:
            print(f"\n❌ Exception: {e}")
            return False

if __name__ == "__main__":
    success = asyncio.run(test_api_key())
    exit(0 if success else 1)
