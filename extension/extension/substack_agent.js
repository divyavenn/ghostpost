// Substack AI Agent - Content Script
// Executes actions determined by AI analysis of the page

// Execute a single action on the page
async function executeAction(action) {
  console.log('[Substack Agent] Executing action:', action);

  switch (action.action) {
    case 'click': {
      const element = document.querySelector(action.selector);
      if (!element) {
        return { success: false, error: `Element not found: ${action.selector}` };
      }
      element.click();
      return { success: true };
    }

    case 'type': {
      const element = document.querySelector(action.selector);
      if (!element) {
        return { success: false, error: `Element not found: ${action.selector}` };
      }

      element.focus();

      // Handle contenteditable elements (like ProseMirror)
      if (element.getAttribute('contenteditable') === 'true' || element.classList.contains('ProseMirror')) {
        // Clear existing content
        element.innerHTML = '';

        // Use execCommand for better compatibility with rich text editors
        document.execCommand('insertText', false, action.text);

        // Also dispatch input event
        element.dispatchEvent(new InputEvent('input', {
          bubbles: true,
          cancelable: true,
          inputType: 'insertText',
          data: action.text,
        }));
      } else if (element.tagName === 'TEXTAREA' || element.tagName === 'INPUT') {
        element.value = action.text;
        element.dispatchEvent(new Event('input', { bubbles: true }));
      } else {
        // Try setting textContent as fallback
        element.textContent = action.text;
        element.dispatchEvent(new Event('input', { bubbles: true }));
      }

      return { success: true };
    }

    case 'wait': {
      await new Promise(r => setTimeout(r, action.ms || 1000));
      return { success: true };
    }

    case 'done': {
      return { success: action.success, done: true, error: action.error };
    }

    default:
      return { success: false, error: `Unknown action: ${action.action}` };
  }
}

// Get simplified DOM snapshot for AI analysis
function getDOMSnapshot() {
  // Clone the body to manipulate without affecting the page
  const clone = document.body.cloneNode(true);

  // Remove non-essential elements
  const removeSelectors = ['script', 'style', 'svg', 'noscript', 'iframe', 'link', 'meta', 'img'];
  removeSelectors.forEach(sel => {
    clone.querySelectorAll(sel).forEach(el => el.remove());
  });

  // Simplify the DOM to reduce tokens
  function simplify(el, depth = 0) {
    if (depth > 5) return '';
    if (el.nodeType === Node.TEXT_NODE) {
      const text = el.textContent.trim();
      return text.length > 0 && text.length < 100 ? text : '';
    }
    if (el.nodeType !== Node.ELEMENT_NODE) return '';

    const tag = el.tagName.toLowerCase();

    // Skip hidden elements
    const style = window.getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden') return '';

    // Build attributes string (only useful ones)
    const attrs = [];
    const usefulAttrs = ['id', 'class', 'type', 'placeholder', 'aria-label', 'data-testid', 'role', 'contenteditable', 'name', 'disabled'];
    usefulAttrs.forEach(attr => {
      let val = el.getAttribute(attr);
      if (val) {
        // Truncate long class names but keep important ones
        if (attr === 'class' && val.length > 80) {
          val = val.substring(0, 80) + '...';
        }
        attrs.push(`${attr}="${val}"`);
      }
    });

    const attrStr = attrs.length > 0 ? ' ' + attrs.join(' ') : '';
    const indent = '  '.repeat(depth);

    // For interactive elements, always include them
    const isInteractive = ['button', 'input', 'textarea', 'a', 'select'].includes(tag) ||
      el.getAttribute('contenteditable') === 'true' ||
      el.getAttribute('role') === 'textbox' ||
      el.getAttribute('role') === 'button';

    // Get text content for buttons/links
    const directText = Array.from(el.childNodes)
      .filter(n => n.nodeType === Node.TEXT_NODE)
      .map(n => n.textContent.trim())
      .join(' ')
      .substring(0, 50);

    // Get children
    const children = Array.from(el.children)
      .map(child => simplify(child, depth + 1))
      .filter(s => s.length > 0)
      .join('\n');

    // Self-closing elements
    if (['input', 'br', 'hr'].includes(tag)) {
      return `${indent}<${tag}${attrStr} />`;
    }

    // Interactive elements - always show
    if (isInteractive) {
      if (children) {
        return `${indent}<${tag}${attrStr}>\n${children}\n${indent}</${tag}>`;
      }
      return `${indent}<${tag}${attrStr}>${directText}</${tag}>`;
    }

    // Container elements with children
    if (children) {
      // Skip wrapper divs without useful attributes
      if (tag === 'div' && !attrStr && depth < 3) {
        return children;
      }
      return `${indent}<${tag}${attrStr}>\n${children}\n${indent}</${tag}>`;
    }

    // Skip empty non-interactive elements
    return '';
  }

  return simplify(clone);
}

// Check if user appears to be logged in
function checkLoginState() {
  // Look for signs of being logged in
  const loggedInIndicators = [
    // User menu/avatar
    'img[alt*="profile" i]',
    'img[alt*="avatar" i]',
    '[data-testid="user-menu"]',
    // Compose button (only visible when logged in)
    'button[aria-label*="compose" i]',
    '[data-testid="compose-button"]',
    // Any contenteditable (note input)
    '[contenteditable="true"]',
  ];

  for (const selector of loggedInIndicators) {
    if (document.querySelector(selector)) {
      return { loggedIn: true };
    }
  }

  // Look for login buttons (indicates NOT logged in)
  const buttons = document.querySelectorAll('button, a');
  for (const btn of buttons) {
    const text = btn.textContent?.toLowerCase() || '';
    if (text.includes('sign in') || text.includes('log in') || text.includes('get started')) {
      return { loggedIn: false };
    }
  }

  // Default to logged in if we can't tell
  return { loggedIn: true };
}

// Listen for messages from service worker
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'substack-agent') {
    (async () => {
      try {
        switch (message.action) {
          case 'checkLogin':
            sendResponse(checkLoginState());
            break;

          case 'getDOMSnapshot':
            const snapshot = getDOMSnapshot();
            sendResponse({ success: true, snapshot });
            break;

          case 'executeAction':
            const result = await executeAction(message.data);
            sendResponse(result);
            break;

          default:
            sendResponse({ success: false, error: 'Unknown action' });
        }
      } catch (error) {
        sendResponse({ success: false, error: error.message });
      }
    })();
    return true; // Keep channel open for async response
  }
});

console.log('[Substack Agent] AI-powered content script loaded');
