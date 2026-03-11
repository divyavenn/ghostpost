// Generic Browser Agent Content Script
// Handles DOM snapshots and action execution for the AI agent

(function() {
  // Prevent double-injection
  if (window.__browserAgentLoaded) return;
  window.__browserAgentLoaded = true;

  console.log('[Agent] Content script loaded on', window.location.href);

  // Get simplified DOM snapshot for AI analysis
  function getDOMSnapshot() {
    function simplify(el, depth = 0) {
      if (depth > 6) return '';

      if (el.nodeType === Node.TEXT_NODE) {
        const text = el.textContent.trim();
        return text.length > 0 && text.length < 100 ? text : '';
      }

      if (el.nodeType !== Node.ELEMENT_NODE) return '';

      const tag = el.tagName.toLowerCase();

      // Skip hidden and non-visual elements
      try {
        const style = window.getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
          return '';
        }
      } catch (e) {}

      // Skip non-essential elements
      if (['script', 'style', 'noscript', 'svg', 'path', 'img', 'video', 'audio', 'canvas', 'iframe'].includes(tag)) {
        return '';
      }

      // Build attributes (only useful ones)
      const attrs = [];
      const keep = ['id', 'class', 'type', 'placeholder', 'aria-label', 'data-testid', 'role', 'contenteditable', 'name', 'disabled', 'value', 'href'];

      for (const attr of keep) {
        let val = el.getAttribute(attr);
        if (val) {
          // Truncate long values
          if (val.length > 60) val = val.substring(0, 60) + '...';
          attrs.push(`${attr}="${val}"`);
        }
      }

      const attrStr = attrs.length ? ' ' + attrs.join(' ') : '';
      const indent = '  '.repeat(depth);

      // Check if interactive
      const isInteractive =
        ['button', 'input', 'textarea', 'a', 'select', 'label'].includes(tag) ||
        el.getAttribute('contenteditable') === 'true' ||
        el.getAttribute('role') === 'button' ||
        el.getAttribute('role') === 'textbox' ||
        el.getAttribute('role') === 'link' ||
        el.onclick !== null;

      // Get direct text content
      const directText = Array.from(el.childNodes)
        .filter(n => n.nodeType === Node.TEXT_NODE)
        .map(n => n.textContent.trim())
        .filter(t => t.length > 0)
        .join(' ')
        .substring(0, 50);

      // Get children
      const children = Array.from(el.children)
        .map(child => simplify(child, depth + 1))
        .filter(s => s.length > 0)
        .join('\n');

      // Self-closing tags
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

      // Containers with content
      if (children) {
        // Skip meaningless wrappers
        if (tag === 'div' && !attrStr) {
          return children;
        }
        return `${indent}<${tag}${attrStr}>\n${children}\n${indent}</${tag}>`;
      }

      // Keep elements with meaningful text
      if (directText && attrStr) {
        return `${indent}<${tag}${attrStr}>${directText}</${tag}>`;
      }

      return '';
    }

    return simplify(document.body);
  }

  // Execute an action on the page
  async function executeAction(action) {
    console.log('[Agent] Executing:', action);

    switch (action.action) {
      case 'click': {
        const el = document.querySelector(action.selector);
        if (!el) {
          return { success: false, error: `Element not found: ${action.selector}` };
        }
        el.scrollIntoView({ behavior: 'instant', block: 'center' });
        el.focus();
        el.click();
        return { success: true };
      }

      case 'type': {
        const el = document.querySelector(action.selector);
        if (!el) {
          return { success: false, error: `Element not found: ${action.selector}` };
        }

        el.scrollIntoView({ behavior: 'instant', block: 'center' });
        el.focus();

        // Small delay after focus
        await new Promise(r => setTimeout(r, 100));

        if (el.getAttribute('contenteditable') === 'true') {
          // Rich text editor (ProseMirror, etc.)
          el.innerHTML = '';

          // Try execCommand first
          const success = document.execCommand('insertText', false, action.text);

          if (!success) {
            // Fallback: set textContent
            el.textContent = action.text;
          }

          // Dispatch events
          el.dispatchEvent(new InputEvent('input', {
            bubbles: true,
            cancelable: true,
            inputType: 'insertText',
            data: action.text,
          }));
          el.dispatchEvent(new Event('change', { bubbles: true }));

        } else if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
          el.value = action.text;
          el.dispatchEvent(new Event('input', { bubbles: true }));
          el.dispatchEvent(new Event('change', { bubbles: true }));
        } else {
          el.textContent = action.text;
          el.dispatchEvent(new Event('input', { bubbles: true }));
        }

        return { success: true };
      }

      case 'wait': {
        await new Promise(r => setTimeout(r, action.ms || 1000));
        return { success: true };
      }

      case 'scroll': {
        const el = action.selector ? document.querySelector(action.selector) : window;
        if (action.selector && !el) {
          return { success: false, error: `Element not found: ${action.selector}` };
        }
        if (el === window) {
          window.scrollBy(0, action.y || 300);
        } else {
          el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
        return { success: true };
      }

      default:
        return { success: false, error: `Unknown action: ${action.action}` };
    }
  }

  // Listen for messages
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    // Handle both 'browser-agent' and 'substack-agent' for backwards compatibility
    if (message.type === 'browser-agent' || message.type === 'substack-agent') {
      (async () => {
        try {
          switch (message.action) {
            case 'getDOMSnapshot':
              const snapshot = getDOMSnapshot();
              sendResponse({ success: true, snapshot });
              break;

            case 'executeAction':
              const result = await executeAction(message.data);
              sendResponse(result);
              break;

            case 'checkLogin':
              // Generic login check - look for login/signin buttons
              const loginButtons = document.querySelectorAll('a, button');
              let loggedIn = true;
              for (const btn of loginButtons) {
                const text = btn.textContent?.toLowerCase() || '';
                if (text.includes('sign in') || text.includes('log in') || text === 'login') {
                  loggedIn = false;
                  break;
                }
              }
              sendResponse({ loggedIn });
              break;

            default:
              sendResponse({ success: false, error: `Unknown action: ${message.action}` });
          }
        } catch (error) {
          console.error('[Agent] Error:', error);
          sendResponse({ success: false, error: error.message });
        }
      })();
      return true; // Keep channel open
    }
  });
})();
