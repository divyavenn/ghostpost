chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === 'capture-html') {
    try {
      const html = document.documentElement?.outerHTML || '';
      sendResponse({ html });
    } catch (error) {
      console.warn('HTML capture failed', error);
      sendResponse({ html: null, error: error?.message || String(error) });
    }
    return true;
  }

  if (message?.type === 'extract-metadata') {
    try {
      const metadata = {
        title: document.title || null,
        author: document.querySelector('meta[name="author"]')?.content ||
                document.querySelector('meta[property="article:author"]')?.content ||
                document.querySelector('[rel="author"]')?.textContent?.trim() || null,
        publishDate: document.querySelector('meta[property="article:published_time"]')?.content ||
                     document.querySelector('meta[name="date"]')?.content ||
                     document.querySelector('time[datetime]')?.getAttribute('datetime') || null,
        url: window.location.href,
        contentType: null, // Will be set by service worker based on URL pattern
      };
      sendResponse({ metadata });
    } catch (error) {
      console.warn('Metadata extraction failed', error);
      sendResponse({ metadata: null, error: error?.message || String(error) });
    }
    return true;
  }

  return undefined;
});

