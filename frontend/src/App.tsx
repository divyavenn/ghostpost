import { useEffect, useState } from 'react';
import {TweetDisplay, type TweetData } from './components/tweet_new';
import { api } from './api/client';

function App() {
  const [username, setUsername] = useState<string | null>(localStorage.getItem('username'));
  const [tweets, setTweets] = useState<TweetData[]>([]);
  const [currentTweetIndex, setCurrentTweetIndex] = useState(0);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    // Check for OAuth callback parameters
    const params = new URLSearchParams(window.location.search);
    const callbackUsername = params.get('username');
    const status = params.get('status');
    const error = params.get('error');
    const errorDescription = params.get('error_description');

    if (status === 'error') {
      // OAuth failed, show error and go back to login
      alert(`Authentication failed: ${errorDescription || error || 'Unknown error'}`);
      setUsername(null);
      localStorage.removeItem('username');

      // Clean up URL
      window.history.replaceState({}, document.title, window.location.pathname);
    } else if (callbackUsername && status === 'success') {
      // OAuth successful, save username and load tweets
      setUsername(callbackUsername);
      localStorage.setItem('username', callbackUsername);
      loadTweets(callbackUsername);

      // Clean up URL
      window.history.replaceState({}, document.title, window.location.pathname);
    } else if (username) {
      loadTweets(username);
    }
  }, []);

  const loadTweets = async (user: string) => {
    setIsLoading(true);
    try {
      const data = await api.getTweetsCache(user);
      // Sort by created_at date (newest first)
      const sorted = data.sort((a, b) => {
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      });
      setTweets(sorted);
      setCurrentTweetIndex(0);
    } catch (error) {
      console.error('Failed to load tweets:', error);
      alert('Failed to load tweets. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleLogin = async () => {
    try {
      console.log('Starting OAuth flow...');
      // Start Twitter OAuth - this will redirect to Twitter
      const response = await api.startTwitterOAuth(window.location.origin);
      console.log('OAuth response:', response);

      const { auth_url } = response;
      console.log('Auth URL:', auth_url);

      if (!auth_url) {
        throw new Error('No auth URL received from server');
      }

      // Open Twitter OAuth in new tab
      window.open(auth_url, '_blank');
    } catch (error) {
      console.error('Login failed:', error);
      alert(`Login failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  const handleLogout = () => {
    setUsername(null);
    setTweets([]);
    localStorage.removeItem('username');
  };

  const handleEditReply = async (tweetId: string, newReply: string) => {
    if (!username) return;

    try {
      await api.editTweetReply(username, tweetId, newReply);
      // Update local state
      setTweets(tweets.map(t =>
        t.id === tweetId ? { ...t, reply: newReply } : t
      ));
    } catch (error) {
      console.error('Failed to edit reply:', error);
    }
  };

  const handlePublish = async (text: string) => {
    if (!username || !tweets[currentTweetIndex]) return;

    const tweet = tweets[currentTweetIndex];
    try {
      await api.postReply(username, text, tweet.id, tweet.cache_id);
      alert('Reply posted successfully!');
      // Move to next tweet
      handleSkip();
    } catch (error) {
      console.error('Failed to post reply:', error);
      alert('Failed to post reply. Please try again.');
    }
  };

  const handleSkip = () => {
    if (currentTweetIndex < tweets.length - 1) {
      setCurrentTweetIndex(currentTweetIndex + 1);
    } else {
      setCurrentTweetIndex(0);
    }
  };

  if (!username) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-neutral-950 p-6">
        <div className="text-center">
          <h1 className="text-4xl font-bold text-white mb-8">FloodMe</h1>
          <button
            onClick={handleLogin}
            className="rounded-full bg-sky-500 px-8 py-3 text-lg font-semibold text-white transition hover:bg-sky-600"
          >
            Login with Twitter
          </button>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-neutral-950 p-6">
        <div className="text-white text-xl">Loading tweets...</div>
      </div>
    );
  }

  if (tweets.length === 0) {
    return (
      <div className="flex min-h-screen flex-col bg-neutral-950 p-6">
        <div className="absolute top-6 right-6">
          <button
            onClick={handleLogout}
            className="rounded-full bg-neutral-800 px-4 py-2 text-sm font-semibold text-white transition hover:bg-neutral-700"
          >
            Logout ({username})
          </button>
        </div>
        <div className="flex flex-1 items-center justify-center">
          <div className="text-center text-white">
            <p className="text-xl mb-4">No tweets found in cache</p>
            <button
              onClick={() => loadTweets(username)}
              className="rounded-full bg-sky-500 px-6 py-2 text-sm font-semibold text-white transition hover:bg-sky-600"
            >
              Refresh
            </button>
          </div>
        </div>
      </div>
    );
  }

  const currentTweet = tweets[currentTweetIndex];

  return (
    <div className="flex min-h-screen flex-col bg-neutral-950 p-6">
      <div className="absolute top-6 right-6">
        <button
          onClick={handleLogout}
          className="rounded-full bg-neutral-800 px-4 py-2 text-sm font-semibold text-white transition hover:bg-neutral-700"
        >
          Logout ({username})
        </button>
      </div>

      <div className="flex flex-1 items-center justify-center">
        <TweetDisplay
          tweet={currentTweet}
          replyText={currentTweet.reply || ''}
          onPublish={handlePublish}
          onSkip={handleSkip}
          onEditReply={(newReply) => handleEditReply(currentTweet.id, newReply)}
        />
      </div>

      <div className="text-center text-neutral-500 mt-4">
        Tweet {currentTweetIndex + 1} of {tweets.length}
      </div>
    </div>
  );
}

export default App;
