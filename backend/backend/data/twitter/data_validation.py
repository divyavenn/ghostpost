from typing import Literal

from pydantic import BaseModel, Field


class MediaItem(BaseModel):
    type: str  # "photo", "video", "animated_gif"
    url: str
    alt_text: str = ""


class QuotedTweet(BaseModel):
    text: str
    author_handle: str
    author_name: str
    media: list[MediaItem] = []


class OtherReply(BaseModel):
    """A reply to a tweet from another user."""
    text: str
    author_handle: str
    author_name: str
    likes: int = 0


class User(BaseModel):
    # account info
    uid: int | None = None  # Auto-generated on first creation
    account_type: Literal["trial", "poster", "premium"] = "trial"
    email: str | None = None  # Collected after first login

    # data from twitter
    handle: str
    username: str
    profile_pic_url: str
    follower_count: int

    # settings
    models: list[str] = []
    relevant_accounts: dict[str, bool] = {}  # handle -> isverified
    queries: list[str] | list[list[str]] = []  # Can be list of strings (legacy) or list of [query, summary] pairs
    max_tweets_retrieve: int = 30
    number_of_generations: int = 2
    intent: str = ""  # User's intent for filtering and query generation

    # metrics
    lifetime_new_follows: int = 0
    lifetime_posts: int = 0
    scrolling_time_saved: int = 0
    scrapes_left: int | None = None
    posts_left: int | None = None

    # seen tweets tracking (to prevent showing duplicate tweets)
    seen_tweets: dict[str, str] = {}  # tweet_id -> timestamp


class Source(BaseModel):
    type: Literal["account", "query"]
    value: str
    summary: str | None = None  # Short 1-2 word summary for queries


class ScrapedTweet(BaseModel):
    id: str
    text: str
    thread: list[str] = []
    other_replies: list[OtherReply] = []  # Top replies from other users

    # retrieval info
    scraped_from: Source | None = None
    cache_id: str

    # tweet metadata
    created_at: str  # Date string in Twitter format
    url: str
    username: str
    handle: str
    author_profile_pic_url: str
    quoted_tweet: QuotedTweet | None = None

    # attachments
    media: list[MediaItem] = []  # List of media items with type, url, and alt_text

    # performance
    likes: int
    retweets: int
    quotes: int
    replies: int
    impressions: int = 0  # view/impression count
    followers: int  # follower count of author at time of tweet
    score: float  # calculated engagement score

    # replies - list of tuples: (reply_text, model_name)
    generated_replies: list[tuple[str, str]] = []
    edited: bool = False  # True if user has edited any generated reply
    seen: bool = False  # True if user has scrolled past this tweet in the UI


MonitoringState = Literal["active", "warm", "cold"]
TweetSource = Literal["app_posted", "external"]
ResurrectionSource = Literal["none", "notification", "search"]
CommentStatus = Literal["pending", "replied", "skipped"]
PostType = Literal["original", "reply", "comment_reply"]


class PostedTweet(BaseModel):
    id: str
    text: str

    # performance
    likes: int
    retweets: int
    quotes: int
    replies: int
    impressions: int = 0  # view/impression count

    # metadata
    created_at: str  # ISO 8601 datetime string
    url: str
    last_metrics_update: str | None = None  # ISO 8601 datetime string

    # Media attachments (photos only - videos/GIFs filtered)
    media: list[dict] = Field(default_factory=list)  # [{type: "photo", url: "...", alt_text: "..."}]

    # Parent chain tracking - array of ancestor IDs from root to immediate parent
    parent_chain: list[str] = Field(default_factory=list)

    # Legacy fields (keep for frontend compatibility)
    response_to_thread: list[str] = Field(default_factory=list)  # Thread of the original tweet
    responding_to: str = ""  # Handle of the person being replied to
    replying_to_pfp: str = ""  # Profile pic URL of person being replied to
    original_tweet_url: str = ""  # URL of the original tweet

    # Source tracking
    source: TweetSource = "app_posted"

    # Monitoring state machine
    monitoring_state: MonitoringState = "active"

    # Timestamps for monitoring
    last_activity_at: str | None = None
    last_deep_scrape: str | None = None
    last_shallow_scrape: str | None = None

    # Metrics snapshot for activity detection
    last_reply_count: int | None = None
    last_quote_count: int | None = None
    last_like_count: int | None = None
    last_retweet_count: int | None = None

    # Resurrection info
    resurrected_via: ResurrectionSource = "none"

    # Reply tracking for activity detection
    last_scraped_reply_ids: list[str] = Field(default_factory=list)

    # Post classification and engagement
    post_type: PostType = "reply"  # original, reply, or comment_reply
    score: int = 0  # engagement score: likes + 2*retweets + 3*quotes + replies


class CommentRecord(BaseModel):
    """A comment (reply from someone else) on user's tweet or thread."""
    id: str
    text: str

    # Commenter info
    handle: str
    username: str
    author_profile_pic_url: str = ""
    followers: int = 0

    # performance
    likes: int = 0
    retweets: int = 0
    quotes: int = 0
    replies: int = 0
    impressions: int = 0

    # metadata
    created_at: str
    url: str
    last_metrics_update: str | None = None

    # Parent chain tracking
    parent_chain: list[str] = Field(default_factory=list)
    in_reply_to_status_id: str | None = None  # Immediate parent tweet ID

    # Comment-specific
    status: CommentStatus = "pending"
    generated_replies: list[tuple[str, str]] = Field(default_factory=list)  # [(reply_text, model_name)]
    edited: bool = False

    # Monitoring (same as PostedTweet)
    source: TweetSource = "external"
    monitoring_state: MonitoringState = "active"
    last_activity_at: str | None = None
    last_deep_scrape: str | None = None
    last_shallow_scrape: str | None = None
    last_reply_count: int | None = None
    last_quote_count: int | None = None
    last_like_count: int | None = None
    last_retweet_count: int | None = None
    resurrected_via: ResurrectionSource = "none"
    last_scraped_reply_ids: list[str] = Field(default_factory=list)

    # Optional fields from scraping
    thread: list[str] = Field(default_factory=list)
    other_replies: list["OtherReply"] = Field(default_factory=list)
    quoted_tweet: "QuotedTweet | None" = None
    media: list["MediaItem"] = Field(default_factory=list)


class Token(BaseModel):
    access_token: str
    refresh_token: str
    expires_at: float


class BrowserState(BaseModel):
    cookies: list[dict]
    origins: list[dict]
    timestamp: str  # ISO 8601 datetime string


# not using this for now
class Origin(BaseModel):
    origin: str
    local_storage: list


# not using this for now
class Cookie(BaseModel):
    domain: str
    expirationDate: float | None
    hostOnly: bool
    httpOnly: bool
    name: str
    path: str
    sameSite: str
    secure: bool
    session: bool
    storeId: str
    value: str


# Request models for user API endpoints
class RelevantAccountModel(BaseModel):
    handle: str
    validated: bool


class UpdateSettingsRequest(BaseModel):
    queries: list[str] | None = None
    relevant_accounts: dict[str, bool] | None = None
    max_tweets_retrieve: int | None = None
    number_of_generations: int | None = None
    # models are NOT accepted here - use dedicated model management endpoint


class UpdateEmailRequest(BaseModel):
    email: str


class RemoveQueryRequest(BaseModel):
    query: str


class UpdateModelsRequest(BaseModel):
    models: list[str]
