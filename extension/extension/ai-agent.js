// AI-powered browser agent using OpenAI
// Analyzes page DOM and determines actions dynamically

const OPENAI_API_URL = 'https://api.openai.com/v1/chat/completions';

// Call OpenAI to analyze the page and get next action
export async function getAIAction(apiKey, task, domSnapshot, previousActions = []) {
  const systemPrompt = `You are a browser automation agent. You analyze webpage DOM snapshots and return precise actions to accomplish tasks.

You will receive:
1. A task to accomplish (e.g., "post a note with text: hello")
2. A simplified DOM snapshot of the current page
3. Previous actions taken (if any)

You must respond with a JSON object containing ONE action to take:

For clicking elements:
{"action": "click", "selector": "CSS selector here", "description": "why clicking this"}

For typing text:
{"action": "type", "selector": "CSS selector here", "text": "text to type", "description": "why typing here"}

For waiting:
{"action": "wait", "ms": 1000, "description": "why waiting"}

When the task is complete:
{"action": "done", "success": true, "description": "task completed because..."}

If the task cannot be completed:
{"action": "done", "success": false, "error": "explanation of why it failed"}

Rules:
- Use specific, unique CSS selectors that will match exactly one element
- Prefer data-testid, aria-label, or unique class combinations
- For contenteditable divs, the selector should target the editable element directly
- Always verify the element exists in the DOM snapshot before selecting it
- If you see a placeholder like "What's on your mind?" that's likely the input field`;

  const userPrompt = `Task: ${task}

Previous actions taken:
${previousActions.length > 0 ? previousActions.map((a, i) => `${i + 1}. ${a.action}: ${a.description}`).join('\n') : 'None yet'}

Current DOM snapshot:
${domSnapshot}

What is the next action to take? Respond with only the JSON object.`;

  try {
    const response = await fetch(OPENAI_API_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model: 'gpt-4o-mini',
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: userPrompt },
        ],
        temperature: 0,
        max_tokens: 500,
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`OpenAI API error: ${response.status} - ${error}`);
    }

    const data = await response.json();
    const content = data.choices[0]?.message?.content?.trim();

    // Parse JSON from response (handle markdown code blocks)
    let jsonStr = content;
    if (content.includes('```')) {
      jsonStr = content.replace(/```json?\n?/g, '').replace(/```/g, '').trim();
    }

    return JSON.parse(jsonStr);
  } catch (error) {
    console.error('[AI Agent] Error calling OpenAI:', error);
    throw error;
  }
}

// Simplify DOM for AI consumption (reduce token usage)
export function simplifyDOM(html) {
  // Parse and extract relevant elements
  const parser = new DOMParser();
  const doc = parser.parseFromString(html, 'text/html');

  // Remove script, style, svg, and other non-essential elements
  const removeSelectors = ['script', 'style', 'svg', 'noscript', 'iframe', 'link', 'meta'];
  removeSelectors.forEach(sel => {
    doc.querySelectorAll(sel).forEach(el => el.remove());
  });

  // Function to get simplified representation of an element
  function simplifyElement(el, depth = 0) {
    if (depth > 6) return ''; // Limit depth
    if (el.nodeType === Node.TEXT_NODE) {
      const text = el.textContent.trim();
      return text.length > 0 && text.length < 100 ? text : '';
    }
    if (el.nodeType !== Node.ELEMENT_NODE) return '';

    const tag = el.tagName.toLowerCase();

    // Skip hidden elements
    if (el.hidden || el.style?.display === 'none') return '';

    // Build attributes string (only useful ones)
    const attrs = [];
    const usefulAttrs = ['id', 'class', 'type', 'placeholder', 'aria-label', 'data-testid', 'role', 'contenteditable', 'href', 'name'];
    usefulAttrs.forEach(attr => {
      const val = el.getAttribute(attr);
      if (val) {
        // Truncate long class names
        const truncated = val.length > 100 ? val.substring(0, 100) + '...' : val;
        attrs.push(`${attr}="${truncated}"`);
      }
    });

    const attrStr = attrs.length > 0 ? ' ' + attrs.join(' ') : '';
    const indent = '  '.repeat(depth);

    // Get children
    const children = Array.from(el.childNodes)
      .map(child => simplifyElement(child, depth + 1))
      .filter(s => s.length > 0)
      .join('\n');

    // Self-closing or empty elements
    if (!children && ['input', 'img', 'br', 'hr'].includes(tag)) {
      return `${indent}<${tag}${attrStr} />`;
    }

    // Elements with content
    if (children) {
      return `${indent}<${tag}${attrStr}>\n${children}\n${indent}</${tag}>`;
    }

    // Empty elements (still might be clickable buttons, etc.)
    if (['button', 'a', 'div'].includes(tag) && attrStr) {
      const text = el.textContent?.trim().substring(0, 50);
      if (text) {
        return `${indent}<${tag}${attrStr}>${text}</${tag}>`;
      }
      return `${indent}<${tag}${attrStr}></${tag}>`;
    }

    return '';
  }

  return simplifyElement(doc.body);
}
