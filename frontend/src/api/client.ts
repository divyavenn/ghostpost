import { type ReplyData } from '../components/ReplyDisplay';
import { type PostedData } from '../components/PostedDisplay';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'https://x.ghostposter.app/api';

// Media item type
export interface MediaItem {
  type: string;  // "photo", "video", "animated_gif"
  url: string;
  alt_text?: string;
}

// Quoted tweet type
export interface QuotedTweet {
  text: string;
  author_handle: string;
  author_name: string;
  author_profile_pic_url?: string;
  url?: string;
  media?: MediaItem[];
}

// Comment data type
export interface CommentData {
  id: string;
  text: string;
  handle: string;
  username: string;
  author_profile_pic_url: string;
  followers: number;
  likes: number;
  retweets: number;
  quotes: number;
  replies: number;
  impressions: number;
  created_at: string;
  url: string;
  parent_chain: string[];
  in_reply_to_status_id: string | null;
  status: 'pending' | 'replied' | 'skipped';
  generated_replies: Array<[string, string]>; // [(text, model), ...]
  edited: boolean;
  thread?: string[];
  other_replies?: Array<{
    text: string;
    author_handle: string;
    author_name: string;
    likes: number;
  }>;
  media?: MediaItem[];
  quoted_tweet?: QuotedTweet | null;
  engagement_type?: 'reply' | 'quote_tweet'; // "reply" for regular replies, "quote_tweet" for quote tweets
}

export interface ThreadContext {
  id: string;
  text: string;
  handle: string;
  username: string;
  author_profile_pic_url: string;
  is_user: boolean;
  deleted?: boolean;
  media?: MediaItem[];
}

// Post data for grouped comments view
export interface PostSummary {
  id: string;
  text: string;
  url: string;
  created_at: string;
  likes: number;
  retweets: number;
  quotes: number;
  replies: number;
  impressions: number;
  response_to_thread: string[];
  responding_to: string;
  original_tweet_url: string;
  media: Array<{ type: string; url: string; alt_text?: string }>;
}

// Comment with thread context for grouped view
export interface CommentWithContext extends CommentData {
  thread_context: ThreadContext[];
}

// A post with all its comments grouped together
export interface PostWithComments {
  post: PostSummary;
  comments: CommentWithContext[];
  total_pending: number;
}
console.log('Using API_BASE_URL:', API_BASE_URL);

// Flag to prevent multiple auth redirects
let isRedirecting = false;

// Helper function to check for authentication errors and redirect to login
async function handleAuthError(response: Response): Promise<void> {
  if (response.status === 401) {
    // Check if this is an authentication token issue
    const errorText = await response.clone().text();
    let shouldLogout = false;

    try {
      const errorData = JSON.parse(errorText);
      // Check for our custom AUTHENTICATION_REQUIRED error code
      if (errorData.detail === 'AUTHENTICATION_REQUIRED') {
        shouldLogout = true;
      }
    } catch {
      // If we can't parse the error, assume 401 means logout needed
      shouldLogout = true;
    }

    if (shouldLogout) {
      // Prevent multiple redirects
      if (isRedirecting) {
        throw new Error('Authentication required');
      }
      isRedirecting = true;

      // Clear stored username and redirect to login silently
      localStorage.removeItem('username');
      window.location.href = '/login';
      throw new Error('Authentication required');
    }
  }
}

export interface AuthResponse {
  auth_url: string;
  state: string;
  session_id: string;
  message: string;
  debugger_url?: string;  // Browserbase live debugger URL
}

export interface BrowserLoginResponse {
  session_id: string;
  debugger_url: string;
  login_url: string;
  message: string;
}

export interface BrowserLoginStatus {
  status: 'pending' | 'complete' | 'error';
  username?: string;
  error?: string;
  message?: string;
  current_url?: string;
}

export interface TwitterStatus {
  connected: boolean;
  twitter_handle: string | null;
  expires_at: string | null;
}

// Query can be either a plain string or [query, summary] tuple
export type QueryItem = string | [string, string];

export interface UserSettings {
  queries: QueryItem[];
  relevant_accounts: Record<string, boolean>; // {handle: validated}
  ideal_num_posts: number;
  number_of_generations: number;
  min_impressions_filter?: number;
  manual_minimum_impressions?: number | null;
  models?: string[]; // Read-only, managed via dedicated endpoint
  intent?: string; // User's intent for filtering and query generation
}

// Helper to extract query string and summary from QueryItem
export function parseQueryItem(item: QueryItem): { query: string; summary: string } {
  if (Array.isArray(item)) {
    return { query: item[0], summary: item[1] };
  }
  // For plain strings, generate a summary from first 2 words
  const words = item.split(' ').filter(w => !w.startsWith('-') && !w.startsWith('('));
  return { query: item, summary: words.slice(0, 2).join(' ') || 'Query' };
}

export interface SurveyData {
  interested_socials?: string[];
  [key: string]: unknown;
}

export interface UserInfo {
  handle: string;
  username: string;
  profile_pic_url: string;
  follower_count: number;
  lifetime_posts: number;
  lifetime_new_follows: number;
  scrolling_time_saved: number;
  email?: string;
  models?: string[];
  account_type?: 'trial' | 'poster' | 'premium';
  uid?: number;
  scrapes_left?: number;
  posts_left?: number;
  min_impressions_filter?: number;
  manual_minimum_impressions?: number | null;
  survey_data?: SurveyData;
}

// Job status types
export interface JobStatus {
  status: 'idle' | 'running' | 'complete' | 'error';
  phase: string;
  percentage: number;
  details?: string | null;  // Human-readable details (e.g., "@handle", "keyword", "your feed")
  progress?: { current: number; total: number };
  triggered_by?: string | null;
  error?: string | null;
  results?: Record<string, unknown>;
  started_at?: string | null;
}

export interface AllJobsStatus {
  jobs: {
    find_and_reply_to_new_posts: JobStatus;
    find_user_activity: JobStatus;
    find_and_reply_to_engagement: JobStatus;
  };
  overall: {
    status: 'idle' | 'running' | 'complete' | 'error';
    running_jobs: string[];
    completed_jobs: string[];
    error_jobs: string[];
  };
}

export interface ValidationDelayConfig {
  delay_seconds: number;
  delay_ms: number;
  tier: string;
}

export const api = {
  // Config endpoints
  getValidationDelay: async (): Promise<ValidationDelayConfig> => {
    const response = await fetch(`${API_BASE_URL}/user/config/validation-delay`);
    if (!response.ok) throw new Error('Failed to get validation delay config');
    return response.json();
  },

  // Auth endpoints
  startTwitterOAuth: async (redirectTo?: string): Promise<AuthResponse> => {
    const response = await fetch(`${API_BASE_URL}/auth/twitter/start`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        redirect_to: redirectTo
      }),
    });
    if (!response.ok) throw new Error('Failed to start OAuth');
    return response.json();
  },

  getTwitterStatus: async (): Promise<TwitterStatus> => {
    const response = await fetch(`${API_BASE_URL}/auth/twitter/status`);
    if (!response.ok) throw new Error('Failed to get Twitter status');
    return response.json();
  },

  startBrowserLogin: async (): Promise<BrowserLoginResponse> => {
    const response = await fetch(`${API_BASE_URL}/auth/twitter/browser-login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });
    if (!response.ok) throw new Error('Failed to start browser login');
    return response.json();
  },

  checkBrowserLogin: async (sessionId: string): Promise<BrowserLoginStatus> => {
    const response = await fetch(`${API_BASE_URL}/auth/twitter/browser-login/check/${sessionId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });
    if (!response.ok) throw new Error('Failed to check browser login');
    return response.json();
  },

  getLoginUrl: async (frontendUrl: string): Promise<{ login_url: string; session_id: string }> => {
    const response = await fetch(`${API_BASE_URL}/auth/twitter/login-url`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        frontend_url: frontendUrl
      }),
    });
    if (!response.ok) throw new Error('Failed to get login URL');
    return response.json();
  },

  checkCookieStatus: async (sessionId: string): Promise<{ status: string; username?: string; verified?: boolean }> => {
    const response = await fetch(`${API_BASE_URL}/auth/twitter/cookie-status/${sessionId}`);
    if (!response.ok) throw new Error('Failed to check cookie status');
    return response.json();
  },

  // Tweet cache endpoints
  getTweetsCache: async (username: string): Promise<ReplyData[]> => {
    const response = await fetch(`${API_BASE_URL}/tweets/${username}`);
    await handleAuthError(response);
    if (!response.ok) throw new Error('Failed to fetch tweets');
    return response.json();
  },

  editTweetReply: async (username: string, tweetId: string, newReply: string, replyIndex: number = 0): Promise<void> => {
    const response = await fetch(`${API_BASE_URL}/tweets/${username}/${tweetId}/reply`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ new_reply: newReply, reply_index: replyIndex }),
    });
    if (!response.ok) throw new Error('Failed to edit reply');
  },

  deleteTweet: async (username: string, tweetId: string, logDeletion: boolean = true): Promise<void> => {
    const response = await fetch(`${API_BASE_URL}/tweets/${username}/${tweetId}?log_deletion=${logDeletion}`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error('Failed to delete tweet');
  },

  postReply: async (username: string, text: string, tweetId: string, cacheId?: string, replyIndex?: number): Promise<{ data: { id: string }; posted_tweet_id?: string }> => {
    const response = await fetch(`${API_BASE_URL}/post/reply?username=${encodeURIComponent(username)}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        text,
        tweet_id: tweetId,
        cache_id: cacheId,
        reply_index: replyIndex,
      }),
    });
    await handleAuthError(response);
    if (!response.ok) throw new Error('Failed to post reply');
    return response.json();
  },

  /**
   * Add a tweet to the posting queue. This will:
   * 1. Add to the persistent queue (survives browser close)
   * 2. Mark source as post_pending
   * 3. Immediately post to Twitter
   * 4. On success: remove from queue, delete from source
   * 5. On failure: remove from queue, restore post_pending
   */
  addToPostQueue: async (username: string, payload: {
    type: 'reply' | 'comment_reply';
    response_to: string;
    reply: string;
    reply_index?: number;
    model?: string;
    prompt_variant?: string;
    media?: Array<{ type: string; url: string; alt_text?: string }>;
    parent_chain?: string[];
    response_to_thread?: string[];
    responding_to?: string;
    replying_to_pfp?: string;
    original_tweet_url?: string;
  }): Promise<{
    message: string;
    status: 'posted' | 'duplicate' | 'failed';
    posted_tweet_id?: string;
    data?: unknown;
  }> => {
    const response = await fetch(`${API_BASE_URL}/post/queue?username=${encodeURIComponent(username)}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
    await handleAuthError(response);
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to post' }));
      throw new Error(error.detail || 'Failed to post');
    }
    return response.json();
  },

  /**
   * Get pending posts formatted for display in PostedTab
   */
  getPendingPosts: async (username: string): Promise<{
    pending_posts: Array<{
      id: string;
      originalTweetId: string;
      text: string;
      respondingTo: string;
      originalTweetUrl: string;
      originalThreadText: string[];
      source: 'discovered' | 'comments';
      startedAt: string;
      replyingToPfp: string;
      parentChain: string[];
      media: Array<{ type: string; url: string; alt_text?: string }>;
    }>;
    count: number;
  }> => {
    const response = await fetch(`${API_BASE_URL}/post/pending?username=${encodeURIComponent(username)}`);
    if (!response.ok) throw new Error('Failed to get pending posts');
    return response.json();
  },

  deletePostedTweet: async (username: string, tweetId: string): Promise<{ message: string; tweet_id: string; deleted: boolean }> => {
    const response = await fetch(`${API_BASE_URL}/post/tweet/${tweetId}?username=${encodeURIComponent(username)}`, {
      method: 'DELETE',
    });
    await handleAuthError(response);
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to delete tweet' }));
      throw new Error(error.detail || 'Failed to delete tweet');
    }
    return response.json();
  },

  readTweets: async (username: string, payload?: {
    usernames?: string[];
    queries?: string[];
    max_scrolls?: number;
    max_tweets?: number;
  }): Promise<{ message: string; status: string; background_task: string }> => {
    // Use 1 hour timeout for scraping operations
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3600000); // 1 hour

    try {
      const response = await fetch(`${API_BASE_URL}/read/${encodeURIComponent(username)}/tweets`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload || {}),
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      await handleAuthError(response);
      if (!response.ok) throw new Error('Failed to read tweets');
      return response.json();
    } catch (error) {
      clearTimeout(timeoutId);
      if (error instanceof Error && error.name === 'AbortError') {
        throw new Error('Scraping timed out after 1 hour. The scraping may still be running in the background.');
      }
      throw error;
    }
  },

  // NOTE: getScrapingStatus removed - use getJobsStatus instead for unified status tracking

  generateReplies: async (username: string, payload?: {
    delay_seconds?: number;
    overwrite?: boolean;
  }): Promise<{ message: string; total_tweets: number; replies_generated: number }> => {
    const response = await fetch(`${API_BASE_URL}/generate/${encodeURIComponent(username)}/replies`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload || {}),
    });
    await handleAuthError(response);
    if (!response.ok) throw new Error('Failed to generate replies');
    return response.json();
  },

  regenerateSingleReply: async (username: string, tweetId: string): Promise<{ message: string; tweet_id: string; new_replies: Array<[string, string]> }> => {
    const response = await fetch(`${API_BASE_URL}/generate/${encodeURIComponent(username)}/replies/${encodeURIComponent(tweetId)}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });
    await handleAuthError(response);
    if (!response.ok) throw new Error('Failed to regenerate reply');
    return response.json();
  },

  // User settings endpoints
  getUserInfo: async (handle: string): Promise<UserInfo> => {
    const response = await fetch(`${API_BASE_URL}/user/${encodeURIComponent(handle)}/info`);
    await handleAuthError(response);
    if (!response.ok) throw new Error('Failed to get user info');
    return response.json();
  },

  updateUserEmail: async (handle: string, email: string): Promise<{ message: string; email: string }> => {
    const response = await fetch(`${API_BASE_URL}/user/${encodeURIComponent(handle)}/email`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ email }),
    });
    if (!response.ok) throw new Error('Failed to update user email');
    return response.json();
  },

  updateSurveyData: async (handle: string, surveyData: SurveyData): Promise<{ message: string; survey_data: SurveyData }> => {
    const response = await fetch(`${API_BASE_URL}/user/${encodeURIComponent(handle)}/survey-data`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ survey_data: surveyData }),
    });
    if (!response.ok) throw new Error('Failed to update survey data');
    return response.json();
  },

  getUserSettings: async (handle: string): Promise<UserSettings> => {
    const response = await fetch(`${API_BASE_URL}/user/${encodeURIComponent(handle)}/settings`);
    await handleAuthError(response);
    if (!response.ok) throw new Error('Failed to get user settings');
    return response.json();
  },

  updateUserSettings: async (handle: string, settings: Partial<UserSettings>): Promise<{ message: string; settings: UserSettings }> => {
    const response = await fetch(`${API_BASE_URL}/user/${encodeURIComponent(handle)}/settings`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(settings),
    });
    if (!response.ok) throw new Error('Failed to update user settings');
    return response.json();
  },

  addAccount: async (handle: string, accountHandle: string, validated: boolean): Promise<{ message: string; settings: UserSettings }> => {
    const response = await fetch(`${API_BASE_URL}/user/${encodeURIComponent(handle)}/settings/account`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ handle: accountHandle, validated }),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to add account' }));
      throw new Error(error.detail || 'Failed to add account');
    }
    return response.json();
  },

  updateAccountValidation: async (handle: string, account: string, validated: boolean): Promise<{ message: string; settings: UserSettings }> => {
    const response = await fetch(`${API_BASE_URL}/user/${encodeURIComponent(handle)}/settings/account/${encodeURIComponent(account)}/validation?validated=${validated}`, {
      method: 'PATCH',
    });
    if (!response.ok) throw new Error('Failed to update account validation');
    return response.json();
  },

  removeAccount: async (handle: string, account: string): Promise<{ message: string; settings: UserSettings }> => {
    const response = await fetch(`${API_BASE_URL}/user/${encodeURIComponent(handle)}/settings/account/${encodeURIComponent(account)}`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error('Failed to remove account');
    return response.json();
  },

  removeQuery: async (handle: string, query: string): Promise<{ message: string; settings: UserSettings }> => {
    const response = await fetch(`${API_BASE_URL}/user/${encodeURIComponent(handle)}/settings/query`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ query }),
    });
    if (!response.ok) throw new Error('Failed to remove query');
    return response.json();
  },

  validateTwitterHandle: async (username: string, handle: string): Promise<{ valid: boolean; handle: string; data?: unknown; error?: string }> => {
    // Use a longer timeout to allow for retry logic on the backend (up to 30 seconds)
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);

    try {
      const response = await fetch(
        `${API_BASE_URL}/user/${encodeURIComponent(username)}/validate/${encodeURIComponent(handle)}`,
        { signal: controller.signal }
      );
      clearTimeout(timeoutId);

      if (!response.ok) throw new Error('Failed to validate Twitter handle');
      return response.json();
    } catch (error) {
      clearTimeout(timeoutId);
      if (error instanceof Error && error.name === 'AbortError') {
        return {
          valid: false,
          handle,
          error: 'Validation timed out. The Twitter API may be rate limiting requests. Please try again in a moment.'
        };
      }
      throw error;
    }
  },

  validateAllAccounts: async (username: string): Promise<{ message: string; validated_count: number }> => {
    const response = await fetch(`${API_BASE_URL}/user/${encodeURIComponent(username)}/validate-accounts`, {
      method: 'POST'
    });
    if (!response.ok) throw new Error('Failed to validate accounts');
    return response.json();
  },

  updateIntent: async (username: string, intent: string): Promise<{ message: string; intent: string; background_task: string }> => {
    const response = await fetch(`${API_BASE_URL}/intent/${encodeURIComponent(username)}/update`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ intent }),
    });
    if (!response.ok) throw new Error('Failed to update intent');
    return response.json();
  },

  runBackgroundJobs: async (username: string): Promise<{ message: string; username: string; jobs: string[]; status: string; triggered_by: string }> => {
    const response = await fetch(`${API_BASE_URL}/jobs/${encodeURIComponent(username)}/run-background-jobs`, {
      method: 'POST',
    });
    if (!response.ok) throw new Error('Failed to start background jobs');
    return response.json();
  },

  // Posted tweets endpoints
  getPostedTweets: async (username: string, limit: number = 50, offset: number = 0): Promise<{ username: string; total: number; count: number; limit: number; offset: number; tweets: PostedData[] }> => {
    const response = await fetch(`${API_BASE_URL}/performance/${encodeURIComponent(username)}/posted-tweets?limit=${limit}&offset=${offset}`);
    await handleAuthError(response);
    if (!response.ok) throw new Error('Failed to get posted tweets');
    return response.json();
  },

  checkTweetPerformance: async (username: string, tweetIds: string[]): Promise<{ message: string; updated_count: number; metrics: Array<{ id: string; likes: number; retweets: number; quotes: number; replies: number }> }> => {
    const response = await fetch(`${API_BASE_URL}/performance/${encodeURIComponent(username)}/check-performance`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        tweet_ids: tweetIds
      }),
    });
    await handleAuthError(response);
    if (!response.ok) throw new Error('Failed to check tweet performance');
    return response.json();
  },

  // Comments endpoints
  getComments: async (username: string, limit: number = 20, offset: number = 0, status?: string): Promise<{
    comments: CommentData[];
    total: number;
    limit: number;
    offset: number;
    has_more: boolean;
  }> => {
    let url = `${API_BASE_URL}/comments/${encodeURIComponent(username)}?limit=${limit}&offset=${offset}`;
    if (status) {
      url += `&status=${encodeURIComponent(status)}`;
    }
    const response = await fetch(url);
    await handleAuthError(response);
    if (!response.ok) throw new Error('Failed to get comments');
    return response.json();
  },

  getCommentsGroupedByPost: async (username: string, status: string = 'pending'): Promise<{
    posts_with_comments: PostWithComments[];
    total_posts: number;
    total_comments: number;
  }> => {
    const url = `${API_BASE_URL}/comments/${encodeURIComponent(username)}/grouped?status=${encodeURIComponent(status)}`;
    const response = await fetch(url);
    await handleAuthError(response);
    if (!response.ok) throw new Error('Failed to get grouped comments');
    return response.json();
  },

  getComment: async (username: string, commentId: string): Promise<{
    comment: CommentData;
    thread_context: ThreadContext[];
  }> => {
    const response = await fetch(`${API_BASE_URL}/comments/${encodeURIComponent(username)}/${encodeURIComponent(commentId)}`);
    if (!response.ok) throw new Error('Failed to get comment');
    return response.json();
  },

  updateCommentStatus: async (username: string, commentId: string, status: 'pending' | 'replied' | 'skipped'): Promise<{
    message: string;
    comment_id: string;
    new_status: string;
  }> => {
    const response = await fetch(`${API_BASE_URL}/comments/${encodeURIComponent(username)}/${encodeURIComponent(commentId)}/status`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ status }),
    });
    if (!response.ok) throw new Error('Failed to update comment status');
    return response.json();
  },

  postCommentReply: async (username: string, commentId: string, text: string, replyIndex?: number): Promise<{
    message: string;
    comment_id: string;
    posted_tweet_id: string;
  }> => {
    const response = await fetch(`${API_BASE_URL}/comments/${encodeURIComponent(username)}/${encodeURIComponent(commentId)}/reply`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ text, reply_index: replyIndex }),
    });
    await handleAuthError(response);
    if (!response.ok) throw new Error('Failed to post comment reply');
    return response.json();
  },

  skipComment: async (username: string, commentId: string): Promise<{
    message: string;
    comment_id: string;
  }> => {
    const response = await fetch(`${API_BASE_URL}/comments/${encodeURIComponent(username)}/${encodeURIComponent(commentId)}`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error('Failed to skip comment');
    return response.json();
  },

  getCommentsStats: async (username: string): Promise<{
    total: number;
    pending: number;
    replied: number;
    skipped: number;
  }> => {
    const response = await fetch(`${API_BASE_URL}/comments/${encodeURIComponent(username)}/stats/summary`);
    if (!response.ok) throw new Error('Failed to get comments stats');
    return response.json();
  },

  generateCommentReplies: async (username: string, commentIds?: string[], overwrite?: boolean): Promise<{
    message: string;
    processed: number;
    skipped: number;
    errors: number;
    total_replies_generated: number;
  }> => {
    const response = await fetch(`${API_BASE_URL}/comments/${encodeURIComponent(username)}/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ comment_ids: commentIds, overwrite }),
    });
    await handleAuthError(response);
    if (!response.ok) throw new Error('Failed to generate comment replies');
    return response.json();
  },

  regenerateCommentReply: async (username: string, commentId: string): Promise<{
    message: string;
    comment_id: string;
    new_replies: Array<[string, string]>;
  }> => {
    const response = await fetch(`${API_BASE_URL}/comments/${encodeURIComponent(username)}/generate/${encodeURIComponent(commentId)}`, {
      method: 'POST',
    });
    await handleAuthError(response);
    if (!response.ok) throw new Error('Failed to regenerate comment reply');
    return response.json();
  },

  editCommentReply: async (username: string, commentId: string, newReply: string, replyIndex: number = 0): Promise<{
    message: string;
    comment_id: string;
    reply_index: number;
    new_reply: string;
  }> => {
    const response = await fetch(`${API_BASE_URL}/comments/${encodeURIComponent(username)}/${encodeURIComponent(commentId)}/edit`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ new_reply: newReply, reply_index: replyIndex }),
    });
    if (!response.ok) throw new Error('Failed to edit comment reply');
    return response.json();
  },

  startEngagementMonitoring: async (username: string): Promise<{
    message: string;
    username: string;
    handle: string;
  }> => {
    const response = await fetch(`${API_BASE_URL}/comments/${encodeURIComponent(username)}/monitor/start`, {
      method: 'POST',
    });
    if (!response.ok) throw new Error('Failed to start engagement monitoring');
    return response.json();
  },

  // Mark tweets as seen (user scrolled past them)
  markTweetsSeen: async (username: string, tweetIds: string[]): Promise<{
    message: string;
    marked_count: number;
  }> => {
    const response = await fetch(`${API_BASE_URL}/tweets/${encodeURIComponent(username)}/mark-seen`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ tweet_ids: tweetIds }),
    });
    if (!response.ok) throw new Error('Failed to mark tweets as seen');
    return response.json();
  },

  // Mark tweets as NOT seen (protect freshly scraped tweets from being cleared)
  markTweetsUnseen: async (username: string, tweetIds: string[]): Promise<{
    message: string;
    marked_count: number;
  }> => {
    const response = await fetch(`${API_BASE_URL}/tweets/${encodeURIComponent(username)}/mark-unseen`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ tweet_ids: tweetIds }),
    });
    if (!response.ok) throw new Error('Failed to mark tweets as unseen');
    return response.json();
  },

  // Purge seen (but unedited) tweets from cache
  purgeSeenTweets: async (username: string): Promise<{
    message: string;
    removed_count: number;
  }> => {
    const response = await fetch(`${API_BASE_URL}/tweets/${encodeURIComponent(username)}/purge-seen`, {
      method: 'POST',
    });
    if (!response.ok) throw new Error('Failed to purge seen tweets');
    return response.json();
  },

  // Job status endpoints
  getJobsStatus: async (username: string): Promise<AllJobsStatus> => {
    const response = await fetch(`${API_BASE_URL}/jobs/${encodeURIComponent(username)}/status`);
    await handleAuthError(response);
    if (!response.ok) throw new Error('Failed to get jobs status');
    return response.json();
  },

  getJobStatus: async (username: string, jobName: string): Promise<JobStatus> => {
    const response = await fetch(`${API_BASE_URL}/jobs/${encodeURIComponent(username)}/status/${encodeURIComponent(jobName)}`);
    if (!response.ok) throw new Error('Failed to get job status');
    return response.json();
  },

  // Billing endpoints
  createCheckoutSession: async (username: string): Promise<{ checkout_url: string; session_id: string }> => {
    const response = await fetch(`${API_BASE_URL}/billing/${encodeURIComponent(username)}/create-checkout-session`, {
      method: 'POST',
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to create checkout session' }));
      throw new Error(error.detail || 'Failed to create checkout session');
    }
    return response.json();
  },

  getBillingStatus: async (username: string): Promise<{ username: string; account_type: string; is_subscribed: boolean }> => {
    const response = await fetch(`${API_BASE_URL}/billing/${encodeURIComponent(username)}/status`);
    if (!response.ok) throw new Error('Failed to get billing status');
    return response.json();
  },

  sendPremiumInquiry: async (email: string, phone?: string, twitterHandle?: string): Promise<{ message: string }> => {
    const response = await fetch(`${API_BASE_URL}/billing/contact-premium`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        email,
        phone: phone || null,
        twitter_handle: twitterHandle || null,
      }),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to send contact request' }));
      throw new Error(error.detail || 'Failed to send contact request');
    }
    return response.json();
  },
};
