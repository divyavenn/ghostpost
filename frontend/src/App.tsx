import { useEffect, useState, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {TweetDisplay, type TweetData } from './components/tweet_new';
import {PostedTweetDisplay, type PostedTweetData } from './components/posted_tweet';
import { api, type UserInfo } from './api/client';
import { DotLottieReact } from '@lottiefiles/dotlottie-react';
import { AnimatedText } from './components/AnimatedText';
import { UserSettingsModal } from './components/UserSettingsModal';
import { StatsDashboard } from './components/StatsDashboard';
import { Background } from './components/Background';
import desktopLottie from './assets/desktop.lottie';
import writingLottie from './assets/writing.lottie';

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
          setScrapingStatusText('Scraping tweets');
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
      setScrapingStatusText('Generating replies (Starting...)');
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

  if (tweets.length === 0) {
    return (
      <Background className="flex flex-col p-6">
        {/* Logo - Top Left */}
        <div className="absolute top-6 left-6">
          <img
            src="/ghostposter_logo.png"
            alt="GhostPoster"
            className="h-12 w-auto object-contain"
          />
        </div>

        {/* Logout - Top Right */}
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

        {/* Settings modal for first-time setup */}
        {userInfo && (
          <UserSettingsModal
            isOpen={isSettingsOpen}
            onClose={async () => {
              const wasFirstTimeSetup = isFirstTimeSetup;
              setIsSettingsOpen(false);

              // Reload user info to update settings state
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

        {/* Loading overlay with translucent black background */}
        {loadingPhase && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-70">
            <div className="flex flex-col items-center gap-6">
              <div className={loadingPhase === 'scraping' ? 'mt-[-230px] w-[700px] h-[700px]' : 'w-[250px] h-[250px]'}>
                <DotLottieReact
                  src={loadingPhase === 'scraping' ? desktopLottie : writingLottie}
                  loop
                  autoplay
                />
              </div>
              <AnimatedText
                text={scrapingStatusText}
                className={loadingPhase === 'scraping' ? "text-white text-xl mt-[-150px] text-center" : "text-white text-xl text-center"}
              />
            </div>
          </div>
        )}
      </Background>
    );
  }

  return (
    <Background className="flex flex-col p-20">
      {/* Logo - Top Left */}
      <div className="absolute top-6 left-6 z-10">
        <img
          src="/ghostposter_logo.png"
          alt="GhostPoster"
          className="h-12 w-auto object-contain"
        />
      </div>

      {/* Settings & Refresh - Top Right */}
      <div className="absolute top-6 right-6 z-10 flex gap-3">
        <button
          onClick={() => setIsSettingsOpen(true)}
          className="relative rounded-full bg-neutral-800 p-3 text-white transition hover:bg-neutral-700"
          aria-label="Settings"
          title="Settings"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640" className="w-5 h-5 fill-current">
            <path d="M256.5 72C322.8 72 376.5 125.7 376.5 192C376.5 258.3 322.8 312 256.5 312C190.2 312 136.5 258.3 136.5 192C136.5 125.7 190.2 72 256.5 72zM226.7 368L286.1 368L287.6 368C274.7 394.8 279.8 426.2 299.1 447.5C278.9 469.8 274.3 503.3 289.7 530.9L312.2 571.3C313.1 572.9 314.1 574.5 315.1 576L78.1 576C61.7 576 48.4 562.7 48.4 546.3C48.4 447.8 128.2 368 226.7 368zM432.6 311.6C432.6 298.3 443.3 287.6 456.6 287.6L504.6 287.6C517.9 287.6 528.6 298.3 528.6 311.6L528.6 317.7C528.6 336.6 552.7 350.5 569.1 341.1L574.1 338.2C585.7 331.5 600.6 335.6 607.1 347.3L629.5 387.5C635.7 398.7 632.1 412.7 621.3 419.5L616.6 422.4C600.4 432.5 600.4 462.3 616.6 472.5L621.2 475.4C632 482.2 635.7 496.2 629.5 507.4L607 547.8C600.5 559.5 585.6 563.7 574 556.9L569.1 554C552.7 544.5 528.6 558.5 528.6 577.4L528.6 583.5C528.6 596.8 517.9 607.5 504.6 607.5L456.6 607.5C443.3 607.5 432.6 596.8 432.6 583.5L432.6 577.6C432.6 558.6 408.4 544.6 391.9 554.1L387.1 556.9C375.5 563.6 360.7 559.5 354.1 547.8L331.5 507.4C325.3 496.2 328.9 482.1 339.8 475.3L344.2 472.6C360.5 462.5 360.5 432.5 344.2 422.4L339.7 419.6C328.8 412.8 325.2 398.7 331.4 387.5L353.9 347.2C360.4 335.5 375.3 331.4 386.8 338.1L391.6 340.9C408.1 350.4 432.3 336.4 432.3 317.4L432.3 311.5zM532.5 447.8C532.5 419.1 509.2 395.8 480.5 395.8C451.8 395.8 428.5 419.1 428.5 447.8C428.5 476.5 451.8 499.8 480.5 499.8C509.2 499.8 532.5 476.5 532.5 447.8z"/>
          </svg>
          {hasInvalidAccounts && (
            <span className="absolute -top-1 -right-1 flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
            </span>
          )}
        </button>
        <button
          onClick={handleRefresh}
          className="rounded-full bg-green-600 p-3 text-white transition hover:bg-green-700"
          aria-label="Refresh"
          title="Refresh"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640" className="w-5 h-5 fill-current">
            <path d="M129.9 292.5C143.2 199.5 223.3 128 320 128C373 128 421 149.5 455.8 184.2C456 184.4 456.2 184.6 456.4 184.8L464 192L416.1 192C398.4 192 384.1 206.3 384.1 224C384.1 241.7 398.4 256 416.1 256L544.1 256C561.8 256 576.1 241.7 576.1 224L576.1 96C576.1 78.3 561.8 64 544.1 64C526.4 64 512.1 78.3 512.1 96L512.1 149.4L500.8 138.7C454.5 92.6 390.5 64 320 64C191 64 84.3 159.4 66.6 283.5C64.1 301 76.2 317.2 93.7 319.7C111.2 322.2 127.4 310 129.9 292.6zM573.4 356.5C575.9 339 563.7 322.8 546.3 320.3C528.9 317.8 512.6 330 510.1 347.4C496.8 440.4 416.7 511.9 320 511.9C267 511.9 219 490.4 184.2 455.7C184 455.5 183.8 455.3 183.6 455.1L176 447.9L223.9 447.9C241.6 447.9 255.9 433.6 255.9 415.9C255.9 398.2 241.6 383.9 223.9 383.9L96 384C87.5 384 79.3 387.4 73.3 393.5C67.3 399.6 63.9 407.7 64 416.3L65 543.3C65.1 561 79.6 575.2 97.3 575C115 574.8 129.2 560.4 129 542.7L128.6 491.2L139.3 501.3C185.6 547.4 249.5 576 320 576C449 576 555.7 480.6 573.4 356.5z"/>
          </svg>
        </button>
      </div>

      {userInfo && (
        <UserSettingsModal
          isOpen={isSettingsOpen}
          onClose={() => {
            setIsSettingsOpen(false);
            // Reload user info to check for invalid accounts after closing settings
            loadUserInfo(username!);
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
      <div className="flex justify-center gap-4 pt-2 pb-4">
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
          Posted ({userInfo?.lifetime_posts || 0})
        </button>
      </div>

      {/* Continuous scroll with hidden scrollbar */}
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
            tweets.length === 0 ? (
              <div className="w-full flex items-center justify-center h-64">
                <p className="text-neutral-400 text-lg">No tweets in cache</p>
              </div>
            ) : (
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
            )
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

      {/* Loading overlay with translucent black background */}
      {loadingPhase && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-70">
          <div className="flex flex-col items-center gap-6">
            <div className={loadingPhase === 'scraping' ? 'mt-[-230px] w-[700px] h-[700px]' : 'w-[250px] h-[250px]'}>
              <DotLottieReact
                src={loadingPhase === 'scraping' ? desktopLottie : writingLottie}
                loop
                autoplay
              />
            </div>
            <AnimatedText
              text={scrapingStatusText}
              className={loadingPhase === 'scraping' ? "text-white text-xl mt-[-150px] text-center" : "text-white text-xl text-center"}
            />
          </div>
        </div>
      )}

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
