# Floodme Desktop App

Desktop application for running browser automation jobs in the background.

## Features

- 🔄 Automatic polling for pending jobs from backend
- 🌐 Headless browser automation using Playwright
- 🔐 Secure Twitter session management (cookies stored locally)
- 🚀 Auto-start on system boot
- 📊 System tray integration
- 📝 Logging and monitoring

## Installation

```bash
cd desktop
npm install
```

## Development

```bash
npm run dev
```

## Building

### macOS
```bash
npm run build:mac
```

### Windows
```bash
npm run build:win
```

### Linux
```bash
npm run build:linux
```

## Configuration

On first run, the app will prompt you to configure:

- **Username**: Your backend username (e.g., `divya_venn`)
- **Backend URL**: URL of your backend server (e.g., `http://localhost:8000`)
- **Poll Interval**: How often to check for jobs (default: 60 seconds)
- **Headless Mode**: Run browser in background (recommended: enabled)
- **Auto-start**: Start on system login (recommended: enabled)

You can access configuration later from the system tray menu.

## How It Works

1. **App starts** when you open your laptop (auto-start enabled)
2. **Polls backend** every 60 seconds: `GET /desktop-jobs/{username}/pending`
3. **Executes jobs** using Playwright with saved Twitter session
4. **Returns results** to backend: `POST /desktop-jobs/{job_id}/complete`

## Supported Job Types

- `fetch_home_timeline` - Scrape home timeline
- `search_tweets` - Search for tweets
- `fetch_user_timeline` - Scrape user's timeline
- `deep_scrape_thread` - Scrape tweet replies

## File Locations

- **Config**: `~/Library/Application Support/floodme-desktop/config.json` (macOS)
- **Session**: `~/Library/Application Support/floodme-desktop/twitter_session.json`
- **Logs**: `~/Library/Application Support/floodme-desktop/floodme.log`

## System Tray Menu

- **Configure** - Open configuration window
- **Start/Stop Polling** - Control job polling
- **Show Logs** - View recent logs
- **Quit** - Exit application

## Security

- Twitter credentials NEVER sent to backend
- Session cookies stored encrypted on your machine
- All browser automation happens locally
- Backend only receives scraped data results

## Troubleshooting

### App not polling

1. Check system tray - is polling active?
2. View logs for errors
3. Verify backend URL in configuration
4. Ensure backend server is running

### Browser automation failing

1. Check if Twitter session is valid
2. Try logging into Twitter manually (app will save new session)
3. Check logs for specific errors

### Can't connect to backend

1. Verify backend URL is correct
2. Ensure backend server is running
3. Check firewall settings
4. View logs for connection errors

## Development

### Project Structure

```
desktop/
├── src/
│   ├── main.js           # Electron main process
│   ├── config.js         # Configuration management
│   ├── polling.js        # Job polling loop
│   ├── job-executor.js   # Playwright job execution
│   └── logger.js         # Logging utility
├── views/
│   ├── config.html       # Configuration UI
│   └── logs.html         # Logs viewer UI
├── assets/
│   └── icon.png          # App icon
└── package.json
```

### Adding New Job Types

1. Add handler in `job-executor.js`:
```javascript
case 'your_new_job_type':
    result = await yourNewJobHandler(page, job.params);
    break;
```

2. Implement the handler function:
```javascript
async function yourNewJobHandler(page, params) {
    // Your Playwright automation code
    return { /* results */ };
}
```

3. Backend creates job with matching `job_type`

## License

MIT
