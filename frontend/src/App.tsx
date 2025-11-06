import { useEffect, useState, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useRecoilState } from 'recoil';
import {TweetDisplay, type TweetData } from './components/tweet_new';
import {PostedTweetDisplay, type PostedTweetData } from './components/posted_tweet';
import { api } from './api/client';
import { UserSettingsModal } from './components/UserSettingsModal';
import { StatsDashboard } from './components/StatsDashboard';
import { Background } from './components/Background';
import { Header } from './components/Header';
import { EmptyState } from './components/EmptyState';
import { LoadingOverlay } from './components/LoadingOverlay';
import { TabNavigation } from './components/TabNavigation';
import FirstTimeUserModal from './components/FirstTimeUserModal';
import { PremiumFeatureModal } from './components/PremiumFeatureModal';
import { PaidFeatureModal } from './components/PaidFeatureModal';
import {
  usernameState,
  userInfoState,
  isSettingsOpenState,
  showFirstTimeModalState,
  activeTabState,
  loadingPhaseState,
  loadingStatusDataState,
} from './atoms';

function App() {
  const navigate = useNavigate();

  // Recoil state - used directly
  const [username, setUsername] = useRecoilState(usernameState);
  const [userInfo, setUserInfo] = useRecoilState(userInfoState);
  const [isSettingsOpen, setIsSettingsOpen] = useRecoilState(isSettingsOpenState);
  const [showFirstTimeModal, setShowFirstTimeModal] = useRecoilState(showFirstTimeModalState);
  const [activeTab, setActiveTab] = useRecoilState(activeTabState);
  const [loadingPhase, setLoadingPhase] = useRecoilState(loadingPhaseState);
  const [, setLoadingStatusData] = useRecoilState(loadingStatusDataState);

  // Local state (component-specific)
  const [tweets, setTweets] = useState<TweetData[]>([]);
  const [currentTweetIndex, setCurrentTweetIndex] = useState(0);
  const [deletingTweetIds, setDeletingTweetIds] = useState<Set<string>>(new Set());
  const [postingTweetIds, setPostingTweetIds] = useState<Set<string>>(new Set());
  const [regeneratingTweetIds, setRegeneratingTweetIds] = useState<Set<string>>(new Set());
  const [postedTweets, setPostedTweets] = useState<PostedTweetData[]>([]);
  const [hasInvalidAccounts, setHasInvalidAccounts] = useState(false);
  const [isFirstTimeSetup, setIsFirstTimeSetup] = useState(false);
  const [hasMorePostedTweets, setHasMorePostedTweets] = useState(true);
  const [isLoadingMorePosted, setIsLoadingMorePosted] = useState(false);
  const [numberOfGenerations, setNumberOfGenerations] = useState<number>(1);
  const [showPremiumModal, setShowPremiumModal] = useState(false);
  const [showPaidModal, setShowPaidModal] = useState(false);
  const [paidModalConfig, setPaidModalConfig] = useState<{
    actionType: 'scrape' | 'post';
    remaining: number;
    onAction: () => void;
  } | null>(null);
  const postedTweetsOffsetRef = useRef(0);

  // Derived state: isLoading can be determined from loadingPhase
  const isLoading = loadingPhase !== null;

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

      // Check if user needs to provide email (first-time users)
      if (!info.email || info.email.trim() === '') {
        setShowFirstTimeModal(true);
      }

      // Check for invalid accounts
      const settings = await api.getUserSettings(user);
      const hasInvalid = Object.values(settings.relevant_accounts).some(validated => validated === false);
      setHasInvalidAccounts(hasInvalid);

      // Store number of generations setting
      setNumberOfGenerations(settings.number_of_generations || 1);

      // Check if first-time setup is needed (both queries and accounts are empty)
      const hasNoQueries = !settings.queries || settings.queries.length === 0;
      const hasNoAccounts = !settings.relevant_accounts || Object.keys(settings.relevant_accounts).length === 0;
      const needsSetup = hasNoQueries && hasNoAccounts;

      setIsFirstTimeSetup(needsSetup);

      // Auto-open settings modal for first-time users (after email modal is closed)
      if (needsSetup && info.email) {
        setIsSettingsOpen(true);
      }
    } catch (error) {
      console.error('Failed to load user info:', error);
    }
  };

  const loadTweets = async (user: string) => {
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
    }
  };

  // Handle scraping + generation (full refresh)
  const handleScrapeInternal = async () => {
    if (!username) return;

    // Start polling for scraping status and tweets in the background
    const pollInterval = setInterval(async () => {
      if (!username) return;
      try {
        // Poll scraping status
        const status = await api.getScrapingStatus(username);
        console.log('[Polling] Status:', status, '| Current phase:', loadingPhase);

        // Update status based on current scraping phase
        if (status.type === 'account') {
          console.log('[Polling] Setting phase to scraping (account)');
          setLoadingPhase('scraping');
          setLoadingStatusData({ type: 'account', value: status.value });
        } else if (status.type === 'query') {
          console.log('[Polling] Setting phase to scraping (query)');
          setLoadingPhase('scraping');
          setLoadingStatusData({ type: 'query', value: status.value });
        } else if (status.type === 'generating') {
          console.log('[Polling] Setting phase to generating');
          setLoadingPhase('generating');
          setLoadingStatusData({ type: 'generating', value: status.value });
        } else if (status.type === 'complete') {
          console.log('[Polling] Status complete, stopping polling');
          setLoadingStatusData({ type: 'complete', value: '' });

          // Stop polling and finish up
          clearInterval(pollInterval);
          setLoadingPhase(null);
          setLoadingStatusData(null);
          await loadUserInfo(username);
          await loadTweets(username);
        } else if (status.type !== 'idle') {
          // Log unexpected status types (idle is expected when not scraping)
          console.warn('[Polling] Unexpected status type:', status.type);
        } 

        // Poll tweets to show them appearing in real-time
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

    // Fire the scraping request without awaiting - let polling handle everything
    setLoadingPhase('scraping');
    setLoadingStatusData(null);

    api.readTweets(username).catch((error) => {
      clearInterval(pollInterval);
      console.error('Failed to start scraping:', error);
      alert('Failed to start scraping. Please try again.');
      setLoadingPhase(null);
      setLoadingStatusData(null);
    });
  };

  // Wrapper for scraping with trial limit check
  const handleScrape = async () => {
    if (!username) return;

    // Check if user is trial and has scrapes remaining
    const accountType = userInfo?.account_type;
    if (accountType === 'trial') {
      const scrapesRemaining = userInfo?.scrapes_left ?? 0;

      if (scrapesRemaining <= 0) {
        // No scrapes left - show upgrade message
        setPaidModalConfig({
          actionType: 'scrape',
          remaining: 0,
          onAction: () => {} // No action if no scrapes left
        });
        setShowPaidModal(true);
        return;
      }

      // Has scrapes left - show confirmation modal
      setPaidModalConfig({
        actionType: 'scrape',
        remaining: scrapesRemaining,
        onAction: handleScrapeInternal
      });
      setShowPaidModal(true);
      return;
    }

    // Non-trial users can scrape directly
    await handleScrapeInternal();
  };

  // Handle generation only (no scraping)
  const handleGenerate = async () => {
    if (!username) return;

    // Check if user has premium account (regenerate all is premium-only)
    const accountType = userInfo?.account_type;
    if (accountType === 'trial' || accountType === 'poster') {
      setShowPremiumModal(true);
      return;
    }

    // Start polling for generation status
    const pollInterval = setInterval(async () => {
      if (!username) return;
      try {
        // Poll scraping status (reuses same endpoint)
        const status = await api.getScrapingStatus(username);

        // Update status based on current phase
        if (status.type === 'generating') {
          setLoadingStatusData({ type: 'generating', value: status.value });
        } else if (status.type === 'complete') {
          setLoadingStatusData({ type: 'complete', value: '' });
        }

        // Poll tweets to show updated replies
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
      // Only generate AI replies for existing cached tweets (with overwrite)
      setLoadingPhase('generating');
      setLoadingStatusData(null);
      const generateResult = await api.generateReplies(username, { overwrite: true });
      console.log(`Generated ${generateResult.replies_generated} replies`);

      // Stop polling and do final reload
      clearInterval(pollInterval);
      setLoadingPhase(null);
      setLoadingStatusData(null);
      await loadTweets(username);
    } catch (error) {
      clearInterval(pollInterval);
      console.error('Failed to generate replies:', error);
      alert('Failed to generate replies. Please try again.');
      setLoadingPhase(null);
      setLoadingStatusData(null);
    }
  };


  const handleLogout = () => {
    setUsername(null);
    setTweets([]);
    localStorage.removeItem('username');
  };

  const handleEditReply = async (tweetId: string, newReply: string, replyIndex: number = 0) => {
    if (!username) return;

    try {
      await api.editTweetReply(username, tweetId, newReply, replyIndex);
      // Update local state - update the specific reply in the generated_replies array
      // Preserve tuple format: [(text, model), ...]
      setTweets(tweets.map(t => {
        if (t.id === tweetId) {
          const generatedReplies: Array<[string, string]> = t.generated_replies || (t.reply ? [[t.reply, 'unknown']] : []);
          const updatedReplies: Array<[string, string]> = [...generatedReplies];
          // Update the text while preserving the model name
          const currentModel = Array.isArray(updatedReplies[replyIndex]) && updatedReplies[replyIndex].length >= 2
            ? updatedReplies[replyIndex][1]
            : 'unknown';
          updatedReplies[replyIndex] = [newReply, currentModel];
          return { ...t, generated_replies: updatedReplies };
        }
        return t;
      }));
    } catch (error) {
      console.error('Failed to edit reply:', error);
    }
  };

  const handleRegenerate = async (tweetId: string) => {
    if (!username) return;

    // Check if user has premium account (regenerate is premium-only)
    const accountType = userInfo?.account_type;
    if (accountType === 'trial' || accountType === 'poster') {
      setShowPremiumModal(true);
      return;
    }

    // Mark as regenerating
    setRegeneratingTweetIds(prev => new Set(prev).add(tweetId));

    try {
      const result = await api.regenerateSingleReply(username, tweetId);
      // Update local state with the new generated_replies (array of tuples)
      setTweets(tweets.map(t =>
        t.id === tweetId ? { ...t, generated_replies: result.new_replies } : t
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

  const handlePublishInternal = async (tweetId: string, text: string, replyIndex: number = 0) => {
    if (!username) return;

    // Mark as posting to trigger animation
    setPostingTweetIds(prev => new Set(prev).add(tweetId));

    // Wait for animation to complete
    setTimeout(async () => {
      const tweet = tweets.find(t => t.id === tweetId);
      if (!tweet) return;

      try {
        await api.postReply(username, text, tweet.id, tweet.cache_id, replyIndex);

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

  // Wrapper for publishing with trial limit check
  const handlePublish = async (tweetId: string, text: string, replyIndex: number = 0) => {
    if (!username) return;

    // Check if user is trial and has posts remaining
    const accountType = userInfo?.account_type;
    if (accountType === 'trial') {
      const postsRemaining = userInfo?.posts_left ?? 0;

      if (postsRemaining <= 0) {
        // No posts left - show upgrade message
        setPaidModalConfig({
          actionType: 'post',
          remaining: 0,
          onAction: () => {} // No action if no posts left
        });
        setShowPaidModal(true);
        return;
      }

      // Has posts left - show confirmation modal
      setPaidModalConfig({
        actionType: 'post',
        remaining: postsRemaining,
        onAction: () => handlePublishInternal(tweetId, text, replyIndex)
      });
      setShowPaidModal(true);
      return;
    }

    // Non-trial users can post directly
    await handlePublishInternal(tweetId, text, replyIndex);
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

  const handleFirstTimeModalComplete = async (email: string) => {
    if (!username) return;

    try {
      if (email) {
        await api.updateUserEmail(username, email);
        console.log('Email saved successfully');
      }

      // Close the modal
      setShowFirstTimeModal(false);

      // Reload user info to get updated data
      await loadUserInfo(username);
    } catch (error) {
      console.error('Failed to save email:', error);
      throw error; // Re-throw to let modal show error
    }
  };

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
        onScrapeClick={handleScrape}
        onGenerateClick={handleGenerate}
        hasInvalidAccounts={hasInvalidAccounts}
      />

      {userInfo && (
        <UserSettingsModal
          isOpen={isSettingsOpen}
          onClose={async (generationHappened?: boolean) => {
            const wasFirstTimeSetup = isFirstTimeSetup;
            setIsSettingsOpen(false);

            // If generation will happen, show loading overlay and poll for completion
            if (generationHappened) {
              setLoadingPhase('generating');
              setLoadingStatusData(null);

              // Start polling for status immediately
              const pollInterval = setInterval(async () => {
                if (!username) return;
                try {
                  const status = await api.getScrapingStatus(username);

                  if (status.type === 'generating') {
                    setLoadingStatusData({ type: 'generating', value: status.value });
                  } else if (status.type === 'complete') {
                    setLoadingStatusData({ type: 'complete', value: '' });
                    // Stop polling when complete
                    clearInterval(pollInterval);

                    // Wait a moment then reload and hide overlay
                    setTimeout(async () => {
                      setLoadingPhase(null);
                      setLoadingStatusData(null);
                      await loadTweets(username!);
                      await loadUserInfo(username!);
                    }, 1000);
                  }

                  // Also poll tweets to show them updating in real-time
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
              }, 1000); // Poll every second

              // Safety timeout - if status never becomes 'complete', stop after 60 seconds
              setTimeout(() => {
                clearInterval(pollInterval);
                setLoadingPhase(null);
                setLoadingStatusData(null);
                loadTweets(username!).catch(console.error);
                loadUserInfo(username!).catch(console.error);
              }, 60000);
            } else {
              // No generation, just reload normally
              await loadUserInfo(username!);
              await loadTweets(username!);
            }

            // If we just completed first-time setup, auto-trigger scrape
            if (wasFirstTimeSetup) {
              setTimeout(() => {
                handleScrape();
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
        <EmptyState onRefresh={handleScrape} />
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
                      myProfilePicUrl={userInfo!.profile_pic_url}
                      maxReplies={numberOfGenerations}
                      onPublish={(text, replyIndex) => handlePublish(tweet.id, text, replyIndex)}
                      onSkip={() => handleDelete(tweet.id)}
                      onEditReply={(newReply, replyIndex) => handleEditReply(tweet.id, newReply, replyIndex)}
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
                      myProfilePicUrl={userInfo!.profile_pic_url}
                      maxReplies={numberOfGenerations}
                      onPublish={(text, replyIndex) => handlePublish(tweet.id, text, replyIndex)}
                      onSkip={() => handleDelete(tweet.id)}
                      onEditReply={(newReply, replyIndex) => handleEditReply(tweet.id, newReply, replyIndex)}
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
      <LoadingOverlay />

      {/* First-time user email modal */}
      {showFirstTimeModal && username && (
        <FirstTimeUserModal
          username={username}
          onComplete={handleFirstTimeModalComplete}
        />
      )}

      {/* Premium feature modal */}
      <PremiumFeatureModal
        isOpen={showPremiumModal}
        onClose={() => setShowPremiumModal(false)}
      />

      {/* Paid feature modal (trial limits) */}
      <PaidFeatureModal
        isOpen={showPaidModal}
        onClose={() => setShowPaidModal(false)}
        actionType={paidModalConfig?.actionType}
        remaining={paidModalConfig?.remaining}
        onAction={paidModalConfig?.onAction}
      />

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
