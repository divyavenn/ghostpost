  // AI Browser Agent with Chrome DevTools Protocol
// Loops: Screenshot/DOM → AI decision → Execute CDP tool → Repeat

import { CDPTools, CDP_TOOL_DEFINITIONS } from './cdp-tools.js';

const CLAUDE_API_URL = 'https://api.anthropic.com/v1/messages';

export class BrowserAgent {
  constructor(apiKey, options = {}) {
    this.apiKey = apiKey;
    this.maxSteps = options.maxSteps || 15;
    this.stepDelay = options.stepDelay || 1000;
    this.model = options.model || 'claude-sonnet-4-20250514';
    this.verbose = options.verbose ?? true;
    // Screenshot modes: false = DOM only, true = screenshots only, 'hybrid' = DOM + screenshot on failure
    this.useScreenshots = options.useScreenshots ?? 'hybrid';
    this.consecutiveFailures = 0;
  }

  log(...args) {
    if (this.verbose) {
      console.log('[BrowserAgent]', ...args);
    }
  }

  // Main agent loop
  async run(tabId, task) {
    this.log('Starting task:', task);
    this.log('Tab ID:', tabId);
    this.consecutiveFailures = 0; // Reset failure counter

    // Initialize CDP tools
    const cdp = new CDPTools(tabId);

    try {
      await cdp.attach();
      this.log('CDP attached');

      const history = [];

      for (let step = 1; step <= this.maxSteps; step++) {
        this.log(`\n=== Step ${step}/${this.maxSteps} ===`);

        // 1. Get current page state
        let pageState;
        try {
          const dom = await this.getSimplifiedDOM(cdp);

          if (this.useScreenshots === true) {
            // Screenshot only mode
            const screenshot = await cdp.screenshot();
            pageState = { type: 'screenshot', data: screenshot };
          } else if (this.useScreenshots === 'hybrid' && this.consecutiveFailures >= 2) {
            // Hybrid mode: include screenshot after failures
            const screenshot = await cdp.screenshot();
            pageState = { type: 'hybrid', dom, screenshot };
            this.log('Using hybrid mode (DOM + screenshot) after failures');
          } else {
            // DOM only mode
            pageState = { type: 'dom', data: dom };
          }
        } catch (error) {
          this.log('Failed to get page state:', error.message);
          await this.sleep(this.stepDelay);
          continue;
        }

        this.log('Page state:', pageState.type, pageState.type === 'dom' ? `${pageState.data.length} chars` : 'screenshot');

        // 2. Ask AI what to do next
        let action;
        try {
          action = await this.getNextAction(task, pageState, history);
        } catch (error) {
          this.log('AI error:', error.message);
          return { success: false, error: `AI error: ${error.message}`, steps: history };
        }

        this.log('AI chose tool:', action.tool, action.input);
        history.push({ step, tool: action.tool, input: action.input });

        // 3. Check if task is complete
        if (action.tool === 'done') {
          const success = action.input?.success ?? false;
          const message = action.input?.message ?? '';
          this.log('Task finished:', success ? 'SUCCESS' : 'FAILED', message);

          await cdp.detach();
          return { success, message, steps: history };
        }

        // 4. Execute the action via CDP
        const result = await this.executeAction(cdp, action);
        this.log('Action result:', result);

        // Handle done tool result
        if (result.done) {
          await cdp.detach();
          return { success: result.taskSuccess, message: result.message, steps: history };
        }

        if (!result.success) {
          history[history.length - 1].failed = true;
          history[history.length - 1].error = result.error;
          this.consecutiveFailures++;
          this.log('Action failed:', result.error, `(${this.consecutiveFailures} consecutive failures)`);
        } else {
          this.consecutiveFailures = 0;
        }

        // 5. Wait before next iteration
        await this.sleep(this.stepDelay);
      }

      // Max steps reached
      await cdp.detach();
      this.log('Max steps reached');
      return {
        success: false,
        error: 'max_steps_exceeded',
        message: `Task not completed after ${this.maxSteps} steps`,
        steps: history,
      };

    } catch (error) {
      this.log('Fatal error:', error);
      try { await cdp.detach(); } catch {}
      return { success: false, error: error.message, steps: [] };
    }
  }

  // Get DOM snapshot with full element details for AI to identify selectors
  async getSimplifiedDOM(cdp) {
    this.log('Getting DOM snapshot via CDP...');

    const result = await cdp.evaluate(`
      (function() {
        const elements = [];

        // Find all interactive and important elements
        const selectors = [
          'button',
          'a[href]',
          'input',
          'textarea',
          '[contenteditable="true"]',
          '[role="button"]',
          '[role="textbox"]',
          '[role="dialog"]',
          '[data-testid]',
          '[placeholder]',
          '[aria-label]',
          'form',
          '[class*="composer"]',
          '[class*="modal"]',
          '[class*="input"]',
          '[class*="editor"]'
        ];

        const found = document.querySelectorAll(selectors.join(', '));
        const seen = new Set();

        found.forEach((el) => {
          // Skip hidden elements
          const rect = el.getBoundingClientRect();
          if (rect.width === 0 || rect.height === 0) return;

          // Skip duplicates
          const key = el.outerHTML.substring(0, 200);
          if (seen.has(key)) return;
          seen.add(key);

          const tag = el.tagName.toLowerCase();
          const attrs = [];

          // Get ALL attributes that could be useful for selectors
          ['id', 'class', 'type', 'placeholder', 'aria-label', 'data-testid', 'role', 'contenteditable', 'name', 'href', 'value', 'disabled', 'tabindex'].forEach(attr => {
            const val = el.getAttribute(attr);
            if (val) {
              // Keep class names intact so AI can use them as selectors
              const displayVal = attr === 'class'
                ? val  // Keep full class for selector use
                : (val.length > 80 ? val.substring(0, 80) + '...' : val);
              attrs.push(attr + '="' + displayVal.replace(/"/g, "'") + '"');
            }
          });

          // Get text content (for buttons, links, etc.)
          const text = el.textContent?.trim().substring(0, 100) || '';

          // Build the element representation
          const attrStr = attrs.length ? ' ' + attrs.join(' ') : '';

          // Add a suggested selector comment
          let suggestedSelector = tag;
          if (el.id) suggestedSelector = '#' + el.id;
          else if (el.getAttribute('data-testid')) suggestedSelector = '[data-testid="' + el.getAttribute('data-testid') + '"]';
          else if (el.className && typeof el.className === 'string') {
            // Find a unique-looking class
            const classes = el.className.split(' ').filter(c => c.length > 0);
            const uniqueClass = classes.find(c => c.includes('-') || c.includes('_'));
            if (uniqueClass) suggestedSelector = tag + '[class*="' + uniqueClass.split('-')[0] + '"]';
          }

          elements.push('<!-- selector: ' + suggestedSelector + ' --><' + tag + attrStr + '>' + text + '</' + tag + '>');
        });

        return elements.join('\\n');
      })()
    `);

    this.log('DOM evaluate result:', result.success ? 'success' : 'failed', 'length:', result.value?.length);
    if (!result.success) {
      this.log('DOM evaluate error:', result.error);
      return '';
    }
    return result.value || '';
  }

  // Execute action via CDP
  async executeAction(cdp, action) {
    const tool = action.tool;
    const input = action.input || {};

    this.log(`Executing: ${tool}`, input);

    try {
      switch (tool) {
        case 'click':
          return await cdp.click(input.selector);

        case 'type':
          return await cdp.type(input.text);

        case 'typeInto':
          const clickResult = await cdp.click(input.selector);
          if (!clickResult.success) return clickResult;
          await this.sleep(200);
          return await cdp.type(input.text);

        case 'pressKey':
          return await cdp.pressKey(input.key);

        case 'scroll':
          const scrollAmount = input.direction === 'up' ? -(input.amount || 300) : (input.amount || 300);
          return await cdp.scrollBy(0, scrollAmount);

        case 'wait':
          await this.sleep(input.ms || 1000);
          return { success: true };

        case 'done':
          // This is handled in the main loop, just return the input
          return { success: true, done: true, taskSuccess: input.success, message: input.message };

        default:
          return { success: false, error: `Unknown tool: ${tool}` };
      }
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  // Define tools for Claude's native tool_use
  getToolDefinitions() {
    return [
      {
        name: 'click',
        description: 'Click on an element by CSS selector.',
        input_schema: {
          type: 'object',
          properties: {
            selector: {
              type: 'string',
              description: 'CSS selector for the element to click'
            },
            reason: {
              type: 'string',
              description: 'Brief explanation of why clicking this element'
            }
          },
          required: ['selector', 'reason']
        }
      },
      {
        name: 'type',
        description: 'Type text into the currently focused element',
        input_schema: {
          type: 'object',
          properties: {
            text: {
              type: 'string',
              description: 'The text to type'
            }
          },
          required: ['text']
        }
      },
      {
        name: 'typeInto',
        description: 'Click on an element to focus it, then type text into it',
        input_schema: {
          type: 'object',
          properties: {
            selector: {
              type: 'string',
              description: 'The exact CSS selector for the input element'
            },
            text: {
              type: 'string',
              description: 'The text to type'
            }
          },
          required: ['selector', 'text']
        }
      },
      {
        name: 'pressKey',
        description: 'Press a keyboard key',
        input_schema: {
          type: 'object',
          properties: {
            key: {
              type: 'string',
              description: 'The key to press (e.g., Enter, Tab, Escape, Backspace)'
            }
          },
          required: ['key']
        }
      },
      {
        name: 'scroll',
        description: 'Scroll the page',
        input_schema: {
          type: 'object',
          properties: {
            direction: {
              type: 'string',
              enum: ['up', 'down'],
              description: 'Direction to scroll'
            },
            amount: {
              type: 'number',
              description: 'Pixels to scroll (default 300)'
            }
          },
          required: ['direction']
        }
      },
      {
        name: 'wait',
        description: 'Wait for a specified time',
        input_schema: {
          type: 'object',
          properties: {
            ms: {
              type: 'number',
              description: 'Milliseconds to wait'
            },
            reason: {
              type: 'string',
              description: 'Why waiting is needed'
            }
          },
          required: ['ms']
        }
      },
      {
        name: 'done',
        description: 'Signal that the task is complete or cannot be completed',
        input_schema: {
          type: 'object',
          properties: {
            success: {
              type: 'boolean',
              description: 'Whether the task was completed successfully'
            },
            message: {
              type: 'string',
              description: 'Description of what was accomplished or why it failed'
            }
          },
          required: ['success', 'message']
        }
      }
    ];
  }

  // Ask AI for next action using native tool_use
  async getNextAction(task, pageState, history) {
    const systemPrompt = `You are a browser automation agent. You analyze the actual DOM HTML of web pages and use tools to complete tasks.

CRITICAL RULES:
1. Look at the DOM HTML carefully - each element shows its TAG, ATTRIBUTES, and TEXT CONTENT
2. For BUTTONS: Always verify the TEXT CONTENT matches what you want to click!
   - Multiple buttons may have similar classes - distinguish them by their text
   - Example: <button class="primary">Post</button> vs <button class="primary">Create</button>
   - To click "Post", find the button whose text content is "Post", not just any button with "primary" class
3. For contenteditable elements, use: [contenteditable="true"]
4. If an action fails, examine the DOM again and try a different approach
5. Only call "done" with success=true AFTER you've clicked the submit button and see confirmation

SELECTOR STRATEGIES (in order of preference):
1. By unique text: Find the element in DOM, note its tag and a unique class, e.g., button[class*="uniquePart"]
2. By ID: #elementId
3. By data-testid: [data-testid="value"]
4. By unique class combination: button[class*="primary"][class*="specific"]

WARNING: Class names like "priority_primary" appear on MULTIPLE buttons. Always check the element's TEXT to ensure you're selecting the right one!`;

    const historyText = history.length > 0
      ? history.map(h => {
          let line = `Step ${h.step}: ${h.tool}`;
          if (h.input?.selector) line += ` on "${h.input.selector}"`;
          if (h.input?.text) line += ` with text "${h.input.text.substring(0, 30)}..."`;
          if (h.failed) line += ` [FAILED: ${h.error}]`;
          return line;
        }).join('\n')
      : 'No actions taken yet';

    let domContent = pageState.data || '';

    // Truncate DOM if too long (Claude has context limits)
    if (domContent.length > 50000) {
      domContent = domContent.substring(0, 50000) + '\n... [DOM truncated]';
    }

    const userPrompt = `TASK: ${task}

PREVIOUS ACTIONS:
${historyText}

CURRENT PAGE DOM (use these exact elements/selectors):
${domContent}

Analyze the DOM above and decide the next action. Use selectors that exist in the DOM.`;

    // Build messages
    const messages = [{ role: 'user', content: userPrompt }];

    // If using screenshots, add image
    if (pageState.type === 'screenshot' || pageState.type === 'hybrid') {
      const screenshotData = pageState.type === 'hybrid' ? pageState.screenshot : pageState.data;
      if (screenshotData) {
        messages[0] = {
          role: 'user',
          content: [
            { type: 'text', text: userPrompt },
            {
              type: 'image',
              source: {
                type: 'base64',
                media_type: 'image/png',
                data: screenshotData,
              },
            },
          ],
        };
      }
    }

    const response = await fetch(CLAUDE_API_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': this.apiKey,
        'anthropic-version': '2023-06-01',
        'anthropic-dangerous-direct-browser-access': 'true',
      },
      body: JSON.stringify({
        model: this.model,
        max_tokens: 1024,
        system: systemPrompt,
        tools: this.getToolDefinitions(),
        tool_choice: { type: 'any' }, // Force tool use
        messages,
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Claude API ${response.status}: ${error}`);
    }

    const data = await response.json();
    this.log('AI response:', JSON.stringify(data.content, null, 2));

    // Find the tool_use block in the response
    const toolUse = data.content.find(block => block.type === 'tool_use');

    if (!toolUse) {
      // If no tool use, check for text response (shouldn't happen with tool_choice: any)
      const textBlock = data.content.find(block => block.type === 'text');
      if (textBlock) {
        this.log('AI returned text instead of tool:', textBlock.text);
      }
      throw new Error('AI did not return a tool use');
    }

    return {
      tool: toolUse.name,
      input: toolUse.input,
      id: toolUse.id
    };
  }

  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

export function createBrowserAgent(apiKey, options) {
  return new BrowserAgent(apiKey, options);
}
