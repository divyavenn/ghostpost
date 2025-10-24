# Twitter Cookie Sync Extension

Automatically syncs your Twitter cookies to the GhostPoster backend for seamless authentication.

## Features

- 🔄 **Auto-sync**: Syncs cookies when you log into Twitter
- ⏰ **Periodic sync**: Syncs every 5 minutes automatically
- 🔒 **Secure**: Only syncs Twitter/X cookies to your backend
- 🎯 **Manual trigger**: Click "Sync Now" to force immediate sync

## Installation

### Chrome/Edge/Brave

1. Open browser and navigate to: `chrome://extensions/`
2. Enable "Developer mode" (toggle in top-right)
3. Click "Load unpacked"
4. Select the `browser-extension` folder
5. The extension icon should appear in your toolbar

### Firefox

1. Open browser and navigate to: `about:debugging#/runtime/this-firefox`
2. Click "Load Temporary Add-on"
3. Select `manifest.json` from the `browser-extension` folder
4. Extension will load (note: temporary in Firefox, reloads on browser restart)

## Setup

1. **Click the extension icon** in your browser toolbar
2. **Enter your Twitter username** (e.g., `divya_venn`)
3. **Click "Save Settings"**
4. **Log into Twitter** in a new tab
5. Cookies will automatically sync!

## Configuration

### Change Backend URL

Edit `background.js` line 3:

```javascript
const BACKEND_URL = 'http://localhost:8000'; // Change for production
```

For production, update to your deployed backend URL:

```javascript
const BACKEND_URL = 'https://your-backend.com';
```

### Adjust Sync Interval

Edit `background.js` line 4:

```javascript
const SYNC_INTERVAL = 5 * 60 * 1000; // 5 minutes in milliseconds
```

## How It Works

1. **Cookie Detection**: Extension monitors all cookies for `twitter.com` and `x.com`
2. **Auto-Sync Triggers**:
   - When you log into Twitter
   - When any Twitter cookie changes
   - Every 5 minutes (periodic)
   - When you click "Sync Now"
3. **Backend Import**: Sends cookies to `POST /api/auth/twitter/import-cookies`
4. **Status Updates**: Shows last sync time in popup

## Troubleshooting

### "No cookies found"
- Make sure you're logged into Twitter/X
- Check that extension has cookie permissions

### "Backend connection failed"
- Verify backend is running: `docker compose ps`
- Check backend URL in `background.js`
- Look at browser console: right-click extension → "Inspect popup"

### Cookies not syncing
- Open extension popup to check last sync status
- Check browser console logs: Extensions → Twitter Cookie Sync → "Inspect views: service worker"
- Manually trigger sync with "Sync Now" button

## Privacy & Security

- **Local only**: Cookies only sent to YOUR backend
- **No third parties**: No external services involved
- **Minimal permissions**: Only requests cookie access
- **Open source**: All code visible in this folder

## Development

### Testing Changes

1. Edit extension files
2. Go to `chrome://extensions/`
3. Click "Reload" button under the extension
4. Test changes

### View Logs

**Background worker logs**:
- Chrome: `chrome://extensions/` → "Inspect views: service worker"
- Firefox: `about:debugging` → Extension → "Inspect"

**Popup logs**:
- Right-click extension icon → "Inspect popup"

### Debugging

Enable verbose logging in `background.js`:

```javascript
const DEBUG = true;

if (DEBUG) {
  console.log('Debug info:', data);
}
```

## Production Deployment

### Build for Production

1. Update `BACKEND_URL` in `background.js` to production URL
2. Create icons (see Icons section below)
3. Test extension thoroughly
4. Package for distribution (optional)

### Create Icons

You need three icon sizes: 16x16, 48x48, 128x128

Quick placeholders (replace with real icons):

```bash
# On Mac with ImageMagick:
convert -size 128x128 xc:blue -pointsize 100 -gravity center \
  -fill white -annotate +0+0 "T" icon128.png
convert icon128.png -resize 48x48 icon48.png
convert icon128.png -resize 16x16 icon16.png
```

Or use an online icon generator.

### Publishing (Optional)

To publish to Chrome Web Store or Firefox Add-ons:

1. Create developer account
2. Package extension as .zip
3. Submit for review
4. Wait for approval

**Note**: For personal use, loading as "unpacked" is sufficient!

## Future Improvements

Potential features to add:

- [ ] Multiple account support
- [ ] Encrypted cookie storage
- [ ] Sync status notifications
- [ ] One-click login from extension
- [ ] Cookie expiration warnings
- [ ] Backup/restore functionality
