import { ContentTypes, contentTypes } from './content-types.js';

const STATE_KEY = 'markdownLoadState';
const SETTINGS_KEY = 'markdownLoadSettings';

const queueList = document.getElementById('queue-list');
const readyList = document.getElementById('ready-list');
const filenameInput = document.getElementById('filename');
const queueButton = document.getElementById('queue');
const statusLabel = document.getElementById('status');
const notesInput = document.getElementById('notes');
const downloadAllButton = document.getElementById('download-all');

const mainView = document.getElementById('main-view');
const settingsView = document.getElementById('settings-view');
const settingsButton = document.getElementById('settings-button');
const backButton = document.getElementById('back-button');
const openaiKeyInput = document.getElementById('openai-key');
const clearOpenaiKeyButton = document.getElementById('clear-openai-key');
const claudeKeyInput = document.getElementById('claude-key');
const clearClaudeKeyButton = document.getElementById('clear-claude-key');
const saveSettingsButton = document.getElementById('save-settings');
const settingsStatus = document.getElementById('settings-status');

// New button references
const bookmarkButton = document.getElementById('extract-metadata');
const sendStateButton = document.getElementById('send-state');

// Timestamp inputs (only shown for video content types)
const timestampRow = document.getElementById('timestamp-row');
const startTimeInput = document.getElementById('start-time');
const endTimeInput = document.getElementById('end-time');

// Video settings checkboxes
const videoDownloadCheckbox = document.getElementById('video-download-checkbox');
const audioDownloadCheckbox = document.getElementById('audio-download-checkbox');
const transcriptDownloadCheckbox = document.getElementById('transcript-download-checkbox');

const errorIcon = "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 640 640\"><!--!Font Awesome Free v7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc.--><path d=\"M320 64C334.7 64 348.2 72.1 355.2 85L571.2 485C577.9 497.4 577.6 512.4 570.4 524.5C563.2 536.6 550.1 544 536 544L104 544C89.9 544 76.8 536.6 69.6 524.5C62.4 512.4 62.1 497.4 68.8 485L284.8 85C291.8 72.1 305.3 64 320 64zM320 416C302.3 416 288 430.3 288 448C288 465.7 302.3 480 320 480C337.7 480 352 465.7 352 448C352 430.3 337.7 416 320 416zM320 224C301.8 224 287.3 239.5 288.6 257.7L296 361.7C296.9 374.2 307.4 384 319.9 384C332.5 384 342.9 374.3 343.8 361.7L351.2 257.7C352.5 239.5 338.1 224 319.8 224z\"/></svg>"
const downloadIcon = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640" aria-hidden="true"><path d="M320 64C178.6 64 64 178.6 64 320C64 461.4 178.6 576 320 576C461.4 576 576 461.4 576 320C576 178.6 461.4 64 320 64zM308.7 451.3L204.7 347.3C200.1 342.7 198.8 335.8 201.2 329.9C203.6 324 209.5 320 216 320L272 320L272 224C272 206.3 286.3 192 304 192L336 192C353.7 192 368 206.3 368 224L368 320L424 320C430.5 320 436.3 323.9 438.8 329.9C441.3 335.9 439.9 342.8 435.3 347.3L331.3 451.3C325.1 457.5 314.9 457.5 308.7 451.3z" /></svg>';
const xIcon = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free v7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc.--><path d="M183.1 137.4C170.6 124.9 150.3 124.9 137.8 137.4C125.3 149.9 125.3 170.2 137.8 182.7L275.2 320L137.9 457.4C125.4 469.9 125.4 490.2 137.9 502.7C150.4 515.2 170.7 515.2 183.2 502.7L320.5 365.3L457.9 502.6C470.4 515.1 490.7 515.1 503.2 502.6C515.7 490.1 515.7 469.8 503.2 457.3L365.8 320L503.1 182.6C515.6 170.1 515.6 149.8 503.1 137.3C490.6 124.8 470.3 124.8 457.8 137.3L320.5 274.7L183.1 137.4z"/></svg>';
const trashcanIcon = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640" aria-hidden="true"><path d="M232.7 69.9L224 96L128 96C110.3 96 96 110.3 96 128C96 145.7 110.3 160 128 160L512 160C529.7 160 544 145.7 544 128C544 110.3 529.7 96 512 96L416 96L407.3 69.9C402.9 56.8 390.7 48 376.9 48L263.1 48C249.3 48 237.1 56.8 232.7 69.9zM512 208L128 208L149.1 531.1C150.7 556.4 171.7 576 197 576L443 576C468.3 576 489.3 556.4 490.9 531.1L512 208z" /></svg>';
const settingsIcon = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free v7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc.--><path d="M259.1 73.5C262.1 58.7 275.2 48 290.4 48L350.2 48C365.4 48 378.5 58.7 381.5 73.5L396 143.5C410.1 149.5 423.3 157.2 435.3 166.3L503.1 143.8C517.5 139 533.3 145 540.9 158.2L570.8 210C578.4 223.2 575.7 239.8 564.3 249.9L511 297.3C511.9 304.7 512.3 312.3 512.3 320C512.3 327.7 511.8 335.3 511 342.7L564.4 390.2C575.8 400.3 578.4 417 570.9 430.1L541 481.9C533.4 495 517.6 501.1 503.2 496.3L435.4 473.8C423.3 482.9 410.1 490.5 396.1 496.6L381.7 566.5C378.6 581.4 365.5 592 350.4 592L290.6 592C275.4 592 262.3 581.3 259.3 566.5L244.9 496.6C230.8 490.6 217.7 482.9 205.6 473.8L137.5 496.3C123.1 501.1 107.3 495.1 99.7 481.9L69.8 430.1C62.2 416.9 64.9 400.3 76.3 390.2L129.7 342.7C128.8 335.3 128.4 327.7 128.4 320C128.4 312.3 128.9 304.7 129.7 297.3L76.3 249.8C64.9 239.7 62.3 223 69.8 209.9L99.7 158.1C107.3 144.9 123.1 138.9 137.5 143.7L205.3 166.2C217.4 157.1 230.6 149.5 244.6 143.4L259.1 73.5zM320.3 400C364.5 399.8 400.2 363.9 400 319.7C399.8 275.5 363.9 239.8 319.7 240C275.5 240.2 239.8 276.1 240 320.3C240.2 364.5 276.1 400.2 320.3 400z"/></svg>'

let activeTab = null;
let activeContentType = null;
let queueDisabled = false;
let statusTimer = null;
let fileSchemeAllowed = true;

function capturePageHtml(tabId) {
  return new Promise((resolve) => {
    chrome.tabs.sendMessage(tabId, { type: 'capture-html' }, (response) => {
      if (chrome.runtime.lastError) {
        console.warn('HTML capture failed', chrome.runtime.lastError.message);
        resolve(null);
        return;
      }
      resolve(response?.html || null);
    });
  });
}

function formatDuration(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) {
    return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  }
  return `${m}:${String(s).padStart(2, '0')}`;
}

function slugify(text) {
  return (text || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '') || 'download';
}

function normaliseFilename(name, fallback) {
  let cleaned = '';
  if (typeof name === 'string') {
    cleaned = name.trim();
  } else if (name != null) {
    cleaned = String(name).trim();
  }

  let base = cleaned;
  if (!base) {
    if (typeof fallback === 'string') {
      base = fallback.trim();
    } else if (fallback != null) {
      base = String(fallback).trim();
    }
  }

  if (!base) {
    base = 'download';
  }

  const lower = base.toLowerCase();
  return lower.endsWith('.md') ? base : `${base}.md`;
}


function setStatus(message) {
  if (statusTimer) {
    clearTimeout(statusTimer);
    statusTimer = null;
  }
  statusLabel.textContent = message;
  statusTimer = setTimeout(() => {
    statusLabel.textContent = '';
    statusTimer = null;
  }, 3000);
}


function sendMessage(payload) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(payload, (response) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
        return;
      }
      if (!response) {
        reject(new Error('No response from background script.'));
        return;
      }
      if (response.error) {
        reject(new Error(response.error));
        return;
      }
      resolve(response);
    });
  });
}

function renderQueue(items) {
  queueList.innerHTML = '';
  if (!items.length) {
    return;
  }
  queueList.style.display = 'flex';

  for (const item of items) {
    const li = document.createElement('li');
    li.className = 'list-item fade';

    const deleteButton = document.createElement('button');
    deleteButton.className = 'icon-button';
    deleteButton.title = 'Remove from list';
    deleteButton.innerHTML = xIcon;
    deleteButton.addEventListener('click', () => handleRemove(item.id));
    li.appendChild(deleteButton);

    const content = document.createElement('span');
    content.className = 'filename';
    content.textContent = item.filename;
    li.appendChild(content);

    if (item.status === 'error') {
      const errorButton = document.createElement('button');
      errorButton.className = 'icon-button error-icon';
      errorButton.title = item.error || 'Conversion failed';
      errorButton.innerHTML = errorIcon;
      errorButton.addEventListener('click', () => handleRetry(item.id));
      li.appendChild(errorButton);
    } else {
      const spinner = document.createElement('div');
      spinner.className = 'spinner';
      li.appendChild(spinner);
    }

    queueList.appendChild(li);
  }
}

function renderReady(items) {
  readyList.innerHTML = '';
  if (!items.length) {
    downloadAllButton.style.display = 'none';
    return;
  }
  readyList.style.display = 'flex';
  downloadAllButton.style.display = 'flex';

  for (const item of items) {
    const li = document.createElement('li');
    li.className = 'list-item fade';

    const deleteButton = document.createElement('button');
    deleteButton.className = 'icon-button';
    deleteButton.title = 'Remove from list';
    deleteButton.innerHTML = trashcanIcon;
    deleteButton.addEventListener('click', () => handleRemoveReady(item.id));
    li.appendChild(deleteButton);

    const filename = document.createElement('span');
    filename.className = 'filename';
    filename.textContent = item.filename;
    li.appendChild(filename);

    const button = document.createElement('button');
    button.className = 'icon-button';
    button.title = 'Download markdown';
    button.innerHTML = downloadIcon;
    button.addEventListener('click', () => handleDownload(item.id));
    li.appendChild(button);

    readyList.appendChild(li);
  }
}

async function handleRetry(id) {
  try {
    await sendMessage({ type: 'retry', id });
    setStatus('Retrying…');
  } catch (error) {
    setStatus(error.message || 'Retry failed.');
  }
}

async function handleRemove(id) {
  try {
    await sendMessage({ type: 'removeQueue', id });
    setStatus('removed from queue');
  } catch (error) {
    setStatus(error.message || 'Remove failed.');
  }
}

async function handleDownload(id) {
  try {
    await sendMessage({ type: 'downloadReady', id });
    setStatus('downloading');
  } catch (error) {
    setStatus(error.message || 'Download failed.');
  }
}

async function handleRemoveReady(id) {
  try {
    await sendMessage({ type: 'removeReady', id });
    setStatus('removed download');
  } catch (error) {
    setStatus(error.message || 'Remove failed.');
  }
}

async function handleDownloadAll() {
  try {
    downloadAllButton.disabled = true;
    setStatus('creating zip file...');

    // Get all ready items from service worker
    const response = await sendMessage({ type: 'downloadAllReady' });
    const items = response.items;

    if (!items || items.length === 0) {
      setStatus('No files to download');
      return;
    }

    // Create zip file using JSZip
    const zip = new JSZip();
    for (const item of items) {
      zip.file(item.filename, item.markdown);
    }

    // Generate the zip blob
    const zipBlob = await zip.generateAsync({ type: 'blob' });

    // Create download link
    const url = URL.createObjectURL(zipBlob);
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').split('T')[0];
    const filename = `markdowns-${timestamp}.zip`;

    // Trigger download using chrome.downloads API
    await new Promise((resolve, reject) => {
      chrome.downloads.download(
        {
          url: url,
          filename: filename,
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

    // Clean up URL
    setTimeout(() => URL.revokeObjectURL(url), 30000);

    // Clear all ready items at once (just like individual downloads remove themselves)
    await sendMessage({ type: 'clearAllReady' });

    setStatus('downloading zip!');
  } catch (error) {
    setStatus(error.message || 'Download all failed.');
  } finally {
    downloadAllButton.disabled = false;
  }
}

async function refreshState() {
  const state = await new Promise((resolve) => {
    chrome.storage.local.get(STATE_KEY, (result) => {
      resolve(result[STATE_KEY] || { queue: [], ready: [] });
    });
  });
  renderQueue(state.queue || []);
  renderReady(state.ready || []);
}


async function getCookieValue(url, name) {
  return new Promise((resolve) => {
    chrome.cookies.get({ url, name }, (cookie) => {
      if (chrome.runtime.lastError) {
        console.warn('Cookie lookup failed', chrome.runtime.lastError.message);
        resolve(null);
        return;
      }
      resolve(cookie ? cookie.value : null);
    });
  });
}

// this function doesn't work but would be great if it did 
async function getHostCookies(url, host) {
  const topLevelSite = new URL(url).origin;

  // Ask for substack.com cookies scoped to this tab’s partition
  const cookies = await chrome.cookies.getAll({
    domain: host,
    partitionKey: { topLevelSite }
  });

  return cookies;
}

async function getAllCookies(tabURL) {
  return new Promise((resolve) => {
    chrome.cookies.getAll({ url : tabURL} , (cookies) => {
      if (chrome.runtime.lastError) {
        console.warn('Cookie lookup failed', chrome.runtime.lastError.message);
        resolve({});
        return;
      }

      const lookup = Object.create(null);
      for (const cookie of cookies || []) {
        if (cookie?.name && cookie.value !== undefined) {
          lookup[cookie.name] = cookie.value;
        }
      }

      resolve(lookup);
    });
  });
}

function disableQueue(message) {
  queueDisabled = true;
  queueButton.disabled = true;
  if (filenameInput) {
    filenameInput.value = '';
  }
  setStatus(message);
}
async function prepareUI(url, activeContentType) {
  const required = activeContentType.requiredCookies || [];
  let necessaryCookies = {};

  const allCookies = await getAllCookies(url);

  if (required.length === 1 && required[0] === '*') {
    necessaryCookies = allCookies;
  }
  
  else {
    // get cookies again in case tab is refreshed or user signed out.
    for (const name of required) {
      const value = allCookies[name];
      if (value) necessaryCookies[name] = value;
    }


    const missing = required.filter((cookie) => !necessaryCookies[cookie]);

    if (missing.length) {
      disableQueue(activeContentType.errorMessage || 'try logging in first!');
      return;
    }
  }


  if (activeContentType.name === 'pdf-local' && !fileSchemeAllowed) {
    disableQueue('enable "allow access to file URLs" in chrome://extensions');
    return;
  }

  const targetUrl = activeTab.url;

  let capturedHtml = null;
  if (activeContentType.captureHtml) {
    capturedHtml = await capturePageHtml(activeTab.id);
    if (capturedHtml) {
      console.log('HTML captured successfully, length:', capturedHtml.length);
      console.log('Contains <article>:', capturedHtml.includes('<article'));
    } else {
      console.warn('HTML capture returned null');
    }
  }

  const settings = await loadSettings();

  const videoSettings = settings.videoSettings || { video: false, audio: false, transcript: true };

  await sendMessage({
    type: 'enqueue',
    url: targetUrl,
    cookies: necessaryCookies,
    contentType: activeContentType,
    filename: filenameInput.value,
    html: capturedHtml,
    openaiApiKey: settings.openaiApiKey || null,
    startTime: activeContentType.isVideo ? (startTimeInput.value.trim() || null) : null,
    endTime: activeContentType.isVideo ? (endTimeInput.value.trim() || null) : null,
    videoSettings: activeContentType.isVideo ? videoSettings : null,
  });
  setStatus('downloading! feel free to close this tab and add more :)');
}

function suggestSubstackFilename(url) {
  const slug = slugify(url.split('/').pop() || 'substack-article');
  return `${slug}.md`;
}

function suggestPdfFilename(url) {
  try {
    const parsed = new URL(url);
    const base = parsed.pathname.split('/').pop() || 'document.pdf';
    const name = base.replace(/\.pdf$/i, '') || 'document';
    return `${slugify(name)}.md`;
  } catch (error) {
    const fallback = url.split('/').pop() || 'document.pdf';
    const name = fallback.replace(/\.pdf$/i, '') || 'document';
    return `${slugify(name)}.md`;
  }
}

function suggestArticleFilename(url) {
  try {
    const parsed = new URL(url);
    const host = (parsed.hostname || 'article').replace(/^www\./i, '').replace(/\.[^.]+$/, '');
    const segments = parsed.pathname.split('/').filter(Boolean);
    const slugSegment = segments.length ? segments[segments.length - 1] : 'article';
    const hostSlug = slugify(host);
    const pathSlug = slugify(slugSegment);
    const combined = [hostSlug, pathSlug].filter(Boolean).join('_') || 'article';
    return `${combined}.md`;
  } catch (error) {
    const fallback = url.split('/').filter(Boolean).pop() || 'article';
    return `${slugify(fallback)}.md`;
  }
}

function suggestYoutubeFilename(url) {
  try {
    const parsed = new URL(url);
    const videoId = parsed.searchParams.get('v') || parsed.pathname.split('/').pop();
    const name = videoId || 'youtube-video';
    return `${slugify(name)}.md`;
  } catch (error) {
    const fallback = url.split('/').pop() || 'youtube-video';
    return `${slugify(fallback)}.md`;
  }
}


function suggestTweetFilename(url) {
  const match = url.match(ContentTypes.TWITTER.regex);
  const handle = match ? match[1] : 'thread';
  const tweetId = match ? match[2] : 'tweet';
  const slug = slugify(`${handle}-${tweetId}`);
  return `${slug}.md`;
}

async function detectContentType(url) {
  if (typeof url !== 'string' || !url) {
    return null;
  }

  for (const type of contentTypes) {
    if (type?.regex && type.regex.test(url)) return type;
  }
  return null;
}


async function prepareForContentType(type, url) {
  try {
    await prepareUI(url, type);
  } catch (error) {
    console.warn('Preparation failed', error);
    disableQueue('Unable to prepare this page for download.');
    throw error;
  }
}

async function initialise() {
  try {
    fileSchemeAllowed = await chrome.extension.isAllowedFileSchemeAccess();
  } catch (error) {
    console.warn('Unable to determine file URL access', error);
    fileSchemeAllowed = false;
  }

  activeTab = await new Promise((resolve) => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      resolve(tabs[0] || null);
    });
  });

  await refreshState();

  const url = activeTab?.url || '';
  activeContentType= await detectContentType(url);

  if (!activeContentType) {
    disableQueue('nothing to download here!');
    return;
  }

  if (activeContentType.name === 'pdf-local' && !fileSchemeAllowed) {
    disableQueue('enable "allow access to file URLs" in chrome://extensions');
    return;
  }

  // Check daemon status and disable bookmark button if not available
  try {
    const daemonStatus = await sendMessage({ type: 'getDaemonStatus' });
    if (!daemonStatus.daemonAvailable) {
      bookmarkButton.disabled = true;
      bookmarkButton.classList.add('disabled');
      bookmarkButton.title = 'Local daemon not running';
    }
  } catch {
    bookmarkButton.disabled = true;
    bookmarkButton.classList.add('disabled');
    bookmarkButton.title = 'Local daemon not running';
  }

  // Show timestamp row and populate defaults from the page's video element
  if (activeContentType.isVideo) {
    timestampRow.style.display = 'flex';
    startTimeInput.value = '0:00';
    endTimeInput.value = '0:00';
    try {
      const results = await chrome.scripting.executeScript({
        target: { tabId: activeTab.id },
        func: () => {
          const video = document.querySelector('video');
          return video ? video.duration : null;
        },
      });
      const duration = results?.[0]?.result;
      if (duration && isFinite(duration) && duration > 0) {
        endTimeInput.value = formatDuration(duration);
      }
    } catch (e) {
      // Leave defaults if we can't inject (e.g. restricted page)
    }
  }

  queueDisabled = false;
  queueButton.disabled = false;

  let slug = "download.md";
    switch (activeContentType.name) {
      case 'substack':
        slug = suggestSubstackFilename(url);
        break;
      case 'twitter':
        slug = suggestTweetFilename(url);
        break;
      case 'pdf-remote':
      case 'pdf-local':
        slug = suggestPdfFilename(url);
        break;
      case 'youtube':
        slug = suggestYoutubeFilename(url);
        break;
      case 'article':
        slug = suggestArticleFilename(url);
        break;
    }
    const fname = normaliseFilename(filenameInput.value, slug);
    if (!filenameInput.value.trim()) {
        filenameInput.value = normaliseFilename('', fname);
    }
  return;
}

queueButton.addEventListener('click', async () => {
  const state = await new Promise((resolve) => {
    chrome.storage.local.get(STATE_KEY, (result) => {
      resolve(result[STATE_KEY] || { queue: [], ready: [] });
    });
  });

  if (queueDisabled) {
    setStatus('nothing to download here!');
    return;
  }

  if (!activeTab || !activeTab.url || !activeContentType) {
    setStatus('nothing to download here!');
    return;
  }


  const alreadyQueued = (state.queue || []).some((item) => item.url === activeTab.url);
  const alreadyReady = (state.ready || []).some((item) => item.url === activeTab.url);

  if (alreadyQueued) {
    setStatus('already queued!');
    return;
  }

  if (alreadyReady) {
    setStatus('aleady ready to download!');
    return;
  }

  queueButton.disabled = true;

  try {
    await prepareForContentType(activeContentType, activeTab.url);
  } catch (error) {
    setStatus(error.message || 'Failed to queue item.');
  } finally {
    queueButton.disabled = false;
  }
});

downloadAllButton.addEventListener('click', handleDownloadAll);

// Send browser state button handler (in settings)
sendStateButton.addEventListener('click', async () => {
  if (!activeTab || !activeTab.url) {
    setSettingsStatus('No active tab');
    return;
  }

  sendStateButton.disabled = true;
  setSettingsStatus('Sending browser state...', 0);

  try {
    const response = await sendMessage({
      type: 'sendBrowserState',
      url: activeTab.url,
      browserInfo: {
        viewport: { width: window.screen.availWidth, height: window.screen.availHeight },
        screen: { width: window.screen.width, height: window.screen.height },
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        language: navigator.language,
        languages: [...navigator.languages],
        platform: navigator.platform,
        userAgent: navigator.userAgent,
      },
    });
    setSettingsStatus(response.success ? 'Browser state sent!' : 'Failed to send state');
  } catch (error) {
    setSettingsStatus(error.message || 'Failed to send browser state');
  } finally {
    sendStateButton.disabled = false;
  }
});

// Ghostpost button handler - sends URL to daemon so it can create a Ghostpost draft
bookmarkButton.addEventListener('click', async () => {
  if (!activeTab || !activeTab.url) {
    setStatus('No active tab');
    return;
  }

  bookmarkButton.disabled = true;
  setStatus('Sending to Ghostpost...');

  try {
    // Get highlighted text from the active tab
    let highlightedText = '';
    try {
      const results = await chrome.scripting.executeScript({
        target: { tabId: activeTab.id },
        func: () => window.getSelection()?.toString() || '',
      });
      highlightedText = results?.[0]?.result || '';
    } catch (e) {
      // Ignore errors (e.g., can't inject into chrome:// pages)
      console.log('Could not get selection:', e.message);
    }

    const notes = notesInput.value.trim();

    const response = await sendMessage({
      type: 'bookmark',
      url: activeTab.url,
      highlightedText: highlightedText,
      notes: notes || undefined,
    });
    if (response.success) {
      notesInput.value = '';
    }
    setStatus(response.success ? 'Sent to Ghostpost' : 'Failed to send to Ghostpost');
  } catch (error) {
    setStatus(error.message || 'Ghostpost draft failed');
  } finally {
    bookmarkButton.disabled = false;
  }
});

chrome.storage.onChanged.addListener((changes, areaName) => {
  if (areaName !== 'local' || !changes[STATE_KEY]) {
    return;
  }
  const next = changes[STATE_KEY].newValue || { queue: [], ready: [] };
  renderQueue(next.queue || []);
  renderReady(next.ready || []);
});

// Settings functions
async function loadSettings() {
  return new Promise((resolve) => {
    chrome.storage.sync.get(SETTINGS_KEY, (result) => {
      resolve(result[SETTINGS_KEY] || {});
    });
  });
}

async function saveSettings(settings) {
  return new Promise((resolve) => {
    chrome.storage.sync.set({ [SETTINGS_KEY]: settings }, resolve);
  });
}

function showSettingsView() {
  mainView.style.display = 'none';
  settingsView.style.display = 'flex';
}

function showMainView() {
  settingsView.style.display = 'none';
  mainView.style.display = 'flex';
}

function setSettingsStatus(message, duration = 3000) {
  settingsStatus.textContent = message;
  if (duration > 0) {
    setTimeout(() => {
      settingsStatus.textContent = '';
    }, duration);
  }
}

async function validateOpenAIKey(apiKey) {
  if (!apiKey || !apiKey.trim()) {
    return { valid: false, error: 'API key is empty' };
  }

  try {
    const response = await fetch('https://api.openai.com/v1/models', {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json'
      }
    });

    if (response.ok) {
      return { valid: true };
    } else if (response.status === 401) {
      return { valid: false, error: 'Invalid API key' };
    } else {
      return { valid: false, error: `Validation failed (${response.status})` };
    }
  } catch (error) {
    return { valid: false, error: 'Network error during validation' };
  }
}

settingsButton.addEventListener('click', async () => {
  const settings = await loadSettings();
  openaiKeyInput.value = settings.openaiApiKey || '';
  claudeKeyInput.value = settings.claudeApiKey || '';
  const vs = settings.videoSettings || { video: false, audio: false, transcript: true };
  videoDownloadCheckbox.checked = vs.video || false;
  audioDownloadCheckbox.checked = vs.audio || false;
  transcriptDownloadCheckbox.checked = vs.transcript !== false;
  showSettingsView();
});

backButton.addEventListener('click', () => {
  showMainView();
  settingsStatus.textContent = '';
});

clearOpenaiKeyButton.addEventListener('click', () => {
  openaiKeyInput.value = '';
  openaiKeyInput.focus();
});

clearClaudeKeyButton.addEventListener('click', () => {
  claudeKeyInput.value = '';
  claudeKeyInput.focus();
});

saveSettingsButton.addEventListener('click', async () => {
  const openaiKey = openaiKeyInput.value.trim();
  const claudeKey = claudeKeyInput.value.trim();

  saveSettingsButton.disabled = true;
  setSettingsStatus('Validating...', 0);

  // Validate OpenAI key if provided
  if (openaiKey) {
    const validation = await validateOpenAIKey(openaiKey);
    if (!validation.valid) {
      setSettingsStatus('OpenAI: ' + (validation.error || 'Invalid API key'));
      saveSettingsButton.disabled = false;
      return;
    }
  }

  // Validate Claude key format if provided (basic check)
  if (claudeKey && !claudeKey.startsWith('sk-ant-')) {
    setSettingsStatus('Claude key should start with sk-ant-');
    saveSettingsButton.disabled = false;
    return;
  }

  const settings = {
    openaiApiKey: openaiKey,
    claudeApiKey: claudeKey,
    videoSettings: {
      video: videoDownloadCheckbox.checked,
      audio: audioDownloadCheckbox.checked,
      transcript: transcriptDownloadCheckbox.checked,
    },
  };

  await saveSettings(settings);
  setSettingsStatus('Settings saved!');
  saveSettingsButton.disabled = false;

  setTimeout(() => {
    showMainView();
    settingsStatus.textContent = '';
  }, 1000);
});

initialise();
