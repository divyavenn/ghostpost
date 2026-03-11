# Orchestration Flow Implementation Specification

This document provides complete implementation details for the consumed orchestration system. A Claude instance should be able to implement the Chrome extension and remote server using this spec.

---

## System Overview

Three-component orchestration for automated Substack posting:

1. **Local Daemon** (existing) - Desktop task queue manager at `consumed-daemon/`
2. **Chrome Extension** (to build) - Browser automation executor at `consumed-extension/`
3. **Remote Server** (to build) - Cloud orchestrator for multi-device sync

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        LOCAL MACHINE                                 │
│                                                                      │
│  ┌─────────────────┐                      ┌──────────────────┐      │
│  │ Chrome Extension│──────────────────────►│  Local Daemon    │      │
│  │  (Executor)     │◄──────────────────────│  (Task Queue)    │      │
│  └────────┬────────┘   HTTP localhost:9876 └────────┬─────────┘      │
│           │                                         │                │
│      ┌────▼────┐                           ┌────────▼────────┐      │
│      │ Substack │                          │   SQLite DB     │      │
│      │  (Web)   │                          │ ~/.consumed/    │      │
│      └──────────┘                          │   tasks.db      │      │
│                                            └─────────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Sync
                                    ▼
                        ┌─────────────────────┐
                        │   Remote Server     │
                        │   (Cloud Sync)      │
                        └──────────┬──────────┘
                                   │
                            ┌──────▼──────┐
                            │  PostgreSQL │
                            │  (Cloud)    │
                            └─────────────┘
```

---

## Communication Flow

```
1. USER BOOKMARKS URL
   └─► Chrome bookmark event fired

2. EXTENSION DETECTS BOOKMARK
   └─► chrome.bookmarks.onCreated listener
   └─► Extracts URL from bookmark
   └─► Captures highlighted text from page (if any)
   └─► POST /bookmark to daemon with { url, excerpt }

3. DAEMON PROCESSES REQUEST (creates TWO parallel tasks)
   └─► Extracts metadata using Rust (consumed_core::metadata::extract)
       → Returns { title, author, content_type, image_url }
   └─► Calls Python: create_recommendation(url, title, author, content_type, excerpt)
       → Returns { content }
   └─► Builds full payload:
       {
         url, title, author, content_type, excerpt, image_url,
         content (generated recommendation)
       }
   └─► Creates TWO tasks in parallel:

       TASK 1: LogToGitHub (daemon executes immediately)
       ├─► type: "LogToGitHub"
       ├─► payload: { url, title, author, content_type }
       ├─► Daemon commits to GitHub diary
       └─► Removed from queue on commit success

       TASK 2: PostSubstackNote (extension executes)
       ├─► id: "uuid-xxx" (task_id for confirmation)
       ├─► type: "PostSubstackNote"
       ├─► payload: { url, title, author, content_type, excerpt, image_url, content }
       └─► Stays in queue until extension confirms with task_id

   └─► Returns flat response to extension:
       {
         success: true,
         task_id: "uuid-xxx",  // For completion confirmation
         url, title, author, content_type, excerpt, image_url, content
       }

4. PARALLEL EXECUTION

   DAEMON (GitHub):                    EXTENSION (Substack):
   ├─► Commits entry to diary          ├─► Opens Substack notes tab
   ├─► Pushes to GitHub                ├─► Injects content + image
   ├─► On success: remove task         ├─► Clicks post button
   └─► On failure: retry later         └─► Waits for confirmation

5. EXTENSION REPORTS RESULT (using task_id from step 3)
   ├─► SUCCESS: POST /confirm-substack-post {task_id, status: "completed"}
   │   └─► Daemon removes PostSubstackNote task from queue
   └─► FAILURE: POST /confirm-substack-post {task_id, status: "failed", error: "..."}
       └─► Task stays in queue with full payload for retry

6. RETRY ON STARTUP
   └─► Extension polls GET /tasks/pending?type=PostSubstackNote
   └─► Gets tasks with id + full payload (no re-generation needed)
   └─► Executes each task, confirms with PATCH /tasks/{task.id}
```

**Key Principle**: Extension initiates ALL communication. Daemon is passive and never reaches out to extension.

---

## Part 1: Chrome Extension Implementation

### Directory Structure

```
consumed-extension/
├── manifest.json          # Extension configuration (Manifest V3)
├── background.js          # Service worker - bookmark listener, task management
├── content.js             # Content script for Substack DOM automation
├── popup.html             # Extension popup UI
├── popup.js               # Popup logic
├── popup.css              # Popup styles
├── config.js              # Configuration (daemon URL, etc.)
└── icons/
    ├── icon16.png
    ├── icon48.png
    └── icon128.png
```

### manifest.json

```json
{
  "manifest_version": 3,
  "name": "Consumed - Auto Substack",
  "version": "1.0.0",
  "description": "Automatically post bookmarked content to Substack",

  "permissions": [
    "bookmarks",
    "tabs",
    "storage",
    "scripting"
  ],

  "host_permissions": [
    "http://localhost:9876/*",
    "http://127.0.0.1:9876/*",
    "https://substack.com/*",
    "https://*.substack.com/*"
  ],

  "background": {
    "service_worker": "background.js",
    "type": "module"
  },

  "content_scripts": [
    {
      "matches": ["https://*.substack.com/notes*", "https://substack.com/notes*"],
      "js": ["content.js"],
      "run_at": "document_idle"
    }
  ],

  "action": {
    "default_popup": "popup.html",
    "default_icon": {
      "16": "icons/icon16.png",
      "48": "icons/icon48.png",
      "128": "icons/icon128.png"
    }
  },

  "icons": {
    "16": "icons/icon16.png",
    "48": "icons/icon48.png",
    "128": "icons/icon128.png"
  }
}
```

### config.js

```javascript
export const CONFIG = {
  DAEMON_URL: 'http://localhost:9876',
  SUBSTACK_NOTES_URL: 'https://substack.com/notes',
  RETRY_DELAY_MS: 5000,
  MAX_EXECUTION_ATTEMPTS: 3
};
```

### background.js (Service Worker)

```javascript
import { CONFIG } from './config.js';

// ============================================
// DAEMON API FUNCTIONS
// ============================================

async function createBookmark(url, excerpt = null) {
  // POST /bookmark creates TWO tasks:
  // 1. LogToGitHub (daemon executes in background)
  // 2. PostSubstackNote (extension executes)

  const response = await fetch(`${CONFIG.DAEMON_URL}/bookmark`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, excerpt })
  });

  if (!response.ok) {
    throw new Error(`Failed to create bookmark: ${response.status}`);
  }

  const data = await response.json();
  // Flat response:
  // {
  //   success, task_id, url, title, author,
  //   content_type, excerpt, image_url, content, error
  // }

  if (!data.success) {
    throw new Error(data.error || 'Unknown error');
  }

  // Return the data for extension to post
  // (GitHub task is already being executed by daemon in background)
  return data;
}

async function getPendingTasks() {
  const response = await fetch(`${CONFIG.DAEMON_URL}/tasks/pending`);

  if (!response.ok) {
    throw new Error(`Failed to get pending tasks: ${response.status}`);
  }

  const data = await response.json();
  return data.tasks || [];
}

async function confirmSubstackPost(taskId, status, error = null) {
  const body = { task_id: taskId, status };
  if (error) body.error = error;

  const response = await fetch(`${CONFIG.DAEMON_URL}/confirm-substack-post`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });

  return response.ok;
}

// ============================================
// TASK EXECUTION
// ============================================

async function executeSubstackPost(data) {
  // data = { task_id, url, title, author, content_type, excerpt, image_url, content }
  const taskId = data.task_id;
  console.log(`[Consumed] Posting to Substack, task ${taskId}`);

  try {
    // Open Substack notes in a new tab
    const tab = await chrome.tabs.create({
      url: CONFIG.SUBSTACK_NOTES_URL,
      active: false // Background tab
    });

    // Wait for page to load
    await waitForTabLoad(tab.id);

    // Execute content script to post
    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: postToSubstack,
      args: [data]  // Pass the flat data object
    });

    const result = results[0]?.result;

    if (result?.success) {
      // Confirm completion to daemon
      await confirmSubstackPost(taskId, 'completed');
      console.log(`[Consumed] Task ${taskId} completed successfully`);
    } else {
      throw new Error(result?.error || 'Unknown error during posting');
    }

    // Close the tab
    await chrome.tabs.remove(tab.id);

  } catch (error) {
    console.error(`[Consumed] Task ${taskId} failed:`, error);
    // Report failure - task stays in queue for retry
    await confirmSubstackPost(taskId, 'failed', error.message);
  }
}

function waitForTabLoad(tabId) {
  return new Promise((resolve) => {
    chrome.tabs.onUpdated.addListener(function listener(id, info) {
      if (id === tabId && info.status === 'complete') {
        chrome.tabs.onUpdated.removeListener(listener);
        // Additional delay for React hydration
        setTimeout(resolve, 2000);
      }
    });
  });
}

// This function is injected into the Substack page
// data = { task_id, url, title, author, content_type, excerpt, image_url, content }
function postToSubstack(data) {
  return new Promise((resolve) => {
    try {
      const content = data.content;
      const url = data.url;

      if (!content) {
        resolve({ success: false, error: 'No content in payload' });
        return;
      }

      // Find the note composer textarea
      // Substack uses contenteditable divs, not textareas
      const composer = document.querySelector('[data-testid="note-composer"]') ||
                       document.querySelector('.ProseMirror') ||
                       document.querySelector('[contenteditable="true"]');

      if (!composer) {
        resolve({ success: false, error: 'Could not find note composer' });
        return;
      }

      // Focus and insert content with preserved line breaks
      composer.focus();

      // Split content by newlines and insert with proper paragraph breaks
      const lines = content.split('\n');
      lines.forEach((line, index) => {
        if (line) {
          document.execCommand('insertText', false, line);
        }
        // Insert line break for each \n (except after the last line)
        if (index < lines.length - 1) {
          document.execCommand('insertLineBreak', false, null);
        }
      });

      // If URL should be included, add it with spacing
      if (url && !content.includes(url)) {
        document.execCommand('insertLineBreak', false, null);
        document.execCommand('insertLineBreak', false, null);
        document.execCommand('insertText', false, url);
      }

      // Find and click the post button
      setTimeout(() => {
        const postButton = document.querySelector('[data-testid="post-button"]') ||
                          document.querySelector('button[type="submit"]') ||
                          Array.from(document.querySelectorAll('button'))
                            .find(b => b.textContent.toLowerCase().includes('post'));

        if (postButton) {
          postButton.click();

          // Wait for post to complete
          setTimeout(() => {
            // Check for success indicators
            const successIndicator = document.querySelector('[data-testid="note-posted"]') ||
                                    document.querySelector('.success-message');

            if (successIndicator) {
              resolve({ success: true, message: 'Posted successfully' });
            } else {
              // Assume success if no error shown
              resolve({ success: true, message: 'Post submitted' });
            }
          }, 3000);
        } else {
          resolve({ success: false, error: 'Could not find post button' });
        }
      }, 500);

    } catch (error) {
      resolve({ success: false, error: error.message });
    }
  });
}

async function checkAndExecutePendingTasks() {
  try {
    console.log('[Consumed] Checking for pending tasks...');
    const tasks = await getPendingTasks();
    console.log(`[Consumed] Found ${tasks.length} pending tasks`);

    for (const task of tasks) {
      // Convert task object to flat data format
      const data = {
        task_id: task.id,
        ...task.payload  // Contains url, title, author, content_type, excerpt, image_url, content
      };
      await executeSubstackPost(data);
      // Small delay between tasks
      await new Promise(r => setTimeout(r, 1000));
    }
  } catch (error) {
    console.error('[Consumed] Error checking pending tasks:', error);
  }
}

// ============================================
// EVENT LISTENERS
// ============================================

// On extension startup - check for pending tasks
chrome.runtime.onStartup.addListener(() => {
  console.log('[Consumed] Extension started');
  checkAndExecutePendingTasks();
});

// On extension install - also check
chrome.runtime.onInstalled.addListener(() => {
  console.log('[Consumed] Extension installed');
  checkAndExecutePendingTasks();
});

// On bookmark created - create task and execute
chrome.bookmarks.onCreated.addListener(async (id, bookmark) => {
  if (!bookmark.url) {
    console.log('[Consumed] Bookmark has no URL, skipping');
    return;
  }

  console.log(`[Consumed] Bookmark created: ${bookmark.url}`);

  try {
    // Try to get highlighted text from the active tab
    let excerpt = null;
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tab?.id) {
        const results = await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          func: () => window.getSelection()?.toString() || null
        });
        excerpt = results[0]?.result;
      }
    } catch (e) {
      console.log('[Consumed] Could not get selection:', e);
    }

    // Create bookmark - daemon creates GitHub + Substack tasks, returns data for posting
    const data = await createBookmark(bookmark.url, excerpt);
    console.log(`[Consumed] Task created: ${data.task_id}`);

    // Execute Substack post immediately
    await executeSubstackPost(data);

  } catch (error) {
    console.error('[Consumed] Error processing bookmark:', error);
  }
});

// Listen for messages from popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'GET_PENDING_TASKS') {
    getPendingTasks().then(sendResponse);
    return true; // Async response
  }

  if (message.type === 'EXECUTE_TASK') {
    executeSubstackPost(message.data).then(() => sendResponse({ success: true }));
    return true;
  }

  if (message.type === 'CHECK_DAEMON') {
    fetch(`${CONFIG.DAEMON_URL}/health`)
      .then(r => r.json())
      .then(data => sendResponse({ connected: true, ...data }))
      .catch(() => sendResponse({ connected: false }));
    return true;
  }
});
```

### content.js

```javascript
// Content script for Substack pages
// Handles DOM manipulation for posting notes

(function() {
  console.log('[Consumed] Content script loaded on Substack');

  // Listen for messages from background script
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === 'POST_NOTE') {
      postNote(message.content, message.url)
        .then(result => sendResponse(result))
        .catch(error => sendResponse({ success: false, error: error.message }));
      return true; // Async response
    }
  });

  async function postNote(content, url) {
    // Wait for composer to be available
    const composer = await waitForElement(
      '[data-testid="note-composer"], .ProseMirror, [contenteditable="true"]',
      10000
    );

    if (!composer) {
      throw new Error('Note composer not found');
    }

    // Focus and clear
    composer.focus();

    // Insert content
    document.execCommand('selectAll', false, null);
    document.execCommand('insertText', false, content);

    // Add URL if not in content
    if (url && !content.includes(url)) {
      document.execCommand('insertText', false, `\n\n${url}`);
    }

    // Click post button
    const postButton = await waitForElement(
      '[data-testid="post-button"], button[type="submit"]',
      5000
    );

    if (!postButton) {
      throw new Error('Post button not found');
    }

    postButton.click();

    // Wait for success
    await new Promise(r => setTimeout(r, 3000));

    return { success: true };
  }

  function waitForElement(selector, timeout = 5000) {
    return new Promise((resolve) => {
      const element = document.querySelector(selector);
      if (element) {
        resolve(element);
        return;
      }

      const observer = new MutationObserver(() => {
        const element = document.querySelector(selector);
        if (element) {
          observer.disconnect();
          resolve(element);
        }
      });

      observer.observe(document.body, { childList: true, subtree: true });

      setTimeout(() => {
        observer.disconnect();
        resolve(null);
      }, timeout);
    });
  }
})();
```

### popup.html

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {
      width: 300px;
      padding: 16px;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      font-size: 14px;
    }

    h1 {
      font-size: 18px;
      margin: 0 0 16px 0;
    }

    .status {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 16px;
      padding: 8px;
      border-radius: 4px;
    }

    .status.connected {
      background: #d4edda;
      color: #155724;
    }

    .status.disconnected {
      background: #f8d7da;
      color: #721c24;
    }

    .status-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
    }

    .status.connected .status-dot {
      background: #28a745;
    }

    .status.disconnected .status-dot {
      background: #dc3545;
    }

    .tasks {
      margin-bottom: 16px;
    }

    .task {
      padding: 8px;
      border: 1px solid #ddd;
      border-radius: 4px;
      margin-bottom: 8px;
    }

    .task-type {
      font-weight: 600;
      font-size: 12px;
      color: #666;
    }

    .task-url {
      font-size: 12px;
      color: #333;
      word-break: break-all;
    }

    .task-status {
      font-size: 11px;
      color: #999;
    }

    .no-tasks {
      color: #666;
      font-style: italic;
    }

    button {
      width: 100%;
      padding: 8px;
      background: #007bff;
      color: white;
      border: none;
      border-radius: 4px;
      cursor: pointer;
    }

    button:hover {
      background: #0056b3;
    }

    button:disabled {
      background: #ccc;
      cursor: not-allowed;
    }
  </style>
</head>
<body>
  <h1>Consumed</h1>

  <div id="status" class="status">
    <span class="status-dot"></span>
    <span class="status-text">Checking...</span>
  </div>

  <div class="tasks">
    <h3>Pending Tasks</h3>
    <div id="task-list">
      <span class="no-tasks">Loading...</span>
    </div>
  </div>

  <button id="refresh">Refresh</button>

  <script src="popup.js"></script>
</body>
</html>
```

### popup.js

```javascript
document.addEventListener('DOMContentLoaded', async () => {
  await checkDaemonStatus();
  await loadPendingTasks();

  document.getElementById('refresh').addEventListener('click', async () => {
    await checkDaemonStatus();
    await loadPendingTasks();
  });
});

async function checkDaemonStatus() {
  const statusEl = document.getElementById('status');

  try {
    const response = await chrome.runtime.sendMessage({ type: 'CHECK_DAEMON' });

    if (response.connected) {
      statusEl.className = 'status connected';
      statusEl.querySelector('.status-text').textContent = `Connected (v${response.version || '?'})`;
    } else {
      throw new Error('Not connected');
    }
  } catch (error) {
    statusEl.className = 'status disconnected';
    statusEl.querySelector('.status-text').textContent = 'Daemon not running';
  }
}

async function loadPendingTasks() {
  const listEl = document.getElementById('task-list');

  try {
    const tasks = await chrome.runtime.sendMessage({ type: 'GET_PENDING_TASKS' });

    if (!tasks || tasks.length === 0) {
      listEl.innerHTML = '<span class="no-tasks">No pending tasks</span>';
      return;
    }

    listEl.innerHTML = tasks.map(task => `
      <div class="task">
        <div class="task-type">${task.task_type}</div>
        <div class="task-url">${task.payload?.url || 'No URL'}</div>
        <div class="task-status">Retries: ${task.retry_count}/${task.max_retries}</div>
      </div>
    `).join('');

  } catch (error) {
    listEl.innerHTML = '<span class="no-tasks">Error loading tasks</span>';
  }
}
```

---

## Part 2: Daemon Modifications

### File: consumed-daemon/src/server.rs

New endpoint `POST /bookmark` creates TWO parallel tasks: one for GitHub logging, one for Substack posting.

#### New Route

```rust
// In router setup
.route("/bookmark", post(bookmark_handler))
.route("/confirm-substack-post", post(confirm_substack_post_handler))
```

#### Request/Response Types

```rust
#[derive(Deserialize)]
struct BookmarkRequest {
    url: String,
    excerpt: Option<String>,
}

#[derive(Serialize)]
struct BookmarkResponse {
    success: bool,
    task_id: Option<String>,           // Substack task ID for confirmation
    url: Option<String>,
    title: Option<String>,
    author: Option<String>,
    content_type: Option<String>,
    excerpt: Option<String>,
    image_url: Option<String>,
    content: Option<String>,           // Generated recommendation
    error: Option<String>,
}

#[derive(Deserialize)]
struct ConfirmSubstackPostRequest {
    task_id: String,
    status: String,  // "completed" or "failed"
    error: Option<String>,
}
```

#### Handler Implementation

```rust
async fn bookmark_handler(
    State(state): State<Arc<ServerState>>,
    Json(request): Json<BookmarkRequest>,
) -> impl IntoResponse {
    let url = &request.url;
    let excerpt = request.excerpt.as_deref();

    // Step 1: Extract metadata using Rust
    let metadata = match consumed_core::metadata::extract(url) {
        Ok(entry) => entry,
        Err(e) => {
            return Json(BookmarkResponse {
                success: false,
                substack_task: None,
                github_task: None,
                metadata: None,
                error: Some(format!("Failed to extract metadata: {}", e)),
            });
        }
    };

    // Step 2: Generate recommendation via Python
    let python_input = serde_json::json!({
        "url": url,
        "title": &metadata.title,
        "author": &metadata.author,
        "content_type": metadata.content_type.to_string(),
        "excerpt": excerpt,
        "image_url": &metadata.image_url,
    });

    let generated = match generate_recommendation(&python_input).await {
        Ok(g) => g,
        Err(e) => {
            return Json(BookmarkResponse {
                success: false,
                substack_task: None,
                github_task: None,
                metadata: None,
                error: Some(format!("Failed to generate recommendation: {}", e)),
            });
        }
    };

    // Step 3: Create TWO tasks

    // Task 1: LogToGitHub (daemon executes in background)
    let github_task = state.task_queue.create_task(CreateTaskRequest {
        task_type: TaskType::LogToGitHub,
        payload: serde_json::json!({
            "url": url,
            "title": &metadata.title,
            "author": &metadata.author,
            "content_type": metadata.content_type.to_string(),
        }),
        scheduled_for: None,
        max_retries: 3,
    }).ok();

    // Task 2: PostSubstackNote (extension executes)
    // Full payload stored for retry capability
    let substack_task = state.task_queue.create_task(CreateTaskRequest {
        task_type: TaskType::PostSubstackNote,
        payload: serde_json::json!({
            "url": url,
            "title": &metadata.title,
            "author": &metadata.author,
            "content_type": metadata.content_type.to_string(),
            "excerpt": excerpt,
            "image_url": &metadata.image_url,
            "content": &generated.content,
        }),
        scheduled_for: None,
        max_retries: 3,
    }).ok();

    // Step 4: Execute GitHub task in background (don't block response)
    if let Some(ref task) = github_task {
        let task_id = task.id.clone();
        let state_clone = state.clone();
        tokio::spawn(async move {
            execute_github_task(&state_clone, &task_id).await;
        });
    }

    // Return flat response with task_id for confirmation
    Json(BookmarkResponse {
        success: true,
        task_id: substack_task.as_ref().map(|t| t.id.clone()),
        url: Some(url.to_string()),
        title: Some(metadata.title),
        author: metadata.author,
        content_type: Some(metadata.content_type.to_string()),
        excerpt: excerpt.map(|s| s.to_string()),
        image_url: metadata.image_url,
        content: Some(generated.content),
        error: None,
    })
}
```

#### Confirm Substack Post Handler

```rust
async fn confirm_substack_post_handler(
    State(state): State<Arc<ServerState>>,
    Json(request): Json<ConfirmSubstackPostRequest>,
) -> impl IntoResponse {
    let task_id = &request.task_id;

    match request.status.as_str() {
        "completed" => {
            // Mark task as completed and remove from queue
            let _ = state.task_queue.update_task(task_id, UpdateTaskRequest {
                status: Some(TaskStatus::Completed),
                ..Default::default()
            });
            Json(serde_json::json!({ "success": true }))
        }
        "failed" => {
            // Increment retry count, task stays in queue
            let _ = state.task_queue.increment_retry(task_id);
            let _ = state.task_queue.update_task(task_id, UpdateTaskRequest {
                error: request.error,
                ..Default::default()
            });
            Json(serde_json::json!({ "success": true, "will_retry": true }))
        }
        _ => {
            Json(serde_json::json!({ "success": false, "error": "Invalid status" }))
        }
    }
}
```

#### Background GitHub Task Executor

```rust
async fn execute_github_task(state: &Arc<ServerState>, task_id: &str) {
    let task = match state.task_queue.get_task(task_id) {
        Ok(Some(t)) => t,
        _ => return,
    };

    // Mark as running
    let _ = state.task_queue.update_task(task_id, UpdateTaskRequest {
        status: Some(TaskStatus::Running),
        ..Default::default()
    });

    // Execute GitHub commit
    let url = task.payload["url"].as_str().unwrap_or_default();
    let result = consumed_core::github::add_entry_to_github_with_date(url, None).await;

    match result {
        Ok(_) => {
            // Success - mark completed
            let _ = state.task_queue.update_task(task_id, UpdateTaskRequest {
                status: Some(TaskStatus::Completed),
                ..Default::default()
            });
        }
        Err(e) => {
            // Failure - increment retry, stays pending
            let _ = state.task_queue.increment_retry(task_id);
            let _ = state.task_queue.update_task(task_id, UpdateTaskRequest {
                error: Some(e.to_string()),
                ..Default::default()
            });
        }
    }
}
```

#### Python Recommendation Generator

```rust
struct GeneratedContent {
    content: String,
}

async fn generate_recommendation(payload: &serde_json::Value) -> Result<GeneratedContent, String> {
    let output = tokio::task::spawn_blocking({
        let payload_str = payload.to_string();
        move || {
            std::process::Command::new("uv")
                .args(["run", "python", "-m", "consumed.generate", &payload_str])
                .output()
        }
    })
    .await
    .map_err(|e| format!("Task join error: {}", e))?
    .map_err(|e| format!("Failed to spawn process: {}", e))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("Generation script failed: {}", stderr));
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    let parsed: serde_json::Value = serde_json::from_str(&stdout)
        .map_err(|e| format!("Failed to parse generation output: {}", e))?;

    Ok(GeneratedContent {
        content: parsed.get("content")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string(),
    })
}
```

---

## Part 3: Remote Server Implementation

### Technology Stack

- **Framework**: Rust with Axum (consistency with daemon) or Python with FastAPI
- **Database**: PostgreSQL
- **Hosting**: Shuttle.rs (already in use per Shuttle.toml)

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/sync` | Daemon syncs local tasks to cloud |
| GET | `/api/tasks` | Get tasks for a user/device |
| POST | `/api/tasks` | Create task (from extension if daemon offline) |
| PATCH | `/api/tasks/:id` | Update task status |
| DELETE | `/api/tasks/:id` | Delete task |
| POST | `/api/register` | Register device |
| POST | `/api/auth` | Authenticate user |

### Database Schema

```sql
-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Devices table (one user can have multiple devices)
CREATE TABLE devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    name VARCHAR(255),
    last_seen TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tasks table (cloud mirror of local tasks)
CREATE TABLE tasks (
    id UUID PRIMARY KEY,
    device_id UUID REFERENCES devices(id),
    task_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    payload JSONB NOT NULL,
    result JSONB,
    error TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    scheduled_for TIMESTAMP WITH TIME ZONE,
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    synced_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_tasks_device_status ON tasks(device_id, status);
CREATE INDEX idx_tasks_synced ON tasks(synced_at);
```

### Sync Protocol

```
DAEMON → SERVER (Push changes)
POST /api/sync
{
  "device_id": "uuid",
  "since": "2024-01-15T10:00:00Z",  // Last sync time
  "tasks": [
    { "id": "...", "status": "completed", "updated_at": "..." },
    { "id": "...", "status": "pending", "payload": {...}, "created_at": "..." }
  ]
}

SERVER → DAEMON (Pull changes from other devices)
Response:
{
  "tasks": [...],  // Tasks from other devices
  "sync_timestamp": "2024-01-15T10:05:00Z"
}
```

### Directory Structure

```
consumed-server/
├── src/
│   ├── main.rs
│   ├── routes/
│   │   ├── mod.rs
│   │   ├── auth.rs
│   │   ├── tasks.rs
│   │   └── sync.rs
│   ├── models/
│   │   ├── mod.rs
│   │   ├── user.rs
│   │   ├── device.rs
│   │   └── task.rs
│   └── db.rs
├── Cargo.toml
├── Shuttle.toml
└── migrations/
    └── 001_initial.sql
```

---

## Part 4: Existing Code Reference

### Key Files in consumed-daemon/

| File | Purpose | Relevant Functions |
|------|---------|-------------------|
| `src/server.rs` | HTTP endpoints | `create_task_handler`, `get_pending_tasks_handler`, `update_task_handler` |
| `src/tasks.rs` | Task queue logic | `TaskQueue`, `Task`, `TaskType`, `TaskStatus` |
| `src/config.rs` | Configuration | `Config`, `ConfigState` |
| `src/cookies.rs` | Browser state | `import_browser_state`, `BrowserStateRequest` |

### Key Files in python/consumed/

| File | Purpose |
|------|---------|
| `generate.py` | LLM-based recommendation generation (`create_recommendation`) |
| `llm_extract.py` | Metadata extraction with Claude |
| `post.py` | Playwright-based Substack posting |

### create_recommendation Function

**Location**: `python/consumed/generate.py`

**Purpose**: Takes metadata + optional highlighted text and uses Claude to generate a recommendation post.

**CLI Usage**:
```bash
uv run python -m consumed.generate '{"url": "...", "title": "...", "excerpt": "..."}'
```

**Input JSON** (from extension):
```json
{
  "url": "https://example.com/article",      // required
  "excerpt": "Selected passage..."   // optional - from user selection
}
```

**Input JSON** (with metadata, if available):
```json
{
  "url": "https://example.com/article",      // required
  "title": "Article Title",                   // optional
  "authors": "Author Name",                   // optional
  "contentType": "article",                   // optional
  "excerpt": "Selected passage..."   // optional
}
```

**Output JSON**:
```json
{
  "content": "Generated recommendation text...\n\nhttps://example.com/article",
  "url": "https://example.com/article",
  "title": "Article Title",
  "highlight": "Selected passage..."
}
```

**Daemon Integration** (in server.rs):
```rust
async fn generate_recommendation(payload: &serde_json::Value) -> Result<String, String> {
    let input = serde_json::json!({
        "url": payload.get("url"),
        "title": payload.get("title"),
        "authors": payload.get("authors"),
        "content_type": payload.get("content_type"),
        "excerpt": payload.get("excerpt"),
    });

    let output = tokio::task::spawn_blocking({
        let input_str = input.to_string();
        move || {
            std::process::Command::new("uv")
                .args(["run", "python", "-m", "consumed.generate", &input_str])
                .output()
        }
    })
    .await
    .map_err(|e| format!("Task join error: {}", e))?
    .map_err(|e| format!("Failed to spawn process: {}", e))?;

    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).to_string());
    }

    Ok(String::from_utf8_lossy(&output.stdout).to_string())
}
```

### Task Types (tasks.rs)

```rust
pub enum TaskType {
    PostSubstackNote,  // Post to Substack notes (extension executes)
    LogToGitHub,       // Commit entry to GitHub diary (daemon executes)
    PostTweet,         // Post to Twitter/X
    ScrollTwitter,     // Browse Twitter
}
```

### Task Payloads

**PostSubstackNote payload** (full data for retry):
```json
{
  "url": "https://example.com/article",
  "title": "Article Title",
  "author": "Author Name",
  "content_type": "article",
  "excerpt": "User-selected text from page",
  "image_url": "https://example.com/og-image.jpg",
  "content": "Generated recommendation text ready to post..."
}
```

**LogToGitHub payload**:
```json
{
  "url": "https://example.com/article",
  "title": "Article Title",
  "author": "Author Name",
  "content_type": "article"
}
```

### Task Statuses (tasks.rs)

```rust
pub enum TaskStatus {
    Pending,      // Ready to execute
    Running,      // Currently executing
    Completed,    // Successfully finished
    Failed,       // Failed after max retries
    AuthRequired, // Needs authentication
}
```

---

## Implementation Order

1. **Phase 1**: Modify daemon `create_task_handler` to generate LLM content
2. **Phase 2**: Build Chrome extension core (manifest, background.js)
3. **Phase 3**: Build Chrome extension UI (popup)
4. **Phase 4**: Build Substack content script automation
5. **Phase 5**: Test end-to-end flow
6. **Phase 6**: Build remote server (optional, for multi-device)

---

## Testing Checklist

### Daemon LLM Integration
- [ ] `POST /tasks` with `PostSubstackNote` returns task with `generated_content`
- [ ] LLM generation handles errors gracefully
- [ ] Task is stored with enriched payload

### Chrome Extension
- [ ] Extension loads without errors
- [ ] Bookmark creation triggers `POST /tasks`
- [ ] Extension receives task with content
- [ ] Pending tasks shown in popup
- [ ] Daemon connection status shown

### Substack Automation
- [ ] Extension opens Substack notes tab
- [ ] Content is inserted into composer
- [ ] Post button is clicked
- [ ] Success is detected and reported
- [ ] Failure is detected and reported

### Retry Flow
- [ ] Failed task remains in queue
- [ ] `retry_count` increments
- [ ] Task retried on extension startup
- [ ] Task marked `Failed` after max retries

---

## Environment Variables

### Daemon
```
GITHUB_TOKEN=<token>        # For diary logging
GITHUB_REPO=owner/repo      # Target repository
ANTHROPIC_API_KEY=<key>     # For LLM generation
```

### Remote Server
```
DATABASE_URL=postgres://...
JWT_SECRET=<secret>
```
