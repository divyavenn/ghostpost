# GhostPoster Regression Test Suite

**Last Updated:** 2025-10-17  
**Version:** 2.0 (Unified OAuth + Browser State Flow)

## Table of Contents
1. [Introduction](#introduction)
2. [Test Environment Setup](#test-environment-setup)
3. [Authentication Tests](#authentication-tests)
4. [Core Workflow Tests](#core-workflow-tests)
5. [User Settings Tests](#user-settings-tests)
6. [Data Management Tests](#data-management-tests)
7. [Error Handling Tests](#error-handling-tests)

---

## Introduction

This document provides comprehensive testing procedures for GhostPoster's unified OAuth + browser state authentication system and core workflows.

### Recent Major Updates (2025-10-17)

#### Unified OAuth + Browser State Flow
- **OAuth now happens in server-side Playwright browser** (visible, not headless)
- Browser state (cookies/localStorage) **automatically saved** after OAuth completes
- Frontend polls for login completion (no redirect flow)
- Eliminates redirect issues and simplifies authentication

#### Key Implementation Changes:
1. `POST /auth/twitter/start` launches Playwright browser on backend
2. Browser navigates to OAuth, user completes auth in that window
3. `GET /auth/callback` saves both OAuth tokens AND browser state
4. Browser navigates to Twitter home to capture all cookies
5. Frontend polls `GET /auth/twitter/status/{session_id}` for completion
6. Automation reuses saved browser state (no re-authentication)

---

## Test Environment Setup

### Prerequisites

- [ ] Python 3.11+ installed
- [ ] Node.js 16+ installed  
- [ ] uv package manager installed
- [ ] **Playwright installed:** `pip install playwright && playwright install chromium`
- [ ] Twitter Developer Account with Elevated Access
- [ ] Valid Twitter API credentials in `.env`

### Environment Variables

`backend/.env` must contain:
```
TWITTER_CLIENT_ID="..."
TWITTER_CLIENT_SECRET="..."
TWITTER_BEARER_TOKEN="..."
OBELISK_KEY="..."
OAUTH_TOKEN_ENCRYPTION_KEY="..."
BACKEND_URL='http://localhost:8000'
```

### Twitter Developer Portal Configuration

**CRITICAL:** Register callback URLs in Twitter app settings:

1. Go to https://developer.twitter.com/en/portal/dashboard
2. Select your app → "User authentication settings" → "Edit"
3. Add callback URLs:
   - `http://localhost:8000/auth/callback` ✅ (backend OAuth)
   - `http://localhost:8000/api/auth/callback` (Vite proxy)
4. Verify "App permissions": **Read and write**
5. Verify "Type of App": **Web App, Automated App or Bot**

### Server Startup

```bash
./setup_venv.sh
./start_backend.sh
cd frontend && npm install && npm run dev
```

Verify:
- Backend: http://localhost:8000
- Frontend: http://localhost:5173
- No startup errors

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

- [ ] Test Case 1: Unified OAuth ⭐ (CRITICAL)
- [ ] Test Case 2: Session Persistence
- [ ] Test Case 4: Scraping with State Reuse
- [ ] All core workflow tests passed
- [ ] User settings functional
- [ ] Data persists correctly
- [ ] Error handling verified
- [ ] No critical bugs found

---

## Troubleshooting Guide

| Problem | Solution |
|---------|----------|
| "You weren't able to give access" | Verify `http://localhost:8000/auth/callback` in Twitter portal |
| Browser doesn't open | Run `playwright install chromium` |
| Frontend stuck polling | Check `/auth/twitter/status/{session_id}` endpoint |
| Scraping requires re-auth | Check `storage_state.json` has valid cookies |
| "No authorization found" | Browser state expired, re-authenticate |

---

## API Endpoint Reference

**Authentication:**
- `POST /auth/twitter/start` - Start OAuth (launches server browser)
- `GET /auth/callback` - OAuth callback (saves tokens + browser state)
- `GET /auth/twitter/status/{session_id}` - Poll login status

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
- `POST /read/{username}/tweets` - Scrape (uses saved browser state)

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
