import { useEffect, useState } from 'react';
import {TweetDisplay, type TweetData } from './components/tweet_new';
import { api } from './api/client';
import { DotLottieReact } from '@lottiefiles/dotlottie-react';

function App() {
  const [username, setUsername] = useState<string | null>(localStorage.getItem('username'));
  const [tweets, setTweets] = useState<TweetData[]>([]);
  const [currentTweetIndex, setCurrentTweetIndex] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingPhase, setLoadingPhase] = useState<'scraping' | 'generating' | null>(null);
  const [deletingTweetIds, setDeletingTweetIds] = useState<Set<string>>(new Set());
  const [postingTweetIds, setPostingTweetIds] = useState<Set<string>>(new Set());
  const [postedTweets, setPostedTweets] = useState<TweetData[]>([]);
  const [activeTab, setActiveTab] = useState<'generated' | 'posted'>('generated');

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

  const handleRefresh = async () => {
    if (!username) return;

    setIsLoading(true);
    try {
      // Step 1: Call the read tweets endpoint to scrape new tweets
      setLoadingPhase('scraping');
      const readResult = await api.readTweets(username);
      console.log(`Scraped ${readResult.count} new tweets`);

      // Step 2: Generate AI replies for the scraped tweets
      setLoadingPhase('generating');
      const generateResult = await api.generateReplies(username);
      console.log(`Generated ${generateResult.replies_generated} replies`);

      // Step 3: Reload the cache to show the new tweets with replies
      setLoadingPhase(null);
      await loadTweets(username);
    } catch (error) {
      console.error('Failed to refresh tweets:', error);
      alert('Failed to refresh tweets. Please try again.');
      setIsLoading(false);
      setLoadingPhase(null);
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

  const handlePublish = async (tweetId: string, text: string) => {
    if (!username) return;

    // Mark as posting to trigger animation
    setPostingTweetIds(prev => new Set(prev).add(tweetId));

    // Wait for animation to complete
    setTimeout(async () => {
      const tweet = tweets.find(t => t.id === tweetId);
      if (!tweet) return;

      try {
        await api.postReply(username, text, tweet.id, tweet.cache_id);
        // Remove tweet from cache backend without logging (since we already logged the post)
        await api.deleteTweet(username, tweet.id, false);

        // Add to posted tweets list
        setPostedTweets(prev => [{...tweet, reply: text}, ...prev]);

        // Remove from local state
        const updatedTweets = tweets.filter(t => t.id !== tweetId);
        setTweets(updatedTweets);

        // Remove from posting set
        setPostingTweetIds(prev => {
          const next = new Set(prev);
          next.delete(tweetId);
          return next;
        });

        // Adjust index if needed
        if (currentTweetIndex >= updatedTweets.length) {
          setCurrentTweetIndex(Math.max(0, updatedTweets.length - 1));
        }
      } catch (error) {
        console.error('Failed to post reply:', error);
        alert('Failed to post reply. Please try again.');
        // Remove from posting set on error
        setPostingTweetIds(prev => {
          const next = new Set(prev);
          next.delete(tweetId);
          return next;
        });
      }
    }, 400); // Match animation duration
  };

  const handleDelete = async (tweetId: string) => {
    if (!username) return;

    // Mark as deleting to trigger animation
    setDeletingTweetIds(prev => new Set(prev).add(tweetId));

    // Wait for animation to complete
    setTimeout(async () => {
      try {
        await api.deleteTweet(username, tweetId);

        // Remove from local state
        const updatedTweets = tweets.filter(t => t.id !== tweetId);
        setTweets(updatedTweets);

        // Remove from deleting set
        setDeletingTweetIds(prev => {
          const next = new Set(prev);
          next.delete(tweetId);
          return next;
        });

        // Adjust index if needed
        if (currentTweetIndex >= updatedTweets.length) {
          setCurrentTweetIndex(Math.max(0, updatedTweets.length - 1));
        }
      } catch (error) {
        console.error('Failed to delete tweet:', error);
        alert('Failed to delete tweet. Please try again.');
        // Remove from deleting set on error
        setDeletingTweetIds(prev => {
          const next = new Set(prev);
          next.delete(tweetId);
          return next;
        });
      }
    }, 300); // Match animation duration
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

  if (isLoading && !loadingPhase) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-neutral-950 p-6">
        <div className="text-white text-xl">Loading tweets...</div>
      </div>
    );
  }

  if (loadingPhase) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-neutral-950 p-6">
        <div className="flex flex-col items-center gap-6">
          <div className={loadingPhase === 'scraping' ? 'mt-[-230px] w-[700px] h-[700px]' : 'w-[250px] h-[250px]'}>
            <DotLottieReact
              src={loadingPhase === 'scraping' ? '/src/assets/desktop.lottie' : '/src/assets/writing.lottie'}
              loop
              autoplay
            />
          </div>
          <div className= {loadingPhase === 'scraping' ? "text-white text-xl mt-[-150px] text-center" : "text-white text-xl y text-center"}>
            {loadingPhase === 'scraping' ? 'Scraping tweets...' : 'Generating replies...'}
          </div>
        </div>
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
              onClick={handleRefresh}
              className="rounded-full bg-sky-500 px-6 py-2 text-sm font-semibold text-white transition hover:bg-sky-600"
            >
              Refresh
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-neutral-950">
      <div className="absolute top-6 right-6 z-10 flex gap-3">
        <button
          onClick={handleRefresh}
          className="rounded-full bg-green-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-green-700"
        >
          Refresh
        </button>
        <button
          onClick={handleLogout}
          className="rounded-full bg-neutral-800 px-4 py-2 text-sm font-semibold text-white transition hover:bg-neutral-700"
        >
          Logout ({username})
        </button>
      </div>

      {/* Tab Navigation */}
      <div className="flex justify-center gap-4 pt-6 pb-4">
        <button
          onClick={() => setActiveTab('generated')}
          className={`px-6 py-2 text-sm font-semibold transition rounded-full ${
            activeTab === 'generated'
              ? 'bg-sky-500 text-white'
              : 'bg-neutral-800 text-neutral-400 hover:bg-neutral-700 hover:text-white'
          }`}
        >
          Generated ({tweets.length})
        </button>
        <button
          onClick={() => setActiveTab('posted')}
          className={`px-6 py-2 text-sm font-semibold transition rounded-full ${
            activeTab === 'posted'
              ? 'bg-sky-500 text-white'
              : 'bg-neutral-800 text-neutral-400 hover:bg-neutral-700 hover:text-white'
          }`}
        >
          Posted ({postedTweets.length})
        </button>
      </div>

      {/* Continuous scroll with hidden scrollbar */}
      <div className="flex-1 overflow-y-auto scrollbar-hide">
        <div className="space-y-6 py-10 px-6">
          {activeTab === 'generated' ? (
            tweets.length === 0 ? (
              <div className="flex items-center justify-center h-64">
                <p className="text-neutral-400 text-lg">No tweets in cache</p>
              </div>
            ) : (
              tweets.map((tweet) => (
                <TweetDisplay
                  key={tweet.id}
                  tweet={tweet}
                  replyText={tweet.reply || ''}
                  onPublish={(text) => handlePublish(tweet.id, text)}
                  onSkip={() => handleDelete(tweet.id)}
                  onEditReply={(newReply) => handleEditReply(tweet.id, newReply)}
                  isDeleting={deletingTweetIds.has(tweet.id)}
                  isPosting={postingTweetIds.has(tweet.id)}
                />
              ))
            )
          ) : (
            postedTweets.length === 0 ? (
              <div className="flex items-center justify-center h-64">
                <p className="text-neutral-400 text-lg">No tweets posted yet</p>
              </div>
            ) : (
              postedTweets.map((tweet) => (
                <TweetDisplay
                  key={tweet.id}
                  tweet={tweet}
                  replyText={tweet.reply || ''}
                  onPublish={() => {}}
                  onSkip={() => {}}
                  isDeleting={false}
                  isPosting={false}
                  readOnly={true}
                />
              ))
            )
          )}
        </div>
      </div>

      <style>{`
        .scrollbar-hide::-webkit-scrollbar {
          display: none;
        }
        .scrollbar-hide {
          -ms-overflow-style: none;
          scrollbar-width: none;
        }
      `}</style>
    </div>
  );
}

export default App;
