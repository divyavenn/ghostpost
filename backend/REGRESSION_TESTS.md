# GhostPoster Regression Test Suite

**Last Updated:** 2025-10-19
**Version:** 3.0 (Docker + noVNC Production Setup)

## Table of Contents
1. [Introduction](#introduction)
2. [Test Environment Setup](#test-environment-setup)
3. [Docker + noVNC Tests](#docker--novnc-tests) ⭐ NEW
4. [Authentication Tests](#authentication-tests)
5. [Core Workflow Tests](#core-workflow-tests)
6. [Scheduler & Automation Tests](#scheduler--automation-tests) ⭐ NEW
7. [User Settings Tests](#user-settings-tests)
8. [Data Management Tests](#data-management-tests)
9. [Error Handling Tests](#error-handling-tests)

---

## Introduction

This document provides comprehensive testing procedures for GhostPoster's Docker-based production deployment with noVNC remote browser access, unified OAuth + browser state authentication, and automated 24-hour scraping.

### Recent Major Updates (2025-10-19)

#### Docker + noVNC Production Setup ⭐ NEW
- **Complete Docker Compose deployment** - One command deployment
- **Integrated noVNC** - Web-based remote browser access on any device
- **No manual setup scripts** - Xvfb, x11vnc, noVNC auto-configured
- **Production-ready** - Works on headless Linux servers
- **Health check endpoint** - `/health/vnc` verifies services ready

#### Unified OAuth + Browser State Flow
- **OAuth browser accessible via noVNC** at `http://server:6080/vnc.html`
- Works on ANY device (Mac, Windows, Linux, iPad, Android)
- Browser state (cookies/localStorage) **automatically saved** after OAuth
- Frontend polls for login completion (no redirect flow)
- Automation reuses saved browser state (no re-authentication)

#### 24-Hour Automated Scraping ⭐ NEW
- **Background scheduler** runs every 24 hours for all users with valid sessions
- **Automatic cache cleanup** - Removes tweets older than 3 days (72 hours)
- **Headless scraping** - Runs silently in background (production)
- **Session validation** - Only scrapes for users with valid browser state

#### Key Implementation Changes:
1. **Docker deployment:** `docker-compose up -d` starts everything
2. **VNC services:** Xvfb, x11vnc, noVNC auto-start in container
3. `POST /auth/twitter/start` launches Playwright browser (visible via noVNC)
4. User opens `http://server:6080/vnc.html` to complete OAuth
5. `GET /auth/callback` saves both OAuth tokens AND browser state
6. Browser navigates to Twitter home to capture all cookies
7. Frontend polls `GET /auth/twitter/status/{session_id}` for completion
8. **Scheduler:** Auto-scrapes every 24 hours, cleans up old tweets
9. Automation reuses saved browser state (headless mode)

---

## Test Environment Setup

### Choose Your Testing Environment

#### Option 1: Docker (Recommended for Production Testing)

**Prerequisites:**
- [ ] Docker and Docker Compose installed
- [ ] Valid Twitter API credentials
- [ ] Server IP or domain configured in Twitter Developer Portal

**Setup:**
```bash
cd backend
cp .env.example .env
# Edit .env with your credentials
nano .env

# Deploy
cd ..
docker-compose up -d

# Wait for services to start
sleep 10

# Verify health
curl http://localhost:8000/health/vnc
```

**Access Points:**
- Backend API: http://localhost:8000
- Frontend: http://localhost:80
- noVNC (OAuth browser): http://localhost:6080/vnc.html

---

#### Option 2: Local Development (Manual Setup)

**Prerequisites:**
- [ ] Python 3.11+ installed
- [ ] Node.js 16+ installed
- [ ] uv package manager installed
- [ ] **Playwright installed:** `pip install playwright && playwright install chromium`
- [ ] Twitter Developer Account with Elevated Access
- [ ] Valid Twitter API credentials in `.env`

**Setup:**
```bash
./setup_venv.sh
./start_backend.sh
cd frontend && npm install && npm run dev
```

**Access Points:**
- Backend: http://localhost:8000
- Frontend: http://localhost:5173

---

### Environment Variables

`backend/.env` must contain:
```bash
TWITTER_CLIENT_ID="..."
TWITTER_CLIENT_SECRET="..."
TWITTER_BEARER_TOKEN="..."
OBELISK_KEY="..."
OAUTH_TOKEN_ENCRYPTION_KEY="..."
BACKEND_URL='http://localhost:8000'  # or 'http://your-server-ip:8000' in production

# Browser settings (NEW)
# Controls headless mode for SCRAPING only (OAuth always visible)
HEADLESS_BROWSER=false  # false=local dev, true=production headless scraping
```

### Twitter Developer Portal Configuration

**CRITICAL:** Register callback URLs in Twitter app settings:

1. Go to https://developer.twitter.com/en/portal/dashboard
2. Select your app → "User authentication settings" → "Edit"
3. Add callback URLs:
   - **Local:** `http://localhost:8000/auth/callback` ✅
   - **Production:** `http://your-server-ip:8000/auth/callback` ✅
4. Verify "App permissions": **Read and write**
5. Verify "Type of App": **Web App, Automated App or Bot**

**Important Notes:**
- ✅ Callback URL: `/auth/callback` (no `/api` prefix!)
- ❌ **NOT** `/api/auth/callback` (frontend uses `/api`, but Twitter doesn't)
- Callback URL must EXACTLY match `BACKEND_URL` + `/auth/callback` in your `.env`
- Frontend uses `/api/auth/...` but Vite proxy strips `/api` before sending to backend
- Twitter OAuth redirects **directly to backend**, bypassing Vite proxy

---

## Docker + noVNC Tests

### Test Case D1: VNC Services Health Check ⭐ CRITICAL

**Objective:** Verify Xvfb, x11vnc, and noVNC started successfully in Docker container

**Prerequisites:** Docker deployment running (`docker-compose up -d`)

**Steps:**
```bash
# 1. Check VNC health endpoint
curl http://localhost:8000/health/vnc

# 2. Check container logs for startup messages
docker-compose logs backend | grep "✅"

# 3. Verify processes running in container
docker-compose exec backend ps aux | grep -E 'Xvfb|x11vnc|novnc'

# 4. Check DISPLAY environment variable
docker-compose exec backend bash -c 'echo $DISPLAY'
```

**Expected Result:**
- ✅ Health check returns `{"ready": true, "checks": {"display": true, "x11vnc": true, "novnc": true}}`
- ✅ Logs show: "✅ Xvfb started (PID: xxx)"
- ✅ Logs show: "✅ x11vnc started (PID: xxx)"
- ✅ Logs show: "✅ noVNC started (PID: xxx)"
- ✅ All three processes visible in `ps aux`
- ✅ `$DISPLAY` outputs `:99`

**Common Failures:**
- Health check shows `"ready": false` → Check container logs for errors
- "Xvfb failed to start" → Permission issues with `/tmp/.X99-lock`
- "x11vnc failed to start" → Xvfb not ready, check display
- "noVNC failed to start" → Check `/opt/novnc` exists and is executable

---

### Test Case D2: noVNC Web Access

**Objective:** Verify noVNC web interface accessible from browser

**Steps:**
1. Open browser to http://localhost:6080/vnc.html
2. Click "Connect" button
3. Observe desktop display
4. Check browser console for errors

**Expected Result:**
- ✅ noVNC page loads (HTML page with VNC canvas)
- ✅ "Connect" button visible
- ✅ After clicking Connect, see gray desktop (Xvfb virtual display)
- ✅ No WebSocket errors in browser console
- ✅ Connection indicator shows "Connected"

**Common Failures:**
- "Failed to connect to server" → Check if x11vnc running on port 5900
- WebSocket errors → Port 6080 not exposed or blocked by firewall
- Blank page → noVNC files not installed, check `/opt/novnc`
- "Connection timeout" → x11vnc not listening, check service

---

### Test Case D3: OAuth Through noVNC (Production Workflow) ⭐ CRITICAL

**Objective:** Verify complete OAuth flow through noVNC remote browser

**Prerequisites:**
- Docker deployment running
- VNC health check passing
- `HEADLESS_BROWSER=true` in `.env` (production mode)

**Steps:**
1. Open frontend: http://localhost:80
2. Click "Login with Twitter"
3. **Open noVNC in another tab:** http://localhost:6080/vnc.html
4. In noVNC window, observe Playwright browser opens
5. Twitter OAuth page visible in noVNC
6. Complete login in noVNC window (enter credentials, authorize)
7. Browser redirects to callback
8. Success page appears in noVNC
9. Browser closes automatically after 2 seconds
10. **Switch back to frontend tab** - should auto-load (polling detected)

**Expected Result:**
- ✅ Browser opens in noVNC display (visible remotely)
- ✅ OAuth page renders correctly in noVNC
- ✅ Can interact with login form via noVNC
- ✅ OAuth completes successfully
- ✅ Browser state saved to `/app/cache/storage_state.json`
- ✅ OAuth tokens saved to `/app/cache/tokens.json`
- ✅ Frontend detects completion and loads

**Verification:**
```bash
# Check browser state saved
docker-compose exec backend ls -la /app/cache/storage_state.json

# Check tokens saved
docker-compose exec backend cat /app/cache/tokens.json | jq

# Check user info
docker-compose exec backend cat /app/cache/user_info.json | jq
```

**Common Failures:**
- Browser doesn't open in noVNC → Check DISPLAY variable inheritance
- "Cannot open display" error → Xvfb not running, check health
- OAuth visible locally but not in noVNC → `headless=False` not respecting DISPLAY
- Browser state not saved → Path issue, check `/app/cache` volume mount
- Callback URL mismatch → Verify Twitter portal matches `BACKEND_URL`

---

### Test Case D4: Headless Scraping After OAuth

**Objective:** Verify automated scraping runs headlessly (no visible browser) after OAuth

**Prerequisites:** OAuth completed through noVNC (Test D3 passed)

**Steps:**
1. Configure user settings (add accounts/queries)
2. Click "Refresh" to trigger scraping
3. **Observe: NO browser window opens** (headless mode)
4. Check backend logs for browser state retrieval
5. Watch noVNC display - should remain gray/empty
6. Wait for scraping to complete

**Expected Result:**
- ✅ NO browser visible in noVNC during scraping
- ✅ Backend logs: "✅ Retrieved browser state for {username}"
- ✅ Scraping completes successfully
- ✅ Tweets appear in frontend
- ✅ No "Cannot open display" errors

**Verification:**
```bash
# Check logs for headless execution
docker-compose logs backend | grep "Retrieved browser state"

# Verify tweets cached
docker-compose exec backend ls -la /app/cache/*_tweets.json
```

**Common Failures:**
- Browser opens during scraping → `HEADLESS_BROWSER` not set to `true`
- "Cannot open display" during headless scraping → Headless mode not actually enabled
- "Session expired" → Browser state invalid, re-run OAuth

---

### Test Case D5: Container Restart Persistence

**Objective:** Verify browser state and tokens persist across container restarts

**Steps:**
```bash
# 1. Note current tweet count and username
# 2. Restart backend container
docker-compose restart backend

# 3. Wait for services to reinitialize
sleep 10

# 4. Check VNC health
curl http://localhost:8000/health/vnc

# 5. Refresh frontend
# 6. Trigger scraping
```

**Expected Result:**
- ✅ VNC services restart successfully
- ✅ Health check passes after restart
- ✅ User still logged in (tokens persisted)
- ✅ Browser state still valid (file persisted)
- ✅ Tweets from before restart still visible
- ✅ Can scrape without re-authentication

**Verification:**
```bash
# Check volume mount persisted data
ls -la backend/cache/
# Should show storage_state.json, tokens.json, etc.
```

---

### Test Case D6: Production Deployment on Headless Server

**Objective:** Verify deployment works on Linux server without GUI

**Prerequisites:** Linux server with Docker, no X11/GUI

**Steps:**
1. SSH into server
2. Deploy: `docker-compose up -d`
3. Check health: `curl http://localhost:8000/health/vnc`
4. **From your laptop:** Open `http://server-ip:6080/vnc.html`
5. Complete OAuth through noVNC
6. Verify automated scraping works

**Expected Result:**
- ✅ Deployment succeeds on headless Linux
- ✅ noVNC accessible from remote machine
- ✅ Can complete OAuth from laptop/phone/tablet
- ✅ Automated scraping runs headlessly on server
- ✅ Scheduler works (check 24 hours later)

**Common Failures:**
- Port 6080 not accessible → Firewall blocking, run `sudo ufw allow 6080/tcp`
- noVNC doesn't load → Check if noVNC service started in container
- OAuth fails → Callback URL must include server IP, not localhost

---

## Authentication Tests

### Test Case 1: Unified OAuth + Browser State Login ⭐

**Objective:** Verify single-flow authentication that saves both OAuth tokens AND browser state

**Steps:**
1. Navigate to http://localhost:5173
2. Observe flickering GhostPoster logo and "Login with Twitter" button
3. Click "Login with Twitter"
4. Alert appears: "A browser window will open on the server..."
5. **Server-side Playwright browser opens** (visible window on backend)
6. Browser automatically navigates to Twitter OAuth page
7. Complete OAuth in that window (enter credentials, click "Authorize app")
8. Browser redirects to callback
9. **Browser navigates to Twitter home** (capturing full session)
10. Success page appears: "Login Successful! Welcome @{handle}"
11. **Browser closes automatically after 2 seconds**
12. **Frontend automatically loads** (polling detected completion)

**Expected Result:**
- ✅ Server browser opens visibly (not headless)
- ✅ OAuth completes in server browser
- ✅ `backend/cache/storage_state.json` contains cookies/localStorage
- ✅ `backend/cache/tokens.json` contains OAuth tokens
- ✅ `backend/cache/user_info.json` contains profile
- ✅ Frontend loads automatically (no manual refresh)
- ✅ URL clean (no OAuth query parameters)

**Common Failures:**
- "You weren't able to give access" → Verify `http://localhost:8000/auth/callback` in Twitter portal
- Browser doesn't open → Run `playwright install chromium`
- Frontend stuck polling → Check `/auth/twitter/status/{session_id}` endpoint

---

### Test Case 2: Session Persistence & Browser State Reuse

**Objective:** Verify sessions persist AND automation reuses browser state

**Steps:**
1. After successful login, note username
2. Refresh page (F5)
3. Close tab, reopen http://localhost:5173
4. Close browser entirely, reopen
5. **Test automation:** Click Refresh to scrape tweets
6. Verify NO new OAuth browser opens
7. Check backend logs for: "✅ Retrieved browser state for {username}"

**Expected Result:**
- ✅ User stays logged in across all scenarios
- ✅ Scraping reuses saved browser state (no re-auth)
- ✅ No visible Playwright browser during automation
- ✅ Backend logs show state retrieval

**Technical:** `read_browser_state()` loads from `storage_state.json`, creates Playwright context with saved cookies.

---

### Test Case 3: Browser State Validation

**Objective:** Verify system detects expired sessions

**Steps:**
1. After login, manually corrupt `storage_state.json` entry
2. Trigger tweet scraping
3. Observe backend logs

**Expected Result:**
- ✅ Detects invalid state: "⚠️ Session expired for {username}"
- ✅ Fails gracefully (doesn't crash)
- ✅ User can re-login to restore

---

## Core Workflow Tests

### Test Case 4: Tweet Scraping with Saved State

**Objective:** Verify automation uses saved browser state (no re-auth)

**Prerequisites:** Authenticated user with accounts/queries configured

**Steps:**
1. Click Refresh button
2. **Verify NO new browser window opens**
3. Watch backend logs for state retrieval
4. Observe "Scraping tweets" animation
5. Wait for completion

**Expected Result:**
- ✅ NO visible Playwright browser (reusing state)
- ✅ Backend logs: "✅ Retrieved browser state for {username}"
- ✅ Tweets scraped successfully
- ✅ Replies generated

**Common Failures:**
- Browser opens again → `storage_state.json` missing/invalid, check cookies
- "No authorization found" → Browser state expired, re-authenticate

---

### Test Case 5: Reply Regeneration

**Objective:** Verify individual reply regeneration

**Steps:**
1. Locate tweet card with reply
2. Click Regenerate button (refresh icon)
3. Observe "Regenerating reply" animation
4. Wait for new reply
5. Verify reply changed

**Expected Result:**
- ✅ Animation displays during generation
- ✅ New reply generated (different from original)
- ✅ Changes saved automatically
- ✅ Persists after page refresh

---

### Test Case 6: Reply Editing with Auto-Save

**Steps:**
1. Click into reply textarea
2. Modify text
3. Observe Save button enables
4. Click Save
5. Refresh page

**Expected Result:**
- ✅ Save button disabled when no changes
- ✅ Save button enables when text modified
- ✅ Changes persist after refresh

---

### Test Case 7: Tweet Grid with Independent Heights

**Objective:** Verify grid cards have independent heights

**Steps:**
1. Observe 2-column tweet grid
2. Verify each card shows complete data
3. Note cards in left/right columns have different heights

**Expected Result:**
- ✅ Cards size independently (not forced to match opposite column)
- ✅ Grid uses `auto-rows-auto items-start`
- ✅ All data visible without truncation

---

### Test Case 8: Publishing Reply

**Steps:**
1. Select tweet
2. Click Reply button (blue)
3. Observe posting animation
4. Switch to Posted tab
5. Verify tweet appears
6. Check Twitter to confirm posted

**Expected Result:**
- ✅ Animation smooth
- ✅ Tweet moved to Posted tab
- ✅ Actually appears on Twitter
- ✅ Action logged

---

### Test Case 9: Skipping Tweet

**Steps:**
1. Click Skip button (X icon)
2. Observe delete animation
3. Verify removed from list
4. Check cache file updated

**Expected Result:**
- ✅ Fade animation plays
- ✅ Tweet removed from UI
- ✅ Deleted from cache
- ✅ Logged in `{username}_log.jsonl`

---

### Test Case 10: Tab Switching (Generated vs Posted)

**Steps:**
1. Verify default "Generated" tab active
2. Click "Posted" tab
3. Verify posted tweets read-only (no edit/publish buttons)
4. Click back to "Generated"

**Expected Result:**
- ✅ Tabs switch without reload
- ✅ Count badges accurate
- ✅ Posted tweets read-only
- ✅ Active tab highlighted (sky-500)

---

## Scheduler & Automation Tests

### Test Case S1: 24-Hour Scheduler Startup ⭐ NEW

**Objective:** Verify background scheduler starts with backend and runs every 24 hours

**Steps:**
```bash
# 1. Start backend and check logs
docker-compose up -d
docker-compose logs -f backend | grep -i scheduler

# OR for local dev:
./start_backend.sh
# Check logs for scheduler messages
```

**Expected Result:**
- ✅ Logs show: "🚀 Scheduler started with 24-hour interval"
- ✅ Logs show: "⏰ Next auto-scrape scheduled for..."
- ✅ No errors during scheduler initialization

**Verification:**
```bash
# Check scheduler is running
curl http://localhost:8000/scheduler/status
```

---

### Test Case S2: Session Validation Before Auto-Scrape ⭐ NEW

**Objective:** Verify scheduler only scrapes for users with valid browser sessions

**Prerequisites:**
- At least one user with valid OAuth + browser state
- One user with expired/missing browser state (optional, for negative test)

**Steps:**
```bash
# 1. Trigger manual scheduler run (for testing)
curl -X POST http://localhost:8000/scheduler/trigger

# 2. Check logs
docker-compose logs backend | grep -E "valid sessions|Session expired"

# 3. Verify scraping only for valid users
```

**Expected Result:**
- ✅ Logs show: "Found X users with valid sessions"
- ✅ Logs show auto-scrape starting for each valid user
- ✅ Logs show: "⚠️ Browser session expired for {expired_user}" (if any)
- ✅ Expired users are skipped (no scraping attempted)
- ✅ Valid users scraped successfully

**Verification:**
```bash
# Check which users have valid sessions
docker-compose exec backend uv run python -c "
from backend.scheduler import get_users_with_valid_sessions
print('Valid users:', get_users_with_valid_sessions())
"
```

---

### Test Case S3: Automatic Cache Cleanup (3-Day Threshold) ⭐ NEW

**Objective:** Verify tweets older than 72 hours are automatically removed during scheduled scrape

**Prerequisites:** Cached tweets with various ages

**Setup:**
```bash
# Create test tweets with old timestamps
docker-compose exec backend uv run python -c "
import json
from datetime import datetime, timedelta
from pathlib import Path

# Create tweets with different ages
tweets = [
    {'id': '1', 'text': '1 hour old', 'timestamp': (datetime.now() - timedelta(hours=1)).isoformat()},
    {'id': '2', 'text': '2 days old', 'timestamp': (datetime.now() - timedelta(days=2)).isoformat()},
    {'id': '3', 'text': '4 days old (should be deleted)', 'timestamp': (datetime.now() - timedelta(days=4)).isoformat()},
    {'id': '4', 'text': '7 days old (should be deleted)', 'timestamp': (datetime.now() - timedelta(days=7)).isoformat()},
]

cache_file = Path('/app/cache/test_user_tweets.json')
with open(cache_file, 'w') as f:
    json.dump(tweets, f)
print(f'Created test cache with {len(tweets)} tweets')
"
```

**Steps:**
1. Trigger scheduled scrape for test user
2. Check backend logs for cleanup messages
3. Verify old tweets removed

**Expected Result:**
- ✅ Logs show: "🧹 Cleaned up X old tweets (older than 72 hours)"
- ✅ Tweets older than 3 days are deleted
- ✅ Recent tweets (< 3 days) are retained
- ✅ Cache file updated correctly

**Verification:**
```bash
# Check remaining tweets
docker-compose exec backend cat /app/cache/test_user_tweets.json | jq 'length'
# Should be 2 (only tweets 1 and 2 remain)

docker-compose exec backend cat /app/cache/test_user_tweets.json | jq '.[].text'
# Should NOT include "4 days old" or "7 days old"
```

---

### Test Case S4: 24-Hour Interval Verification

**Objective:** Verify scheduler actually waits 24 hours between runs

**Note:** This test requires patience or time manipulation

**Steps (Option 1 - Quick Test):**
```bash
# Temporarily change interval to 1 minute for testing
# Edit backend/backend/main.py: start_scheduler(interval_hours=24)
# Change to: start_scheduler(interval_hours=1/60)  # 1 minute

docker-compose restart backend
docker-compose logs -f backend | grep "auto-scrape"

# Should see runs every 1 minute
```

**Steps (Option 2 - Production Test):**
1. Deploy to production
2. Note first auto-scrape timestamp in logs
3. Check logs 24 hours later
4. Verify next run occurred

**Expected Result:**
- ✅ Exactly 24 hours between scheduled runs
- ✅ Manual triggers don't affect schedule
- ✅ Schedule persists across container restarts

---

### Test Case S5: Scheduler Graceful Shutdown

**Objective:** Verify scheduler stops cleanly when backend shuts down

**Steps:**
```bash
# 1. Start backend
docker-compose up -d

# 2. Trigger a long-running scrape
curl -X POST http://localhost:8000/scheduler/trigger

# 3. Immediately stop backend
docker-compose stop backend

# 4. Check logs
docker-compose logs backend | tail -20
```

**Expected Result:**
- ✅ Logs show: "🛑 Scheduler stopped"
- ✅ No errors or stack traces
- ✅ Container stops cleanly (exit code 0)
- ✅ Any in-progress scrapes complete or cancel gracefully

---

### Test Case S6: Failed Auto-Scrape Recovery ⭐ NEW

**Objective:** Verify scheduler continues after a user's scrape fails

**Setup:**
```bash
# Create a user with invalid settings (to trigger failure)
docker-compose exec backend uv run python -c "
from backend.user import write_user_settings
write_user_settings('error_test_user', {
    'relevant_accounts': {'nonexistentuser12345678990': True},
    'queries': [],
    'max_tweets_retrieve': 10
})
"
```

**Steps:**
1. Trigger scheduler manually
2. Observe error for error_test_user
3. Verify scheduler continues for other users

**Expected Result:**
- ✅ Logs show: "❌ [Auto-scrape] Failed for error_test_user: ..."
- ✅ Scheduler CONTINUES processing other users
- ✅ No crashes or hangs
- ✅ Next scheduled run still occurs

**Cleanup:**
```bash
docker-compose exec backend rm /app/cache/error_test_user_settings.json
```

---

## User Settings Tests

### Test Case 11: First-Time Setup Flow

**Objective:** Verify first-time users guided through configuration

**Steps:**
1. Fresh login with no prior settings
2. Settings modal auto-opens
3. Add 2-3 accounts
4. Add 2-3 queries
5. Save
6. Observe auto-refresh triggers

**Expected Result:**
- ✅ Modal opens immediately after first login
- ✅ Can add accounts/queries
- ✅ Auto-refresh after setup

---

### Test Case 12: Managing Accounts

**Steps:**
1. Open settings
2. Add valid account (e.g., "elonmusk")
3. Wait for validation (green checkmark)
4. Add invalid account (e.g., "thisdoesnotexist99999")
5. Observe red warning icon
6. Remove an account

**Expected Result:**
- ✅ Valid accounts marked green
- ✅ Invalid accounts marked red
- ✅ Settings icon shows red badge if any invalid
- ✅ Can remove accounts

---

### Test Case 13: Managing Queries

**Steps:**
1. Open settings
2. Add query: "AI -filter:replies lang:en"
3. Verify accepted
4. Remove a query

**Expected Result:**
- ✅ Can add complex queries with filters
- ✅ Queries saved to `user_info.json`
- ✅ Next scrape uses updated queries

---

## Data Management Tests

### Test Case 14: Cache Persistence

**Steps:**
1. Note tweet count
2. Restart backend
3. Refresh frontend
4. Verify tweets still present

**Expected Result:**
- ✅ Tweets persist after restart
- ✅ `{username}_tweets.json` contains all data

---

### Test Case 15: Cache Append (Not Overwrite)

**Steps:**
1. Note tweet count (e.g., 10)
2. Click Refresh
3. Verify new tweets added (e.g., now 25)
4. Confirm old tweets still exist

**Expected Result:**
- ✅ New tweets appended
- ✅ Old tweets retained
- ✅ No duplicates (same ID)

---

### Test Case 16: Interaction Logging

**Steps:**
1. Perform actions: scrape, edit, delete, post
2. Open `{username}_log.jsonl`
3. Verify entries

**Expected Result:**
- ✅ Each action logged
- ✅ JSONL format (one JSON per line)
- ✅ Contains: timestamp, username, action, tweet_id, metadata

---

## Error Handling Tests

### Test Case 17: Network Failure

**Steps:**
1. Start scraping
2. Disconnect WiFi
3. Observe error handling
4. Reconnect and retry

**Expected Result:**
- ✅ Error message displayed
- ✅ App doesn't crash
- ✅ Can retry after reconnection

---

### Test Case 18: Rate Limiting

**Steps:**
1. Configure 30+ accounts
2. Click Refresh repeatedly
3. Observe timeout errors
4. Wait 15 minutes, retry

**Expected Result:**
- ✅ Timeout errors per account
- ✅ Other accounts continue
- ✅ System recovers after wait

---

### Test Case 19: Expired Browser State

**Steps:**
1. Delete cookies from `storage_state.json`
2. Trigger scraping
3. Observe error

**Expected Result:**
- ✅ Detects expiration
- ✅ Error: "Session expired, please login again"
- ✅ Can re-authenticate

---

## Test Completion Checklist

### Docker + noVNC (Production) ⭐ CRITICAL
- [ ] Test Case D1: VNC Services Health Check
- [ ] Test Case D2: noVNC Web Access
- [ ] Test Case D3: OAuth Through noVNC ⭐ (MOST CRITICAL)
- [ ] Test Case D4: Headless Scraping After OAuth
- [ ] Test Case D5: Container Restart Persistence
- [ ] Test Case D6: Production Deployment on Headless Server

### Scheduler & Automation ⭐ NEW
- [ ] Test Case S1: 24-Hour Scheduler Startup
- [ ] Test Case S2: Session Validation Before Auto-Scrape
- [ ] Test Case S3: Automatic Cache Cleanup (3-Day Threshold)
- [ ] Test Case S4: 24-Hour Interval Verification
- [ ] Test Case S5: Scheduler Graceful Shutdown
- [ ] Test Case S6: Failed Auto-Scrape Recovery

### Authentication
- [ ] Test Case 1: Unified OAuth ⭐ (CRITICAL)
- [ ] Test Case 2: Session Persistence
- [ ] Test Case 3: Browser State Validation

### Core Workflows
- [ ] Test Case 4: Tweet Scraping with Saved State
- [ ] Test Case 5: Reply Regeneration
- [ ] Test Case 6: Reply Editing with Auto-Save
- [ ] Test Case 7: Tweet Grid with Independent Heights
- [ ] Test Case 8: Publishing Reply
- [ ] Test Case 9: Skipping Tweet
- [ ] Test Case 10: Tab Switching

### Settings & Data
- [ ] Test Case 11: First-Time Setup Flow
- [ ] Test Case 12: Managing Accounts
- [ ] Test Case 13: Managing Queries
- [ ] Test Case 14: Cache Persistence
- [ ] Test Case 15: Cache Append (Not Overwrite)
- [ ] Test Case 16: Interaction Logging

### Error Handling
- [ ] Test Case 17: Network Failure
- [ ] Test Case 18: Rate Limiting
- [ ] Test Case 19: Expired Browser State

---

## Troubleshooting Guide

### Docker + noVNC Issues

| Problem | Solution |
|---------|----------|
| Health check shows `"ready": false` | Check `docker-compose logs backend` for VNC service errors |
| "Xvfb failed to start" | Permission issues with `/tmp/.X99-lock` - restart container |
| "x11vnc failed to start" | Xvfb not ready - check DISPLAY=:99 set correctly |
| "noVNC failed to start" | Check `/opt/novnc` exists in container, verify port 6080 exposed |
| noVNC page won't load | Port 6080 blocked - check firewall, try `sudo ufw allow 6080/tcp` |
| WebSocket connection failed | x11vnc not running on port 5900 - check service status |
| "Cannot open display" during OAuth | DISPLAY variable not inherited - check docker-compose.yml sets it |
| OAuth browser not visible in noVNC | Browser launched before VNC ready - check `/health/vnc` first |
| Port 6080 not accessible remotely | Firewall or cloud security group blocking - allow TCP 6080 |

### Authentication Issues

| Problem | Solution |
|---------|----------|
| "You weren't able to give access" | Callback URL mismatch - verify `BACKEND_URL` + `/auth/callback` in Twitter portal |
| Browser doesn't open (local dev) | Run `playwright install chromium` or check PATH |
| Frontend stuck polling | Check `/auth/twitter/status/{session_id}` endpoint responding |
| Scraping requires re-auth | Browser state expired/missing - check `storage_state.json` has valid cookies |
| "No authorization found" | Browser state expired or not saved - re-authenticate via OAuth |
| Callback URL redirect_uri mismatch | Ensure Twitter portal URL EXACTLY matches `.env` BACKEND_URL + `/auth/callback` |

### Scheduler Issues

| Problem | Solution |
|---------|----------|
| Scheduler not starting | Check logs for startup errors - verify `/scheduler/status` endpoint |
| Auto-scrape not running | Check if any users have valid sessions - use `get_users_with_valid_sessions()` |
| Cache cleanup not working | Verify `cleanup_old_tweets()` called - check logs for "🧹 Cleaned up..." |
| Scheduler runs too frequently | Check `main.py` interval setting - should be 24 hours |
| Old tweets not deleted | Timestamps not in ISO format or threshold logic issue - check tweet ages |

---

## API Endpoint Reference

**Health Checks:** ⭐ NEW
- `GET /health/vnc` - Check VNC services ready (display, x11vnc, noVNC)

**Authentication:**
- `POST /auth/twitter/start` - Start OAuth (launches server browser)
- `GET /auth/callback` - OAuth callback (saves tokens + browser state)
- `GET /auth/twitter/status/{session_id}` - Poll login status

**Scheduler:** ⭐ NEW
- `GET /scheduler/status` - Get scheduler status (running, next run time)
- `POST /scheduler/trigger` - Manually trigger auto-scrape (testing only)

**Tweets:**
- `GET /tweets/{username}` - Get cached tweets
- `PATCH /tweets/{username}/{tweet_id}/reply` - Edit reply
- `DELETE /tweets/{username}/{tweet_id}` - Delete tweet

**Generation:**
- `POST /generate/{username}/replies` - Generate all replies
- `POST /generate/{username}/replies/{tweet_id}` - Regenerate single

**Posting:**
- `POST /post/reply?username={username}` - Post reply
- `DELETE /post/tweet/{id}?username={username}` - Delete posted

**Scraping:**
- `POST /read/{username}/tweets` - Scrape tweets (uses saved browser state)
- `GET /read/{username}/status` - Get scraping progress status

**User:**
- `GET /user/{username}/info` - Get profile
- `GET /user/{username}/settings` - Get settings
- `PUT /user/{username}/settings` - Update settings

---

## File Structure

```
backend/cache/
├── storage_state.json      # Browser state (cookies/localStorage) per user
├── tokens.json             # OAuth tokens (refresh/access/expires_at) per user
├── user_info.json          # Profiles and settings
├── {username}_tweets.json  # Tweet cache per user
└── {username}_log.jsonl    # Interaction log (append-only)
```

---

## Change Log

### 2025-10-19 (v3.0) - Docker + noVNC + Scheduler
- ✅ **NEW:** Complete Docker + noVNC test suite (Test Cases D1-D6)
  - VNC services health check
  - noVNC web access verification
  - OAuth through noVNC (production workflow)
  - Headless scraping after OAuth
  - Container restart persistence
  - Production deployment on headless servers
- ✅ **NEW:** Scheduler & Automation tests (Test Cases S1-S6)
  - 24-hour scheduler startup verification
  - Session validation before auto-scrape
  - Automatic cache cleanup (3-day threshold)
  - 24-hour interval verification
  - Scheduler graceful shutdown
  - Failed auto-scrape recovery
- ✅ **NEW:** Environment setup options (Docker vs Local)
- ✅ **NEW:** `HEADLESS_BROWSER` environment variable documentation
- ✅ **NEW:** VNC health check endpoint (`/health/vnc`)
- ✅ **NEW:** Scheduler API endpoints (`/scheduler/status`, `/scheduler/trigger`)
- ✅ **NEW:** Scraping status endpoint (`/read/{username}/status`)
- ✅ Updated Test Case 1: Now mentions noVNC option for production
- ✅ Updated Test Completion Checklist: Organized by category with new Docker/Scheduler sections
- ✅ Updated Troubleshooting Guide: Added Docker+noVNC and Scheduler issues
- ✅ Updated API Endpoint Reference: Added health checks and scheduler endpoints
- ✅ Updated Twitter Developer Portal: Added production callback URL note

### 2025-10-17 (v2.0)
- ✅ Updated for unified OAuth + browser state flow
- ✅ Added Test Case 1: Unified OAuth (server browser)
- ✅ Added Test Case 2: Session persistence & state reuse
- ✅ Added Test Case 3: Browser state validation
- ✅ Updated scraping test to verify state reuse (no re-auth)
- ✅ Added reply regeneration test
- ✅ Updated grid layout test (independent heights)
- ✅ Added troubleshooting for new OAuth flow
- ✅ Updated API endpoint reference
- ✅ Added technical implementation details

### Previous
- Initial regression test suite
