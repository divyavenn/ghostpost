# GhostPoster Regression Test Suite

## Table of Contents
1. [Introduction](#introduction)
2. [Test Environment Setup](#test-environment-setup)
3. [Authentication Tests](#authentication-tests)
4. [Core Workflow Tests](#core-workflow-tests)
5. [User Settings Tests](#user-settings-tests)
6. [Data Management Tests](#data-management-tests)
7. [Error Handling Tests](#error-handling-tests)
8. [Integration Tests](#integration-tests)

---

## Introduction

This document provides a comprehensive checklist for manually testing GhostPoster before releases. Each test case includes step-by-step instructions that can be followed by both technical and non-technical team members.

### How to Use This Document

1. **Before Each Release**: Run through all test cases in order
2. **Track Results**: Mark each test as PASS/FAIL
3. **Document Issues**: Note any failures with screenshots and error messages
4. **Retest Fixes**: After bug fixes, rerun failed tests to verify resolution

### Test Status Legend
- ✅ **PASS**: Feature works as expected
- ❌ **FAIL**: Feature does not work or produces errors
- ⚠️ **PARTIAL**: Feature works but with minor issues
- ⏭️ **SKIP**: Test not applicable to current build

---

## Test Environment Setup

### Prerequisites Checklist

Before beginning tests, ensure:

- [ ] Python 3.11+ installed
- [ ] Node.js 16+ installed
- [ ] uv package manager installed
- [ ] Twitter Developer Account with Elevated Access
- [ ] Valid Twitter API credentials in `.env` file

### Environment Variables Required

Verify the following exist in `backend/.env`:
```
TWITTER_CLIENT_ID="..."
TWITTER_CLIENT_SECRET="..."
TWITTER_BEARER_TOKEN="..."
OBELISK_KEY="..."
OAUTH_TOKEN_ENCRYPTION_KEY="..."
BACKEND_URL='http://localhost:8000'
```

### Server Startup

**Mac:**
```bash
./setup_venv.sh
./start_backend.sh
cd frontend && npm install && npm run dev
```

**Linux (Ubuntu):**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
./setup_venv.sh
./start_backend.sh
cd frontend && npm install && npm run dev
```

### Verification

- [ ] Backend running on http://localhost:8000
- [ ] Frontend running on http://localhost:5173
- [ ] No startup errors in terminal

---

## Authentication Tests

### Test Case 1: Initial OAuth Login Flow

**Objective:** Verify users can successfully authenticate with Twitter OAuth

**Prerequisites:**
- Fresh browser session (clear cache/cookies)
- No existing authentication
- Valid Twitter account

**Steps:**
1. Navigate to http://localhost:5173
2. Observe the login screen displays "GhostPost" title and "Login with Twitter" button
3. Click "Login with Twitter" button
4. Observe popup window opens (or page redirects if popup blocked)
5. Twitter OAuth page loads
6. Enter Twitter credentials if not already logged in
7. Click "Authorize app" on Twitter's authorization page
8. Wait for redirect back to application

**Expected Result:**
- Popup closes automatically (or page redirects back)
- URL updates with `?username={handle}&status=success`
- Main application interface loads
- Tweet cache loads (may be empty initially)
- Up to date PFP, username, handle, and follower count ares diplayed in user settings panel (Click the icon on top left with person and gear)
- backend/cache/storage_state.json shows the user's storage state (this does not work yet, am fixing this)
- backend/cache/user_info.json shows the user's up to date info and follower count. 
- backend/cache/tokens.json shows the user's refresh and access tokens 
- URL cleans up (removes query parameters)

**Pass/Fail Criteria:**
- ✅ PASS: User successfully authenticated, username stored, app loads
- ❌ FAIL: OAuth flow errors, popup doesn't close, user not authenticated

**Common Failures:**
- Popup blocked by browser → Verify popup blocker settings
- Invalid redirect URI → Check Twitter Developer Portal callback URL matches `http://localhost:8000/auth/callback`
- "Unauthorized" error → Verify CLIENT_ID and CLIENT_SECRET in .env

---

### Test Case 2: OAuth Error Handling

**Objective:** Verify graceful handling of OAuth failures

**Prerequisites:**
- Fresh browser session

**Steps:**
1. Start OAuth flow (Login with Twitter)
2. On Twitter OAuth page, click "Cancel" or close the window
3. Observe application response

**Expected Result:**
- Alert displays: "Authentication failed: [error description]"
- User returned to login screen
- localStorage cleared
- URL parameters cleaned up

**Pass/Fail Criteria:**
- ✅ PASS: Error message displayed, user on login screen
- ❌ FAIL: App crashes, blank screen, or user stuck in broken state

---

### Test Case 3: Session Persistence

**Objective:** Verify authentication persists across browser sessions

**Prerequisites:**
- Successfully authenticated user (from Test Case 1)

**Steps:**
1. Note the current username in top-right
2. Refresh the page (F5 or Cmd+R)
3. Close browser tab
4. Open new tab to http://localhost:5173
5. Close browser entirely
6. Reopen browser and navigate to http://localhost:5173

**Expected Result:**
- After refresh: User remains logged in, tweets reload
- After closing tab: User remains logged in when returning
- After closing browser: User remains logged in on next visit
- Username displayed consistently
- No need to re-authenticate

**Pass/Fail Criteria:**
- ✅ PASS: User session persists through all scenarios
- ❌ FAIL: User logged out after any of the above actions

---

### Test Case 4: Logout Functionality

**Objective:** Verify users can successfully log out

**Prerequisites:**
- Authenticated user session

**Steps:**
1. Click settings icon (gear) in top-right
2. Settings modal opens
3. Click "Logout" button at bottom of modal
4. Observe application state

**Expected Result:**
- User returned to login screen
- Username cleared from display
- localStorage cleared
- Tweet cache cleared from UI
- No authentication errors in console

**Pass/Fail Criteria:**
- ✅ PASS: Clean logout, login screen shown
- ❌ FAIL: Errors thrown, user still appears authenticated

---

### Test Case 5: Token Storage and Encryption

**Objective:** Verify OAuth tokens are securely stored

**Prerequisites:**
- Authenticated user session
- Access to backend cache directory

**Steps:**
1. Complete OAuth login
2. Navigate to `backend/cache/`
3. Look for file matching pattern `{username}_oauth_token.enc`
4. Attempt to open/read the file
5. Verify file contents are encrypted (not plaintext)

**Expected Result:**
- Token file exists in cache directory
- File contains encrypted binary data (not readable JSON/text)
- Token persists after server restart
- Re-authentication not required after server restart

**Pass/Fail Criteria:**
- ✅ PASS: Token file exists, encrypted, persists across restarts
- ❌ FAIL: Token file missing, plaintext, or lost after restart

---

### Test Case 6: Browser State (Cookies) Storage

**Objective:** Verify headless browser cookies stored for tweet scraping

**Prerequisites:**
- Authenticated user session (proudlurker)

**Steps:**
1. Complete OAuth login for proudlurker account
2. Navigate to `backend/cache/`
3. Look for file `proudlurker_browser_state.json`
4. Verify file contains cookies and session data
5. Test scraping functionality still works after server restart

**Expected Result:**
- Browser state file exists
- File contains valid JSON with cookies array
- Scraping works without re-authentication
- State persists across server restarts

**Pass/Fail Criteria:**
- ✅ PASS: Browser state saved, scraping works
- ❌ FAIL: State missing, scraping requires re-login

---

## Core Workflow Tests

### Test Case 7: Tweet Scraping (Read Tweets)

**Objective:** Verify application can scrape relevant tweets from Twitter

**Prerequisites:**
- Authenticated user with configured settings
- User has relevant accounts and/or queries configured
- OBELISK_KEY configured in .env
- user has a valid model specified in user_info.json

**Steps:**
1. Log in successfully
2. If cache is empty, observe "No tweets found in cache" message
3. Click "Refresh" button (green circular arrow icon)
4. Observe loading animation with "Scraping tweets" text
5. Wait for scraping to complete (may take 30-60 seconds)
4. Observe writing animation with "Generating replies" text
5. Wait for generating to complete (may take 30-60 seconds)

**Expected Result:**
- Desktop animation displays during scraping
- "Scraping tweets" text shows with animated dots
- Console shows: `Scraped X new tweets`
- Progress transitions to "Generating replies" phase
- No timeout errors
- Tweets appear in cache after completion WITH generated replies 

**Pass/Fail Criteria:**
- ✅ PASS: Tweets successfully scraped, no errors
- ❌ FAIL: Timeout errors, no tweets scraped, scraping hangs

**Common Failures:**
- Timeout errors for multiple accounts → Reduce number of accounts in settings
- "No authorization found" → proudlurker (current user w browser state, eventually authenticated user) needs to re-authenticate
- Rate limiting errors → Wait 15 minutes and retry
- "OBELISK_KEY not set" → Verify environment variable
- API errors → Check OBELISK_KEY validity
- Empty replies → Check tweet thread data available


---

### Test Case 9: Tweet Display and Navigation

**Objective:** Verify tweets display correctly with all information

**Prerequisites:**
- Tweets with replies loaded in [user]_tweets.json
- This file can be filled with mock data if scrping and generating is not functional.

**Steps:**
1. Observe main tweet grid (2 columns)
2. Verify each tweet card shows:
   - Original tweet text
   - Author username and handle
   - Engagement stats (likes, retweets, quotes, replies)
   - Generated reply text
   - Action buttons (Edit, Publish, Skip)
3. Scroll through tweet list
4. Check for proper formatting and readability

**Expected Result:**
- All tweet data displays correctly
- Images/formatting preserved
- Reply text clearly separated from original tweet
- Cards properly sized and aligned
- Scroll works smoothly
- No missing data or "undefined" values

**Pass/Fail Criteria:**
- ✅ PASS: All tweets display with complete information
- ❌ FAIL: Missing data, formatting broken, UI glitches

---

### Test Case 10: Reply Editing

**Objective:** Verify users can edit generated replies

**Prerequisites:**
- Tweets with replies loaded in [user]_tweets.json
- This file can be filled with mock data if scrping and generating is not functional.

**Steps:**
1. Locate any tweet card
2. Click "Edit" button (pencil icon) on the reply
3. Reply text becomes editable textarea
4. Modify the reply text (add/remove/change words)
5. Click outside the textarea or press "Save"
6. Refresh the page

**Expected Result:**
- Reply text becomes editable
- Cursor placed in textarea
- Changes saved immediately
- Tweet card updates with new reply
- Changes persist after page refresh
- Edit logged in interaction log

**Pass/Fail Criteria:**
- ✅ PASS: Reply editable, changes persist
- ❌ FAIL: Cannot edit, changes lost after refresh

**API Endpoint:** `PATCH /tweets/{username}/{tweet_id}/reply`

---

### Test Case 11: Publishing Reply (Posting to Twitter)

**Objective:** Verify replies can be posted to Twitter

**Prerequisites:**
- Valid OAuth token for posting
- Tweets with replies loaded in [user]_tweets.json
- This file can be filled with mock data if scrping and generating is not functional.

**Steps:**
1. Select a tweet with a reply you want to post
2. Review the reply text
3. Click "Publish" button (checkmark icon)
4. Observe posting animation (tweet card fades/slides)
5. Wait ~400ms for animation
6. Verify tweet moved to "Posted" tab
7. Check Twitter to confirm reply actually posted

**Expected Result:**
- Smooth animation on publish
- Tweet removed from "Generated" tab
- Tweet appears in "Posted" tab
- Reply successfully posted on Twitter
- Tweet deleted from cache (not logged as deletion)
- Post action logged in interaction log
- Success message (no errors)

**Pass/Fail Criteria:**
- ✅ PASS: Reply posted to Twitter, moved to Posted tab
- ❌ FAIL: Post fails, error message, tweet stuck in limbo

**Common Failures:**
- "Invalid token" → Re-authenticate user
- "Rate limit exceeded" → Wait and retry
- Tweet appears in Posted but not on Twitter → Check OAuth scopes

**API Endpoints:**
- `POST /post/reply?username={username}`
- `DELETE /tweets/{username}/{tweet_id}?log_deletion=false`

---

### Test Case 12: Skipping Tweet (Delete)

**Objective:** Verify users can skip/delete tweets they don't want to reply to

**Prerequisites:**
- Tweets with replies loaded in [user]_tweets.json
- This file can be filled with mock data if scrping and generating is not functional.

**Steps:**
1. Select a tweet you want to skip
2. Click "Skip" button (X icon)
3. Observe delete animation (~300ms)
4. Verify tweet removed from list
5. Check cache to confirm deletion
6. Verify deletion logged in interaction log

**Expected Result:**
- Delete animation plays smoothly
- Tweet removed from UI immediately after animation
- Tweet removed from cache file
- Deletion logged with tweet details
- Current index adjusts if last tweet deleted
- No errors in console

**Pass/Fail Criteria:**
- ✅ PASS: Tweet deleted, animation smooth, logged correctly
- ❌ FAIL: Tweet remains, animation glitchy, or deletion fails

**API Endpoint:** `DELETE /tweets/{username}/{tweet_id}?log_deletion=true`

---

### Test Case 13: Tab Switching (Generated vs Posted)

**Objective:** Verify users can switch between Generated and Posted views

**Prerequisites:**
- Tweets with replies loaded in [user]_tweets.json
- This file can be filled with mock data if scrping and generating is not functional.
- At least one tweet posted (in Posted tab)

**Steps:**
1. Verify default view is "Generated" tab
2. Note count badge on "Generated" tab
3. Click "Posted" tab
4. Observe view switches to posted tweets
5. Note count badge on "Posted" tab
6. Verify posted tweets are read-only (no edit/publish buttons)
7. Click back to "Generated" tab
8. Verify tabs highlighted correctly

**Expected Result:**
- Tabs switch smoothly without page reload
- Count badges accurate
- Posted tweets display in read-only mode
- No action buttons on posted tweets
- Active tab highlighted (sky-500 blue)
- Inactive tab grayed out (neutral-800)

**Pass/Fail Criteria:**
- ✅ PASS: Tabs work, counts accurate, read-only enforced
- ❌ FAIL: Tab switching broken, wrong counts, or posted tweets editable

---

## User Settings Tests

### Test Case 14: Opening Settings Modal

**Objective:** Verify settings modal opens and displays user info

**Prerequisites:**
- Authenticated user with info in user_info.json

**Steps:**
1. Click settings icon (gear) in top-right corner
2. Observe modal opens
3. Verify user profile information displays:
   - Profile picture
   - Username
   - Twitter handle
   - Follower count

**Expected Result:**
- Modal opens with smooth animation
- User profile loads correctly
- All user data accurate
- Modal overlay darkens background
- Can close modal by clicking X or outside modal

**Pass/Fail Criteria:**
- ✅ PASS: Modal opens, user data displayed
- ❌ FAIL: Modal doesn't open, data missing

**API Endpoint:** `GET /user/{username}/info`

---

### Test Case 15: Managing Relevant Accounts

**Objective:** Verify users can add/remove accounts for tweet scraping

**Prerequisites:**
- Settings modal open
- authenticated user has entry in user_info.json

**Steps:**
1. Navigate to "Accounts" section in settings
2. View list of current relevant accounts
3. Observe validation status (green checkmark or red warning)
4. Add a new account:
   - Enter Twitter handle in input field
   - Click "Add" or press Enter
5. Remove an account:
   - Click remove icon next to account
6. Save changes
7. Test scraping includes new account

**Expected Result:**
- Current accounts list accurate
- Invalid accounts marked with red indicator
- Settings icon shows warning badge if invalid accounts exist
- New account added successfully
- Account validation runs automatically
- Removed accounts no longer scraped
- Changes persist after modal close

**Pass/Fail Criteria:**
- ✅ PASS: Can add/remove accounts, validation works
- ❌ FAIL: Cannot modify accounts, validation broken

**API Endpoints:**
- `GET /user/{username}/settings`
- `PUT /user/{username}/settings`

---

### Test Case 16: Managing Search Queries

**Objective:** Verify users can configure search queries for scraping

**Prerequisites:**
- Settings modal open
- authenticated user has entry in user_info.json

**Steps:**
1. Navigate to "Queries" section in settings
2. View current list of queries
3. Add a new query:
   - Enter search query (e.g., "AI -filter:links -filter:replies lang:en")
   - Click "Add"
4. Remove a query:
   - Click remove icon next to query
5. Save changes
6. Test scraping includes tweets from new query

**Expected Result:**
- Query list displays correctly
- Can add complex queries with filters
- Can remove queries
- Changes saved to user_info.json
- Next scrape uses updated queries
- Queries properly URL-encoded when scraping

**Pass/Fail Criteria:**
- ✅ PASS: Can manage queries, scraping uses updates
- ❌ FAIL: Cannot modify queries, changes not applied

---

### Test Case 17: Invalid Account Detection

**Objective:** Verify system detects and alerts invalid Twitter handles

**Prerequisites:**
- Settings modal with ability to add accounts
- authenticated user has entry in user_info.json

**Steps:**
1. Add a non-existent Twitter handle (e.g., "thisisnotarealhandle999999")
2. Save settings
3. Trigger tweet scraping
4. Observe timeout errors for invalid account
5. Reopen settings modal
6. Verify invalid account marked with warning icon
7. Check settings icon has red notification badge

**Expected Result:**
- System attempts to scrape from invalid handle
- Times out after 30 seconds
- Account marked as invalid (validated: false)
- Red notification badge on settings icon
- Warning icon next to invalid account in settings
- Can remove invalid account to clear warning

**Pass/Fail Criteria:**
- ✅ PASS: Invalid accounts detected, user notified
- ❌ FAIL: No validation, or app crashes on invalid handle

---

## Data Management Tests

### Test Case 18: Tweet Cache Persistence

**Objective:** Verify tweets persist in cache across sessions

**Prerequisites:**
- Tweets scraped and cached in [handle]_tweets.json
- This file can be filled with mock data if scrping and generating is not functional.

**Steps:**
1. Note current number of tweets in cache
2. Restart backend server
3. Refresh frontend
4. Verify tweets still present
5. Check `backend/cache/{username}_tweets.json` file exists
6. Verify file contains all tweet data

**Expected Result:**
- Tweets persist after backend restart
- Cache file exists and contains valid JSON
- All tweet metadata preserved:
  - tweet_id, cache_id
  - text, thread
  - likes, retweets, quotes, replies
  - handle, username, url
  - reply text
  - scraped_from metadata

**Pass/Fail Criteria:**
- ✅ PASS: All data persists correctly
- ❌ FAIL: Cache cleared, data corrupted, or file missing

---

### Test Case 19: Cache Append (Not Overwrite)

**Objective:** Verify new tweets appended to cache, not replacing existing

**Prerequisites:**
- At least one tweet scraped and cached in [handle]_tweets.json
- This file can be filled with mock data if scrping and generating is not functional.

**Steps:**
1. Note current tweet count (e.g., 10 tweets)
2. Click Refresh to scrape new tweets
3. Verify new tweets added (e.g., now 25 tweets total)
4. Confirm old tweets still present (IDs match)
5. Check cache file size increased

**Expected Result:**
- New tweets added to existing cache
- Old tweets retained (not overwritten)
- No duplicate tweets (same ID)
- If tweet ID exists, metadata updated (not duplicated)

**Pass/Fail Criteria:**
- ✅ PASS: Cache appends, no duplicates
- ❌ FAIL: Cache overwritten, duplicates exist

**Note:** Cache append logic in `tweets_cache.py:write_to_cache()`

---

### Test Case 20: Interaction Logging

**Objective:** Verify all user actions logged to append-only log

**Prerequisites:**
- Ability to generate various interactions

**Steps:**
1. Perform the following actions:
   - Scrape tweets (WRITTEN)
   - Edit a reply (EDITED)
   - Delete a tweet (DELETED)
   - Post a reply (POSTED)
2. Navigate to `backend/cache/{username}_log.jsonl`
3. Open log file and verify entries

**Expected Result:**
- Each action creates a log entry
- Log file in JSONL format (one JSON per line)
- Each entry contains:
  - timestamp
  - username
  - action type (WRITTEN, EDITED, DELETED, POSTED)
  - tweet_id
  - metadata (varies by action):
    - WRITTEN: cache_id
    - EDITED: old_reply, new_reply, diff
    - DELETED: cache_id, deleted_reply
    - POSTED: text, posted_tweet_id, cache_id
- Logs append-only (never deleted)
- Formatted with indentation for readability

**Pass/Fail Criteria:**
- ✅ PASS: All actions logged with complete metadata
- ❌ FAIL: Missing logs, incomplete data, or file corrupted

**API Endpoint:** `GET /logs/{username}`

---

### Test Case 21: Multiple User Support

**Objective:** Verify system supports multiple users with separate caches

**Prerequisites:**
- Two different Twitter accounts

**Steps:**
1. Authenticate as User A
2. Configure settings and scrape tweets
3. Note tweets cached for User A
4. Logout
5. Authenticate as User B
6. Configure different settings and scrape
7. Verify User B sees different tweets
8. Check cache directory has separate files:
   - `userA_tweets.json`
   - `userB_tweets.json`
   - `userA_log.jsonl`
   - `userB_log.jsonl`

**Expected Result:**
- Each user has independent cache
- Settings stored separately
- No data leakage between users
- Switching users shows correct data

**Pass/Fail Criteria:**
- ✅ PASS: Users fully isolated, data separate
- ❌ FAIL: Data mixed, or users see each other's tweets

---

### Test Case 22: Training Data Export

**Objective:** Verify training data can be exported for AI model training. This is not part of core program/web interface but is a key functionality for onboarding. 

**Prerequisites:**
- Backend access
- Tweets cached for a user

**Steps:**
1. Run: `python backend/get_training_data.py nakul 5 10 5 100`
2. Verify output file created: `backend/cache/training_data_nakul.jsonl`
3. Open file and verify format:
   ```json
   {
     "thread": ["tweet text..."],
     "url": "https://x.com/...",
     "poster": "handle",
     "likes": 123,
     "discovered_via": "account",
     "discovered_from": "garrytan",
     "reply": ""
   }
   ```
4. Verify data includes:
   - Tweet thread (array of texts)
   - Tweet URL
   - Author handle
   - Like count
   - Source metadata
   - Empty reply field (for training)

**Expected Result:**
- JSONL file created successfully
- Each line is valid JSON object
- Formatted with indentation (indent=2)
- All required fields present
- Ready for AI training pipeline

**Pass/Fail Criteria:**
- ✅ PASS: File created, format valid, data complete
- ❌ FAIL: Script fails, file malformed, missing data

---

## Error Handling Tests

### Test Case 23: Network Failure During Scraping

**Objective:** Verify graceful handling of network errors

**Prerequisites:**
- Ability to simulate network issues

**Steps:**
1. Start tweet scraping
2. During scraping, disconnect network/WiFi
3. Observe application behavior
4. Reconnect network
5. Retry scraping

**Expected Result:**
- User-friendly error message displayed
- Application doesn't crash
- Partial data not corrupted
- Can retry after reconnection
- Previous cached tweets intact

**Pass/Fail Criteria:**
- ✅ PASS: Error handled gracefully, can recover
- ❌ FAIL: App crashes, data corrupted, or stuck

---

### Test Case 24: Twitter API Rate Limiting

**Objective:** Verify handling of Twitter API rate limits

**Prerequisites:**
- Trigger rate limit (scrape many accounts quickly)

**Steps:**
1. Configure many accounts (50+) in settings
2. Click Refresh repeatedly
3. Observe timeout errors
4. Wait 15 minutes
5. Try again

**Expected Result:**
- Timeout errors displayed per account
- Other accounts continue scraping
- User informed of rate limiting
- System recovers after wait period
- No permanent damage to data

**Pass/Fail Criteria:**
- ✅ PASS: Rate limits handled, system recovers
- ❌ FAIL: App crashes, or retries infinitely

**Recommended Settings:** Limit to 10 accounts, 5 queries to avoid rate limits

---

### Test Case 25: Invalid Token / Session Expiry

**Objective:** Verify handling of expired authentication

**Prerequisites:**
- Authenticated session
- Ability to manually expire token

**Steps:**
1. Authenticate successfully
2. Manually delete token file: `backend/cache/{username}_oauth_token.enc`
3. Try to post a reply
4. Observe error handling

**Expected Result:**
- Clear error message: "No token found for user"
- User prompted to re-authenticate
- Application doesn't crash
- Data preserved

**Pass/Fail Criteria:**
- ✅ PASS: Error handled, user can re-auth
- ❌ FAIL: App crashes or unclear error

---

### Test Case 26: Missing Environment Variables

**Objective:** Verify handling of missing configuration

**Prerequisites:**
- Fresh installation

**Steps:**
1. Remove OBELISK_KEY from .env
2. Attempt reply generation
3. Observe error handling
4. Add OBELISK_KEY back
5. Retry successfully

**Expected Result:**
- Clear error: "OBELISK_KEY not set"
- Application doesn't crash
- Can recover after adding key
- Logs error appropriately

**Pass/Fail Criteria:**
- ✅ PASS: Clear error message, recoverable
- ❌ FAIL: Unclear error or app crash

---

### Test Case 27: Database/File Corruption

**Objective:** Verify recovery from corrupted cache files

**Prerequisites:**
- Valid cache file

**Steps:**
1. Backup cache file
2. Corrupt JSON in cache file (invalid syntax)
3. Refresh application
4. Observe error handling
5. Restore backup file

**Expected Result:**
- Error logged: "Error reading JSON file"
- Empty array returned (doesn't crash)
- User can re-scrape to rebuild cache
- Previous log entries intact

**Pass/Fail Criteria:**
- ✅ PASS: Handles corruption gracefully
- ❌ FAIL: App crashes or data lost

---

### Test Case 28: Concurrent User Actions

**Objective:** Verify system handles multiple simultaneous actions

**Prerequisites:**
- Multiple tweets loaded

**Steps:**
1. Quickly click multiple actions in sequence:
   - Edit reply on Tweet A
   - Publish Tweet B
   - Delete Tweet C
   - Refresh cache
2. Observe system handles all actions
3. Verify data consistency

**Expected Result:**
- All actions complete successfully
- No race conditions or data conflicts
- UI updates smoothly
- Cache and logs consistent
- No duplicate entries or lost data

**Pass/Fail Criteria:**
- ✅ PASS: All actions complete correctly
- ❌ FAIL: Actions conflict, data corrupted, or app crashes

---

## Integration Tests

### Test Case 29: End-to-End User Journey (First Time User)

**Objective:** Test complete first-time user experience

**Prerequisites:**
- Fresh installation
- New user account

**Steps:**
1. Start with no authentication
2. Click "Login with Twitter"
3. Complete OAuth flow
4. Settings modal appears (first-time setup)
5. Add relevant accounts (e.g., 3-5 accounts)
6. Add search queries (e.g., 2-3 queries)
7. Save settings
8. Click Refresh to scrape first batch of tweets
9. Wait for scraping and reply generation
10. Review generated replies
11. Edit a reply
12. Publish a reply
13. Skip a tweet
14. Switch to Posted tab
15. Verify posted tweet appears

**Expected Result:**
- Smooth onboarding experience
- Clear guidance at each step
- All features work in sequence
- Data persists correctly
- User can complete full workflow without errors

**Pass/Fail Criteria:**
- ✅ PASS: User can complete entire flow without help
- ❌ FAIL: User stuck, confused, or encounters errors

---

### Test Case 30: End-to-End User Journey (Returning User)

**Objective:** Test experience for user returning after days/weeks

**Prerequisites:**
- Previously authenticated user
- Existing settings and cache

**Steps:**
1. Open application (session persists)
2. Observe cached tweets load immediately
3. Click Refresh to get new tweets
4. Verify old tweets retained, new ones added
5. Continue workflow (edit, publish, skip)
6. Check logs show continuity

**Expected Result:**
- User immediately logged in
- Previous cache intact
- New tweets append to cache
- Settings preserved
- Workflow continues seamlessly

**Pass/Fail Criteria:**
- ✅ PASS: Returning user experience smooth
- ❌ FAIL: Session lost, data gone, or errors

---

### Test Case 31: Cross-Platform Compatibility

**Objective:** Verify application works on Mac and Linux

**Test on Mac:**
1. Follow setup for Mac (homebrew, uv)
2. Run all core tests
3. Note any Mac-specific issues

**Test on Linux (Ubuntu):**
1. Follow setup for Linux (curl install uv)
2. Run all core tests
3. Note any Linux-specific issues

**Expected Result:**
- Both platforms fully functional
- Setup scripts work correctly
- No platform-specific crashes
- File paths resolve correctly

**Pass/Fail Criteria:**
- ✅ PASS: Works identically on both platforms
- ❌ FAIL: Platform-specific failures

---

### Test Case 32: Browser Compatibility

**Objective:** Verify frontend works across browsers

**Prerequisites:**
- Backend running
- Test on multiple browsers

**Test Browsers:**
1. Chrome/Chromium
2. Firefox
3. Safari (Mac only)
4. Edge

**Steps for Each Browser:**
1. Open http://localhost:5173
2. Complete OAuth flow
3. Test core features:
   - Scraping
   - Reply generation
   - Editing
   - Publishing
   - Deleting
4. Test animations and UI

**Expected Result:**
- All browsers display correctly
- OAuth works in all browsers
- Features function identically
- Animations smooth

**Pass/Fail Criteria:**
- ✅ PASS: Works in all browsers
- ⚠️ PARTIAL: Works but with minor styling differences
- ❌ FAIL: Broken in any browser

---

### Test Case 33: Performance Under Load

**Objective:** Verify system handles large data volumes

**Prerequisites:**
- Ability to generate large dataset

**Steps:**
1. Configure 30+ relevant accounts
2. Set max_tweets to 500+
3. Trigger scraping
4. Observe:
   - Scraping time
   - Memory usage
   - Reply generation time
   - UI responsiveness with 500+ tweets
5. Test scrolling through large list
6. Test editing/publishing with large cache

**Expected Result:**
- Scraping completes within reasonable time (5-10 minutes)
- Reply generation completes (10-15 minutes)
- UI remains responsive
- Scrolling smooth even with many tweets
- No memory leaks or crashes

**Pass/Fail Criteria:**
- ✅ PASS: Handles large volume without issues
- ⚠️ PARTIAL: Works but slow or minor glitches
- ❌ FAIL: Crashes, hangs, or unusably slow

**Note:** May encounter rate limiting with many accounts

---

### Test Case 34: API Health Check

**Objective:** Verify all API endpoints functioning

**Prerequisites:**
- Backend running
- API client (Postman, curl, or browser)

**Endpoints to Test:**

1. **Auth:**
   - `GET /auth/login` → Returns auth URL
   - `GET /auth/callback?code=...` → Exchanges code for token

2. **Tweets:**
   - `GET /tweets/{username}` → Returns cached tweets
   - `DELETE /tweets/{username}/{tweet_id}` → Deletes tweet
   - `PATCH /tweets/{username}/{tweet_id}/reply` → Edits reply
   - `GET /tweets/{username}/{tweet_id}` → Gets single tweet

3. **Read:**
   - `POST /read/{username}/tweets` → Scrapes new tweets

4. **Generate:**
   - `POST /generate/{username}/replies` → Generates AI replies

5. **Post:**
   - `POST /post/tweet?username={username}` → Posts tweet
   - `POST /post/reply?username={username}` → Posts reply

6. **User:**
   - `GET /user/{username}/info` → Gets user info
   - `GET /user/{username}/settings` → Gets settings
   - `PUT /user/{username}/settings` → Updates settings

7. **Logs:**
   - `GET /logs/{username}` → Gets interaction logs

**Expected Result:**
- All endpoints respond correctly
- Proper status codes (200, 201, 204, 404, 500)
- Valid JSON responses
- Error responses informative

**Pass/Fail Criteria:**
- ✅ PASS: All endpoints functional
- ❌ FAIL: Any endpoint broken or returning errors

---

## Test Completion Checklist

Before declaring testing complete:

- [ ] All authentication tests passed
- [ ] Core workflow tested end-to-end
- [ ] User settings functional
- [ ] Data persists correctly
- [ ] Error handling verified
- [ ] Integration tests passed
- [ ] No critical bugs found
- [ ] All P0 issues resolved
- [ ] Documentation updated
- [ ] Known issues documented

## Known Issues & Workarounds

Document any known issues that are not critical:

| Issue | Severity | Workaround | Ticket |
|-------|----------|------------|--------|
| Rate limiting with 50+ accounts | Medium | Limit to 10 accounts | - |
| Popup blockers prevent OAuth | Low | User must allow popups | - |
| ... | ... | ... | ... |

## Appendix: Test Data Setup

### Sample User Settings

```json
{
  "uid": 2,
  "handle": "testuser",
  "email": "test@example.com",
  "model": "divya-2-bon",
  "username": "Test User",
  "relevant_accounts": {
    "garrytan": true,
    "eladgil": true,
    "paulg": true
  },
  "queries": [
    "AI -filter:links -filter:replies lang:en",
    "startups -filter:links -filter:replies lang:en"
  ],
  "max_tweets_retrieve": 30
}
```

### Sample Tweet Cache Entry

```json
{
  "id": "1234567890",
  "cache_id": "uuid-here",
  "text": "This is a sample tweet",
  "thread": ["This is a sample tweet"],
  "likes": 42,
  "retweets": 10,
  "quotes": 5,
  "replies": 3,
  "handle": "testuser",
  "username": "Test User",
  "url": "https://x.com/testuser/status/1234567890",
  "reply": "Great point! I totally agree.",
  "scraped_from": {
    "type": "account",
    "value": "garrytan"
  }
}
```

### Sample Log Entry

```json
{
  "timestamp": "2025-10-13T12:00:00Z",
  "username": "testuser",
  "action": "POSTED",
  "tweet_id": "1234567890",
  "metadata": {
    "text": "Great point! I totally agree.",
    "posted_tweet_id": "9876543210",
    "cache_id": "uuid-here"
  }
}
```

---

## Feedback & Improvements

This regression test suite should evolve with the application. Please update:

- When adding new features
- When discovering edge cases
- When finding common failure patterns
- When improving test procedures

**Last Updated:** [Date]
**Version:** 1.0
**Maintainer:** [Team/Person]
