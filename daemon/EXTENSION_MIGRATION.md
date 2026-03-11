# CLI/Daemon Changes — Chrome Extension Migration Guide

This document summarizes recent changes to the `cli_log` daemon and scraping pipeline that affect the Chrome extension.

---

## 1. Parallel Scrape Pipeline

The `/scrape` endpoint now runs **Rust metadata extraction and Python content scraping in parallel**. Content type is detected from URL patterns alone (no HTTP request), so both tasks start immediately.

**What changed for the extension:** Nothing — the request/response contract is the same. Scraping is just faster.

### Request (unchanged)
```json
POST /scrape
{ "url": "https://..." }
```

### Response (unchanged shape, new behavior)
```json
{
  "success": true,
  "markdown": "# Title\n\n- **Source:** https://...\n\n---\n\ncontent...",
  "filename": "slug.md",
  "content_type": "tweet",
  "title": "@handle: first five words...",
  "author": "Sarah Polley",
  "year": 2011,
  "starring": ["Actor1", "Actor2"],
  "error": null
}
```

---

## 2. Content Type Detection

Content type is now detected from the URL before any HTTP request. **Tweets are now recognized** — previously they fell through to `ArticleExtractor` and returned `content_type: "unknown"`.

| URL pattern | content_type |
|---|---|
| `youtube.com`, `youtu.be` | `youtube` |
| `arxiv.org` | `research paper` |
| `github.com` | `github` |
| `*.substack.com` | `substack` |
| `goodreads.com` | `book` |
| `imdb.com` | `movie` |
| `letterboxd.com` | `movie` |
| `*.wikipedia.org` | `article` |
| `x.com`, `twitter.com` | **`tweet`** (new!) |
| `medium.com` | `medium` |
| path ends `.pdf` | `pdf` |
| everything else | `article` |

**Extension impact:** If you key off `content_type`, tweets now correctly return `"tweet"` instead of `"unknown"`.

---

## 3. Markdown Format Changes

### Headers are now Rust-only

Python scrapers no longer emit their own headers. The Rust `header.rs` module is the single source of truth. All markdown now has a consistent format:

```markdown
# Title

- **Source:** https://example.com/...
- **Author/Director:** Name
- **Year:** 2011
- **Starring:** Actor1, Actor2

---

(content body)
```

Only present fields are included. The `- **Source:** URL` line is new.

### Tweet markdown

**Before:**
```markdown
# Thread Export

- Source: [url](url)
- Author: @handle
- Tweets captured: 19

## Tweet 1

text...
```

**After:**
```markdown
# @handle: first five words...

- **Source:** https://x.com/...

---

## Tweet 1

text...
```

- Title is now `@handle: first 5 words...` (in the `title` response field too)
- No more `# Thread Export`, `Author:`, `Tweets captured:` lines
- Content starts directly at `## Tweet 1`

### YouTube markdown

**Before:**
```markdown
# Video Title

- Source: https://youtube.com/...
- Language: `en`

transcript body...
```

**After:** Just the transcript body. Title/source are in the Rust header.

### Substack markdown

**Before:**
```markdown
# Article Title
### Subtitle
*[Author](href) | Date | Badge | via [Substack](url)*

body...
```

**After:** Just the article body. Title/source/author are in the Rust header. Subtitle and date are dropped (Rust extracts title and author from meta tags).

---

## 4. IMDB Director Extraction

The IMDB extractor now parses JSON-LD structured data (`<script type="application/ld+json">`) instead of walking HTML links. This reliably extracts the director name — the old HTML scraping was broken by IMDB layout changes.

The `author` field in the response now correctly returns the director (e.g., `"Sarah Polley"`).

---

## 5. CDP / Browser Changes

Two browser connection modules now exist with the same interface:

### `consumed/true_cdp.py` (default for tweets)

Uses the user's **real Chrome session** via CDP. Pages open in unfocused background windows using `Target.createTarget` with `background: true, newWindow: true` — equivalent to:

```js
chrome.windows.create({ url, focused: false, state: 'normal' })
```

Pages never steal focus. They close automatically when scraping finishes.

### `consumed/cdp.py` (headless alternative)

Connects to Chrome via CDP **only to extract cookies**, disconnects, then launches a separate **headless Chromium** with those cookies. Completely invisible.

### Switching

In `scrapers/tweet_playwright.py`:

```python
USE_REAL_BROWSER = True   # true_cdp (real Chrome, background windows)
USE_REAL_BROWSER = False  # cdp (headless with extracted cookies)
```

### Extension implications

- The extension's `/import-cookies` endpoint still works as before
- If `true_cdp` is active, scraping happens in the user's real Chrome — the extension should not interfere with background windows created by Playwright
- The hardcoded fallback cookies in `tweet_playwright.py` are only used when both CDP and explicit cookies are unavailable

---

## 6. Python Scraper Return Values

### Tweet scraper

`convert_tweet()` now returns a **4-tuple** instead of 3:

```python
# Before
markdown, handle, root_id = convert_tweet(url)

# After
markdown, handle, root_id, first_tweet_text = convert_tweet(url)
```

The `first_tweet_text` is the raw text of the first tweet, used by the daemon to build the title (`@handle: first 5 words...`).

### scrape.py JSON output

For tweets, the JSON output now includes `first_tweet`:

```json
{"markdown": "...", "filename": "...", "first_tweet": "i have a theory that..."}
```

Other content types are unchanged: `{"markdown": ..., "filename": ...}`.

---

## Summary of Files Changed

| File | What changed |
|---|---|
| `consumed-core/src/metadata/mod.rs` | New `detect_content_type(url)` — URL-only content type detection |
| `consumed-core/src/models.rs` | New `ContentType::has_scraper()` method |
| `consumed-core/src/metadata/header.rs` | Added `- **Source:** URL` to header output |
| `consumed-core/src/metadata/imdb.rs` | Director extraction via JSON-LD instead of HTML |
| `consumed-daemon/src/server.rs` | Parallel scrape pipeline, tweet title construction, URL-detected content_type |
| `python/consumed/cdp.py` | Headless mode: extract cookies from CDP, scrape in headless |
| `python/consumed/true_cdp.py` | **New file** — real Chrome with `Target.createTarget(background: true)` |
| `python/scrapers/tweet.py` | Removed header, returns `first_tweet_text` |
| `python/scrapers/tweet_playwright.py` | `USE_REAL_BROWSER` flag, `cookie_still_valid` moved here |
| `python/scrapers/youtube.py` | Removed header from `build_markdown_transcript` |
| `python/scrapers/substack.py` | Removed header from `convert_html_to_markdown` |
| `python/consumed/scrape.py` | Passes `first_tweet` in JSON for tweets |
| `python/tests/test_scrape.py` | Updated assertions for new format |
