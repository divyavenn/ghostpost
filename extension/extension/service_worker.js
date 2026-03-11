import { contentTypes } from './content-types.js';
import { getWebsiteConfigs } from './website-configs.js';
import { BrowserAgent } from './browser-agent.js';
import { CDPTools } from './cdp-tools.js';

const WEBSITE_CONFIGS = getWebsiteConfigs();

// Get Claude API key from settings storage (same as popup.js uses)
const SETTINGS_KEY = 'markdownLoadSettings';

async function getClaudeApiKey() {
  const result = await chrome.storage.sync.get(SETTINGS_KEY);
  const settings = result[SETTINGS_KEY] || {};
  return settings.claudeApiKey || null;
}
const STATE_KEY = 'markdownLoadState';

const dev = 'http://127.0.0.1:8000'
const API_BASE_URL = dev;

// Local API endpoints
const DAEMON_BASE_URL = 'http://127.0.0.1:9876';
const DAEMON_HEALTH_URL = `${DAEMON_BASE_URL}/health`;
const DAEMON_SCRAPE_URL = `${DAEMON_BASE_URL}/scrape`;
const BROWSER_STATE_URL = `${DAEMON_BASE_URL}/import-cookies`;
const LOCAL_METADATA_URL = `${DAEMON_BASE_URL}/log`;
const LOCAL_BOOKMARK_URL = `${DAEMON_BASE_URL}/bookmark`;

let daemonAvailable = false;

const REQUEST_HEADERS = {
  'Content-Type': 'application/json',
  'Accept': 'application/json'
};

const JOB_STATUS_BASE_URL = `${API_BASE_URL}/scrape/jobs`;
const JOB_POLL_INTERVAL_MS = 3_000;
const JOB_POLL_MAX_INTERVAL_MS = 15_000;

const jobPolls = new Map();

let processingQueue = false;

function sleep(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

async function checkDaemonHealth() {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 3000);
    const response = await fetch(DAEMON_HEALTH_URL, {
      method: 'GET',
      signal: controller.signal,
    });
    clearTimeout(timeout);
    daemonAvailable = response.ok;
  } catch {
    daemonAvailable = false;
  }
  return daemonAvailable;
}

async function submitDaemonJob(item) {
  const body = { url: item.url };
  if (item.startTime) body.startTime = item.startTime;
  if (item.endTime) body.endTime = item.endTime;
  if (item.videoSettings) {
    body.downloadVideo = item.videoSettings.video || false;
    body.downloadAudio = item.videoSettings.audio || false;
    body.downloadTranscript = item.videoSettings.transcript !== false;
  }
  if (item.openaiApiKey) body.openaiApiKey = item.openaiApiKey;

  const response = await fetch(DAEMON_SCRAPE_URL, {
    method: 'POST',
    headers: REQUEST_HEADERS,
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw await buildError(response);
  }

  const result = await response.json();
  if (!result.success) {
    throw new Error(result.error || 'Daemon scrape failed');
  }
  return result;
}

async function getState() {
  const result = await chrome.storage.local.get(STATE_KEY);
  return result[STATE_KEY] || { queue: [], ready: [] };
}

async function setState(state) {
  await chrome.storage.local.set({ [STATE_KEY]: state });
}

function createId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `id-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
}

function trackJobPoll(jobId, factory) {
  if (jobPolls.has(jobId)) {
    return jobPolls.get(jobId);
  }
  const task = (async () => {
    try {
      await factory();
    } finally {
      jobPolls.delete(jobId);
    }
  })();
  jobPolls.set(jobId, task);
  return task;
}

async function getQueueItemReference(itemId) {
  const state = await getState();
  const index = state.queue.findIndex((entry) => entry.id === itemId);
  if (index === -1) {
    return null;
  }
  return { state, index };
}

async function storeQueueItemJobId(itemId, jobId) {
  const reference = await getQueueItemReference(itemId);
  if (!reference) {
    return null;
  }
  const { state, index } = reference;
  const item = state.queue[index];
  item.jobId = jobId;
  await setState(state);
  return item;
}

async function setQueueItemProcessing(itemId) {
  const reference = await getQueueItemReference(itemId);
  if (!reference) {
    return null;
  }
  const { state, index } = reference;
  const item = state.queue[index];
  if (!item.jobId) {
    return null;
  }
  item.status = 'processing';
  item.jobStatus = 'processing';
  item.error = undefined;
  await setState(state);
  return item;
}

async function updateQueueItemJobStatus(itemId, jobStatus) {
  const reference = await getQueueItemReference(itemId);
  if (!reference) {
    return false;
  }
  const { state, index } = reference;
  state.queue[index].jobStatus = jobStatus;
  await setState(state);
  return true;
}

async function markQueueItemError(itemId, message) {
  const reference = await getQueueItemReference(itemId);
  if (!reference) {
    return;
  }
  const { state, index } = reference;
  state.queue[index].status = 'error';
  state.queue[index].jobStatus = 'error';
  state.queue[index].error = message;
  await setState(state);
}

async function moveQueueItemToReady(itemId, result) {
  const reference = await getQueueItemReference(itemId);
  if (!reference) {
    return;
  }
  const { state, index } = reference;
  const entry = state.queue[index];
  const filename = result.filename || entry.filename || 'download.md';
  state.queue.splice(index, 1);
  state.ready.push({
    id: entry.id,
    url: entry.url,
    filename,
    markdown: result.markdown,
    metadata: result.metadata || null,  // Store metadata from backend
    completedAt: Date.now()
  });
  await setState(state);
}

async function extractJobId(response) {
  if (!response.ok) {
    throw await buildError(response);
  }
  let data = null;
  try {
    data = await response.json();
  } catch (error) {
    // ignore parse errors and fall through
  }
  const jobId = data?.jobId;
  if (typeof jobId !== 'string' || !jobId) {
    throw new Error('Backend response missing jobId.');
  }
  return jobId;
}

async function submitConversionJob(item) {
  if (item.url.startsWith('file://')) {
    try {
      const allowed = await chrome.extension.isAllowedFileSchemeAccess();
      if (!allowed) {
        throw new Error('Allow access to file URLs in chrome://extensions');
      }
    } catch (error) {
      if (error instanceof Error) {
        throw error;
      }
      throw new Error('Unable to verify file URL permissions');
    }

    const pdfResponse = await fetch(item.url);
    if (!pdfResponse.ok) {
      throw await buildError(pdfResponse);
    }

    const pdfBlob = await pdfResponse.blob();
    if (!pdfBlob || pdfBlob.size === 0) {
      throw new Error('Received empty PDF when attempting upload.');
    }

    const formData = new FormData();
    formData.append('file', pdfBlob, derivePdfUploadName(item.url));
    if (item.filename) {
      formData.append('filename', item.filename);
    }
    if (item.openaiApiKey) {
      formData.append('openaiApiKey', item.openaiApiKey);
    }

    const response = await fetch(`${API_BASE_URL}/scrape/${item.contentType.endpoint}`, {
      method: 'POST',
      headers: {
        Accept: 'application/json',
      },
      body: formData,
    });

    return await extractJobId(response);
  }

  const payload = {
    url: item.url,
    filename: item.filename,
    cookies: item.cookies,
    html: item.html,
  };

  if (item.openaiApiKey) {
    payload.openaiApiKey = item.openaiApiKey;
  }
  if (item.startTime) payload.startTime = item.startTime;
  if (item.endTime) payload.endTime = item.endTime;
  if (item.videoSettings) {
    payload.downloadVideo = item.videoSettings.video || false;
    payload.downloadAudio = item.videoSettings.audio || false;
    payload.downloadTranscript = item.videoSettings.transcript !== false;
  }

  const response = await fetch(`${API_BASE_URL}/scrape/${item.contentType.endpoint}`, {
    method: 'POST',
    headers: REQUEST_HEADERS,
    body: JSON.stringify(payload),
  });

  return await extractJobId(response);
}

async function requestJobStatus(jobId) {
  const response = await fetch(`${JOB_STATUS_BASE_URL}/${encodeURIComponent(jobId)}`, {
    method: 'GET',
    headers: { Accept: 'application/json' },
    cache: 'no-cache',
  });

  if (response.status === 404) {
    throw new Error('Conversion not found on server.');
  }

  if (!response.ok) {
    throw await buildError(response);
  }

  const data = await response.json();
  if (!data || typeof data.status !== 'string') {
    throw new Error('Invalid job status response from server.');
  }
  return data;
}

async function pollJobUntilComplete(itemId, jobId) {
  let delay = JOB_POLL_INTERVAL_MS;
  let consecutiveFailures = 0;
  const MAX_CONSECUTIVE_FAILURES = 5;

  while (true) {
    const reference = await getQueueItemReference(itemId);
    if (!reference) {
      return;
    }

    let statusData;
    try {
      statusData = await requestJobStatus(jobId);
      consecutiveFailures = 0;
    } catch (error) {
      console.error('Job status request failed', error);
      consecutiveFailures++;

      if (consecutiveFailures >= MAX_CONSECUTIVE_FAILURES) {
        await markQueueItemError(itemId, normalizeErrorMessage(error instanceof Error ? error.message : error, 'Job status check failed repeatedly'));
        return;
      }

      await sleep(delay);
      delay = Math.min(delay + 2_000, JOB_POLL_MAX_INTERVAL_MS);
      continue;
    }

    const status = statusData.status;
    if (status === 'ready') {
      const hasContent = statusData.markdown || statusData.audioData || statusData.videoData;
      if (!hasContent) {
        await markQueueItemError(itemId, 'Backend returned an empty document.');
        return;
      }
      await handleJobResult(itemId, statusData);
      return;
    }

    if (status === 'error') {
      await markQueueItemError(itemId, normalizeErrorMessage(statusData.error));
      return;
    }

    await updateQueueItemJobStatus(itemId, status);
    await sleep(delay);
    delay = Math.min(delay + 2_000, JOB_POLL_MAX_INTERVAL_MS);
  }
}

async function resumeProcessingJobs() {
  const state = await getState();
  for (const entry of state.queue || []) {
    if (entry?.status === 'processing' && entry.jobId) {
      trackJobPoll(entry.jobId, () => pollJobUntilComplete(entry.id, entry.jobId));
    }
  }
}

chrome.runtime.onInstalled.addListener(async () => {
  await checkDaemonHealth();
  processQueue();
});

chrome.runtime.onStartup.addListener(async () => {
  await checkDaemonHealth();
  processQueue();
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  handleMessage(message).then((result) => {
    sendResponse({ ok: true, ...result });
  }).catch((error) => {
    console.error('Markdown.load error:', error);
    sendResponse({ error: error.message || 'Unexpected error' });
  });
  return true;
});

async function handleMessage(message) {
  switch (message?.type) {
    case 'enqueue':
      return enqueueItem(message);
    case 'retry':
      return retryItem(message.id);
    case 'removeQueue':
      return removeQueueItem(message.id);
    case 'downloadReady':
      return downloadReadyItem(message.id);
    case 'downloadAllReady':
      return getAllReadyItems();
    case 'clearAllReady':
      return clearAllReadyItems();
    case 'removeReady':
      return removeReadyItem(message.id);
    case 'sendBrowserState':
      return sendBrowserState(message.url, message.browserInfo);
    case 'bookmark':
      return sendBookmark(message.url, message.highlightedText, message.notes);
    case 'getDaemonStatus':
      await checkDaemonHealth();
      return { daemonAvailable };
    default:
      throw new Error('Unknown message type');
  }
}


async function enqueueItem({ type, url, cookies, contentType, filename, html, openaiApiKey, startTime, endTime, videoSettings }) {
  if (!url) {
    throw new Error('Missing URL');
  }
  const state = await getState();
  const id = createId();
  state.queue.push({
    id,
    url,
    contentType,
    cookies,
    filename,
    html,
    openaiApiKey: openaiApiKey || null,
    startTime: startTime || null,
    endTime: endTime || null,
    videoSettings: videoSettings || null,
    status: 'pending',
    addedAt: Date.now()
  });
  await setState(state);
  processQueue();
  return { id };
}

async function retryItem(id) {
  const state = await getState();
  const item = state.queue.find((entry) => entry.id === id);
  if (!item) {
    throw new Error('Queue item not found');
  }
  item.status = 'pending';
  delete item.error;
  delete item.jobId;
  delete item.jobStatus;
  await setState(state);
  processQueue();
  return {};
}

async function removeQueueItem(id) {
  const state = await getState();
  const index = state.queue.findIndex((entry) => entry.id === id);
  if (index === -1) {
    throw new Error('Queue item not found');
  }
  state.queue.splice(index, 1);
  await setState(state);
  return {};
}

async function downloadReadyItem(id) {
  const state = await getState();
  const entryIndex = state.ready.findIndex((item) => item.id === id);
  if (entryIndex === -1) {
    throw new Error('Download not found');
  }
  const entry = state.ready[entryIndex];

  const blob = new Blob([entry.markdown], { type: 'text/markdown;charset=utf-8' });
  let objectUrl;
  let revokeUrl = null;
  if (typeof URL !== 'undefined' && typeof URL.createObjectURL === 'function') {
    objectUrl = URL.createObjectURL(blob);
    revokeUrl = () => URL.revokeObjectURL(objectUrl);
  } else {
    objectUrl = `data:text/markdown;charset=utf-8,${encodeURIComponent(entry.markdown)}`;
  }

  const downloadId = await new Promise((resolve, reject) => {
    chrome.downloads.download(
      {
        url: objectUrl,
        filename: entry.filename,
        saveAs: false
      },
      (downloadId) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
          return;
        }
        resolve(downloadId);
      }
    );
  });

  if (revokeUrl) {
    setTimeout(revokeUrl, 30_000);
  }

  state.ready.splice(entryIndex, 1);
  await setState(state);

  return { downloadId };
}

async function getAllReadyItems() {
  const state = await getState();
  if (!state.ready || state.ready.length === 0) {
    throw new Error('No files ready to download');
  }
  return { items: state.ready };
}

async function clearAllReadyItems() {
  const state = await getState();
  state.ready = [];
  await setState(state);
  return {};
}

async function removeReadyItem(id) {
  const state = await getState();
  const index = state.ready.findIndex((entry) => entry.id === id);
  if (index === -1) {
    throw new Error('Ready item not found');
  }
  state.ready.splice(index, 1);
  await setState(state);
  return {};
}

async function triggerBase64Download(b64data, filename, mimeType) {
  const binaryString = atob(b64data);
  const bytes = new Uint8Array(binaryString.length);
  for (let i = 0; i < binaryString.length; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  const blob = new Blob([bytes], { type: mimeType });
  const objectUrl = URL.createObjectURL(blob);
  await new Promise((resolve, reject) => {
    chrome.downloads.download({ url: objectUrl, filename, saveAs: false }, (downloadId) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
      } else {
        resolve(downloadId);
      }
    });
  });
  setTimeout(() => URL.revokeObjectURL(objectUrl), 30_000);
}

async function handleJobResult(itemId, result) {
  if (result.audioData) {
    await triggerBase64Download(result.audioData, result.audioFilename || 'audio', result.audioMimeType || 'audio/mpeg');
  }
  if (result.videoData) {
    await triggerBase64Download(result.videoData, result.videoFilename || 'video', result.videoMimeType || 'video/mp4');
  }
  if (result.markdown) {
    await moveQueueItemToReady(itemId, result);
  } else {
    // Binary-only result — remove from queue without adding to ready list
    const state = await getState();
    const index = state.queue.findIndex((e) => e.id === itemId);
    if (index !== -1) {
      state.queue.splice(index, 1);
      await setState(state);
    }
  }
}

async function processQueue() {
  if (processingQueue) {
    return;
  }
  processingQueue = true;

  try {
    await checkDaemonHealth();
    await resumeProcessingJobs();
    while (true) {
      const state = await getState();
      const index = state.queue.findIndex((item) => item.status === 'pending');
      if (index === -1) {
        break;
      }

      const item = state.queue[index];

      if (item.jobId) {
        continue;
      }

      try {
        if (daemonAvailable) {
          // Daemon path: synchronous scrape, handle result (may include binary data)
          const result = await submitDaemonJob(item);
          await handleJobResult(item.id, result);
        } else {
          // Modal path: submit job, poll until complete
          const jobId = await submitConversionJob(item);
          await storeQueueItemJobId(item.id, jobId);
          const updated = await setQueueItemProcessing(item.id);
          if (!updated) {
            continue;
          }
          await trackJobPoll(jobId, () => pollJobUntilComplete(item.id, jobId));
        }
      } catch (error) {
        console.error('Queue item failed', error);
        await markQueueItemError(item.id, normalizeErrorMessage(error instanceof Error ? error.message : error));
      }
    }
  } finally {
    processingQueue = false;
    const state = await getState();
    const hasPending = state.queue?.some((item) => item.status === 'pending');
    if (hasPending) {
      processQueue();
    }
  }
}



function derivePdfUploadName(url) {
  try {
    const parsed = new URL(url);
    const raw = decodeURIComponent(parsed.pathname.split('/').pop() || '');
    if (raw) {
      return raw.endsWith('.pdf') ? raw : `${raw}.pdf`;
    }
  } catch (error) {
    // fall through to string parsing below
  }

  const fallback = url.split('/').pop() || 'document.pdf';
  if (/\.pdf$/i.test(fallback)) {
    return fallback;
  }
  return `${fallback || 'document'}.pdf`;
}


function normalizeErrorMessage(error, fallback = 'Conversion failed') {
  if (!error) {
    return fallback;
  }
  if (typeof error === 'string') {
    return error.trim() || fallback;
  }
  if (typeof error === 'object') {
    // Handle {message: "..."} or {detail: "..."} shaped errors
    if (typeof error.message === 'string' && error.message.trim()) {
      return error.message.trim();
    }
    if (typeof error.detail === 'string' && error.detail.trim()) {
      return error.detail.trim();
    }
    // Last resort: stringify the object
    try {
      const str = JSON.stringify(error);
      return str !== '{}' ? str : fallback;
    } catch {
      return fallback;
    }
  }
  return String(error) || fallback;
}

async function buildError(response) {
  let detail = `HTTP ${response.status}`;
  try {
    const cloned = response.clone();
    const data = await cloned.json();
    if (data?.detail) {
      if (typeof data.detail === 'string') {
        detail = data.detail;
      } else {
        detail = JSON.stringify(data.detail);
      }
    }
  } catch (err) {
    const text = await response.text();
    if (text) {
      detail = text;
    }
  }
  return new Error(detail);
}


// Cookie handling functions
async function sendCookiesToBackend(endpoint, data, cookies) {
  const payload = {
    data: data,
    cookies: cookies
  };

  console.log(`🍪 Sending ${cookies.length} cookies to ${endpoint}`);

  try {
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });

    console.log(`📨 Cookies sent to ${endpoint}, status: ${response.status}`);

    if (!response.ok) {
      const errorText = await response.text();
      return {
        success: false,
        endpoint: endpoint,
        error: `${response.status}: ${errorText}`
      };
    }

    const result = await response.json();
    return {
      success: true,
      endpoint: endpoint,
      result: result
    };
  } catch (error) {
    return {
      success: false,
      endpoint: endpoint,
      error: error.message
    };
  }
}

async function handleLoginSuccess(tabId, url, config) {
  console.log('🔍 Login success detected:', url);
  console.log('📋 Matching config:', config);

  // Find the matching trigger handler
  const trigger = config.triggers.find(([triggerUrl, _]) => url.startsWith(triggerUrl));
  if (!trigger) {
    console.log('⚠️ No matching trigger found for URL:', url);
    return;
  }

  const [_, handler] = trigger;

  // Extract data using the handler (pass tabId, not url)
  const data = await handler(tabId);
  if (!data) {
    console.log('⚠️ Handler returned no data');
    return;
  }

  console.log('📦 Extracted data:', data);

  // Get cookies for all configured domains
  const allCookies = [];
  for (const domain of config.domains) {
    const cookies = await chrome.cookies.getAll({ domain });
    allCookies.push(...cookies);
  }

  console.log(`🍪 Retrieved ${allCookies.length} cookies from domains:`, config.domains);

  // Try each backend URL until one succeeds
  let successCount = 0;
  let lastError = null;
  for (const backendUrl of config.backend_urls) {
    const fullEndpoint = `${backendUrl}${config.endpoint}`;
    console.log(`📤 Sending cookies to endpoint: ${fullEndpoint}`);

    const response = await sendCookiesToBackend(fullEndpoint, data, allCookies);

    if (response.success) {
      console.log(`✅ SUCCESS: Endpoint ${response.endpoint} returned:`, response.result);
      successCount++;
    } else {
      console.log(`⚠️ Failed to send to ${response.endpoint}: ${response.error}`);
      lastError = response;
    }
  }

  // Only show error if ALL endpoints failed
  if (successCount === 0 && lastError) {
    console.error(`❌ FAILED: All endpoints failed. Last error from ${lastError.endpoint}:`, lastError.error);
  }
}

// Monitor cookie changes and URL navigation
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.url) {
    console.log(`🔄 Detected change. Checking URL: ${tab.url}`);

    // Check if URL matches any configured trigger
    for (const config of WEBSITE_CONFIGS) {
      for (const [triggerUrl, _] of config.triggers) {
        const isMatch = tab.url.startsWith(triggerUrl);
        console.log(`   Checking if: "${triggerUrl}" is in "${tab.url}" --- ${isMatch}`);

        if (isMatch) {
          handleLoginSuccess(tabId, tab.url, config);
          return; // Exit after handling the first match
        }
      }
    }
  }
});

// Send browser state (Substack & Twitter cookies) to local API for headless browser use
async function sendBrowserState(tabUrl, browserInfo) {
  // Get Substack cookies
  const substackCookies = await new Promise((resolve) => {
    chrome.cookies.getAll({ domain: '.substack.com' }, (cookies) => {
      if (chrome.runtime.lastError) {
        console.warn('Substack cookie fetch failed', chrome.runtime.lastError.message);
        resolve([]);
        return;
      }
      resolve(cookies || []);
    });
  });

  // Get Twitter/X cookies
  const twitterCookies = await new Promise((resolve) => {
    chrome.cookies.getAll({ domain: '.x.com' }, (cookies) => {
      if (chrome.runtime.lastError) {
        console.warn('Twitter cookie fetch failed', chrome.runtime.lastError.message);
        resolve([]);
        return;
      }
      resolve(cookies || []);
    });
  });

  // Format cookies for headless browser (Playwright/Puppeteer compatible)
  const formatCookies = (cookies) => cookies.map(cookie => ({
    name: cookie.name,
    value: cookie.value,
    domain: cookie.domain,
    path: cookie.path,
    secure: cookie.secure,
    httpOnly: cookie.httpOnly,
    sameSite: cookie.sameSite === 'unspecified' ? 'None' : cookie.sameSite,
    expires: cookie.expirationDate ? Math.floor(cookie.expirationDate) : undefined,
  }));

  const payload = {
    substack: {
      cookies: formatCookies(substackCookies),
    },
    twitter: {
      cookies: formatCookies(twitterCookies),
    },
    ...browserInfo,
    timestamp: Date.now(),
  };

  try {
    const response = await fetch(BROWSER_STATE_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    return { success: true };
  } catch (error) {
    console.warn('Browser state send failed:', error);
    return { success: false, error: error.message };
  }
}

// Send bookmark to daemon
async function sendBookmark(url, excerpt = '', notes = '') {
  try {
    const payload = { url };
    if (excerpt) {
      payload.excerpt = excerpt;
    }
    if (notes) {
      payload.notes = notes;
    }

    const response = await fetch(LOCAL_BOOKMARK_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`Daemon HTTP ${response.status}`);
    }

    const result = await response.json();
    if (!result.success) {
      throw new Error(result.error || 'Daemon returned error');
    }

    return {
      success: true,
      title: result.title,
      author: result.author,
    };
  } catch (error) {
    console.warn('[Bookmark] Failed:', error);
    return { success: false, error: error.message };
  }
}

// ============ Substack Button Helpers ============

/**
 * Click the Post button in Substack composer
 * @param {CDPTools} cdp - CDP tools instance
 */
async function clickSubstackPostButton(cdp) {
  // Find button by text content "Post"
  return await cdp.evaluate(`
    (function() {
      const buttons = document.querySelectorAll('button');
      for (const btn of buttons) {
        if (btn.textContent?.trim() === 'Post' && !btn.disabled) {
          btn.click();
          return { found: true };
        }
      }
      return { found: false };
    })()
  `).then(result => {
    if (result.success && result.value?.found) {
      return { success: true };
    }
    return { success: false, error: 'Post button not found' };
  });
}

/**
 * Click the Cancel button in Substack composer
 * @param {CDPTools} cdp - CDP tools instance
 */
async function clickSubstackCancelButton(cdp) {

  // Find button by text content "Cancel"
  return await cdp.evaluate(`
    (function() {
      const buttons = document.querySelectorAll('button');
      for (const btn of buttons) {
        if (btn.textContent?.trim() === 'Cancel' && !btn.disabled) {
          btn.click();
          return { found: true };
        }
      }
      return { found: false };
    })()
  `).then(result => {
    if (result.success && result.value?.found) {
      return { success: true };
    }
    return { success: false, error: 'Cancel button not found' };
  });
}

/**
 * Click the Image attachment button in Substack composer
 * @param {CDPTools} cdp - CDP tools instance
 */
async function clickSubstackImageButton(cdp) {
  // Image button has priority_tertiary class and contains lucide-image svg
  return await cdp.click('button[class*="priority_tertiary"]:has(svg.lucide-image)');
}

/**
 * Click the Video attachment button in Substack composer
 * @param {CDPTools} cdp - CDP tools instance
 */
async function clickSubstackVideoButton(cdp) {
  // Video button has priority_tertiary class and contains lucide-video svg
  return await cdp.click('button[class*="priority_tertiary"]:has(svg.lucide-video)');
}

/**
 * Click the composer trigger ("What's on your mind?")
 * @param {CDPTools} cdp - CDP tools instance
 */
async function clickSubstackComposer(cdp) {
  return await cdp.click('div[class*="inlineComposer"]');
}

/**
 * Click the note input area (contenteditable)
 * @param {CDPTools} cdp - CDP tools instance
 */
async function clickSubstackNoteInput(cdp) {
  return await cdp.click('[contenteditable="true"]');
}

// ============ Main Functions ============

/**
 * Post a note to Substack deterministically using CDP
 * @param {string} text - The text content of the note
 * @param {string|null} image - Optional image URL or base64 data to attach
 * @returns {Promise<{success: boolean, message?: string, error?: string}>}
 */
async function postSubstackNote(text, image = null) {
  return 
  console.log('[Substack] Posting note deterministically:', { text, hasImage: !!image });

  if (!text || text.trim().length === 0) {
    return { success: false, error: 'Text cannot be empty' };
  }

  // Create a new unfocused window (explicitly normal state to avoid inheriting fullscreen)
  const window = await chrome.windows.create({
    url: SUBSTACK_NOTES_URL,
    focused: false,
    state: 'normal',
    width: 1280,
    height: 800,
  });

  const tabId = window.tabs[0].id;
  const windowId = window.id;
  const cdp = new CDPTools(tabId);

  // Helper to clean up
  async function cleanup() {
    try { await cdp.detach(); } catch {}
    try { await chrome.windows.remove(windowId); } catch {}
  }

  try {
    // Wait for page to fully load (while window is visible but unfocused)
    await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('Page load timeout')), 30000);
      const listener = (updatedTabId, changeInfo) => {
        if (updatedTabId === tabId && changeInfo.status === 'complete') {
          chrome.tabs.onUpdated.removeListener(listener);
          clearTimeout(timeout);
          resolve();
        }
      };
      chrome.tabs.onUpdated.addListener(listener);
    });

    // Wait for JavaScript to initialize
    await sleep(2000);

    // Attach CDP
    await cdp.attach();
    console.log('[Substack] CDP attached to background window');

    // Step 1: Click the composer trigger
    console.log('[Substack] Step 1: Opening composer...');
    const composerClick = await clickSubstackComposer(cdp);
    if (!composerClick.success) {
      await cleanup();
      return { success: false, error: 'Could not find composer trigger' };
    }
    console.log('[Substack] Composer opened!');

    // Wait for modal to open (longer wait for background window)
    await sleep(2000);

    // Step 2: Click the input area (with retry for slow-loading modal)
    console.log('[Substack] Step 2: Clicking input area...');
    let inputClick;
    for (let attempt = 1; attempt <= 3; attempt++) {
      inputClick = await clickSubstackNoteInput(cdp);
      if (inputClick.success) break;
      console.log(`[Substack] Input not found, retry ${attempt}/3...`);
      await sleep(1000);
    }
    if (!inputClick.success) {
      await cleanup();
      return { success: false, error: 'Could not find note input' };
    }
    await sleep(300);

    // Step 2.5: Clear any existing content via JavaScript
    console.log('[Substack] Clearing any existing content...');
    await cdp.evaluate(`
      (function() {
        const el = document.querySelector('[contenteditable="true"]');
        if (el) {
          el.innerHTML = '';
          el.focus();
        }
      })()
    `);
    await sleep(200);

    // Step 3: Type the text
    console.log('[Substack] Step 3: Typing text...');
    const typeResult = await cdp.type(text);
    if (!typeResult.success) {
      await cleanup();
      return { success: false, error: 'Could not type text: ' + typeResult.error };
    }

    // Wait for UI to update and enable Post button
    await sleep(1500);

    // Step 4: Click the Post button
    console.log('[Substack] Step 4: Clicking Post button...');
    const postClickResult = await clickSubstackPostButton(cdp);
    if (!postClickResult.success) {
      await cleanup();
      return { success: false, error: 'Could not find Post button' };
    }

    console.log('[Substack] Post button clicked!');

    // Wait for post to complete
    console.log('[Substack] Waiting for post to complete...');
    await sleep(3000);

    // Clean up and restore original tab
    await cleanup();
    console.log('[Substack] Note posted successfully!');

    return { success: true, message: 'Note posted successfully!' };

  } catch (error) {
    console.error('[Substack] Error:', error);
    await cleanup();
    return { success: false, error: error.message };
  }
}

/**
 * Post a note to Substack using AI browser agent (for complex/dynamic scenarios)
 * @param {string} text - The text content of the note
 * @param {string|null} image - Optional image URL or base64 data to attach
 * @returns {Promise<{success: boolean, message?: string, error?: string}>}
 */
async function postSubstackNoteAgent(text, image = null) {
  console.log('[Substack Agent] Posting note with AI:', { text, hasImage: !!image });

  if (!text || text.trim().length === 0) {
    return { success: false, error: 'Text cannot be empty' };
  }

  // Get API key from secure storage
  const apiKey = await getClaudeApiKey();
  if (!apiKey) {
    return {
      success: false,
      error: 'Claude API key not configured. Add it in extension settings.'
    };
  }

  // Create agent instance
  const agent = new BrowserAgent(apiKey, {
    maxSteps: 15,
    stepDelay: 1500,
    verbose: true,
  });

  // Create a new unfocused window (explicitly normal state to avoid inheriting fullscreen)
  const window = await chrome.windows.create({
    url: SUBSTACK_NOTES_URL,
    focused: false,
    state: 'normal',
    width: 1280,
    height: 800,
  });

  const tabId = window.tabs[0].id;
  const windowId = window.id;

  // Helper to clean up
  async function cleanup() {
    try { await chrome.windows.remove(windowId); } catch {}
  }

  try {
    // Wait for page to fully load (while window is visible but unfocused)
    await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('Page load timeout')), 30000);
      const listener = (updatedTabId, changeInfo) => {
        if (updatedTabId === tabId && changeInfo.status === 'complete') {
          chrome.tabs.onUpdated.removeListener(listener);
          clearTimeout(timeout);
          resolve();
        }
      };
      chrome.tabs.onUpdated.addListener(listener);
    });

    // Wait for JavaScript to initialize
    await sleep(3000);
    console.log('[Substack Agent] Page loaded in background window');

    // Build the task description for the AI
    let task = `Post a note on Substack with this exact text: "${text}"

Instructions:
1. Find and click the note composer input (look for contenteditable div with placeholder "What's on your mind?" or similar)
2. Type the exact text provided
3. Click the "Post" button to publish the note
4. Confirm the note was posted successfully (look for the note appearing in the feed or a success indicator)`;

    if (image) {
      task += `
5. Before posting, also attach this image: ${image}
   (Look for an image/media upload button near the composer)`;
    }

    // Run the AI agent loop
    const result = await agent.run(tabId, task);

    // Clean up and restore original tab
    await cleanup();

    return {
      success: result.success,
      message: result.message,
      error: result.error,
      steps: result.steps,
    };

  } catch (error) {
    console.error('[Substack Agent] Error:', error);
    await cleanup();
    return { success: false, error: error.message };
  }
}

// Expose for console testing
self.postSubstackNote = postSubstackNote;
self.postSubstackNoteAgent = postSubstackNoteAgent;
self.BrowserAgent = BrowserAgent;
self.CDPTools = CDPTools;
self.getClaudeApiKey = getClaudeApiKey;