import { useEffect, useState, useCallback, useRef, useLayoutEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useRecoilState } from 'recoil';
import { type ReplyData } from './components/ReplyDisplay';
import { type PostedData } from './components/PostedDisplay';
import { api, type PostWithComments } from './api/client';
import { DiscoveredTab } from './pages/DiscoveredTab';
import { PostedTab } from './pages/PostedTab';
import { CommentsTab } from './pages/CommentsTab';
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
import { NewPostsModal } from './components/NewPostsModal';
import {
  usernameState,
  userInfoState,
  isSettingsOpenState,
  showFirstTimeModalState,
  activeTabState,
  loadingPhaseState,
  loadingStatusDataState,
  loadingOverlayDismissedState,
  showNewPostsModalState,
  newPostsCountState,
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
  const [loadingStatusData, setLoadingStatusData] = useRecoilState(loadingStatusDataState);
  const [overlayDismissed, setOverlayDismissed] = useRecoilState(loadingOverlayDismissedState);
  const [showNewPostsModal, setShowNewPostsModal] = useRecoilState(showNewPostsModalState);
  const [newPostsCount, setNewPostsCount] = useRecoilState(newPostsCountState);

  // Local state (component-specific)
  const [tweets, setTweets] = useState<ReplyData[]>([]);
  const [currentTweetIndex, setCurrentTweetIndex] = useState(0);
  const [deletingTweetIds, setDeletingTweetIds] = useState<Set<string>>(new Set());
  const [postingTweetIds, setPostingTweetIds] = useState<Set<string>>(new Set());
  const [regeneratingTweetIds, setRegeneratingTweetIds] = useState<Set<string>>(new Set());
  const [postedTweets, setPostedTweets] = useState<PostedData[]>([]);
  const [hasInvalidAccounts, setHasInvalidAccounts] = useState(false);
  const [isFirstTimeSetup, setIsFirstTimeSetup] = useState(false);
  const [hasMorePostedTweets, setHasMorePostedTweets] = useState(true);
  const [isLoadingMorePosted, setIsLoadingMorePosted] = useState(false);
  // Comments state (grouped by post)
  const [postsWithComments, setPostsWithComments] = useState<PostWithComments[]>([]);
  const [pendingCommentsCount, setPendingCommentsCount] = useState(0);
  const [isLoadingComments, setIsLoadingComments] = useState(false);
  const [postingCommentIds, setPostingCommentIds] = useState<Set<string>>(new Set());
  const [skippingCommentIds, setSkippingCommentIds] = useState<Set<string>>(new Set());
  const [regeneratingCommentIds, setRegeneratingCommentIds] = useState<Set<string>>(new Set());
  const [numberOfGenerations, setNumberOfGenerations] = useState<number>(1);
  const [showPremiumModal, setShowPremiumModal] = useState(false);
  const [showPaidModal, setShowPaidModal] = useState(false);
  const [paidModalConfig, setPaidModalConfig] = useState<{
    actionType: 'scrape' | 'post';
    remaining: number;
    onAction: () => void;
  } | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  // Key to trigger resetting "seen" tracking in DiscoveredTab (incremented on purge)
  const [resetSeenKey, setResetSeenKey] = useState(0);
  const postedTweetsOffsetRef = useRef(0);
  // Track tweet IDs that have been marked as seen in this session (to debounce API calls)
  const seenTweetIdsRef = useRef<Set<string>>(new Set());
  // Track tweet count before scrape to calculate new posts count
  const tweetCountBeforeScrapeRef = useRef<number>(0);
  // Track tweet IDs before scrape to identify new tweets
  const tweetIdsBeforeScrapeRef = useRef<Set<string>>(new Set());
  // Track if engagement monitoring is already in progress (debounce post-triggered refreshes)
  const engagementMonitoringInProgressRef = useRef(false);
  // Track if we've seen the job actually running (to avoid treating stale 'idle' as 'complete')
  const hasSeenJobRunningRef = useRef(false);
  // Scroll anchoring refs - keeps user's view stable when new tweets are added
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const scrollAnchorRef = useRef<{ tweetId: string; offsetFromTop: number } | null>(null);
  // Flag to trigger scroll restoration after tweets update
  const [shouldRestoreScroll, setShouldRestoreScroll] = useState(false);

  // Derived state: isLoading can be determined from loadingPhase
  const isLoading = loadingPhase !== null;

  // Capture scroll anchor before tweets update - finds first visible tweet
  const captureScrollAnchor = useCallback(() => {
    if (!scrollContainerRef.current || activeTab !== 'discovered') return;

    const container = scrollContainerRef.current;
    const containerRect = container.getBoundingClientRect();

    // Find all tweet elements
    const tweetElements = container.querySelectorAll('[data-tweet-id]');

    for (const el of tweetElements) {
      const rect = el.getBoundingClientRect();
      // Find first tweet that's at least partially visible
      if (rect.top < containerRect.bottom && rect.bottom > containerRect.top) {
        const tweetId = el.getAttribute('data-tweet-id');
        if (tweetId) {
          scrollAnchorRef.current = {
            tweetId,
            offsetFromTop: rect.top - containerRect.top
          };
          return;
        }
      }
    }
  }, [activeTab]);

  // Restore scroll position after DOM update
  useLayoutEffect(() => {
    if (!shouldRestoreScroll || !scrollAnchorRef.current || !scrollContainerRef.current) {
      return;
    }

    const { tweetId, offsetFromTop } = scrollAnchorRef.current;
    const container = scrollContainerRef.current;
    const anchorElement = container.querySelector(`[data-tweet-id="${tweetId}"]`);

    if (anchorElement) {
      const containerRect = container.getBoundingClientRect();
      const anchorRect = anchorElement.getBoundingClientRect();
      const currentOffset = anchorRect.top - containerRect.top;
      const scrollAdjustment = currentOffset - offsetFromTop;

      if (Math.abs(scrollAdjustment) > 5) { // Only adjust if meaningful difference
        container.scrollTop += scrollAdjustment;
      }
    }

    scrollAnchorRef.current = null;
    setShouldRestoreScroll(false);
  }, [shouldRestoreScroll]);

  // Wrapper for setTweets that preserves scroll position
  const setTweetsWithScrollAnchor = useCallback((updater: ReplyData[] | ((prev: ReplyData[]) => ReplyData[])) => {
    captureScrollAnchor();
    setTweets(updater);
    setShouldRestoreScroll(true);
  }, [captureScrollAnchor]);

  // Helper to translate job status to loading overlay format
  const translateJobStatusToLoadingStatus = (jobStatus: { status: string; phase: string; details?: string | null }) => {
    // Distinguish between idle (job not started/between phases) and complete (job actually finished)
    if (jobStatus.status === 'idle') {
      return { type: 'idle', value: '' };
    }
    if (jobStatus.status === 'complete') {
      return { type: 'complete', value: '' };
    }
    if (jobStatus.status === 'error') {
      return { type: 'error', value: '' };
    }
    // Running - translate phase using new simplified format
    const phase = jobStatus.phase || '';
    const details = jobStatus.details || '';

    if (phase === 'scraping') {
      // details contains @handle
      return { type: 'account', value: details.replace('@', '') };
    }
    if (phase === 'searching') {
      // details contains the query summary
      return { type: 'query', value: details, summary: details };
    }
    if (phase === 'scanning') {
      // Could be home timeline, warm tweets, or active tweets
      return { type: 'home_timeline', value: details };
    }
    if (phase === 'generating') {
      return { type: 'generating', value: details };
    }
    if (phase === 'discovering') {
      return { type: 'discovering', value: details };
    }
    return { type: 'scraping', value: '' };
  };

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
        // Deduplicate when appending to avoid race condition with new tweets shifting positions
        setPostedTweets(prev => {
          const existingIds = new Set(prev.map(t => t.id));
          const newTweets = data.tweets.filter(t => !existingIds.has(t.id));
          return [...prev, ...newTweets];
        });
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
      console.log('[App] Loading user info for:', username);
      loadUserInfo(username);
      loadTweets(username);
      // Don't load posted tweets here - will load when user switches to Posted tab
    } else {
      console.log('[App] No username found in initial load');
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

  // Load comments grouped by post
  const loadCommentsGrouped = useCallback(async (user: string) => {
    setIsLoadingComments(true);
    try {
      const data = await api.getCommentsGroupedByPost(user, 'pending');
      setPostsWithComments(data.posts_with_comments);

      // Use total_comments from grouped data so tab count matches what's displayed
      setPendingCommentsCount(data.total_comments);
    } catch (error) {
      console.error('Failed to load grouped comments:', error);
    } finally {
      setIsLoadingComments(false);
    }
  }, []);

  // Load comments when switching to Comments tab
  useEffect(() => {
    if (activeTab === 'comments' && username) {
      loadCommentsGrouped(username);
    }
  }, [activeTab, username, loadCommentsGrouped]);

  // Comment handlers (work with grouped state)
  const handlePublishCommentReply = async (commentId: string, text: string, replyIndex: number = 0): Promise<void> => {
    if (!username) return;

    setPostingCommentIds(prev => new Set(prev).add(commentId));

    // Wait for animation delay then execute
    await new Promise(resolve => setTimeout(resolve, 400));

    try {
      await api.postCommentReply(username, commentId, text, replyIndex);

      // Remove comment from grouped state
      setPostsWithComments(prev => prev.map(post => ({
        ...post,
        comments: post.comments.filter(c => c.id !== commentId),
        total_pending: post.total_pending - 1
      })).filter(post => post.comments.length > 0)); // Remove empty posts

      setPostingCommentIds(prev => {
        const next = new Set(prev);
        next.delete(commentId);
        return next;
      });

      // Update pending count
      setPendingCommentsCount(prev => Math.max(0, prev - 1));

      // Reload user info to update post count
      await loadUserInfo(username);

      // Trigger engagement monitoring in background (debounced - skip if already in progress)
      if (!isRefreshing && !engagementMonitoringInProgressRef.current) {
        engagementMonitoringInProgressRef.current = true;
        api.startEngagementMonitoring(username)
          .catch(err => console.error('Background engagement monitoring failed:', err))
          .finally(() => {
            // Reset after a delay to allow the job to complete before allowing another trigger
            setTimeout(() => {
              engagementMonitoringInProgressRef.current = false;
            }, 30000); // 30 second debounce
          });
      }
    } catch (error) {
      console.error('Failed to post comment reply:', error);
      setPostingCommentIds(prev => {
        const next = new Set(prev);
        next.delete(commentId);
        return next;
      });
      throw error; // Re-throw so caller knows it failed
    }
  };

  const handleSkipComment = async (commentId: string) => {
    if (!username) return;

    setSkippingCommentIds(prev => new Set(prev).add(commentId));

    setTimeout(async () => {
      try {
        await api.skipComment(username, commentId);

        // Remove comment from grouped state
        setPostsWithComments(prev => prev.map(post => ({
          ...post,
          comments: post.comments.filter(c => c.id !== commentId),
          total_pending: post.total_pending - 1
        })).filter(post => post.comments.length > 0)); // Remove empty posts

        setSkippingCommentIds(prev => {
          const next = new Set(prev);
          next.delete(commentId);
          return next;
        });

        // Update pending count
        setPendingCommentsCount(prev => Math.max(0, prev - 1));
      } catch (error) {
        console.error('Failed to skip comment:', error);
        alert('Failed to skip comment. Please try again.');
        setSkippingCommentIds(prev => {
          const next = new Set(prev);
          next.delete(commentId);
          return next;
        });
      }
    }, 300);
  };

  const handleRegenerateCommentReply = async (commentId: string) => {
    if (!username) return;

    setRegeneratingCommentIds(prev => new Set(prev).add(commentId));

    try {
      const result = await api.regenerateCommentReply(username, commentId);
      // Update comment in grouped state with new replies
      setPostsWithComments(prev => prev.map(post => ({
        ...post,
        comments: post.comments.map(c =>
          c.id === commentId ? { ...c, generated_replies: result.new_replies } : c
        )
      })));
    } catch (error) {
      console.error('Failed to regenerate comment reply:', error);
      alert('Failed to regenerate reply. Please try again.');
    } finally {
      setRegeneratingCommentIds(prev => {
        const next = new Set(prev);
        next.delete(commentId);
        return next;
      });
    }
  };

  const handleEditCommentReply = async (commentId: string, newReply: string, replyIndex: number) => {
    if (!username) return;

    // Update local state immediately for responsive UI
    setPostsWithComments(prev => prev.map(post => ({
      ...post,
      comments: post.comments.map(c => {
        if (c.id === commentId) {
          const updatedReplies = [...(c.generated_replies || [])];
          const currentModel = updatedReplies[replyIndex]?.[1] || 'edited';
          updatedReplies[replyIndex] = [newReply, currentModel];
          return { ...c, generated_replies: updatedReplies, edited: true };
        }
        return c;
      })
    })));

    // Persist to backend (logs the edit action)
    try {
      await api.editCommentReply(username, commentId, newReply, replyIndex);
    } catch (error) {
      console.error('Failed to save comment reply edit:', error);
      // Don't revert - the local edit is still valid
    }
  };

  const loadUserInfo = async (user: string) => {
    console.log('[loadUserInfo] Starting for user:', user);
    try {
      const info = await api.getUserInfo(user);
      console.log('[loadUserInfo] Got info:', info);
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

    // Reset overlay dismissed state when starting a new scrape
    setOverlayDismissed(false);
    // Track current tweet count before scrape
    tweetCountBeforeScrapeRef.current = tweets.length;
    // Track tweet IDs before scrape to identify new tweets
    tweetIdsBeforeScrapeRef.current = new Set(tweets.map(t => t.id));
    // Reset the "has seen running" flag - we need to see the job actually start before treating 'complete' as real
    hasSeenJobRunningRef.current = false;

    // Start polling for scraping status and tweets in the background
    const pollInterval = setInterval(async () => {
      if (!username) return;
      try {
        // Poll job status (unified status endpoint)
        const jobsStatus = await api.getJobsStatus(username);
        const job = jobsStatus.jobs.find_and_reply_to_new_posts;
        const status = translateJobStatusToLoadingStatus(job);
        console.log('[Polling] Job status:', job.status, job.phase, '| Translated:', status.type);

        // Update status based on current scraping phase
        if (status.type === 'account') {
          console.log('[Polling] Setting phase to scraping (account)');
          hasSeenJobRunningRef.current = true;
          setLoadingPhase('scraping');
          setLoadingStatusData({ type: 'account', value: status.value });
        } else if (status.type === 'query') {
          console.log('[Polling] Setting phase to scraping (query)');
          hasSeenJobRunningRef.current = true;
          setLoadingPhase('scraping');
          setLoadingStatusData({ type: 'query', value: status.value, summary: status.summary });
        } else if (status.type === 'generating') {
          console.log('[Polling] Setting phase to generating');
          hasSeenJobRunningRef.current = true;
          setLoadingPhase('generating');
          setLoadingStatusData({ type: 'generating', value: status.value });
        } else if (status.type === 'home_timeline' || status.type === 'discovering' || status.type === 'scraping') {
          // Other running states - mark as running and show generic scraping phase
          console.log(`[Polling] Setting phase to scraping (${status.type})`);
          hasSeenJobRunningRef.current = true;
          setLoadingPhase('scraping');
          setLoadingStatusData({ type: status.type, value: status.value });
        } else if (status.type === 'complete' && hasSeenJobRunningRef.current) {
          // Only treat 'complete' as real if we've seen the job running first
          // This prevents stale 'idle' status from triggering premature completion
          console.log('[Polling] Status complete, stopping polling');
          setLoadingStatusData({ type: 'complete', value: '' });

          // Stop polling
          clearInterval(pollInterval);
          setLoadingPhase(null);
          setLoadingStatusData(null);
          await loadUserInfo(username);

          // Load tweets and calculate new posts count
          const data = await api.getTweetsCache(username);
          const tweetsWithThreads = data.filter(tweet => {
            const hasThread = tweet.thread && Array.isArray(tweet.thread) && tweet.thread.length > 0;
            return hasThread;
          });
          const sorted = tweetsWithThreads.sort((a, b) => {
            return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
          });
          // Merge: preserve local edits for existing tweets
          setTweetsWithScrollAnchor(prevTweets => {
            const prevTweetsMap = new Map(prevTweets.map(t => [t.id, t]));
            return sorted.map(newTweet => {
              const existingTweet = prevTweetsMap.get(newTweet.id);
              if (existingTweet?.edited) {
                return existingTweet;
              }
              return newTweet;
            });
          });

          // Calculate new posts and mark them as unseen before showing modal
          const newTweetIds = sorted
            .filter(t => !tweetIdsBeforeScrapeRef.current.has(t.id))
            .map(t => t.id);
          const newCount = newTweetIds.length;
          setNewPostsCount(Math.max(0, newCount));

          // Mark new tweets as unseen so they won't be removed by "clear seen"
          if (newTweetIds.length > 0) {
            try {
              await api.markTweetsUnseen(username, newTweetIds);
              console.log(`[Polling] Marked ${newTweetIds.length} new tweets as unseen`);
            } catch (err) {
              console.error('[Polling] Failed to mark tweets as unseen:', err);
            }
          }

          setShowNewPostsModal(true);
        } else if (status.type === 'idle') {
          // Status is idle - only treat as complete if we've seen the job actually running
          // This prevents early 'idle' status (before job starts) from triggering completion
          if (hasSeenJobRunningRef.current) {
            console.log('[Polling] Status idle after job ran, treating as complete');
            clearInterval(pollInterval);
            setLoadingPhase(null);
            setLoadingStatusData(null);
            await loadUserInfo(username);

            // Load tweets and calculate new posts count
            const data = await api.getTweetsCache(username);
            const tweetsWithThreads = data.filter(tweet => {
              const hasThread = tweet.thread && Array.isArray(tweet.thread) && tweet.thread.length > 0;
              return hasThread;
            });
            const sorted = tweetsWithThreads.sort((a, b) => {
              return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
            });
            // Merge: preserve local edits for existing tweets
            // Use scroll anchor wrapper to keep user's view stable
            setTweetsWithScrollAnchor(prevTweets => {
              const prevTweetsMap = new Map(prevTweets.map(t => [t.id, t]));
              return sorted.map(newTweet => {
                const existingTweet = prevTweetsMap.get(newTweet.id);
                if (existingTweet?.edited) {
                  return existingTweet;
                }
                return newTweet;
              });
            });

            // Calculate new posts and mark them as unseen before showing modal
            const newTweetIds = sorted
              .filter(t => !tweetIdsBeforeScrapeRef.current.has(t.id))
              .map(t => t.id);
            const newCount = newTweetIds.length;
            setNewPostsCount(Math.max(0, newCount));

            // Mark new tweets as unseen so they won't be removed by "clear seen"
            if (newTweetIds.length > 0) {
              try {
                await api.markTweetsUnseen(username, newTweetIds);
                console.log(`[Polling] Marked ${newTweetIds.length} new tweets as unseen`);
              } catch (err) {
                console.error('[Polling] Failed to mark tweets as unseen:', err);
              }
            }

            setShowNewPostsModal(true);
          } else {
            // Job hasn't started yet, keep polling
            console.log('[Polling] Status idle, waiting for job to start...');
          }
        } else if (status.type === 'complete' && !hasSeenJobRunningRef.current) {
          // Got 'complete' but never saw running - might be stale, keep polling
          console.log('[Polling] Status complete but never saw running, waiting...');
        } else if (status.type === 'error') {
          // Job errored - stop polling and clear loading state
          console.error('[Polling] Job errored, stopping polling');
          clearInterval(pollInterval);
          setLoadingPhase(null);
          setLoadingStatusData(null);
        } else if (status.type !== 'complete' && status.type !== 'idle') {
          // Log unexpected status types
          console.warn('[Polling] Unexpected status type:', status.type);
        }

        // Poll tweets to show them appearing in real-time
        // Merge with existing state to preserve local edits
        const data = await api.getTweetsCache(username);
        const tweetsWithThreads = data.filter(tweet => {
          const hasThread = tweet.thread && Array.isArray(tweet.thread) && tweet.thread.length > 0;
          return hasThread;
        });
        const sorted = tweetsWithThreads.sort((a, b) => {
          return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
        });
        // Merge: preserve local edits for existing tweets, add new tweets
        // Use scroll anchor wrapper to keep user's view stable
        setTweetsWithScrollAnchor(prevTweets => {
          const prevTweetsMap = new Map(prevTweets.map(t => [t.id, t]));
          return sorted.map(newTweet => {
            const existingTweet = prevTweetsMap.get(newTweet.id);
            // If we have a local edit, preserve it
            if (existingTweet?.edited) {
              return existingTweet;
            }
            return newTweet;
          });
        });
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

  // Handle refresh (engagement monitoring - check for new comments on existing posts)
  const handleRefresh = async () => {
    if (!username || isRefreshing) return;

    setIsRefreshing(true);

    try {
      // Start engagement monitoring in the background
      await api.startEngagementMonitoring(username);

      // Poll job status until jobs are complete
      const pollInterval = setInterval(async () => {
        try {
          // Check job status
          const jobsStatus = await api.getJobsStatus(username);
          const activityJob = jobsStatus.jobs.find_user_activity;
          const engagementJob = jobsStatus.jobs.find_and_reply_to_engagement;

          console.log(`[Refresh] Activity: ${activityJob.status} (${activityJob.percentage}%), Engagement: ${engagementJob.status} (${engagementJob.percentage}%)`);

          // Check if both relevant jobs are complete (or idle, meaning they finished)
          const activityDone = activityJob.status === 'complete' || activityJob.status === 'idle';
          const engagementDone = engagementJob.status === 'complete' || engagementJob.status === 'idle';

          if (activityDone && engagementDone) {
            clearInterval(pollInterval);

            // Refresh data after jobs complete
            const postedData = await api.getPostedTweets(username, 50, 0);
            setPostedTweets(postedData.tweets || []);
            postedTweetsOffsetRef.current = postedData.tweets?.length || 0;
            setHasMorePostedTweets((postedData.tweets?.length || 0) >= 50);

            const commentsData = await api.getCommentsGroupedByPost(username, 'pending');
            setPostsWithComments(commentsData.posts_with_comments || []);
            setPendingCommentsCount(commentsData.total_comments || 0);

            setIsRefreshing(false);
            console.log('[Refresh] Complete - jobs finished');
          }
        } catch (error) {
          console.error('Polling error during refresh:', error);
          // Continue polling on error
        }
      }, 2000); // Poll every 2 seconds

    } catch (error) {
      console.error('Failed to start engagement monitoring:', error);
      setIsRefreshing(false);
    }
  };

  const handleLogout = () => {
    setUsername(null);
    setTweets([]);
    localStorage.removeItem('username');
  };

  const handleEditReply = async (tweetId: string, newReply: string, replyIndex: number = 0) => {
    if (!username) return;

    // Immediately mark as edited to prevent polling from overwriting during API call
    setTweets(prev => prev.map(t => t.id === tweetId ? { ...t, edited: true } : t));

    try {
      await api.editTweetReply(username, tweetId, newReply, replyIndex);
      // Update local state - update the specific reply in the generated_replies array
      // Preserve tuple format: [(text, model), ...]
      // Reset edited flag since backend cache now has the update
      setTweets(prev => prev.map(t => {
        if (t.id === tweetId) {
          const generatedReplies: Array<[string, string]> = t.generated_replies || (t.reply ? [[t.reply, 'unknown']] : []);
          const updatedReplies: Array<[string, string]> = [...generatedReplies];
          // Update the text while preserving the model name
          const currentModel = Array.isArray(updatedReplies[replyIndex]) && updatedReplies[replyIndex].length >= 2
            ? updatedReplies[replyIndex][1]
            : 'unknown';
          updatedReplies[replyIndex] = [newReply, currentModel];
          return { ...t, generated_replies: updatedReplies, edited: false };
        }
        return t;
      }));
    } catch (error) {
      console.error('Failed to edit reply:', error);
      // Keep edited: true on error to preserve user's local changes
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

        // Trigger engagement monitoring in background (debounced - skip if already in progress)
        if (!isRefreshing && !engagementMonitoringInProgressRef.current) {
          engagementMonitoringInProgressRef.current = true;
          api.startEngagementMonitoring(username)
            .catch(err => console.error('Background engagement monitoring failed:', err))
            .finally(() => {
              // Reset after a delay to allow the job to complete before allowing another trigger
              setTimeout(() => {
                engagementMonitoringInProgressRef.current = false;
              }, 30000); // 30 second debounce
            });
        }

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

  // Handler for viewing a posted tweet - refresh metrics
  const handleViewPostedTweet = async (tweetId: string) => {
    if (!username) return;

    try {
      const result = await api.checkTweetPerformance(username, [tweetId]);

      // Update the local state with new metrics
      if (result.metrics && result.metrics.length > 0) {
        const updatedMetrics = result.metrics[0];
        setPostedTweets(prev =>
          prev.map(tweet =>
            tweet.id === tweetId
              ? {
                  ...tweet,
                  likes: updatedMetrics.likes,
                  retweets: updatedMetrics.retweets,
                  quotes: updatedMetrics.quotes,
                  replies: updatedMetrics.replies,
                  last_metrics_update: new Date().toISOString()
                }
              : tweet
          )
        );
      }
    } catch (error) {
      // Silently fail - don't block opening the tweet
      console.error('Failed to refresh metrics:', error);
    }
  };

  // Handler for dismissing loading overlay
  const handleDismissOverlay = () => {
    setOverlayDismissed(true);
  };

  // Handler for purging seen tweets (modal confirm)
  const handlePurgeSeenTweets = async () => {
    if (!username) return;

    try {
      const result = await api.purgeSeenTweets(username);
      console.log(`Purged ${result.removed_count} seen tweets`);

      // Clear the seen tracking ref so remaining tweets can be re-marked when scrolled
      seenTweetIdsRef.current.clear();
      // Increment key to trigger DiscoveredTab to clear its local seen tracking
      setResetSeenKey(k => k + 1);

      // Reload tweets to reflect purged state
      await loadTweets(username);
    } catch (error) {
      console.error('Failed to purge seen tweets:', error);
    } finally {
      setShowNewPostsModal(false);
    }
  };

  // Handler for canceling purge (modal cancel)
  const handleCancelPurge = () => {
    setShowNewPostsModal(false);
  };

  // Handler for marking tweets as seen when they scroll into view
  const handleMarkTweetsSeen = useCallback(async (tweetIds: string[]) => {
    if (!username || tweetIds.length === 0) return;

    // Filter out already-marked tweets
    const newTweetIds = tweetIds.filter(id => !seenTweetIdsRef.current.has(id));
    if (newTweetIds.length === 0) return;

    // Add to local tracking immediately
    newTweetIds.forEach(id => seenTweetIdsRef.current.add(id));

    try {
      await api.markTweetsSeen(username, newTweetIds);
      console.log(`Marked ${newTweetIds.length} tweets as seen`);
    } catch (error) {
      console.error('Failed to mark tweets as seen:', error);
      // Remove from local tracking on error so we can retry
      newTweetIds.forEach(id => seenTweetIdsRef.current.delete(id));
    }
  }, [username]);

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
        username={username || ''}
        onSettingsClick={() => setIsSettingsOpen(true)}
        onScrapeClick={handleScrape}
        onRefreshClick={handleRefresh}
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

              // Start polling for status immediately (using unified job status)
              const pollInterval = setInterval(async () => {
                if (!username) return;
                try {
                  const jobsStatus = await api.getJobsStatus(username);
                  const job = jobsStatus.jobs.find_and_reply_to_new_posts;
                  const status = translateJobStatusToLoadingStatus(job);

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
                  // Merge: preserve local edits for existing tweets
                  // Use scroll anchor wrapper to keep user's view stable
                  setTweetsWithScrollAnchor(prevTweets => {
                    const prevTweetsMap = new Map(prevTweets.map(t => [t.id, t]));
                    return sorted.map(newTweet => {
                      const existingTweet = prevTweetsMap.get(newTweet.id);
                      if (existingTweet?.edited) {
                        return existingTweet;
                      }
                      return newTweet;
                    });
                  });
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
        discoveredCount={tweets.length}
        postedCount={userInfo?.lifetime_posts || 0}
        commentsCount={pendingCommentsCount}
      />

      {/* Content Area - Show tweets or empty state */}
      {activeTab === 'discovered' && tweets.length === 0 ? (
        <EmptyState onRefresh={handleScrape} />
      ) : (
        <div
          ref={scrollContainerRef}
          className="flex-1 overflow-y-auto scrollbar-hide"
          onScroll={(e) => {
            const element = e.currentTarget;
            const isNearBottom = element.scrollHeight - element.scrollTop - element.clientHeight < 500;

            if (activeTab === 'posted' && isNearBottom && !isLoadingMorePosted && hasMorePostedTweets) {
              loadMorePostedTweets();
            }
          }}
        >
          <div className="flex gap-6 py-10 px-6">
            {activeTab === 'discovered' && userInfo && (
              <DiscoveredTab
                tweets={tweets}
                userProfilePicUrl={userInfo.profile_pic_url}
                numberOfGenerations={numberOfGenerations}
                deletingTweetIds={deletingTweetIds}
                postingTweetIds={postingTweetIds}
                regeneratingTweetIds={regeneratingTweetIds}
                onPublish={handlePublish}
                onDelete={handleDelete}
                onEditReply={handleEditReply}
                onRegenerate={handleRegenerate}
                onTweetsSeen={handleMarkTweetsSeen}
                resetSeenKey={resetSeenKey}
              />
            )}

            {activeTab === 'posted' && userInfo && (
              <PostedTab
                postedTweets={postedTweets}
                userProfilePicUrl={userInfo.profile_pic_url}
                userHandle={userInfo.handle}
                userUsername={userInfo.username}
                deletingTweetIds={deletingTweetIds}
                isLoadingMore={isLoadingMorePosted}
                onDelete={handleDeletePosted}
                onViewTweet={handleViewPostedTweet}
              />
            )}

            {activeTab === 'comments' && userInfo && (
              <CommentsTab
                postsWithComments={postsWithComments}
                numberOfGenerations={numberOfGenerations}
                isLoading={isLoadingComments}
                userProfilePicUrl={userInfo.profile_pic_url}
                postingCommentIds={postingCommentIds}
                skippingCommentIds={skippingCommentIds}
                regeneratingCommentIds={regeneratingCommentIds}
                onPublishReply={handlePublishCommentReply}
                onSkipComment={handleSkipComment}
                onEditReply={handleEditCommentReply}
                onRegenerateReply={handleRegenerateCommentReply}
              />
            )}
          </div>
        </div>
      )}

      {/* Loading overlay - only show if not dismissed */}
      {!overlayDismissed && (
        <LoadingOverlay
          phase={loadingPhase}
          statusData={loadingStatusData}
          onDismiss={handleDismissOverlay}
        />
      )}

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

      {/* New posts modal - shown after scrape completes */}
      <NewPostsModal
        isOpen={showNewPostsModal}
        onConfirm={handlePurgeSeenTweets}
        onCancel={handleCancelPurge}
        newPostsCount={newPostsCount}
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
