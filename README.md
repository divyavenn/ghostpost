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

### 2. Twitter Developer App Configuration

**CRITICAL**: Proper Twitter app configuration is essential for the authentication to work.

#### App Settings in Twitter Developer Portal:

1. **App Type**: Select **"Native App"** (Public client)
   - This enables OAuth 2.0 User Context authentication
   - Required for posting tweets with user permissions

2. **App Permissions**: Select **"Read and write and Direct message"**
   - Enables tweet posting capabilities
   - Required for the `tweet.write` scope

4. **Callback URI**: Set to `http://localhost:8000/auth/callback` 
   - This is only for testing on localhost:8000. When this updates to some other domain, you will have
    to update it on the developer portal too.
   - Must match exactly in your app configuration

#### Required OAuth 2.0 Scopes:
- `tweet.read` - Read tweets
- `tweet.write` - Post tweets and replies
- `users.read` - Read user information
- `offline.access` - Refresh tokens for persistent sessions

### 3. Environment Variables

Create a `.env` file in the project root:

```bash
# Twitter OAuth 2.0 Configuration
TWITTER_CLIENT_ID=your_client_id_here
TWITTER_CLIENT_SECRET=your_client_secret_here

# Obelisk API Key (for AI-generated content)
OBELISK_KEY=your_obelisk_key_here
```

### 4. Run the Application

```bash
# Start the backend server
python run_dashboard.py

# The dashboard will be available at:
# - Frontend: http://localhost:8000
# - API Docs: http://localhost:8000/docs
# - WebSocket: ws://localhost:8000/ws/
```

## 🔧 Key Technical Changes Made

### OAuth 2.0 PKCE Implementation

**Solution**: Implemented OAuth 2.0 PKCE (Proof Key for Code Exchange) authentication flow.

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
