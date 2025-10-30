
from typing import Literal

from pydantic import BaseModel


class MediaItem(BaseModel):
  type: str  # "photo", "video", "animated_gif"
  url: str
  alt_text: str = ""


class QuotedTweet(BaseModel):
  text: str
  author_handle: str
  author_name: str
  media: list[MediaItem] = []


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
  relevant_accounts: dict[str, bool] = {} # handle -> isverified
  queries: list[str] = []
  max_tweets_retrieve: int = 30
  number_of_generations: int = 2

  # metrics
  lifetime_new_follows: int = 0
  lifetime_posts: int = 0
  scrolling_time_saved: int = 0
  scrapes_left: int | None = None
  posts_left: int | None = None


class Source(BaseModel):
  type: Literal["account", "query"]
  value: str

class ScrapedTweet(BaseModel):
  id: str
  text: str
  thread: list[str] = []

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
  followers: int  # follower count of author at time of tweet
  score: float  # calculated engagement score

  # replies - list of tuples: (reply_text, model_name)
  generated_replies: list[tuple[str, str]] = []
  
  
class PostedTweet(BaseModel):
  id: str
  text: str

  # performance
  likes: int
  retweets: int
  quotes: int
  replies: int

  # metadata
  created_at: str  # ISO 8601 datetime string
  url: str
  last_metrics_update: str  # ISO 8601 datetime string

  # data about tweet it's responding to
  response_to_thread: list[str]  # Thread of the original tweet
  responding_to: str  # Handle of the person being replied to
  replying_to_pfp: str  # Profile pic URL of person being replied to
  original_tweet_url: str  # URL of the original tweet
  
  
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
  