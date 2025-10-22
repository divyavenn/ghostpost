// Background service worker - monitors cookie changes and syncs to backend

const BACKEND_URL = 'http://localhost:8000'; // Change to your production URL
const SYNC_INTERVAL = 5 * 60 * 1000; // Sync every 5 minutes
const TWITTER_DOMAINS = ['.x.com', '.twitter.com'];

// Listen for cookie changes
chrome.cookies.onChanged.addListener((changeInfo) => {
  const cookie = changeInfo.cookie;

  // Only sync Twitter cookies
  if (TWITTER_DOMAINS.some(domain => cookie.domain.includes(domain))) {
    console.log('Twitter cookie changed:', cookie.name);

    // Debounce: sync after 2 seconds of no changes
    clearTimeout(window.syncTimer);
    window.syncTimer = setTimeout(() => {
      syncCookies();
    }, 2000);
  }
});

// Sync cookies to backend
async function syncCookies() {
  try {
    // Get username from storage
    const { username } = await chrome.storage.sync.get('username');

    if (!username) {
      console.warn('Username not set. Open extension popup to configure.');
      return;
    }

    // Get all Twitter cookies
    const cookies = await getAllTwitterCookies();

    if (cookies.length === 0) {
      console.log('No Twitter cookies found. User may not be logged in.');
      return;
    }

    // Check if we have critical cookies
    const hasCriticalCookies = cookies.some(c => c.name === 'auth_token');
    if (!hasCriticalCookies) {
      console.log('No auth_token found. User may not be logged in.');
      return;
    }

    console.log(`Syncing ${cookies.length} cookies for @${username}...`);

    // Send to backend
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
    console.log('✅ Cookies synced successfully:', result);

    // Update last sync time
    await chrome.storage.sync.set({
      lastSync: new Date().toISOString(),
      lastSyncSuccess: true
    });

  } catch (error) {
    console.error('❌ Failed to sync cookies:', error);
    await chrome.storage.sync.set({
      lastSyncSuccess: false,
      lastSyncError: error.message
    });
  }
}

// Get all Twitter cookies
async function getAllTwitterCookies() {
  const allCookies = [];

  for (const domain of TWITTER_DOMAINS) {
    const cookies = await chrome.cookies.getAll({ domain: domain });
    allCookies.push(...cookies);
  }

  return allCookies;
}

// Periodic sync (every 5 minutes)
setInterval(() => {
  syncCookies();
}, SYNC_INTERVAL);

// Sync on extension install/update
chrome.runtime.onInstalled.addListener(() => {
  console.log('Twitter Cookie Sync extension installed');
  syncCookies();
});

// Sync when user opens Twitter
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' &&
      (tab.url?.includes('twitter.com') || tab.url?.includes('x.com'))) {
    // Wait a bit for cookies to be set
    setTimeout(() => syncCookies(), 3000);
  }
});

// Listen for manual sync requests from popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'syncNow') {
    syncCookies().then(() => {
      sendResponse({ success: true });
    }).catch(error => {
      sendResponse({ success: false, error: error.message });
    });
    return true; // Keep channel open for async response
  }
});
