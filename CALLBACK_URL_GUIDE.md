# OAuth Callback URL Configuration Guide

## Important: Understanding `/api` vs `/auth`

**Frontend uses `/api` prefix** (Vite proxy strips it):
```javascript
// Frontend code
fetch('/api/auth/twitter/start')  // Vite proxy → backend: /auth/twitter/start
```

**But Twitter OAuth redirects DIRECTLY to backend** (no Vite proxy):
```
Twitter → http://your-server:8000/auth/callback  ← Goes straight to backend
```

**Therefore, callback URL in Twitter Developer Portal is:**
```
http://your-server:8000/auth/callback  ✅ Correct (no /api)
http://your-server:8000/api/auth/callback  ❌ Wrong (has /api)
```

---

## Quick Reference

Your callback URL depends on where you're deploying:

| Environment | BACKEND_URL | Callback URL | Add to Twitter Portal |
|-------------|-------------|--------------|----------------------|
| Local Dev | `http://localhost:8000` | `http://localhost:8000/auth/callback` | ✅ Yes |
| Production (IP) | `http://192.168.8.57:8000` | `http://192.168.8.57:8000/auth/callback` | ✅ Yes |
| Production (Domain) | `http://yourdomain.com:8000` | `http://yourdomain.com:8000/auth/callback` | ✅ Yes |

## Step-by-Step Setup

### 1. Find Your Server IP (if needed)

```bash
# On your production server
ip addr show | grep "inet " | grep -v "127.0.0.1"
# Or simpler:
hostname -I | awk '{print $1}'
```

### 2. Update Your `.env` File

**For local development:**
```bash
BACKEND_URL='http://localhost:8000'
HEADLESS_BROWSER=false
```

**For production:**
```bash
BACKEND_URL='http://YOUR-SERVER-IP:8000'  # Replace with actual IP
HEADLESS_BROWSER=true
```

### 3. Verify Your Callback URL

```bash
./check-callback-url.sh
```

This will show you exactly what callback URL to add to Twitter.

### 4. Add to Twitter Developer Portal

1. **Go to:** https://developer.x.com/en/portal/dashboard
2. **Select your app** (e.g., "FloodMe" or your app name)
3. Click **"User authentication settings"** → **"Edit"**
4. Scroll to **"Callback URI / Redirect URL"**
5. **Add your callback URL** (copy exactly from step 3)
6. Click **"Save"**

### 5. Verify It Works

After deploying, test OAuth:
```bash
# Check backend is running
curl http://YOUR-SERVER-IP:8000

# Try OAuth flow from frontend
# If you get "You weren't able to give access" → callback URL mismatch
```

## Common Mistakes ❌

### Mistake 1: Port Mismatch
- ❌ Wrong: Twitter portal has `http://server:8000/auth/callback` but .env has `http://server/auth/callback`
- ✅ Correct: Both must have `:8000`

### Mistake 2: Protocol Mismatch
- ❌ Wrong: Twitter portal has `https://` but .env has `http://`
- ✅ Correct: Both must match exactly (usually `http://` unless you have SSL)

### Mistake 3: Wrong Path - The `/api` Confusion
- ❌ Wrong: `/api/auth/callback`
- ✅ Correct: `/auth/callback` (no "api")

**Why this is confusing:**
- Frontend code uses `/api/auth/...` (Vite proxy strips `/api`)
- But Twitter redirects **directly to backend**, bypassing frontend/Vite
- Backend constructs callback as `BACKEND_URL + "/auth/callback"` (no `/api`)
- So Twitter Developer Portal needs `/auth/callback`, NOT `/api/auth/callback`

### Mistake 4: Trailing Slash
- ❌ Wrong: `http://server:8000/` in BACKEND_URL
- ✅ Correct: `http://server:8000` (no trailing slash)

### Mistake 5: Using localhost in Production
- ❌ Wrong: `http://localhost:8000` in production .env
- ✅ Correct: `http://actual-server-ip:8000`

## Multiple Environments

You can add multiple callback URLs to Twitter (useful for dev + production):

**In Twitter Developer Portal, add all:**
- `http://localhost:8000/auth/callback` (local dev)
- `http://192.168.8.57:8000/auth/callback` (production)
- `http://yourdomain.com:8000/auth/callback` (if using domain)

Then just change `BACKEND_URL` in your `.env` based on environment.

## Troubleshooting

### "You weren't able to give access to this app"

**Cause:** Callback URL mismatch

**Solution:**
1. Run `./check-callback-url.sh` to see your callback URL
2. Check Twitter Developer Portal - does it match EXACTLY?
3. Look for differences in:
   - Protocol (http vs https)
   - Port number (:8000)
   - Path (/auth/callback)
   - Trailing slashes

### "redirect_uri_mismatch"

**Cause:** Same as above - callback URL doesn't match

**Solution:**
1. Check backend logs for the redirect_uri being sent
2. Compare with Twitter Developer Portal settings
3. Make sure there are no typos

### OAuth works locally but not in production

**Cause:** You added `http://localhost:8000/auth/callback` but production uses different URL

**Solution:**
1. Add BOTH URLs to Twitter Developer Portal:
   - Local: `http://localhost:8000/auth/callback`
   - Production: `http://YOUR-PRODUCTION-IP:8000/auth/callback`

## Quick Test

After configuration, test with curl:

```bash
# Get authorization URL (should not error)
curl -X POST http://YOUR-SERVER-IP:8000/auth/twitter/start

# Should return JSON with "auth_url" field
# If it errors, check your BACKEND_URL and Twitter credentials
```

## Need Help?

Run the callback URL checker:
```bash
./check-callback-url.sh
```

Check the configuration:
```bash
# View current BACKEND_URL
grep BACKEND_URL backend/.env

# Test backend reachable
curl http://YOUR-SERVER-IP:8000

# Check VNC services (Docker only)
curl http://YOUR-SERVER-IP:8000/health/vnc
```
