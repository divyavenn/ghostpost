import { type TweetData } from '../components/tweet_new';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/';

export interface AuthResponse {
  auth_url: string;
  state: string;
  session_id: string;
  message: string;
}

export interface TwitterStatus {
  connected: boolean;
  twitter_handle: string | null;
  expires_at: string | null;
}

export interface UserSettings {
  queries: string[];
  relevant_accounts: Record<string, boolean>; // {handle: validated}
  max_tweets_retrieve: number;
}

export interface UserInfo {
  handle: string;
  username: string;
  profile_pic_url: string;
  follower_count: number;
  email?: string;
  model?: string;
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

  // Tweet cache endpoints
  getTweetsCache: async (username: string): Promise<TweetData[]> => {
    const response = await fetch(`${API_BASE_URL}/tweets/${username}`);
    if (!response.ok) throw new Error('Failed to fetch tweets');
    return response.json();
  },

  editTweetReply: async (username: string, tweetId: string, newReply: string): Promise<void> => {
    const response = await fetch(`${API_BASE_URL}/tweets/${username}/${tweetId}/reply`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ new_reply: newReply }),
    });
    if (!response.ok) throw new Error('Failed to edit reply');
  },

  deleteTweet: async (username: string, tweetId: string, logDeletion: boolean = true): Promise<void> => {
    const response = await fetch(`${API_BASE_URL}/tweets/${username}/${tweetId}?log_deletion=${logDeletion}`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error('Failed to delete tweet');
  },

  postReply: async (username: string, text: string, tweetId: string, cacheId?: string): Promise<{ data: { id: string }; posted_tweet_id?: string }> => {
    const response = await fetch(`${API_BASE_URL}/post/reply?username=${encodeURIComponent(username)}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        text,
        tweet_id: tweetId,
        cache_id: cacheId,
      }),
    });
    if (!response.ok) throw new Error('Failed to post reply');
    return response.json();
  },

  deletePostedTweet: async (username: string, tweetId: string): Promise<{ message: string; tweet_id: string; deleted: boolean }> => {
    const response = await fetch(`${API_BASE_URL}/post/tweet/${tweetId}?username=${encodeURIComponent(username)}`, {
      method: 'DELETE',
    });
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
  }): Promise<{ message: string; count: number; tweets: TweetData[] }> => {
    const response = await fetch(`${API_BASE_URL}/read/${encodeURIComponent(username)}/tweets`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload || {}),
    });
    if (!response.ok) throw new Error('Failed to read tweets');
    return response.json();
  },

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
    if (!response.ok) throw new Error('Failed to generate replies');
    return response.json();
  },

  regenerateSingleReply: async (username: string, tweetId: string): Promise<{ message: string; tweet_id: string; new_reply: string }> => {
    const response = await fetch(`${API_BASE_URL}/generate/${encodeURIComponent(username)}/replies/${encodeURIComponent(tweetId)}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });
    if (!response.ok) throw new Error('Failed to regenerate reply');
    return response.json();
  },

  // User settings endpoints
  getUserInfo: async (handle: string): Promise<UserInfo> => {
    const response = await fetch(`${API_BASE_URL}/user/${encodeURIComponent(handle)}/info`);
    if (!response.ok) throw new Error('Failed to get user info');
    return response.json();
  },

  getUserSettings: async (handle: string): Promise<UserSettings> => {
    const response = await fetch(`${API_BASE_URL}/user/${encodeURIComponent(handle)}/settings`);
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
};
