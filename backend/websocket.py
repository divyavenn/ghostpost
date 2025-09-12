from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, List
import os
from pathlib import Path

from twitter_agent import TwitterAgent, Tweet, CommentOpportunity

app = FastAPI(title="Twitter Agent Dashboard")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store active connections and agent instances
connections: Dict[str, WebSocket] = {}
agents: Dict[str, TwitterAgent] = {}
agent_tasks: Dict[str, asyncio.Task] = {}

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
    """Serve the dashboard HTML"""
    return HTMLResponse(content=open("frontend/index.html").read())

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
