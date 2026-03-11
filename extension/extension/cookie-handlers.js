// Handler functions for extracting data from different login pages
// Each handler should return an object with the data to send along with cookies

// Handler: Extract username from OAuth success page meta tag
export async function getUsernameFromOAuth(tabId) {
  const [{ result }] = await chrome.scripting.executeScript({
    target: { tabId },
    world: 'MAIN', // ensure we see the real page DOM
    func: () => {
      // small helper - returns just the username string
      const pick = (s) => {
        const el = document.querySelector(s);
        if (!el) return null;
        const txt = (el.getAttribute('content') || el.getAttribute('href') || el.textContent || '').trim();
        const m = txt.match(/@?([A-Za-z0-9_]{1,15})/);
        return m ? m[1] : null;
      };

      // 1) the explicit meta used on many OAuth success pages
      const viaMeta = pick('meta[name="twitter-username"]');
      if (viaMeta) return viaMeta;

      // 2) sometimes providers inject the handle into og:title/description
      const viaOg = pick('meta[property="og:title"], meta[name="description"]');
      if (viaOg) return viaOg;

      // 3) canonical link like https://x.com/@handle or /handle
      const canon = document.querySelector('link[rel="canonical"]');
      if (canon && canon.href) {
        const m = canon.href.match(/x\.com\/@?([A-Za-z0-9_]{1,15})/i);
        if (m) return m[1];
      }

      return null;
    }
  });

  if (result) console.log(`✅ OAuth: @${result}`); else console.log('❌ OAuth: not found');
  return { username: result };
}

// Handler: Extract username from Twitter home page
export async function getUsernameFromXHome(tabId) {
  const [{ result }] = await chrome.scripting.executeScript({
    target: { tabId },
    world: 'MAIN',
    func: () => new Promise((resolve) => {
      const HANDLE = /@?([A-Za-z0-9_]{1,15})/;

      const tryDom = () => {
        // 1) Profile link often present in navbar/sidenav
        // Examples seen in production:
        //   a[aria-label="Profile"][href^="/"]
        //   a[data-testid="AppTabBar_Profile_Link"]
        //   [data-testid="SideNav_AccountSwitcher_Button"] (contains "@handle" text)
        const selCandidates = [
          'a[aria-label="Profile"][href^="/"]',
          'a[data-testid="AppTabBar_Profile_Link"]',
          '[data-testid="SideNav_AccountSwitcher_Button"]',
        ];

        for (const s of selCandidates) {
          const el = document.querySelector(s);
          if (!el) continue;

          // href beats innerText: less noisy
          const href = el.href || (el.getAttribute ? el.getAttribute('href') : '') || '';
          const mHref = href.match(/x\.com\/@?([A-Za-z0-9_]{1,15})$/i) || href.match(/^\/@?([A-Za-z0-9_]{1,15})$/);
          if (mHref) return mHref[1];

          // fallback to visible text like "… @handle"
          const txt = (el.textContent || '').trim();
          const mTxt = txt.match(/@([A-Za-z0-9_]{1,15})/);
          if (mTxt) return mTxt[1];
        }

        // 2) Scan any sidenav anchors that look like "/{handle}"
        const anchors = Array.from(document.querySelectorAll('nav a[href^="/"]'));
        for (const a of anchors) {
          const attrHref = a.getAttribute('href');
          const m = attrHref ? attrHref.match(/^\/@?([A-Za-z0-9_]{1,15})$/) : null;
          if (m) return m[1];
        }

        return null;
      };

      const tryLocalStorage = () => {
        // X often keeps user/session blobs in localStorage; we scan JSON values for "screen_name"
        try {
          for (let i = 0; i < localStorage.length; i++) {
            const k = localStorage.key(i);
            if (!k) continue;
            const v = localStorage.getItem(k) || '';
            if (!v || v.length < 3) continue;

            // quick & safe scan without assuming exact key names
            if (v.includes('screen_name') || v.includes('"username"')) {
              try {
                const parsed = JSON.parse(v);
                const deepFind = (obj) => {
                  if (!obj || typeof obj !== 'object') return null;
                  if (typeof obj.screen_name === 'string' && HANDLE.test(obj.screen_name)) {
                    const match = obj.screen_name.match(HANDLE);
                    return match ? match[1] : null;
                  }
                  if (typeof obj.username === 'string' && HANDLE.test(obj.username)) {
                    const match = obj.username.match(HANDLE);
                    return match ? match[1] : null;
                  }
                  for (const key of Object.keys(obj)) {
                    const val = obj[key];
                    const hit = typeof val === 'string'
                      ? (val.match(/@?([A-Za-z0-9_]{1,15})/) || [])[1] || null
                      : deepFind(val);
                    if (hit) return hit;
                  }
                  return null;
                };
                const found = deepFind(parsed);
                if (found) return found;
              } catch { /* value wasn't JSON; ignore */ }
            }
          }
        } catch { /* LS not accessible in some contexts */ }
        return null;
      };

      // Try immediately
      const now = tryDom() || tryLocalStorage();
      if (now) return resolve(now);

      // Otherwise observe for a short window (SPA render)
      const timeoutMs = 4000;
      const start = Date.now();

      const tick = () => {
        const hit = tryDom();
        if (hit) {
          cleanup();
          resolve(hit);
        } else if (Date.now() - start > timeoutMs) {
          const ls = tryLocalStorage();
          cleanup();
          resolve(ls);
        }
      };

      const mo = new MutationObserver(() => tick());
      mo.observe(document.documentElement, { subtree: true, childList: true });

      const interval = setInterval(tick, 200);
      const timer = setTimeout(() => { cleanup(); resolve(null); }, timeoutMs + 2500);

      function cleanup() {
        try { mo.disconnect(); } catch {}
        clearInterval(interval);
        clearTimeout(timer);
      }
    })
  });

  if (result) {
    console.log(`✅ XHome: @${result}`);
    return { username: result };
  } else {
    console.log('❌ XHome: not found (DOM/LS)');
    return null;
  }
}
