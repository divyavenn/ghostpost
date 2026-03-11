// Chrome DevTools Protocol Tools for Browser Agent
// Provides reliable browser automation via CDP

export class CDPTools {
  constructor(tabId) {
    this.tabId = tabId;
    this.attached = false;
  }

  // Attach debugger to tab
  async attach() {
    if (this.attached) return;

    try {
      await chrome.debugger.attach({ tabId: this.tabId }, '1.3');
      this.attached = true;
      console.log('[CDP] Attached to tab', this.tabId);

      // Enable required domains
      await this.send('Runtime.enable');
      await this.send('DOM.enable');
      await this.send('Page.enable');
      console.log('[CDP] Domains enabled');
    } catch (error) {
      // Already attached or other error
      if (error.message?.includes('Already attached')) {
        this.attached = true;
        // Still try to enable domains
        try {
          await this.send('Runtime.enable');
          await this.send('DOM.enable');
          await this.send('Page.enable');
        } catch {}
      } else {
        throw error;
      }
    }
  }

  // Detach debugger
  async detach() {
    if (!this.attached) return;

    try {
      await chrome.debugger.detach({ tabId: this.tabId });
      this.attached = false;
      console.log('[CDP] Detached from tab', this.tabId);
    } catch (error) {
      console.warn('[CDP] Detach error:', error);
    }
  }

  // Send CDP command
  async send(method, params = {}) {
    await this.attach();
    return new Promise((resolve, reject) => {
      chrome.debugger.sendCommand(
        { tabId: this.tabId },
        method,
        params,
        (result) => {
          if (chrome.runtime.lastError) {
            reject(new Error(chrome.runtime.lastError.message));
          } else {
            resolve(result);
          }
        }
      );
    });
  }

  // ============ DOM Tools ============

  // Get the full DOM as a string
  async getDOM() {
    const { root } = await this.send('DOM.getDocument', { depth: -1 });
    const { outerHTML } = await this.send('DOM.getOuterHTML', { nodeId: root.nodeId });
    return outerHTML;
  }

  // Get simplified DOM snapshot for AI
  async getDOMSnapshot() {
    // Use DOMSnapshot for a more structured view
    const result = await this.send('DOMSnapshot.captureSnapshot', {
      computedStyles: ['display', 'visibility'],
      includeDOMRects: true,
    });

    return this.simplifySnapshot(result);
  }

  // Simplify DOM snapshot for AI consumption
  simplifySnapshot(snapshot) {
    const { documents, strings } = snapshot;
    if (!documents || documents.length === 0) return '';

    const doc = documents[0];
    const nodes = doc.nodes;
    const layout = doc.layout;

    const output = [];
    const getString = (idx) => (idx >= 0 && idx < strings.length) ? strings[idx] : '';

    // Build a simplified representation
    for (let i = 0; i < nodes.nodeName.length; i++) {
      const nodeName = getString(nodes.nodeName[i]).toLowerCase();

      // Skip non-element nodes and hidden elements
      if (!nodeName || nodeName === '#text' || nodeName === '#comment') continue;
      if (['script', 'style', 'noscript', 'svg', 'path'].includes(nodeName)) continue;

      // Get attributes
      const attrs = {};
      const attrNames = nodes.attributes[i]?.name || [];
      const attrValues = nodes.attributes[i]?.value || [];

      // Handle the flat array format [name1, value1, name2, value2, ...]
      if (nodes.attributes[i]) {
        const flatAttrs = nodes.attributes[i];
        for (let j = 0; j < flatAttrs.length; j += 2) {
          const name = getString(flatAttrs[j]);
          const value = getString(flatAttrs[j + 1]);
          if (name && ['id', 'class', 'type', 'placeholder', 'aria-label', 'data-testid', 'role', 'contenteditable', 'name', 'href', 'value'].includes(name)) {
            attrs[name] = value.length > 60 ? value.substring(0, 60) + '...' : value;
          }
        }
      }

      // Get text content
      const textValue = nodes.nodeValue ? getString(nodes.nodeValue[i]) : '';

      // Check if interactive
      const isInteractive = ['button', 'input', 'textarea', 'a', 'select'].includes(nodeName) ||
        attrs.contenteditable === 'true' ||
        attrs.role === 'button' ||
        attrs.role === 'textbox';

      // Only include elements with attributes or that are interactive
      if (Object.keys(attrs).length > 0 || isInteractive || textValue.trim()) {
        const attrStr = Object.entries(attrs).map(([k, v]) => `${k}="${v}"`).join(' ');
        const text = textValue.trim().substring(0, 50);
        output.push(`<${nodeName}${attrStr ? ' ' + attrStr : ''}>${text}</${nodeName}>`);
      }
    }

    return output.join('\n');
  }

  // Find element by selector and return its node info
  async querySelector(selector) {
    const { root } = await this.send('DOM.getDocument');
    try {
      const { nodeId } = await this.send('DOM.querySelector', {
        nodeId: root.nodeId,
        selector: selector,
      });
      return nodeId > 0 ? nodeId : null;
    } catch {
      return null;
    }
  }

  // Get element bounding box for clicking
  async getBoundingBox(selector) {
    const nodeId = await this.querySelector(selector);
    if (!nodeId) return null;

    try {
      const { model } = await this.send('DOM.getBoxModel', { nodeId });
      if (!model) return null;

      // content quad: [x1,y1, x2,y2, x3,y3, x4,y4]
      const quad = model.content;
      return {
        x: quad[0],
        y: quad[1],
        width: quad[2] - quad[0],
        height: quad[5] - quad[1],
        centerX: (quad[0] + quad[2]) / 2,
        centerY: (quad[1] + quad[5]) / 2,
      };
    } catch {
      return null;
    }
  }

  // ============ Input Tools ============

  // Click at coordinates
  async clickAt(x, y) {
    // Mouse down
    await this.send('Input.dispatchMouseEvent', {
      type: 'mousePressed',
      x, y,
      button: 'left',
      clickCount: 1,
    });

    // Mouse up
    await this.send('Input.dispatchMouseEvent', {
      type: 'mouseReleased',
      x, y,
      button: 'left',
      clickCount: 1,
    });
  }

  // Click on element by selector (uses JS click for reliability)
  async click(selector) {
    const result = await this.evaluate(`
      (function() {
        const el = document.querySelector('${selector.replace(/'/g, "\\'")}');
        if (!el) return { found: false };
        el.scrollIntoView({ behavior: 'instant', block: 'center' });
        el.focus();
        el.click();
        return { found: true, tag: el.tagName, text: el.textContent?.substring(0, 30) };
      })()
    `);

    if (!result.success || !result.value?.found) {
      return { success: false, error: `Element not found: ${selector}` };
    }

    console.log(`[CDP] Clicked ${selector} (${result.value.tag}: "${result.value.text}")`);
    return { success: true };
  }

  // Click using CDP mouse events (for cases where JS click doesn't work)
  async clickWithMouse(selector) {
    // First scroll element into view
    const scrollResult = await this.evaluate(`
      (function() {
        const el = document.querySelector('${selector.replace(/'/g, "\\'")}');
        if (!el) return { found: false };
        el.scrollIntoView({ behavior: 'instant', block: 'center' });
        return { found: true };
      })()
    `);

    if (!scrollResult.success || !scrollResult.value?.found) {
      return { success: false, error: `Element not found: ${selector}` };
    }

    await new Promise(r => setTimeout(r, 100));

    const box = await this.getBoundingBox(selector);
    if (!box) {
      return { success: false, error: `Could not get bounds: ${selector}` };
    }

    console.log(`[CDP] Mouse clicking ${selector} at (${box.centerX}, ${box.centerY})`);
    await this.clickAt(box.centerX, box.centerY);
    return { success: true };
  }

  // Type text (character by character for better compatibility)
  async type(text) {
    for (const char of text) {
      if (char === '\n') {
        // Handle newlines by pressing Enter
        await this.send('Input.dispatchKeyEvent', {
          type: 'keyDown',
          key: 'Enter',
          code: 'Enter',
          windowsVirtualKeyCode: 13,
          nativeVirtualKeyCode: 13,
        });
        await this.send('Input.dispatchKeyEvent', {
          type: 'keyUp',
          key: 'Enter',
          code: 'Enter',
          windowsVirtualKeyCode: 13,
          nativeVirtualKeyCode: 13,
        });
      } else {
        await this.send('Input.dispatchKeyEvent', {
          type: 'keyDown',
          text: char,
        });
        await this.send('Input.dispatchKeyEvent', {
          type: 'keyUp',
          text: char,
        });
      }
      // Small delay between characters
      await new Promise(r => setTimeout(r, 30));
    }
    return { success: true };
  }

  // Type into a specific element
  async typeInto(selector, text) {
    // First click to focus
    const clickResult = await this.click(selector);
    if (!clickResult.success) return clickResult;

    // Wait a bit for focus
    await new Promise(r => setTimeout(r, 100));

    // Clear existing content (select all + delete)
    await this.send('Input.dispatchKeyEvent', {
      type: 'keyDown',
      key: 'a',
      modifiers: 2, // Ctrl/Cmd
    });
    await this.send('Input.dispatchKeyEvent', {
      type: 'keyUp',
      key: 'a',
      modifiers: 2,
    });
    await this.send('Input.dispatchKeyEvent', {
      type: 'keyDown',
      key: 'Backspace',
    });
    await this.send('Input.dispatchKeyEvent', {
      type: 'keyUp',
      key: 'Backspace',
    });

    // Type the new text
    await this.type(text);
    return { success: true };
  }

  // Press a special key (with optional modifiers: 1=Alt, 2=Ctrl, 4=Meta/Cmd, 8=Shift)
  async pressKey(key, options = {}) {
    const modifiers = options.modifiers || 0;
    await this.send('Input.dispatchKeyEvent', {
      type: 'keyDown',
      key: key,
      modifiers: modifiers,
    });
    await this.send('Input.dispatchKeyEvent', {
      type: 'keyUp',
      key: key,
      modifiers: modifiers,
    });
    return { success: true };
  }

  // Select all text in the focused element (Ctrl/Cmd+A)
  async selectAll() {
    // Use Meta (Cmd) on Mac, Ctrl on others - CDP uses modifiers bitmask
    // 2 = Ctrl, 4 = Meta/Cmd. We'll send both for cross-platform compatibility.
    await this.send('Input.dispatchKeyEvent', {
      type: 'keyDown',
      key: 'a',
      code: 'KeyA',
      modifiers: 2, // Ctrl
    });
    await this.send('Input.dispatchKeyEvent', {
      type: 'keyUp',
      key: 'a',
      code: 'KeyA',
      modifiers: 2,
    });
    return { success: true };
  }

  // ============ Navigation Tools ============

  // Navigate to URL
  async navigate(url) {
    await this.send('Page.navigate', { url });
    return { success: true };
  }

  // Wait for navigation to complete
  async waitForNavigation(timeout = 30000) {
    return new Promise((resolve) => {
      const start = Date.now();
      const check = async () => {
        try {
          const { result } = await this.send('Runtime.evaluate', {
            expression: 'document.readyState',
          });
          if (result.value === 'complete') {
            resolve({ success: true });
          } else if (Date.now() - start > timeout) {
            resolve({ success: false, error: 'Navigation timeout' });
          } else {
            setTimeout(check, 100);
          }
        } catch {
          setTimeout(check, 100);
        }
      };
      check();
    });
  }

  // ============ JavaScript Execution ============

  // Execute JavaScript in page context
  async evaluate(expression) {
    const { result, exceptionDetails } = await this.send('Runtime.evaluate', {
      expression,
      returnByValue: true,
    });

    if (exceptionDetails) {
      return { success: false, error: exceptionDetails.text };
    }

    return { success: true, value: result.value };
  }

  // ============ Screenshot Tools ============

  // Take a screenshot
  async screenshot(options = {}) {
    const result = await this.send('Page.captureScreenshot', {
      format: options.format || 'png',
      quality: options.quality || 80,
      ...options,
    });
    return result.data; // Base64 encoded
  }

  // ============ Scroll Tools ============

  // Scroll to element
  async scrollToElement(selector) {
    const result = await this.evaluate(`
      const el = document.querySelector('${selector}');
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        true;
      } else {
        false;
      }
    `);

    if (result.value === false) {
      return { success: false, error: `Element not found: ${selector}` };
    }
    return { success: true };
  }

  // Scroll by pixels
  async scrollBy(x, y) {
    await this.evaluate(`window.scrollBy(${x}, ${y})`);
    return { success: true };
  }
}

// Tool definitions for the AI agent
export const CDP_TOOL_DEFINITIONS = [
  {
    name: 'click',
    description: 'Click on an element by CSS selector',
    parameters: {
      selector: 'CSS selector of the element to click',
    },
  },
  {
    name: 'type',
    description: 'Type text into the currently focused element',
    parameters: {
      text: 'The text to type',
    },
  },
  {
    name: 'typeInto',
    description: 'Click on an element and type text into it (clears existing content)',
    parameters: {
      selector: 'CSS selector of the input element',
      text: 'The text to type',
    },
  },
  {
    name: 'pressKey',
    description: 'Press a special key (Enter, Tab, Escape, etc.)',
    parameters: {
      key: 'The key to press',
    },
  },
  {
    name: 'scroll',
    description: 'Scroll the page or to an element',
    parameters: {
      selector: 'Optional CSS selector to scroll to, or omit to scroll down',
      y: 'Pixels to scroll vertically (positive = down)',
    },
  },
  {
    name: 'screenshot',
    description: 'Take a screenshot of the current page',
    parameters: {},
  },
  {
    name: 'evaluate',
    description: 'Execute JavaScript code in the page',
    parameters: {
      expression: 'JavaScript code to execute',
    },
  },
  {
    name: 'done',
    description: 'Signal that the task is complete',
    parameters: {
      success: 'Whether the task was successful',
      message: 'Description of result or error',
    },
  },
];
