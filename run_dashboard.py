#!/usr/bin/env python3
"""
Startup script for Twitter Agent Dashboard
Runs both the backend server and opens the frontend
"""

import subprocess
import sys
import time
import webbrowser
from pathlib import Path




def start_backend():
    """Start the FastAPI backend server"""
    print("🚀 Starting backend server...")

    # Change to backend directory
    backend_dir = Path(__file__).parent / "backend"

    # Start uvicorn server
    cmd = [sys.executable, "-m", "uvicorn", "websocket:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

    return subprocess.Popen(cmd, cwd=backend_dir)


def main():
    print("🤖 Twitter Agent Dashboard Launcher")
    print("=" * 40)

    try:
        # Start backend server
        backend_process = start_backend()

        # Wait a moment for server to start
        print("⏳ Waiting for server to start...")
        time.sleep(3)

        # Open browser to dashboard
        dashboard_url = "http://localhost:8000"
        print(f"🌐 Opening dashboard at {dashboard_url}")
        webbrowser.open(dashboard_url)

        print("\n" + "=" * 50)
        print("🎉 Dashboard is now running!")
        print("📊 Frontend: http://localhost:8000")
        print("🔌 WebSocket: ws://localhost:8000/ws/")
        print("📖 API Docs: http://localhost:8000/docs")
        print("=" * 50)
        print("\n💡 Tips:")
        print("- Configure target accounts in the dashboard")
        print("- Start with conservative rate limits (5 comments/hour)")
        print("- Monitor the activity log for real-time updates")
        print("- The browser window will open automatically for monitoring")
        print("\n🛑 Press Ctrl+C to stop the server")

        # Wait for user to stop
        backend_process.wait()

    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        if "backend_process" in locals():
            backend_process.terminate()
            backend_process.wait()
        print("✅ Server stopped")

    except Exception as e:
        print(f"❌ Error: {e}")
        if "backend_process" in locals():
            backend_process.terminate()


if __name__ == "__main__":
    main()
