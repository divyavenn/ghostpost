# FloodMe - Guerrilla Marketing Done Right

### Prerequisites
- Python 3.11+
- Node.js 16+
- Twitter Developer Account with Elevated Access
- uv package manager 

### 1. Environment Setup

```bash
# Clone the repository
git clone <repository-url>
cd floodme

## MAC uv install ##
# install homebrew and uv if not already installed
# homebrew 
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
# uv 
brew install uv

## LINUX (ubuntu) uv install ##
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env


# Setup uv .venv (one time) 
./setup_venv.sh

# Run your FastAPI app
./start_backend.sh

# Run before commiting to fix formatting and linter thigns
./fix-format.sh




# Install additional dependencies
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
