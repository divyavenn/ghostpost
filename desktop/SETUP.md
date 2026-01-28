# Desktop App Setup Guide

## Quick Start

### 1. Install Dependencies

```bash
cd desktop
npm install
```

### 2. Test Backend Connection

Make sure your backend is running, then test the connection:

```bash
node test-setup.js
```

You should see:
```
✅ Backend health check: { status: 'healthy' }
✅ Fetched pending jobs: 0 jobs
✅ Job status: { total: 0, pending: 0, ... }
✅ All tests passed!
```

### 3. Run Desktop App

```bash
npm start
```

On first run, you'll be prompted to configure:
- Username (e.g., `divya_venn`)
- Backend URL (e.g., `http://localhost:8000`)

### 4. Test Job Creation (Backend)

Create a test job from Python:

```python
from backend.desktop.desktop_jobs import create_desktop_job

# Create a test job
job_id = create_desktop_job(
    username="divya_venn",
    job_type="search_tweets",
    params={"query": "philosophy", "max_results": 10}
)

print(f"Created job: {job_id}")
```

The desktop app will pick it up within 60 seconds and execute it!

## Integration with Scheduler

To make the scheduler create desktop jobs instead of running directly:

```python
# In backend/utlils/scheduler.py

from backend.desktop.desktop_jobs import create_desktop_job

def scheduled_task():
    for user in get_users_with_valid_sessions():
        # Instead of running directly:
        # await find_and_reply_to_new_posts(user['handle'])

        # Create desktop job:
        create_desktop_job(
            username=user['handle'],
            job_type="fetch_home_timeline",
            params={"max_tweets": 50}
        )
```

## System Tray Usage

Once the app is running:

1. **Look for the app icon in your system tray** (menu bar on macOS)
2. **Right-click the icon** to see menu:
   - Configure - Change settings
   - Start/Stop Polling - Control job execution
   - Show Logs - View activity logs
   - Quit - Exit app

## Auto-Start Configuration

The app is configured to start automatically on login. To change this:

1. Open configuration window from system tray
2. Uncheck "Start automatically on login"
3. Save configuration

## Troubleshooting

### "Cannot connect to backend"

- Ensure backend is running: `cd backend && uv run ./run-backend.sh`
- Check backend URL in configuration
- View logs for details

### "No jobs executing"

- Check if polling is active (system tray menu)
- View logs for errors
- Verify backend is creating jobs

### "Browser automation failing"

- Ensure Playwright browsers are installed: `npx playwright install`
- Check if Twitter session is valid
- View logs for specific errors

## File Locations

### macOS
- Config: `~/Library/Application Support/floodme-desktop/config.json`
- Session: `~/Library/Application Support/floodme-desktop/twitter_session.json`
- Logs: `~/Library/Application Support/floodme-desktop/floodme.log`

### Windows
- Config: `%APPDATA%\floodme-desktop\config.json`
- Session: `%APPDATA%\floodme-desktop\twitter_session.json`
- Logs: `%APPDATA%\floodme-desktop\floodme.log`

### Linux
- Config: `~/.config/floodme-desktop/config.json`
- Session: `~/.config/floodme-desktop/twitter_session.json`
- Logs: `~/.config/floodme-desktop/floodme.log`

## Backend Endpoints

The desktop app uses these endpoints:

- `GET /desktop-jobs/{username}/pending` - Fetch pending jobs
- `POST /desktop-jobs/{job_id}/complete` - Report job completion
- `POST /desktop-jobs/{job_id}/fail` - Report job failure
- `GET /desktop-jobs/{username}/status` - Get job status
- `DELETE /desktop-jobs/{job_id}` - Delete job

## Development

### Running in Dev Mode

```bash
npm run dev
```

This runs with `--dev` flag and shows more verbose logging.

### Building Distributable

```bash
# macOS
npm run build:mac

# Windows (run on Windows machine)
npm run build:win

# Linux
npm run build:linux
```

Built apps will be in `dist/` folder.

## Security Notes

- Twitter session stored locally (never sent to backend)
- All browser automation happens on user's machine
- Backend only receives scraped data (no credentials)
- Config file stores backend URL and username only

## Next Steps

1. Install and configure the desktop app
2. Modify scheduler to create desktop jobs
3. Monitor logs to ensure jobs execute successfully
4. Build distributable for production use
