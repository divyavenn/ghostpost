"""Test script to verify the /auth/twitter/import-cookies endpoint works."""

import httpx
import json

# Test data - simulating what the extension would send
test_payload = {
    "data": {
        "username": "testuser"  # Change this to an actual username in your system
    },
    "cookies": [
        {
            "name": "auth_token",
            "value": "test_auth_token_value",
            "domain": ".x.com",
            "path": "/",
            "secure": True,
            "httpOnly": True,
            "sameSite": "Lax"
        },
        {
            "name": "ct0",
            "value": "test_ct0_value",
            "domain": ".x.com",
            "path": "/",
            "secure": True,
            "httpOnly": False,
            "sameSite": "Lax"
        }
    ]
}

async def test_import_cookies():
    """Test the import-cookies endpoint."""
    backend_url = "http://localhost:8000"  # Adjust if your backend runs on a different port

    print("Testing /auth/twitter/import-cookies endpoint...")
    print(f"Backend URL: {backend_url}")
    print(f"Payload: {json.dumps(test_payload, indent=2)}")
    print("\nSending request...")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{backend_url}/auth/twitter/import-cookies",
                json=test_payload,
                timeout=30.0
            )

            print(f"\nStatus Code: {response.status_code}")
            print(f"Response: {json.dumps(response.json(), indent=2)}")

            if response.status_code == 200:
                print("\n✅ Endpoint is working!")
            else:
                print(f"\n⚠️  Endpoint returned non-200 status: {response.status_code}")

        except httpx.ConnectError:
            print("\n❌ Connection failed! Is the backend running on port 8000?")
            print("   Try running: cd backend && uv run uvicorn backend.main:app --reload")
        except Exception as e:
            print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_import_cookies())
