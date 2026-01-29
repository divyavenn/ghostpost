"""
List available OpenAI models for the DIVYA_API_KEY.
"""
import asyncio
import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env
load_dotenv(Path(__file__).resolve().parent / '.env')

async def list_models():
    """List all available models."""
    import httpx

    api_key = os.getenv("DIVYA_API_KEY")

    if not api_key:
        print("❌ DIVYA_API_KEY not found in .env")
        return

    print("Fetching available models...")

    url = "https://api.openai.com/v1/models"
    headers = {"Authorization": f"Bearer {api_key}"}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)

            if response.status_code == 200:
                data = response.json()
                models = data.get("data", [])

                # Filter for fine-tuned models (start with 'ft:')
                fine_tuned = [m for m in models if m.get("id", "").startswith("ft:")]
                standard = [m for m in models if not m.get("id", "").startswith("ft:") and "gpt" in m.get("id", "").lower()]

                print(f"\n📊 Found {len(models)} total models")
                print(f"   - {len(fine_tuned)} fine-tuned models")
                print(f"   - {len(standard)} standard GPT models")

                if fine_tuned:
                    print("\n🎯 Fine-tuned models:")
                    for model in fine_tuned:
                        print(f"   - {model['id']}")
                else:
                    print("\n⚠️  No fine-tuned models found")

                print("\n🤖 Available standard GPT models:")
                for model in sorted(standard, key=lambda x: x['id'])[:10]:
                    print(f"   - {model['id']}")

            else:
                print(f"\n❌ Error {response.status_code}: {response.text}")

        except Exception as e:
            print(f"\n❌ Exception: {e}")

if __name__ == "__main__":
    asyncio.run(list_models())
