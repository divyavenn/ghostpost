# Production Setup for Headless Servers

## The Challenge

Your production server runs Linux without a GUI (no X11/display server), but users need to log in via Twitter OAuth by seeing and interacting with a browser window.

## Docker Solution (Recommended - Built-In!)

**Good news: Everything is already configured in Docker!** 🎉

When you deploy with Docker Compose, noVNC is automatically installed and started. No additional setup needed!

### Quick Start

1. **On your production server, set the environment variable:**
   ```bash
   # In backend/.env
   HEADLESS_BROWSER=true
   ```

2. **Deploy with Docker:**
   ```bash
   docker-compose up -d
   ```

3. **Access the browser for OAuth:**
   - Open `http://your-server-ip:6080/vnc.html` in ANY browser
   - Works on Mac, Windows, Linux, iPad, Android - any device!
   - Complete Twitter OAuth login
   - Close browser tab - session is saved!

4. **Automated scraping runs headlessly in the background** ✅

That's it! Port 6080 is exposed automatically by Docker.

---

## Alternative Solutions (If Not Using Docker)

### Option 1: Remote Browser Access (Recommended)

Set up a virtual display and remote access so users can complete OAuth on the server:

```bash
# Install Xvfb (virtual display) and VNC server
sudo apt-get update
sudo apt-get install -y xvfb x11vnc

# Start virtual display
Xvfb :99 -screen 0 1280x720x24 &
export DISPLAY=:99

# Start VNC server (users can connect to see the browser)
x11vnc -display :99 -forever -shared &
```

Users connect via VNC client to complete OAuth login.

### Option 2: Login Locally, Upload State (Simpler)

1. **On your local machine:**
   - Run the backend locally
   - Complete Twitter OAuth login
   - Browser state is saved to `backend/cache/storage_state.json`

2. **Upload to production:**
   ```bash
   # Copy browser state to production server
   scp backend/cache/storage_state.json user@server:/path/to/backend/cache/
   ```

3. **On production:**
   - Set `HEADLESS_BROWSER=true` in `.env`
   - Automated scraping will use the uploaded browser state headlessly
   - Users won't need to log in again until session expires

### Option 3: noVNC Web-Based Access (Recommended for Production!)

**What is noVNC?**
- VNC client that runs in your web browser
- No software installation needed on user's device
- Works on ANY laptop, tablet, or phone with a browser

**How it works:**
1. Production server runs a virtual display (Xvfb)
2. noVNC provides a web interface to that display
3. Users open `http://your-server:6080/vnc.html` in their browser
4. They see the OAuth browser window and can interact with it
5. After login, close the tab - browser state is saved on server!

**Setup (Easy!):**

```bash
# On your production server, run the automated setup script:
sudo bash setup-production-browser.sh
```

That's it! The script:
- ✅ Installs all dependencies (Xvfb, x11vnc, noVNC)
- ✅ Creates systemd services (auto-start on boot)
- ✅ Starts everything automatically
- ✅ Gives you the URL to access

**User Workflow:**
1. User wants to log in with Twitter
2. Backend triggers OAuth flow
3. User opens `http://your-server:6080/vnc.html` in their browser
4. They see the Twitter login page
5. Enter credentials, click "Authorize"
6. Close the browser tab - done!
7. Server now has saved browser state for automated scraping

**Works From:**
- ✅ Mac laptop (Safari, Chrome, Firefox)
- ✅ Windows laptop (Edge, Chrome, Firefox)
- ✅ Linux laptop (Any browser)
- ✅ iPad/iPhone (Mobile Safari)
- ✅ Android (Chrome)
- ✅ Literally any device with a web browser!

**Security:**
- Consider adding VNC password protection
- Use firewall to restrict access to port 6080
- Or set up nginx reverse proxy with HTTPS

## How It Works

### User Login/OAuth Flow
- **ALWAYS runs with visible browser** (`headless=False`)
- Users need to see Twitter's login page
- Users need to click "Authorize" button
- Works on local machines or via remote display solutions above

### Automated Scraping
- **Respects `HEADLESS_BROWSER` setting**
- Uses saved browser state from login
- Runs headlessly in production (no GUI needed)
- Scheduled 24-hour scraping works silently in background

## Environment Variables

```bash
# Production .env
HEADLESS_BROWSER=true  # Scraping runs headless, OAuth still shows browser (via remote display)

# Local Development .env
HEADLESS_BROWSER=false  # Everything visible for debugging
```

## Security Notes

- Browser state file contains session cookies
- Keep `cache/storage_state.json` secure
- Don't commit to git (already in .gitignore)
- Regenerate if compromised (user logs in again)

## Troubleshooting

**Error: "Cannot open display"**
- Solution: Set up Xvfb virtual display (see Option 1 above)

**OAuth window doesn't appear**
- Check if `DISPLAY` environment variable is set
- Verify Xvfb or X server is running
- Use VNC/noVNC to view remote display

**Scraping fails in production**
- Ensure browser state file exists in `cache/` directory
- Check file permissions (should be readable by backend user)
- Re-login if session expired (browser state older than ~30 days)
