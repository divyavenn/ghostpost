# FloodMe - Twitter Automation Dashboard

A Twitter automation platform that uses OAuth 2.0 PKCE authentication to post tweets and replies with AI-generated content.

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 16+
- Twitter Developer Account with Elevated Access
- Conda/Mamba package manager

### 1. Environment Setup

```bash
# Clone the repository
git clone <repository-url>
cd floodme

# Create and activate conda environment
conda env create -f backend/environment.yaml
conda activate floodme-backend

# Install additional dependencies
pip install playwright python-dotenv
playwright install chromium

# Install frontend dependencies
cd frontend
npm install
npm run build
cd ..
```

Make sure

# ISSUES

backend/oauth_utils.py:230 gives you a working manual OAuth PKCE flow: the script launches a local callback server, walks the user through authorizing your X app, swaps the code for tokens, and posts one tweet by prompting for text.
Posting on a user’s behalf is therefore possible, but only through this CLI-side flow; your FastAPI service already has a similar test endpoint (backend/websocket.py:575-647) yet neither piece persists tokens or wires into a multi-user session.
Headless scrolling lives elsewhere (backend/headless_fetch.py), but it is disconnected from the OAuth login—there’s no automated reuse of the granted tokens to drive that browser session.
Pros

Uses OAuth 2.0 PKCE, which X/Twitter requires for user login—no password sharing or embedded secrets.
Requests the correct scopes (tweet.read tweet.write users.read offline.access) so you can read/write tweets for the authorized user.
Keeps the flow self-contained: spin up the helper server, get tokens, post.
Cons / Gaps

Everything is manual: you must run the script locally, copy the URL, and paste the tweet. No multi-user or web UI integration.
Access/refresh tokens are only printed; there’s no secure storage, rotation tracking, or refresh scheduling. A production app needs to encrypt and persist them per user.
The code assumes the redirect URI is accessible from the user’s browser; that breaks once you deploy behind HTTPS or without port forwarding.
There’s no consent or state management for multiple tokens—user_tokens in backend/websocket.py is just an in-memory dict that resets on restart.
Headless browsing logic doesn’t tie into the authenticated session, so there’s no guarantee you’re scrolling with the same user context you just authorized.
Error handling is basic: network failures, token refresh errors, or partial responses bubble up as program exits.

# TODO 
- Wire the PKCE flow into your FastAPI app so users authenticate through your web UI, and persist their tokens (hashed/encrypted) in a database.
- Build a token refresh job and reuse the stored credentials when posting or running the headless browser.
- Gate the headless browser automation behind the stored, user-specific tokens or session cookies so you’re truly acting as the authorized user.


#### Files Created/Modified:

1. **`backend/oauth_utils.py`** (NEW)
   - Implements `TwitterPKCE` class for OAuth 2.0 flow
   - Handles code verifier/challenge generation
   - Manages token exchange and refresh
   - **Critical**: Includes all required scopes: `tweet.read tweet.write users.read offline.access`

2. **`backend/websocket.py`** (MODIFIED)
   - Added OAuth 2.0 authentication routes:
     - `GET /auth/login` - Start OAuth flow
     - `GET /auth/callback` - Handle OAuth callback
     - `GET /auth/status` - Check authentication status
     - `POST /test-post` - Test tweet posting

3. **`backend/post_takes.py`** (MODIFIED)
   - Added `post_take_with_token()` function
   - Uses user access tokens instead of app-only tokens
   - Enables posting tweets with user context permissions

4. **`backend/main.py`** (MINOR CHANGES - REVERTIBLE)
   - Temporarily cleaned up for testing purposes
   - Can be reverted if Playwright workflow is needed
   - Contains the original `/comment` endpoint for AI-generated replies

5. **`run_dashboard.py`** (MINOR CHANGES - REVERTIBLE)
   - Updated to run `websocket.py` instead of `main.py` for dashboard
   - Can be reverted based on workflow requirements
   - Contains dependency checking and server startup logic

### Authentication Flow

```
1. User visits /auth/login
2. Redirected to Twitter OAuth 2.0 authorization page
3. User authorizes the app with required scopes
4. Twitter redirects to /auth/callback with authorization code
5. Server exchanges code for access token using PKCE
6. Token stored for authenticated posting
7. User can now post tweets via /test-post endpoint
```

## 🐛 Common Issues & Solutions

### 403 Forbidden Error
- **Cause**: Missing scopes or incorrect app configuration
- **Solution**: Ensure all required scopes are included

### Invalid State Parameter
- **Cause**: Server restarts clearing in-memory state
- **Solution**: Implemented persistent storage with `code_verifiers.json`

### Application-Only vs User Context
- **Cause**: Wrong app type (Web App instead of Native App)
- **Solution**: Change app type to "Native App" in Twitter Developer Portal

## 📁 Project Structure

```
floodme/
├── backend/
│   ├── oauth_utils.py          # OAuth 2.0 PKCE implementation
│   ├── websocket.py            # Main FastAPI app with auth routes
│   ├── post_takes.py           # Tweet posting functions
│   ├── twitter_agent.py        # Twitter automation logic
│   └── environment.yaml        # Conda environment definition
├── frontend/
│   ├── src/
│   │   ├── App.tsx            # React dashboard
│   │   └── components/        # UI components
│   └── package.json           # Frontend dependencies
├── .env                       # Environment variables
└── README.md                  # This file
```

## 🔐 Security Notes

- Access tokens are stored in memory (not persistent)
- Code verifiers are stored in `code_verifiers.json` (temporary)
- In production, use secure database storage for tokens
- Never commit `.env` file or tokens to version control

## 🔄 Revertible Changes

Some changes were made during development that can be reverted based on your workflow needs:

#### **To Revert to Playwright Workflow:**
1. **`run_dashboard.py`**: Change target from `websocket:app` back to `main:app`

#### **Files with Revertible Changes:**
- `backend/main.py` - Contains original `/comment` endpoint
- `run_dashboard.py` - Server target configuration
- Any Playwright-specific code that was temporarily removed


## 📚 API Endpoints

- `GET /` - Dashboard homepage
- `GET /auth/login` - Start OAuth 2.0 flow
- `GET /auth/callback` - OAuth callback handler
- `GET /auth/status` - Check authentication status
- `POST /test-post` - Test tweet posting
- `GET /docs` - API documentation
