import { type TweetData } from '../components/tweet_new';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export interface AuthResponse {
  auth_url: string;
  state: string;
}

export interface TwitterStatus {
  connected: boolean;
  twitter_handle: string | null;
  expires_at: string | null;
}

export const api = {
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

  postReply: async (username: string, text: string, tweetId: string, cacheId?: string): Promise<{ data: { id: string } }> => {
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
};
