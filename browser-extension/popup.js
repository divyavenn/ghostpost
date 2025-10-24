// Popup script - handles UI interactions

const usernameInput = document.getElementById('username');
const saveBtn = document.getElementById('saveBtn');
const syncBtn = document.getElementById('syncBtn');
const statusDiv = document.getElementById('status');

// Load saved username
chrome.storage.sync.get(['username', 'lastSync', 'lastSyncSuccess', 'lastSyncError'], (data) => {
  if (data.username) {
    usernameInput.value = data.username;
  }

  // Show last sync status
  if (data.lastSync) {
    const syncDate = new Date(data.lastSync);
    const timeAgo = getTimeAgo(syncDate);

    if (data.lastSyncSuccess) {
      showStatus(`Last synced ${timeAgo}`, 'success');
    } else {
      showStatus(`Last sync failed ${timeAgo}: ${data.lastSyncError || 'Unknown error'}`, 'error');
    }
  }
});

// Save username
saveBtn.addEventListener('click', async () => {
  const username = usernameInput.value.trim();

  if (!username) {
    showStatus('Please enter your Twitter username', 'error');
    return;
  }

  await chrome.storage.sync.set({ username });
  showStatus('Settings saved! Cookies will sync automatically.', 'success');
});

// Manual sync
syncBtn.addEventListener('click', async () => {
  const { username } = await chrome.storage.sync.get('username');

  if (!username) {
    showStatus('Please save your username first', 'error');
    return;
  }

  syncBtn.disabled = true;
  syncBtn.textContent = 'Syncing...';

  try {
    const response = await chrome.runtime.sendMessage({ action: 'syncNow' });

    if (response.success) {
      showStatus('Cookies synced successfully!', 'success');
    } else {
      showStatus(`Sync failed: ${response.error}`, 'error');
    }
  } catch (error) {
    showStatus(`Sync failed: ${error.message}`, 'error');
  } finally {
    syncBtn.disabled = false;
    syncBtn.textContent = 'Sync Now';
  }
});

function showStatus(message, type) {
  statusDiv.textContent = message;
  statusDiv.className = `status ${type}`;
  statusDiv.style.display = 'block';
}

function getTimeAgo(date) {
  const seconds = Math.floor((new Date() - date) / 1000);

  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}
