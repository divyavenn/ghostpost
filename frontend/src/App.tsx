import { useEffect, useState, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {TweetDisplay, type TweetData } from './components/tweet_new';
import {PostedTweetDisplay, type PostedTweetData } from './components/posted_tweet';
import { api, type UserInfo } from './api/client';
import { UserSettingsModal } from './components/UserSettingsModal';
import { StatsDashboard } from './components/StatsDashboard';
import { Background } from './components/Background';
import { Header } from './components/Header';
import { EmptyState } from './components/EmptyState';
import { LoadingOverlay } from './components/LoadingOverlay';
import { TabNavigation } from './components/TabNavigation';

function App() {
  const navigate = useNavigate();
  const [username, setUsername] = useState<string | null>(localStorage.getItem('username'));
  const [tweets, setTweets] = useState<TweetData[]>([]);
  const [currentTweetIndex, setCurrentTweetIndex] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingPhase, setLoadingPhase] = useState<'scraping' | 'generating' | null>(null);
  const [deletingTweetIds, setDeletingTweetIds] = useState<Set<string>>(new Set());
  const [postingTweetIds, setPostingTweetIds] = useState<Set<string>>(new Set());
  const [regeneratingTweetIds, setRegeneratingTweetIds] = useState<Set<string>>(new Set());
  const [postedTweets, setPostedTweets] = useState<PostedTweetData[]>([]);
  const [activeTab, setActiveTab] = useState<'generated' | 'posted'>('generated');
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [userInfo, setUserInfo] = useState<UserInfo | null>(null);
  const [hasInvalidAccounts, setHasInvalidAccounts] = useState(false);
  const [isFirstTimeSetup, setIsFirstTimeSetup] = useState(false);
  const [scrapingStatusText, setScrapingStatusText] = useState<string>('Scraping tweets');
  const [hasMorePostedTweets, setHasMorePostedTweets] = useState(true);
  const [isLoadingMorePosted, setIsLoadingMorePosted] = useState(false);
  const postedTweetsOffsetRef = useRef(0); // Track offset with ref to avoid re-creating callback

  // Load posted tweets from backend
  const loadPostedTweets = useCallback(async (user: string, reset: boolean = true) => {
    try {
      if (reset) {
        postedTweetsOffsetRef.current = 0;
        setHasMorePostedTweets(true);
      }

      const data = await api.getPostedTweets(user, 50, reset ? 0 : postedTweetsOffsetRef.current);

      if (reset) {
        setPostedTweets(data.tweets);
      } else {
        setPostedTweets(prev => [...prev, ...data.tweets]);
      }

      // Update offset for next load
      if (!reset) {
        postedTweetsOffsetRef.current += data.count;
      } else {
        postedTweetsOffsetRef.current = data.count;
      }

      // Check if there are more tweets to load
      setHasMorePostedTweets(data.count === 50);

      // Check performance metrics for the newly loaded tweets
      if (data.tweets.length > 0) {
        const tweetIds = data.tweets.map(t => t.id).filter(Boolean);
        if (tweetIds.length > 0) {
          try {
            console.log(`Checking performance for ${tweetIds.length} tweets...`);
            const metricsResult = await api.checkTweetPerformance(user, tweetIds);
            console.log(`Updated metrics for ${metricsResult.updated_count} tweets`);

            // Reload tweets to get updated metrics
            if (reset) {
              const updatedData = await api.getPostedTweets(user, 50, 0);
              setPostedTweets(updatedData.tweets);
            } else {
              // For infinite scroll, reload from beginning to get all updated metrics
              const updatedData = await api.getPostedTweets(user, postedTweetsOffsetRef.current, 0);
              setPostedTweets(updatedData.tweets);
            }
          } catch (error: unknown) {
            // Handle rate limiting gracefully
            const errorMessage = error instanceof Error ? error.message : String(error);
            if (errorMessage.includes('429') || errorMessage.includes('rate limit')) {
              console.warn('⚠️ Twitter API rate limit reached. Showing cached metrics. Try again in 15 minutes.');
            } else {
              console.error('Failed to check tweet performance:', error);
            }
            // Continue anyway - we still have the tweets even if metrics failed
          }
        }
      }
    } catch (error) {
      console.error('Failed to load posted tweets:', error);
    }
  }, []); // No dependencies needed - using functional setState and user param

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
      loadUserInfo(callbackUsername);
      loadTweets(callbackUsername);
      // Don't load posted tweets here - will load when user switches to Posted tab

      // Clean up URL
      window.history.replaceState({}, document.title, window.location.pathname);
    } else if (username) {
      loadUserInfo(username);
      loadTweets(username);
      // Don't load posted tweets here - will load when user switches to Posted tab
    }
    // This should only run once on mount, not when username changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Redirect to login if no username
  useEffect(() => {
    if (!username) {
      navigate('/login');
    }
  }, [username, navigate]);

  // Load posted tweets when switching to Posted tab
  useEffect(() => {
    if (activeTab === 'posted' && username) {
      loadPostedTweets(username, true);
    }
  }, [activeTab, username, loadPostedTweets]);

  // Load more posted tweets (for infinite scroll)
  const loadMorePostedTweets = async () => {
    if (!username || isLoadingMorePosted || !hasMorePostedTweets) return;

    setIsLoadingMorePosted(true);
    try {
      await loadPostedTweets(username, false);
    } finally {
      setIsLoadingMorePosted(false);
    }
  };

  const loadUserInfo = async (user: string) => {
    try {
      const info = await api.getUserInfo(user);
      setUserInfo(info);

      // Check for invalid accounts
      const settings = await api.getUserSettings(user);
      const hasInvalid = Object.values(settings.relevant_accounts).some(validated => validated === false);
      setHasInvalidAccounts(hasInvalid);

      // Check if first-time setup is needed (both queries and accounts are empty)
      const hasNoQueries = !settings.queries || settings.queries.length === 0;
      const hasNoAccounts = !settings.relevant_accounts || Object.keys(settings.relevant_accounts).length === 0;
      const needsSetup = hasNoQueries && hasNoAccounts;
      
      setIsFirstTimeSetup(needsSetup);
      
      // Auto-open settings modal for first-time users
      if (needsSetup) {
        setIsSettingsOpen(true);
      }
    } catch (error) {
      console.error('Failed to load user info:', error);
    }
  };

  const loadTweets = async (user: string) => {
    setIsLoading(true);
    try {
      const data = await api.getTweetsCache(user);

      // Filter: only display tweets that have threads
      // (Tweets without threads remain in cache but aren't shown)
      const tweetsWithThreads = data.filter(tweet => {
        const hasThread = tweet.thread && Array.isArray(tweet.thread) && tweet.thread.length > 0;
        return hasThread;
      });

      // Sort by created_at date (newest first)
      const sorted = tweetsWithThreads.sort((a, b) => {
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

    // Start polling for scraping status and tweets in the background
    const pollInterval = setInterval(async () => {
      if (!username) return;
      try {
        // Poll scraping status
        const status = await api.getScrapingStatus(username);

        // Update status text based on current scraping phase
        if (status.type === 'account') {
          setScrapingStatusText(`Scraping tweets from @${status.value}`);
        } else if (status.type === 'query') {
          setScrapingStatusText(`Scraping tweets related to "${status.value}"`);
        } else if (status.type === 'generating') {
          setScrapingStatusText(`Generating replies (${status.value})`);
        } else if (status.type === 'complete') {
          setScrapingStatusText('Done!');
        }

        // Also poll tweets to show them appearing
        const data = await api.getTweetsCache(username);
        const tweetsWithThreads = data.filter(tweet => {
          const hasThread = tweet.thread && Array.isArray(tweet.thread) && tweet.thread.length > 0;
          return hasThread;
        });
        const sorted = tweetsWithThreads.sort((a, b) => {
          return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
        });
        setTweets(sorted);
      } catch (error) {
        console.error('Polling error:', error);
      }
    }, 2000); // Poll every 2 seconds

    try {
      // Step 1: Call the read tweets endpoint to scrape new tweets
      setLoadingPhase('scraping');
      setScrapingStatusText('Scraping tweets');
      const readResult = await api.readTweets(username);
      console.log(`Scraped ${readResult.count} new tweets`);

      // Update user info to reflect new scrolling_time_saved value
      await loadUserInfo(username);

      // Step 2: Generate AI replies for the scraped tweets
      setLoadingPhase('generating');
      setScrapingStatusText('Generating replies');
      const generateResult = await api.generateReplies(username);
      console.log(`Generated ${generateResult.replies_generated} replies`);

      // Step 3: Stop polling and do final reload
      clearInterval(pollInterval);
      setLoadingPhase(null);
      setScrapingStatusText('Scraping tweets'); // Reset
      await loadTweets(username);
    } catch (error) {
      clearInterval(pollInterval);
      console.error('Failed to refresh tweets:', error);
      alert('Failed to refresh tweets. Please try again.');
      setIsLoading(false);
      setLoadingPhase(null);
      setScrapingStatusText('Scraping tweets'); // Reset
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

  const handleRegenerate = async (tweetId: string) => {
    if (!username) return;

    // Mark as regenerating
    setRegeneratingTweetIds(prev => new Set(prev).add(tweetId));

    try {
      const result = await api.regenerateSingleReply(username, tweetId);
      // Update local state with the new reply
      setTweets(tweets.map(t =>
        t.id === tweetId ? { ...t, reply: result.new_reply } : t
      ));
    } catch (error) {
      console.error('Failed to regenerate reply:', error);
      alert('Failed to regenerate reply. Please try again.');
    } finally {
      // Remove from regenerating set
      setRegeneratingTweetIds(prev => {
        const next = new Set(prev);
        next.delete(tweetId);
        return next;
      });
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

        // Reload user info to update lifetime_posts counter
        await loadUserInfo(username);

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

  const handleDeletePosted = async (postedTweetId: string) => {
    if (!username || !postedTweetId) {
      alert('Cannot delete: tweet ID not found.');
      return;
    }

    // Mark as deleting for animation
    setDeletingTweetIds(prev => new Set(prev).add(postedTweetId));

    setTimeout(async () => {
      try {
        await api.deletePostedTweet(username, postedTweetId);

        // Remove from postedTweets state
        setPostedTweets(prev => prev.filter(t => t.id !== postedTweetId));

        // Clear deleting state
        setDeletingTweetIds(prev => {
          const next = new Set(prev);
          next.delete(postedTweetId);
          return next;
        });

        // Reload user info to update posted count
        await loadUserInfo(username);
      } catch (error) {
        console.error('Failed to delete posted tweet:', error);
        alert(`Failed to delete tweet: ${error instanceof Error ? error.message : 'Unknown error'}`);

        // Clear deleting state on error
        setDeletingTweetIds(prev => {
          const next = new Set(prev);
          next.delete(postedTweetId);
          return next;
        });
      }
    }, 300);
  };


  if (!username) {
    return null;
  }

  if (isLoading && !loadingPhase) {
    return (
      <Background className="flex items-center justify-center p-6">
        <div className="text-white text-xl">Loading tweets...</div>
      </Background>
    );
  }

  // Don't return early if loadingPhase is set - we'll render overlay instead
  return (
    <Background className="flex flex-col p-20">
      <Header
        onSettingsClick={() => setIsSettingsOpen(true)}
        onRefreshClick={handleRefresh}
        hasInvalidAccounts={hasInvalidAccounts}
      />

      {userInfo && (
        <UserSettingsModal
          isOpen={isSettingsOpen}
          onClose={async () => {
            const wasFirstTimeSetup = isFirstTimeSetup;
            setIsSettingsOpen(false);

            // Reload user info to check for invalid accounts after closing settings
            await loadUserInfo(username!);

            // If we just completed first-time setup, auto-trigger refresh
            if (wasFirstTimeSetup) {
              setTimeout(() => {
                handleRefresh();
              }, 100);
            }
          }}
          username={username!}
          userInfo={{
            profile_pic_url: userInfo.profile_pic_url,
            username: userInfo.username,
            follower_count: userInfo.follower_count,
          }}
          onLogout={handleLogout}
          isFirstTimeSetup={isFirstTimeSetup}
        />
      )}

      {/* Stats Dashboard */}
      {userInfo && <StatsDashboard userInfo={userInfo} />}

      {/* Tab Navigation */}
      <TabNavigation
        activeTab={activeTab}
        onTabChange={setActiveTab}
        generatedCount={tweets.length}
        postedCount={userInfo?.lifetime_posts || 0}
      />

      {/* Content Area - Show tweets or empty state */}
      {activeTab === 'generated' && tweets.length === 0 ? (
        <EmptyState onRefresh={handleRefresh} />
      ) : (
        <div
          className="flex-1 overflow-y-auto scrollbar-hide"
          onScroll={(e) => {
            if (activeTab === 'posted') {
              const element = e.currentTarget;
              const isNearBottom = element.scrollHeight - element.scrollTop - element.clientHeight < 500;

              if (isNearBottom && !isLoadingMorePosted && hasMorePostedTweets) {
                loadMorePostedTweets();
              }
            }
          }}
        >
          <div className="flex gap-6 py-10 px-6">
            {activeTab === 'generated' ? (
              <>
                {/* Left Column */}
                <div className="flex-1 flex flex-col gap-6">
                  {tweets.filter((_, index) => index % 2 === 0).map((tweet) => (
                    <TweetDisplay
                      key={tweet.id}
                      tweet={tweet}
                      replyText={tweet.reply || ''}
                      myProfilePicUrl={userInfo!.profile_pic_url}
                      onPublish={(text) => handlePublish(tweet.id, text)}
                      onSkip={() => handleDelete(tweet.id)}
                      onEditReply={(newReply) => handleEditReply(tweet.id, newReply)}
                      onRegenerate={() => handleRegenerate(tweet.id)}
                      isDeleting={deletingTweetIds.has(tweet.id)}
                      isPosting={postingTweetIds.has(tweet.id)}
                      isRegenerating={regeneratingTweetIds.has(tweet.id)}
                    />
                  ))}
                </div>
                {/* Right Column */}
                <div className="flex-1 flex flex-col gap-6">
                  {tweets.filter((_, index) => index % 2 === 1).map((tweet) => (
                    <TweetDisplay
                      key={tweet.id}
                      tweet={tweet}
                      replyText={tweet.reply || ''}
                      myProfilePicUrl={userInfo!.profile_pic_url}
                      onPublish={(text) => handlePublish(tweet.id, text)}
                      onSkip={() => handleDelete(tweet.id)}
                      onEditReply={(newReply) => handleEditReply(tweet.id, newReply)}
                      onRegenerate={() => handleRegenerate(tweet.id)}
                      isDeleting={deletingTweetIds.has(tweet.id)}
                      isPosting={postingTweetIds.has(tweet.id)}
                      isRegenerating={regeneratingTweetIds.has(tweet.id)}
                    />
                  ))}
                </div>
              </>
            ) : (
            <>
              {postedTweets.length === 0 ? (
                <div className="w-full flex items-center justify-center h-64">
                  <p className="text-neutral-400 text-lg">No tweets posted yet</p>
                </div>
              ) : (
              <>
                {/* Left Column */}
                <div className="flex-1 flex flex-col gap-6">
                  {postedTweets.filter((_, index) => index % 2 === 0).map((tweet) => (
                    <PostedTweetDisplay
                      key={tweet.id}
                      tweet={tweet}
                      myProfilePicUrl={userInfo!.profile_pic_url}
                      myHandle={userInfo!.handle}
                      myUsername={userInfo!.username}
                      onDelete={(tweetId) => handleDeletePosted(tweetId)}
                      isDeleting={deletingTweetIds.has(tweet.id)}
                    />
                  ))}
                </div>
                {/* Right Column */}
                <div className="flex-1 flex flex-col gap-6">
                  {postedTweets.filter((_, index) => index % 2 === 1).map((tweet) => (
                    <PostedTweetDisplay
                      key={tweet.id}
                      tweet={tweet}
                      myProfilePicUrl={userInfo!.profile_pic_url}
                      myHandle={userInfo!.handle}
                      myUsername={userInfo!.username}
                      onDelete={(tweetId) => handleDeletePosted(tweetId)}
                      isDeleting={deletingTweetIds.has(tweet.id)}
                    />
                  ))}
                </div>
              </>
              )}

              {/* Loading indicator for infinite scroll */}
              {isLoadingMorePosted && (
                <div className="w-full flex justify-center py-8">
                  <div className="text-neutral-400 text-sm">Loading more tweets...</div>
                </div>
              )}
            </>
          )}
        </div>
        </div>
      )}

      {/* Loading overlay */}
      {loadingPhase && <LoadingOverlay phase={loadingPhase} statusText={scrapingStatusText} />}

      <style>{`
        .scrollbar-hide::-webkit-scrollbar {
          display: none;
        }
        .scrollbar-hide {
          -ms-overflow-style: none;
          scrollbar-width: none;
        }
      `}</style>
    </Background>
  );
}

export default App;
