from typing import Any, Literal

from pydantic import BaseModel, Field


class MediaItem(BaseModel):
    type: str  # "photo", "video", "animated_gif"
    url: str
    alt_text: str = ""


class QuotedTweet(BaseModel):
    text: str
    author_handle: str
    author_name: str
    author_profile_pic_url: str = ""
    url: str = ""
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
    ideal_num_posts: int = 30  # Target number of tweets to retrieve (will aim for ±10 of this)
    number_of_generations: int = 2
    min_impressions_filter: int = 2000  # Minimum impressions required for discovery tweets (auto-adjusted)
    manual_minimum_impressions: int | None = None  # User override - disables auto-adjustment when set
    intent: str = ""  # User's intent for filtering and query generation
    intent_filter_examples: list[dict] = []  # Up to 10 examples of posts user replied to, cleared when intent changes
    intent_filter_last_updated: str | None = None  # ISO 8601 timestamp of when intent was last updated

    # metrics
    lifetime_new_follows: int = 0
    lifetime_posts: int = 0
    scrolling_time_saved: int = 0
    scrapes_left: int | None = None
    posts_left: int | None = None

    # seen tweets tracking (to prevent showing duplicate tweets)
    seen_tweets: dict[str, str] = {}  # tweet_id -> timestamp

    # survey/onboarding data
    survey_data: dict = {}  # Flexible JSON field for survey responses (e.g., interested_socials)

    # post queue - tweets waiting to be posted
    post_queue: list[dict] = Field(default_factory=list)  # List of PendingPost dicts


class Source(BaseModel):
    type: Literal["account", "query", "home_timeline"]
    value: str
    summary: str | None = None  # Short 1-2 word summary for queries


class ScrapedTweet(BaseModel):
    id: str
    text: str
    thread: list[str] = []
    thread_ids: list[str] = []  # Tweet IDs in the thread (for auto-liking)
    other_replies: list[OtherReply] = []  # Top replies from other users

    # retrieval info
    scraped_from: Source | None = None
    cache_id: str = ""  # Generated when written to cache

    # tweet metadata
    created_at: str  # Date string in Twitter format
    url: str
    username: str
    handle: str
    author_profile_pic_url: str
    quoted_tweet: QuotedTweet | None = None
    conversation_id: str = ""  # ID of the root tweet in this conversation

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

    # replies - list of tuples: (reply_text, model_name, prompt_variant)
    # Accepts both legacy 2-tuples and new 3-tuples
    generated_replies: list[tuple[str, str] | tuple[str, str, str]] = []
    edited: bool = False  # True if user has edited any generated reply
    seen: bool = False  # True if user has scrolled past this tweet in the UI
    post_pending: bool = False  # True if this tweet is queued for posting


MonitoringState = Literal["active", "warm", "cold"]
TweetSource = Literal["app_posted", "external"]
ResurrectionSource = Literal["none", "notification", "search"]
CommentStatus = Literal["pending", "replied", "skipped"]
PostType = Literal["original", "reply", "comment_reply"]
EngagementType = Literal["reply", "quote_tweet"]
PendingPostType = Literal["reply", "comment_reply"]


class PendingPost(BaseModel):
    """A tweet queued for posting."""
    type: PendingPostType  # "reply" for discovered tweets, "comment_reply" for comments
    response_to: str  # ID of the tweet/comment being replied to
    reply: str  # The actual reply text
    reply_index: int | None = None  # Which generated reply was selected
    model: str | None = None  # Model used to generate the reply
    prompt_variant: str | None = None  # Prompt variant used

    # Context for displaying in PostingInProgress
    media: list[MediaItem] = Field(default_factory=list)
    parent_chain: list[str] = Field(default_factory=list)
    response_to_thread: list[str] = Field(default_factory=list)
    responding_to: str = ""  # Handle of person being replied to
    replying_to_pfp: str = ""  # Profile pic URL
    original_tweet_url: str = ""

    # Timestamps
    queued_at: str = ""  # ISO 8601 timestamp when added to queue


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

    # Quoted tweet (if this tweet quotes another)
    quoted_tweet: "QuotedTweet | None" = None

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
    generated_replies: list[tuple[str, str] | tuple[str, str, str]] = Field(default_factory=list)  # [(reply_text, model_name, prompt_variant)]
    edited: bool = False
    post_pending: bool = False  # True if this comment reply is queued for posting

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

    # Engagement type: "reply" for regular replies, "quote_tweet" for quote tweets
    engagement_type: "EngagementType" = "reply"


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
    user_id: str | None = None  # Twitter user ID (fetched when account is added)


class UpdateSettingsRequest(BaseModel):
    # Queries can be plain strings or [query, summary] tuples
    queries: list[str | list[str]] | None = None
    # relevant_accounts: {handle: {"user_id": str | None, "validated": bool}}
    relevant_accounts: dict[str, dict[str, Any]] | None = None
    ideal_num_posts: int | None = None
    number_of_generations: int | None = None
    min_impressions_filter: int | None = None
    manual_minimum_impressions: int | None = None
    # models are NOT accepted here - use dedicated model management endpoint


class UpdateEmailRequest(BaseModel):
    email: str


class UpdateSurveyDataRequest(BaseModel):
    survey_data: dict  # Flexible JSON field for survey responses


class RemoveQueryRequest(BaseModel):
    query: str


class UpdateModelsRequest(BaseModel):
    models: list[str]
