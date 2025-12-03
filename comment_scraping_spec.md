# Tweet Activity Tracking Spec

*Recency + Resurrection Pipeline with Comment Tracking*

This document defines **exact, implementation-level behavior** for:
1. Tracking tweet activity for all tweets/replies posted **within** and **outside** the app
2. Tracking and responding to **comments** (replies from others) on your posts
3. Managing tweet lifecycle with monitoring states

---

## 0. Terminology

| Term | Definition |
|------|------------|
| **User** | An end user of our app (e.g., `divya_venn`) |
| **Tweet** | Any tweet or reply authored by the user |
| **Comment** | A reply from someone else to the user's tweet or to a thread the user started |
| **Posted Tweets Cache** | Map at `backend/cache/{username}_posted_tweets.json` |
| **Comments Cache** | Map at `backend/cache/{username}_comments.json` |
| **Monitoring State** | Activity state: `"active"` \| `"warm"` \| `"cold"` |
| **Activity** | Any observable change: new replies, likes, quotes, retweets |
| **parent_chain** | Array of ancestor tweet IDs, ordered from root to immediate parent |

**Four background jobs:**
- `discover_recently_posted` - Find user's tweets posted outside the app
- `discover_engagement` - Update metrics and find new comments
- `discover_resurrected` - Detect activity on cold tweets via notifications
- `repost_top_cold` - Repost top-performing cold tweets

**Two scraping modes:**
- **Shallow scrape** (cheap) - Metrics only, no scrolling
- **Deep scrape** (expensive) - Full thread with all replies

---

## 1. Storage Structure

### 1.1 Map-Based Storage (NOT Arrays)

Both `posted_tweets.json` and `comments.json` use a **map structure** with an `_order` array for pagination.

**`posted_tweets.json`:**
```json
{
  "_order": ["789", "456", "123"],
  "123": {
    "id": "123",
    "text": "My original tweet",
    "parent_chain": [],
    "source": "app_posted",
    ...
  },
  "456": {
    "id": "456",
    "text": "My reply to someone",
    "parent_chain": ["ext_tweet_id"],
    "source": "app_posted",
    ...
  },
  "789": {
    "id": "789",
    "text": "My reply to a comment",
    "parent_chain": ["123", "abc"],
    "source": "app_posted",
    ...
  }
}
```

**`comments.json`:**
```json
{
  "_order": ["def", "abc"],
  "abc": {
    "id": "abc",
    "text": "Someone's reply to my tweet",
    "parent_chain": ["123"],
    "status": "pending",
    ...
  },
  "def": {
    "id": "def",
    "text": "Someone's reply deeper in my thread",
    "parent_chain": ["123", "789"],
    "status": "pending",
    ...
  }
}
```

### 1.2 The `_order` Array

- Contains tweet IDs sorted by `created_at` descending (newest first)
- Used for pagination without sorting on every request
- Updated whenever a tweet is added or removed

```python
def get_paginated(cache: dict, limit: int, offset: int) -> list[dict]:
    order = cache.get("_order", [])
    ids = order[offset:offset + limit]
    return [cache[id] for id in ids if id in cache]
```

---

## 2. Data Models

### 2.1 TweetRecord (for `posted_tweets.json`)

```typescript
type MonitoringState = "active" | "warm" | "cold";
type ResurrectionSource = "none" | "notification" | "search";
type TweetSource = "app_posted" | "external";

interface TweetRecord {
  // Core fields
  id: string;
  text: string;
  likes: number;
  retweets: number;
  quotes: number;
  replies: number;
  impressions: number;
  created_at: string;              // ISO8601
  url: string;
  last_metrics_update: string | null;

  // Parent chain tracking
  parent_chain: string[];          // [root_id, ..., immediate_parent_id] or [] if root

  // Legacy fields (keep for frontend compatibility)
  response_to_thread?: string[];
  responding_to?: string;
  replying_to_pfp?: string;
  original_tweet_url?: string;

  // Source tracking
  source: TweetSource;

  // Monitoring state machine
  monitoring_state: MonitoringState;

  // Timestamps
  last_activity_at: string | null;
  last_deep_scrape: string | null;
  last_shallow_scrape: string | null;

  // Metrics snapshot for activity detection
  last_reply_count: number | null;
  last_quote_count: number | null;
  last_like_count: number | null;
  last_retweet_count: number | null;

  // Resurrection info
  resurrected_via: ResurrectionSource;

  // Reply tracking
  last_scraped_reply_ids?: string[];
}
```

### 2.2 CommentRecord (for `comments.json`)

Comments have **all the same fields as tweets** plus:

```typescript
interface CommentRecord extends TweetRecord {
  // Comment-specific fields
  status: "pending" | "replied" | "skipped";

  // These fields represent the commenter (not the user)
  handle: string;           // commenter's handle
  username: string;         // commenter's display name
  author_profile_pic_url: string;
  followers: number;

  // Generated replies for user to approve
  generated_replies: Array<[string, string]>;  // [reply_text, model_name]
  edited: boolean;
}
```

### 2.3 Key Insight: `parent_chain`

The `parent_chain` array enables:
1. **O(1) root lookup**: `root_id = parent_chain[0]` (or self if empty)
2. **Full context retrieval**: Iterate through `parent_chain` to build conversation
3. **Incremental building**: `new_chain = parent.parent_chain + [parent.id]`

---

## 3. Building and Using `parent_chain`

### 3.1 When User Posts a Reply (via app)

```python
def add_posted_tweet(username: str, posted_tweet_id: str, in_reply_to_id: str | None, ...):
    posted_tweets = read_posted_tweets_cache(username)
    comments = read_comments_cache(username)

    parent_chain = []
    if in_reply_to_id:
        # Look up parent in both caches
        parent = posted_tweets.get(in_reply_to_id) or comments.get(in_reply_to_id)
        if parent:
            parent_chain = parent.get("parent_chain", []) + [in_reply_to_id]
        else:
            # Replying to external tweet we don't track
            parent_chain = [in_reply_to_id]

    # Add to map
    posted_tweets[posted_tweet_id] = {
        "id": posted_tweet_id,
        "parent_chain": parent_chain,
        "source": "app_posted",
        "monitoring_state": "active",
        ...
    }

    # Update order (prepend for newest-first)
    posted_tweets["_order"] = [posted_tweet_id] + posted_tweets.get("_order", [])

    write_posted_tweets_cache(username, posted_tweets)
```

### 3.2 When Scraping New Comments

```python
def process_scraped_replies(username: str, scraped_replies: list[dict]):
    posted_tweets = read_posted_tweets_cache(username)
    comments = read_comments_cache(username)
    user_tweet_ids = set(k for k in posted_tweets.keys() if k != "_order")
    user_handle = get_user_handle(username)

    new_comment_ids = []

    for reply in scraped_replies:
        # Skip user's own tweets (they go in posted_tweets, not comments)
        if reply["handle"] == user_handle:
            continue

        # Skip if already seen - just update metrics
        if reply["id"] in comments:
            update_comment_metrics(comments, reply)
            continue

        in_reply_to_id = reply["in_reply_to_status_id"]

        # Build parent_chain
        parent = posted_tweets.get(in_reply_to_id) or comments.get(in_reply_to_id)
        if parent:
            parent_chain = parent.get("parent_chain", []) + [in_reply_to_id]
        else:
            parent_chain = [in_reply_to_id]

        # Only track if root is user's tweet
        root_id = parent_chain[0] if parent_chain else in_reply_to_id
        if root_id not in user_tweet_ids:
            continue

        # Add to comments
        comments[reply["id"]] = {
            **reply,
            "parent_chain": parent_chain,
            "status": "pending",
            "generated_replies": [],
            "edited": False,
            "monitoring_state": "active",
            "source": "external",
            ...
        }
        new_comment_ids.append(reply["id"])

    # Update order
    comments["_order"] = new_comment_ids + comments.get("_order", [])

    write_comments_cache(username, comments)

    return new_comment_ids  # For reply generation pass
```

### 3.3 Retrieving Full Thread Context

```python
def get_thread_context(tweet_id: str, username: str) -> list[dict]:
    """Returns ordered list from root -> current tweet for LLM context."""
    posted_tweets = read_posted_tweets_cache(username)
    comments = read_comments_cache(username)
    user_tweet_ids = set(k for k in posted_tweets.keys() if k != "_order")

    tweet = posted_tweets.get(tweet_id) or comments.get(tweet_id)
    if not tweet:
        return []

    chain = []
    for ancestor_id in tweet.get("parent_chain", []):
        ancestor = posted_tweets.get(ancestor_id) or comments.get(ancestor_id)
        if ancestor:
            chain.append({
                "id": ancestor_id,
                "text": ancestor.get("text", ""),
                "handle": ancestor.get("handle", ""),
                "username": ancestor.get("username", ""),
                "is_user": ancestor_id in user_tweet_ids
            })
        else:
            # Ancestor was deleted or not tracked
            chain.append({
                "id": ancestor_id,
                "text": "<tweet deleted>",
                "handle": "",
                "username": "",
                "is_user": False,
                "deleted": True
            })

    # Add current tweet
    chain.append({
        "id": tweet_id,
        "text": tweet.get("text", ""),
        "handle": tweet.get("handle", ""),
        "username": tweet.get("username", ""),
        "is_user": tweet_id in user_tweet_ids
    })

    return chain
```

### 3.4 LLM Context for Reply Generation

```python
def build_comment_prompt(comment_id: str, username: str, user_profile: dict) -> str:
    chain = get_thread_context(comment_id, username)

    # Cap context length for LLM
    MAX_MESSAGES = 10
    if len(chain) > MAX_MESSAGES:
        chain = chain[:2] + chain[-(MAX_MESSAGES - 2):]

    prompt = "You are replying in a Twitter conversation.\n\n"
    prompt += "CONVERSATION THREAD:\n"

    for msg in chain:
        if msg.get("deleted"):
            prompt += "[DELETED TWEET]\n\n"
        else:
            role = "[YOU]" if msg["is_user"] else f"[@{msg['handle']}]"
            prompt += f"{role}: {msg['text']}\n\n"

    prompt += f"\nGenerate a reply to the last message."
    return prompt
```

---

## 4. Scraping Modes

### 4.1 Shallow Scrape (cheap)

**Goal**: Detect activity with minimal cost.

```python
async def shallow_scrape(tweet_id: str, username: str) -> ShallowScrapeResult:
    page = await ctx.new_page()
    await page.goto(f"https://twitter.com/{username}/status/{tweet_id}")

    # Intercept TweetDetail GraphQL
    # Extract metrics from first response
    # No scrolling

    return ShallowScrapeResult(
        reply_count=...,
        like_count=...,
        quote_count=...,
        retweet_count=...,
        latest_reply_ids=[...]  # 3-10 top replies
    )
```

### 4.2 Deep Scrape (expensive)

**Goal**: Get full thread with all replies.

```python
async def deep_scrape(tweet_id: str, username: str) -> DeepScrapeResult:
    page = await ctx.new_page()
    await page.goto(f"https://twitter.com/{username}/status/{tweet_id}")

    replies = {}
    seen_pages = set()

    while True:
        await asyncio.sleep(0.5)
        # Capture GraphQL responses
        # Parse replies with in_reply_to_status_id
        # Add to replies dict

        await page.mouse.wheel(0, 2000)

        if no_new_responses_for(3_seconds):
            break

    return DeepScrapeResult(
        reply_count=...,
        like_count=...,
        quote_count=...,
        retweet_count=...,
        all_reply_ids=list(replies.keys()),
        replies=list(replies.values())
    )
```

---

## 5. Activity Detection

```python
def detect_activity(record: dict, scrape_result: dict) -> bool:
    activity = False

    if scrape_result["reply_count"] > (record.get("last_reply_count") or 0):
        activity = True
    if scrape_result["like_count"] > (record.get("last_like_count") or 0):
        activity = True
    if scrape_result["quote_count"] > (record.get("last_quote_count") or 0):
        activity = True
    if scrape_result["retweet_count"] > (record.get("last_retweet_count") or 0):
        activity = True

    # Check for new reply IDs
    old_ids = set(record.get("last_scraped_reply_ids") or [])
    new_ids = set(scrape_result.get("all_reply_ids") or scrape_result.get("latest_reply_ids") or [])
    if new_ids - old_ids:
        activity = True

    return activity
```

---

## 6. Monitoring State Machine

### 6.1 States

| State | Description | Scrape Type |
|-------|-------------|-------------|
| `active` | New or currently hot | Deep |
| `warm` | Cooling down | Shallow |
| `cold` | Inactive | None (unless resurrected) |

### 6.2 Thresholds (in `config.py`)

```python
ACTIVE_MAX_AGE_HOURS = 12
WARM_MAX_AGE_DAYS = 3
INACTIVITY_TO_COLD_HOURS = 24
HARDCUTOFF_COLD_DAYS = 7
```

### 6.3 Transition Logic

```python
def update_monitoring_state(record: dict, activity_detected: bool, now: datetime):
    created = parse_datetime(record["created_at"])
    last_activity = parse_datetime(record["last_activity_at"]) if record["last_activity_at"] else created

    age_hours = (now - created).total_seconds() / 3600
    age_days = age_hours / 24
    inactive_hours = (now - last_activity).total_seconds() / 3600

    state = record["monitoring_state"]

    # Degradation
    if state == "active" and age_hours > ACTIVE_MAX_AGE_HOURS:
        state = "warm"

    if state == "warm":
        if (age_days >= WARM_MAX_AGE_DAYS and inactive_hours >= INACTIVITY_TO_COLD_HOURS) \
           or age_days >= HARDCUTOFF_COLD_DAYS:
            state = "cold"

    # Promotion on activity
    if activity_detected and state in ["warm", "cold"]:
        new_replies = record["replies"] - (record.get("last_reply_count") or 0)
        if new_replies >= 5:
            state = "active"
        else:
            state = "warm"

    record["monitoring_state"] = state
```

---

## 7. Four Background Jobs

### 7.1 Job 1: `discover_recently_posted`

**Purpose**: Find tweets posted outside the app.

**Frequency**: Every 24 hours, **MUST run before** `discover_engagement`.

**Steps**:
1. Load `posted_tweets.json`
2. Build `known_ids = set(posted_tweets.keys()) - {"_order"}`
3. Fetch recent tweets via API or scrape "Tweets & Replies" tab
4. For each tweet by user not in `known_ids`:
   ```python
   posted_tweets[tweet_id] = {
       "id": tweet_id,
       "parent_chain": build_parent_chain(tweet),
       "source": "external",
       "monitoring_state": "active",
       ...
   }
   posted_tweets["_order"].insert(0, tweet_id)
   ```
5. Save atomically

---

### 7.2 Job 2: `discover_engagement`

**Purpose**: Update metrics, detect activity, collect comments.

**Frequency**: Every 6 hours.

**Batching**: Process tweets sorted by `last_activity_at` descending (most recent first).

**Steps**:
1. Load `posted_tweets.json` and `comments.json`
2. Get tweets to process:
   ```python
   tweets_to_scrape = [
       t for t in posted_tweets.values()
       if t != "_order" and t["monitoring_state"] in ["active", "warm"]
   ]
   # Sort by last_activity_at descending
   tweets_to_scrape.sort(key=lambda t: t.get("last_activity_at") or "", reverse=True)
   ```
3. For each tweet:
   - If `active` → deep scrape
   - If `warm` → shallow scrape
4. Detect activity, update metrics
5. **Process scraped replies** → add new comments (see section 3.2)
6. Update monitoring states
7. Save both caches atomically

**After scraping completes** → Run reply generation pass:
```python
def generate_replies_for_new_comments(username: str, new_comment_ids: list[str]):
    comments = read_comments_cache(username)

    for comment_id in new_comment_ids:
        comment = comments.get(comment_id)
        if not comment or comment.get("generated_replies"):
            continue

        prompt = build_comment_prompt(comment_id, username, user_profile)
        replies = generate_replies(prompt)

        comment["generated_replies"] = replies

    write_comments_cache(username, comments)
```

---

### 7.3 Job 3: `discover_resurrected`

**Purpose**: Detect activity on cold tweets via notifications.

**Frequency**: Every 24 hours.

**Steps**:
1. Scrape `https://twitter.com/notifications`
2. Intercept `NotificationTimeline` GraphQL
3. Extract tweet IDs referenced in notifications
4. For each ID in `posted_tweets` that's `cold`:
   ```python
   record["monitoring_state"] = "warm"
   record["resurrected_via"] = "notification"
   record["last_activity_at"] = now
   ```

---

### 7.4 Job 4: `repost_top_cold`

**Purpose**: Repost top-performing cold tweets.

**Frequency**: Weekly.

**Steps**:
1. Get cold tweets:
   ```python
   cold = [t for t in posted_tweets.values() if t.get("monitoring_state") == "cold"]
   cold.sort(key=lambda t: t["likes"] + t["replies"] + t["quotes"] + t["retweets"], reverse=True)
   top_n = cold[:4]
   ```
2. Repost each → automatically added as `active` in `posted_tweets`

---

## 8. Job Execution Order

**Critical**: Jobs must run in this order to ensure data consistency:

```
discover_recently_posted  →  discover_engagement  →  generate_replies
         ↓                           ↓
   (finds external tweets)    (scrapes for comments)
```

If `discover_engagement` runs before `discover_recently_posted`, comments replying to external tweets won't have proper `parent_chain` context.

---

## 9. Migration from Array to Map

```python
def migrate_posted_tweets(username: str):
    path = get_posted_tweets_path(username)
    data = read_json(path)

    if isinstance(data, list):
        new_data = {"_order": []}

        # Sort by created_at descending for order
        data.sort(key=lambda t: t.get("created_at", ""), reverse=True)

        for tweet in data:
            tweet_id = tweet["id"]

            # Add new fields with defaults
            tweet.setdefault("parent_chain", [])
            tweet.setdefault("source", "app_posted")
            tweet.setdefault("monitoring_state",
                "cold" if is_older_than_7_days(tweet["created_at"]) else "active")
            tweet.setdefault("last_activity_at", tweet["created_at"])
            tweet.setdefault("last_reply_count", tweet.get("replies", 0))
            tweet.setdefault("last_like_count", tweet.get("likes", 0))
            tweet.setdefault("last_quote_count", tweet.get("quotes", 0))
            tweet.setdefault("last_retweet_count", tweet.get("retweets", 0))
            tweet.setdefault("resurrected_via", "none")

            new_data[tweet_id] = tweet
            new_data["_order"].append(tweet_id)

        write_json(path, new_data)
```

---

## 10. Frontend: Comments Tab

New tab alongside "Generated" and "Posted" called **"Comments"**.

**Display**:
- Shows comments with `status == "pending"`
- For each comment:
  - Show thread context (collapsible, using `parent_chain`)
  - Show commenter info (handle, avatar, followers)
  - Show their comment text
  - Show generated reply options
  - Actions: Reply, Skip, Edit, Regenerate

**API Endpoints**:
```
GET  /comments/{username}?limit=20&offset=0
POST /comments/{username}/{comment_id}/reply
POST /comments/{username}/{comment_id}/skip
PUT  /comments/{username}/{comment_id}/edit
POST /comments/{username}/{comment_id}/regenerate
```

---

## 11. Summary

| Cache | Structure | Key Fields |
|-------|-----------|------------|
| `posted_tweets.json` | Map + `_order` | User's tweets, `parent_chain`, monitoring state |
| `comments.json` | Map + `_order` | Others' replies, `parent_chain`, `status` |

| Job | Frequency | Purpose |
|-----|-----------|---------|
| `discover_recently_posted` | 24h | Find external tweets |
| `discover_engagement` | 6h | Update metrics, find comments |
| `discover_resurrected` | 24h | Resurrect cold tweets |
| `repost_top_cold` | Weekly | Repost best cold tweets |

**Key invariants**:
- `parent_chain[0]` is always the root tweet ID
- User's tweets are **always** in `posted_tweets`, never in `comments`
- `comments` only contains other people's replies
- Reply generation runs **after** scraping, not during
- Jobs run in order: `discover_recently_posted` → `discover_engagement`
