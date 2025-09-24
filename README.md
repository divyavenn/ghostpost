# FloodMe - Guerrilla Marketing Done Right

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

## X Developer API setup 
1) Go to the X Developer Portal https://developer.x.com/en/portal/dashboard
2) Create an app
3) Go to keys and tokens
4) Put the Cliet ID and Client Secret in the env file
5) Go to user authentication settings 
6) Make sure http://localhost:8000/auth/callback is in the Callback URI in App Info in the X developer portal for the account
you will be using


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
7. Browser cookies stored for headless browsing
7. Posting tweets and headless browsing can both be done without logging in again. 
```