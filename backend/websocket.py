from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, List
import os
import secrets
from pathlib import Path

from twitter_agent import TwitterAgent, Tweet, CommentOpportunity
from oauth_utils import pkce_client

app = FastAPI(title="Twitter Agent Dashboard")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files from the built React app
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

# Store active connections and agent instances
connections: Dict[str, WebSocket] = {}
agents: Dict[str, TwitterAgent] = {}
agent_tasks: Dict[str, asyncio.Task] = {}

# OAuth 2.0 PKCE authentication storage
user_tokens: Dict[str, Dict] = {}
code_verifiers: Dict[str, str] = {}

# Persistent storage for code verifiers (survives server reloads)
import json
from pathlib import Path

CODE_VERIFIERS_FILE = Path(__file__).parent / "code_verifiers.json"

def load_code_verifiers():
    """Load code verifiers from persistent storage"""
    global code_verifiers
    if CODE_VERIFIERS_FILE.exists():
        try:
            with open(CODE_VERIFIERS_FILE, 'r') as f:
                code_verifiers = json.load(f)
        except:
            code_verifiers = {}

def save_code_verifiers():
    """Save code verifiers to persistent storage"""
    with open(CODE_VERIFIERS_FILE, 'w') as f:
        json.dump(code_verifiers, f)

# Load existing verifiers on startup
load_code_verifiers()

class AgentWebSocket:
    """Enhanced TwitterAgent with WebSocket communication"""
    
    def __init__(self, agent: TwitterAgent, websocket: WebSocket, session_id: str):
        self.agent = agent
        self.websocket = websocket
        self.session_id = session_id
        self.is_running = False
    
    async def send_update(self, event_type: str, data: dict):
        """Send real-time updates to frontend"""
        message = {
            "type": event_type,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }
        try:
            await self.websocket.send_text(json.dumps(message))
        except:
            pass  # Connection might be closed
    
    async def enhanced_start_browser(self, headless: bool = False):
        """Start browser with frontend updates"""
        await self.send_update("status", {"message": "🚀 Starting browser...", "status": "starting"})
        
        # Override the original method to add logging
        original_method = self.agent.start_browser
        await original_method(headless=headless)
        
        await self.send_update("status", {"message": "✅ Browser started", "status": "ready"})
    
    async def enhanced_login(self):
        """Login with real-time updates"""
        await self.send_update("status", {"message": "🔐 Logging into Twitter...", "status": "logging_in"})
        
        success = await self.agent.login_to_twitter()
        
        if success:
            await self.send_update("status", {"message": "✅ Successfully logged in", "status": "logged_in"})
        else:
            await self.send_update("status", {"message": "❌ Login failed", "status": "error"})
        
        return success
    
    async def enhanced_monitor_account(self, username: str):
        """Monitor account with real-time updates"""
        await self.send_update("monitoring", {
            "message": f"🔍 Monitoring @{username}...",
            "account": username,
            "status": "monitoring"
        })
        
        # Navigate to user
        if not await self.agent.navigate_to_user(username):
            await self.send_update("error", {
                "message": f"❌ Failed to load @{username}",
                "account": username
            })
            return []
        
        # Extract tweets
        await self.send_update("extracting", {
            "message": f"📊 Extracting tweets from @{username}...",
            "account": username
        })
        
        tweets = await self.agent.extract_tweets(limit=5)
        
        # Send tweet data to frontend
        tweet_data = []
        for tweet in tweets:
            tweet_data.append({
                "id": tweet.id,
                "author": tweet.author,
                "content": tweet.content[:100] + "..." if len(tweet.content) > 100 else tweet.content,
                "engagement": tweet.engagement,
                "timestamp": tweet.timestamp.isoformat()
            })
        
        await self.send_update("tweets_extracted", {
            "account": username,
            "tweets": tweet_data,
            "count": len(tweets)
        })
        
        # Evaluate opportunities
        opportunities = []
        for tweet in tweets:
            opportunity = await self.agent.evaluate_tweet_for_commenting(tweet)
            if opportunity.relevance_score > 0.3:
                opportunities.append(opportunity)
                
                # Send opportunity to frontend
                await self.send_update("opportunity_found", {
                    "account": username,
                    "tweet_content": tweet.content[:100] + "...",
                    "relevance_score": opportunity.relevance_score,
                    "comment_suggestion": opportunity.comment_suggestion,
                    "priority": opportunity.priority
                })
        
        await self.send_update("monitoring_complete", {
            "account": username,
            "opportunities": len(opportunities)
        })
        
        return opportunities
    
    async def enhanced_post_comment(self, opportunity: CommentOpportunity):
        """Post comment with real-time updates"""
        if not self.agent.can_comment():
            await self.send_update("rate_limited", {
                "message": "⏳ Rate limit reached, skipping comment"
            })
            return False
        
        await self.send_update("commenting", {
            "message": f"💬 Posting comment...",
            "comment": opportunity.comment_suggestion,
            "tweet_preview": opportunity.tweet.content[:50] + "..."
        })
        
        # Simulate comment posting (replace with real implementation)
        await asyncio.sleep(3)
        
        # Update counters
        self.agent.comments_today += 1
        self.agent.comments_this_hour += 1
        self.agent.last_comment_time = datetime.now()
        
        await self.send_update("comment_posted", {
            "message": "✅ Comment posted successfully!",
            "comment": opportunity.comment_suggestion,
            "stats": {
                "comments_today": self.agent.comments_today,
                "comments_this_hour": self.agent.comments_this_hour,
                "max_per_hour": self.agent.max_comments_per_hour,
                "max_per_day": self.agent.max_comments_per_day
            }
        })
        
        return True
    
    async def run_enhanced_cycle(self):
        """Run monitoring cycle with real-time updates"""
        self.is_running = True
        
        try:
            await self.enhanced_start_browser(headless=False)
            
            if not await self.enhanced_login():
                return
            
            await self.send_update("cycle_start", {
                "message": "🔄 Starting monitoring cycle",
                "target_accounts": self.agent.target_accounts
            })
            
            all_opportunities = []
            
            # Monitor each account
            for username in self.agent.target_accounts:
                if not self.is_running:
                    break
                    
                if username.strip():
                    opportunities = await self.enhanced_monitor_account(username.strip())
                    all_opportunities.extend(opportunities)
                    
                    # Random delay between accounts
                    delay = 15
                    await self.send_update("waiting", {
                        "message": f"⏳ Waiting {delay}s before next account...",
                        "delay": delay
                    })
                    await asyncio.sleep(delay)
            
            # Sort and post comments
            all_opportunities.sort(key=lambda x: x.priority, reverse=True)
            
            for opportunity in all_opportunities[:3]:  # Top 3
                if not self.is_running or not self.agent.can_comment():
                    break
                    
                await self.enhanced_post_comment(opportunity)
                await asyncio.sleep(60)  # Delay between comments
            
            await self.send_update("cycle_complete", {
                "message": "✅ Monitoring cycle completed",
                "total_opportunities": len(all_opportunities),
                "comments_posted": min(3, len(all_opportunities))
            })
            
        except Exception as e:
            await self.send_update("error", {
                "message": f"❌ Error: {str(e)}",
                "error": str(e)
            })
        finally:
            if self.agent.browser:
                await self.agent.browser.close()
            self.is_running = False

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    connections[session_id] = websocket
    
    try:
        # Create agent instance
        agent = TwitterAgent()
        agents[session_id] = agent
        
        # Create enhanced agent wrapper
        enhanced_agent = AgentWebSocket(agent, websocket, session_id)
        
        await enhanced_agent.send_update("connected", {
            "message": "🤖 Agent connected",
            "session_id": session_id
        })
        
        while True:
            # Wait for commands from frontend
            data = await websocket.receive_text()
            command = json.loads(data)
            
            if command["type"] == "start_monitoring":
                # Start monitoring in background
                task = asyncio.create_task(enhanced_agent.run_enhanced_cycle())
                agent_tasks[session_id] = task
                
            elif command["type"] == "stop_monitoring":
                enhanced_agent.is_running = False
                if session_id in agent_tasks:
                    agent_tasks[session_id].cancel()
                    
            elif command["type"] == "update_config":
                # Update agent configuration
                config = command["data"]
                if "target_accounts" in config:
                    agent.target_accounts = config["target_accounts"]
                if "max_comments_per_hour" in config:
                    agent.max_comments_per_hour = config["max_comments_per_hour"]
                
                await enhanced_agent.send_update("config_updated", {
                    "message": "⚙️ Configuration updated",
                    "config": config
                })
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        # Cleanup
        if session_id in connections:
            del connections[session_id]
        if session_id in agents:
            if agents[session_id].browser:
                await agents[session_id].browser.close()
            del agents[session_id]
        if session_id in agent_tasks:
            agent_tasks[session_id].cancel()
            del agent_tasks[session_id]

@app.get("/")
async def get_dashboard():
    """Serve the dashboard with authentication status"""
    # Check if frontend is built, otherwise serve simple dashboard
    frontend_path = Path(__file__).parent.parent / "frontend" / "dist" / "index.html"
    
    if frontend_path.exists():
        # Serve the built React frontend
        return HTMLResponse(content=open(frontend_path).read())
    else:
        # Serve simple dashboard with auth status
        auth_status = await auth_status()
        
        # Build user list HTML
        user_list_html = ""
        if auth_status['authenticated']:
            user_list_html = "<ul>"
            for user in auth_status.get('users', []):
                user_list_html += f'<li>@{user["username"]} (ID: {user["user_id"]})</li>'
            user_list_html += "</ul>"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>FloodMe Dashboard</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
                .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                h1 {{ color: #1da1f2; }}
                .status {{ background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                .authenticated {{ border-left: 4px solid #28a745; }}
                .not-authenticated {{ border-left: 4px solid #dc3545; }}
                .endpoint {{ background: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 5px; border-left: 4px solid #1da1f2; }}
                .method {{ font-weight: bold; color: #28a745; }}
                .url {{ font-family: monospace; color: #6c757d; }}
                .button {{ background: #1da1f2; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 10px 5px; }}
                .button.danger {{ background: #dc3545; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🤖 FloodMe Dashboard</h1>
                <p>Twitter automation platform with OAuth 2.0 PKCE authentication</p>
                
                <div class="status {'authenticated' if auth_status['authenticated'] else 'not-authenticated'}">
                    <h3>{'✅ Authenticated' if auth_status['authenticated'] else '❌ Not Authenticated'}</h3>
                    {f"<p>Users: {auth_status['user_count']}</p>" if auth_status['authenticated'] else "<p>No users authenticated</p>"}
                    {user_list_html}
                </div>
                
                <h2>Available Endpoints:</h2>
                
                <div class="endpoint">
                    <div class="method">GET</div>
                    <div class="url">/auth/login</div>
                    <div>Start OAuth 2.0 PKCE authentication flow</div>
                    <a href="/auth/login" class="button">Login with Twitter</a>
                </div>
                
                <div class="endpoint">
                    <div class="method">GET</div>
                    <div class="url">/auth/status</div>
                    <div>Check authentication status</div>
                    <a href="/auth/status" class="button">Check Status</a>
                </div>
                
                <div class="endpoint">
                    <div class="method">POST</div>
                    <div class="url">/test-post</div>
                    <div>Test posting a tweet (requires authentication)</div>
                    <p><em>Use API docs to test this endpoint</em></p>
                </div>
                
                <div class="endpoint">
                    <div class="method">GET</div>
                    <div class="url">/docs</div>
                    <div>Interactive API documentation (Swagger UI)</div>
                    <a href="/docs" class="button">View API Docs</a>
                </div>
                
                {f'<a href="/auth/logout" class="button danger">Logout All Users</a>' if auth_status['authenticated'] else ''}
            </div>
        </body>
        </html>
        """
        
        return HTMLResponse(content=html_content)

@app.get("/vite.svg")
async def get_vite_svg():
    """Serve vite.svg"""
    vite_svg_path = Path(__file__).parent.parent / "frontend" / "public" / "vite.svg"
    if vite_svg_path.exists():
        return HTMLResponse(content=open(vite_svg_path).read(), media_type="image/svg+xml")
    else:
        return {"error": "vite.svg not found"}

@app.get("/status")
async def get_status():
    """Get current status of all agents"""
    status = {}
    for session_id, agent in agents.items():
        status[session_id] = {
            "comments_today": agent.comments_today,
            "comments_this_hour": agent.comments_this_hour,
            "target_accounts": agent.target_accounts,
            "is_running": session_id in agent_tasks and not agent_tasks[session_id].done()
        }
    return status


# OAuth 2.0 PKCE Authentication Routes

@app.get("/auth/login")
async def login():
    """Start OAuth 2.0 PKCE flow"""
    try:
        # Generate state first
        state = secrets.token_urlsafe(32)
        
        # Get authorization URL with our state
        auth_url, code_verifier = pkce_client.get_authorization_url(state)
        
        # Store code verifier with our state
        code_verifiers[state] = code_verifier
        save_code_verifiers()  # Persist to file
        
        return RedirectResponse(url=auth_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start OAuth flow: {str(e)}")


@app.get("/auth/callback")
async def callback(request: Request):
    """Handle OAuth callback and exchange code for token"""
    try:
        code = request.query_params.get("code")
        state = request.query_params.get("state")
        
        if not code:
            raise HTTPException(status_code=400, detail="Authorization code not provided")
        
        # Reload verifiers in case of server restart
        load_code_verifiers()
        
        if not state or state not in code_verifiers:
            raise HTTPException(status_code=400, detail="Invalid state parameter")
        
        # Get stored code verifier
        code_verifier = code_verifiers.pop(state)
        save_code_verifiers()  # Update persistent storage
        
        # Exchange code for token
        token_response = pkce_client.exchange_code_for_token(code, code_verifier)
        
        access_token = token_response["access_token"]
        refresh_token = token_response.get("refresh_token")
        
        # Get user info (optional - might fail due to app configuration)
        print("🔄 Getting user info...")
        try:
            user_info = pkce_client.get_user_info(access_token)
            print(f"✅ User info: {user_info}")
            user_id = user_info["data"]["id"]
            username = user_info["data"]["username"]
        except Exception as e:
            print(f"⚠️ User info failed: {e}")
            print("🔄 Using fallback user info...")
            # Use a fallback approach - generate a user ID from the token
            user_id = f"user_{hash(access_token) % 1000000}"
            username = "authenticated_user"
            user_info = {"data": {"id": user_id, "username": username}}
        
        # Store tokens (in production, use secure database storage)
        user_tokens[user_id] = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "username": username,
            "user_id": user_id
        }
        
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Authentication Successful</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
                .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .success {{ color: #28a745; font-size: 24px; margin-bottom: 20px; }}
                .info {{ background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                .button {{ background: #1da1f2; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 10px 5px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success">✅ Authentication Successful!</div>
                <p>Welcome, @{username}!</p>
                <div class="info">
                    <strong>User ID:</strong> {user_id}<br>
                    <strong>Username:</strong> @{username}<br>
                    <strong>Access Token:</strong> {access_token[:20]}...<br>
                </div>
                <p>You can now use the dashboard to manage your Twitter automation.</p>
                <a href="/" class="button">Go to Dashboard</a>
                <a href="/docs" class="button">View API Docs</a>
                <a href="/auth/status" class="button">Check Auth Status</a>
            </div>
        </body>
        </html>
        """)
        
    except Exception as e:
        print(f"❌ Authentication error: {str(e)}")
        print(f"❌ Error type: {type(e).__name__}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Authentication Failed</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
                .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .error {{ color: #dc3545; font-size: 24px; margin-bottom: 20px; }}
                .button {{ background: #1da1f2; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 10px 5px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="error">❌ Authentication Failed</div>
                <p>Error: {str(e)}</p>
                <a href="/auth/login" class="button">Try Again</a>
            </div>
        </body>
        </html>
        """)


@app.get("/auth/status")
async def auth_status():
    """Check authentication status"""
    if not user_tokens:
        return {"authenticated": False, "message": "No users authenticated"}
    
    # Return info for all authenticated users
    users = []
    for user_id, token_data in user_tokens.items():
        users.append({
            "user_id": user_id,
            "username": token_data["username"],
            "has_refresh_token": bool(token_data.get("refresh_token"))
        })
    
    return {
        "authenticated": True,
        "user_count": len(users),
        "users": users
    }


@app.post("/auth/logout")
async def logout(user_id: str = None):
    """Logout user(s)"""
    if user_id:
        if user_id in user_tokens:
            del user_tokens[user_id]
            return {"message": f"User {user_id} logged out"}
        else:
            raise HTTPException(status_code=404, detail="User not found")
    else:
        # Logout all users
        user_tokens.clear()
        return {"message": "All users logged out"}


@app.post("/test-post")
async def test_post(tweet_text: str, user_id: str = None):
    """Test posting a tweet using authenticated user token"""
    try:
        from post_takes import post_take_with_token
        
        if not user_tokens:
            raise HTTPException(status_code=401, detail="No users authenticated")
        
        if user_id:
            if user_id not in user_tokens:
                raise HTTPException(status_code=404, detail="User not found")
            access_token = user_tokens[user_id]["access_token"]
        else:
            # Use first available user's token
            access_token = list(user_tokens.values())[0]["access_token"]
        
        result = post_take_with_token(tweet_text, access_token)
        
        return {
            "success": True,
            "message": "Tweet posted successfully",
            "tweet_id": result.get("data", {}).get("id"),
            "result": result
        }
    except Exception as e:
        print(f"❌ Test post error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to post tweet: {str(e)}")


def get_user_token(user_id: str = None) -> str:
    """Get access token for user (helper function for TwitterAgent)"""
    if not user_tokens:
        raise HTTPException(status_code=401, detail="No users authenticated")
    
    if user_id:
        if user_id not in user_tokens:
            raise HTTPException(status_code=404, detail="User not found")
        return user_tokens[user_id]["access_token"]
    else:
        # Return first available user's token
        return list(user_tokens.values())[0]["access_token"]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
