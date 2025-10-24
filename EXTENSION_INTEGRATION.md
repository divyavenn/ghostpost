# Browser Extension Integration Guide

This document explains how to integrate your browser extension with GhostPoster's cookie import system.

## Complete Login Flow

```
1. User clicks "Login with Twitter" button
   ↓
2. Frontend opens /login-loading.html in new tab (shows animated loading)
   ↓
3. Frontend calls POST /api/auth/twitter/login-url
   ↓
4. Backend returns { login_url: "https://x.com/i/oauth2/authorize?...", session_id: "..." }
   ↓
5. Frontend sends login_url to the tab via postMessage
   ↓
6. Tab navigates to Twitter OAuth authorization page
   ↓
7. User approves OAuth (or logs in first if not already logged in)
   ↓
8. Twitter redirects browser to http://localhost:8000/auth/callback?code=...&state=...
   ↓
9. YOUR EXTENSION detects URL change (redirect happens instantly)
   ↓
10. Backend exchanges OAuth code for API tokens
   ↓
11. Backend returns HTML success page with meta tags (title: "GhostPoster - Login Successful")
   ↓
12. Extension extracts session_id from meta tag (page loads after ~500ms)
   ↓
13. Extension sends cookies to backend via POST /api/auth/twitter/import-cookies
   ↓
14. Backend verifies cookies by visiting https://x.com/home
   ↓
15. Backend updates session status to "success"
   ↓
16. Frontend polls GET /api/auth/twitter/cookie-status/{session_id}
   ↓
17. Frontend gets {status: "success", username: "...", verified: true}
   ↓
18. Frontend sends success message to tab
   ↓
19. Tab shows success animation and closes
   ↓
20. Main app loads user data
```

## Extension Requirements

### What Your Extension Needs to Do

**Monitor OAuth Callback Redirect:**
```javascript
// Detect when Twitter redirects to OAuth callback
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  const url = tab.url || '';

  // IMPORTANT: Watch for URL change (changeInfo.url), not page load completion
  // Twitter redirects browser to callback URL immediately after authorization
  if (changeInfo.url &&
      (url.includes('localhost:8000/auth/callback') ||
       url.includes('your-backend.com/auth/callback'))) {

    console.log('🔄 OAuth callback redirect detected:', url);

    // Extract session_id from URL state parameter
    // URL format: /auth/callback?code=ABC&state=XYZ
    // The backend uses state as session tracking
    const urlParams = new URLSearchParams(new URL(url).search);
    const state = urlParams.get('state');
    const code = urlParams.get('code');

    if (code && state) {
      console.log('✅ OAuth redirect with code and state detected');

      // Wait a moment for page to load and meta tags to be available
      setTimeout(async () => {
        const sessionId = await getSessionIdFromPage(tabId);
        if (sessionId) {
          console.log('📤 Sending cookies for session:', sessionId);
          await sendCookiesToBackend(tabId, sessionId);
        }
      }, 500);
    }
  }
});

// Extract session ID from meta tag in success page
async function getSessionIdFromPage(tabId) {
  try {
    const [{ result }] = await chrome.scripting.executeScript({
      target: { tabId: tabId },
      func: () => {
        const metaTag = document.querySelector('meta[name="session-id"]');
        return metaTag ? metaTag.content : null;
      }
    });
    return result;
  } catch (error) {
    console.error('Error extracting session ID:', error);
    return null;
  }
}
```

**Extract Twitter Username:**
```javascript
// Get username from success page meta tag (backend already got it via OAuth)
async function getTwitterUsername(tabId) {
  try {
    const [{ result }] = await chrome.scripting.executeScript({
      target: { tabId: tabId },
      func: () => {
        const metaTag = document.querySelector('meta[name="twitter-username"]');
        return metaTag ? metaTag.content : null;
      }
    });
    return result;
  } catch (error) {
    console.error('Error extracting username:', error);
    return null;
  }
}
```

**Get All Twitter Cookies:**
```javascript
async function getTwitterCookies() {
  const allCookies = [];

  // Get cookies from both domains
  const xCookies = await chrome.cookies.getAll({ domain: '.x.com' });
  const twitterCookies = await chrome.cookies.getAll({ domain: '.twitter.com' });

  return [...xCookies, ...twitterCookies];
}
```

**Send to Backend:**
```javascript
async function sendCookiesToBackend(tabId, sessionId) {
  // Get username from meta tag (backend got it via OAuth)
  const username = await getTwitterUsername(tabId);
  const cookies = await getTwitterCookies();

  if (!username) {
    console.error('Could not determine Twitter username');
    return;
  }

  if (cookies.length === 0) {
    console.error('No Twitter cookies found');
    return;
  }

  console.log(`📤 Sending ${cookies.length} cookies for @${username}, session: ${sessionId}`);

  // Send to backend with session_id
  const response = await fetch('http://localhost:8000/api/auth/twitter/import-cookies', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      username: username,
      cookies: cookies,
      session_id: sessionId  // Include session ID for tracking
    })
  });

  if (!response.ok) {
    console.error('Failed to import cookies:', await response.text());
    return;
  }

  const result = await response.json();
  console.log('✅ Cookies imported:', result);
}
```

## Backend API Endpoints

### 1. Get Login URL

**POST** `/api/auth/twitter/login-url`

Creates a new login session and returns the Twitter login URL.

**Request:**
```http
POST /api/auth/twitter/login-url
Content-Type: application/json
```

**Response:**
```json
{
  "login_url": "https://twitter.com/i/oauth2/authorize?response_type=code&client_id=...&redirect_uri=...",
  "session_id": "abc123..."
}
```

**Notes:**
- `login_url` is a Twitter OAuth URL that redirects to your callback after login
- The OAuth flow still completes, but your extension captures cookies before the callback
- After OAuth redirect, user will have authenticated browser cookies

---

### 2. Import Cookies (Your Extension Calls This)

**POST** `/api/auth/twitter/import-cookies`

Import cookies from browser extension after user logs in.

**Request:**
```http
POST /api/auth/twitter/import-cookies
Content-Type: application/json

{
  "username": "divya_venn",
  "cookies": [
    {
      "name": "auth_token",
      "value": "...",
      "domain": ".x.com",
      "path": "/",
      "expires": 1793253480,
      "httpOnly": true,
      "secure": true,
      "sameSite": "None"
    },
    {
      "name": "ct0",
      "value": "...",
      "domain": ".x.com",
      "path": "/",
      "expires": 1793253480,
      "httpOnly": false,
      "secure": true,
      "sameSite": "Lax"
    }
    // ... more cookies
  ]
}
```

**Response:**
```json
{
  "message": "Successfully imported cookies for @divya_venn",
  "cookies_count": 15,
  "username": "divya_venn",
  "verified": true
}
```

**What Backend Does:**
1. Saves cookies to `cache/storage_state.json`
2. Verifies cookies by visiting `https://x.com/home` with headless browser
3. Updates all pending login sessions with this username
4. Returns success/failure

---

### 3. Check Cookie Status (Frontend Polls This)

**GET** `/api/auth/twitter/cookie-status/{session_id}`

Frontend polls this to check if cookies have been imported.

**Request:**
```http
GET /api/auth/twitter/cookie-status/abc123...
```

**Response (Pending):**
```json
{
  "status": "pending",
  "username": null,
  "verified": false
}
```

**Response (Success):**
```json
{
  "status": "success",
  "username": "divya_venn",
  "verified": true
}
```

## Complete Extension Example

```javascript
// background.js or service worker

const BACKEND_URL = 'http://localhost:8000';
const TWITTER_DOMAINS = ['.x.com', '.twitter.com'];

// Monitor for Twitter login completion
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  // Only proceed when page finishes loading
  if (changeInfo.status !== 'complete') return;

  // Check if it's Twitter home page (successful login)
  const url = tab.url || '';
  if (url.includes('x.com/home') || url.includes('twitter.com/home')) {
    console.log('✅ Detected Twitter login');

    // Small delay to ensure cookies are set
    setTimeout(async () => {
      await handleTwitterLogin(tabId);
    }, 2000);
  }
});

async function handleTwitterLogin(tabId) {
  try {
    // Step 1: Get username from page
    const username = await extractUsername(tabId);
    if (!username) {
      console.error('Could not extract username');
      return;
    }

    // Step 2: Get all Twitter cookies
    const cookies = await getAllTwitterCookies();
    if (cookies.length === 0) {
      console.error('No cookies found');
      return;
    }

    // Step 3: Send to backend
    console.log(`📤 Sending ${cookies.length} cookies for @${username}...`);

    const response = await fetch(`${BACKEND_URL}/api/auth/twitter/import-cookies`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        username: username,
        cookies: cookies
      })
    });

    if (!response.ok) {
      throw new Error(`Backend returned ${response.status}: ${await response.text()}`);
    }

    const result = await response.json();
    console.log('✅ Import successful:', result);

  } catch (error) {
    console.error('❌ Failed to import cookies:', error);
  }
}

async function extractUsername(tabId) {
  try {
    const [{ result }] = await chrome.scripting.executeScript({
      target: { tabId: tabId },
      func: () => {
        // Try to find username from page
        const accountButton = document.querySelector('[data-testid="SideNav_AccountSwitcher_Button"]');
        if (accountButton) {
          const text = accountButton.innerText;
          const match = text.match(/@(\w+)/);
          if (match) return match[1];
        }

        // Fallback: try to find in any element
        const allText = document.body.innerText;
        const match = allText.match(/@(\w+)/);
        return match ? match[1] : null;
      }
    });

    return result;
  } catch (error) {
    console.error('Error extracting username:', error);
    return null;
  }
}

async function getAllTwitterCookies() {
  const allCookies = [];

  for (const domain of TWITTER_DOMAINS) {
    const cookies = await chrome.cookies.getAll({ domain: domain });
    allCookies.push(...cookies);
  }

  return allCookies;
}
```

## Manifest Permissions Required

```json
{
  "manifest_version": 3,
  "permissions": [
    "cookies",
    "scripting",
    "tabs"
  ],
  "host_permissions": [
    "https://twitter.com/*",
    "https://x.com/*",
    "http://localhost:8000/*"
  ]
}
```

## Testing the Integration

### 1. Test Cookie Import Directly

```bash
# Export cookies from EditThisCookie/Cookie-Editor
# Save to cookies.json

curl -X POST http://localhost:8000/api/auth/twitter/import-cookies \
  -H "Content-Type: application/json" \
  -d '{
    "username": "test_user",
    "cookies": [/* paste cookies here */]
  }'
```

### 2. Test Complete Flow

1. Clear localStorage: `localStorage.clear()`
2. Click "Login with Twitter"
3. Loading tab should open
4. You get redirected to Twitter login
5. Log in with your credentials
6. Your extension detects login and sends cookies
7. Backend verifies cookies
8. Tab closes automatically
9. Main app loads your data

### 3. Monitor Backend Logs

```bash
docker compose logs -f backend | grep -E "(Imported|Verifying|Updated session)"
```

Expected output:
```
📝 Created login session: abc123...
✅ Imported 15 cookies for @divya_venn
🔍 Verifying cookies for @divya_venn...
✅ Cookies for @divya_venn verified successfully
📢 Updated session abc123... with username @divya_venn
```

## Troubleshooting

### Extension Not Detecting Login

**Check:** Is your extension monitoring `tabs.onUpdated`?

```javascript
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  console.log('Tab updated:', tab.url, changeInfo);
});
```

### Cannot Extract Username

**Check:** Can you inject content scripts?

```json
// In manifest.json
"host_permissions": [
  "https://x.com/*",
  "https://twitter.com/*"
]
```

### Cookies Not Working

**Check:** Are critical cookies included?

Required cookies:
- `auth_token` (most important)
- `ct0` (CSRF token)
- `twid` (Twitter ID)

### Backend Verification Fails

**Check:** Backend logs for verification:

```bash
docker compose logs backend --tail 50 | grep -i verify
```

If you see "redirected to login", the cookies are invalid or expired.

## Production Deployment

For production, update your extension's `BACKEND_URL`:

```javascript
const BACKEND_URL = process.env.BACKEND_URL || 'https://your-backend.com';
```

And update backend CORS to allow your extension's origin.

## Summary

Your extension needs to:
1. ✅ Monitor for Twitter home page (`/home`)
2. ✅ Extract username from page content
3. ✅ Get all Twitter cookies
4. ✅ POST to `/api/auth/twitter/import-cookies`
5. ✅ Handle errors gracefully

Backend will:
1. ✅ Save cookies to storage_state.json
2. ✅ Verify cookies work by visiting Twitter home
3. ✅ Update all pending sessions
4. ✅ Notify frontend via polling

Frontend will:
1. ✅ Open loading tab
2. ✅ Get login URL from backend
3. ✅ Navigate tab to Twitter
4. ✅ Poll for cookie import completion
5. ✅ Close tab and load user data
