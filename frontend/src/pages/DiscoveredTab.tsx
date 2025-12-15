import { useEffect, useRef, useCallback } from 'react';
import { AnimatePresence } from 'framer-motion';
import { ReplyDisplay, type ReplyData } from '../components/ReplyDisplay';
import { AnimatedListItem } from '../components/AnimatedListItem';

interface DiscoveredTabProps {
  tweets: ReplyData[];
  userProfilePicUrl: string;
  numberOfGenerations: number;
  deletingTweetIds: Set<string>;
  postingTweetIds: Set<string>;
  regeneratingTweetIds: Set<string>;
  onPublish: (tweetId: string, text: string, replyIndex: number) => void;
  onDelete: (tweetId: string) => void;
  onEditReply: (tweetId: string, newReply: string, replyIndex: number) => void;
  onRegenerate: (tweetId: string) => void;
  onTweetsSeen?: (tweetIds: string[]) => void;
  resetSeenKey?: number;  // Increment to clear seen tracking (after purge)
}

// Distribute tweets evenly between columns based on array index
// This ensures balanced columns after any filtering/purging
function getColumnByIndex(tweets: ReplyData[], tweetId: string): 0 | 1 {
  const index = tweets.findIndex(t => t.id === tweetId);
  // Alternate: even indices go to column 0, odd to column 1
  return (index % 2) as 0 | 1;
}

export function DiscoveredTab({
  tweets,
  userProfilePicUrl,
  numberOfGenerations,
  deletingTweetIds,
  postingTweetIds,
  regeneratingTweetIds,
  onPublish,
  onDelete,
  onEditReply,
  onRegenerate,
  onTweetsSeen,
  resetSeenKey,
}: DiscoveredTabProps) {
  // Track which tweets have been seen in this session (debounce)
  const seenIdsRef = useRef<Set<string>>(new Set());
  // Batch seen tweets for debounced API call
  const pendingSeenIdsRef = useRef<Set<string>>(new Set());
  const flushTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Clear seen tracking when resetSeenKey changes (after purge)
  useEffect(() => {
    if (resetSeenKey !== undefined && resetSeenKey > 0) {
      seenIdsRef.current.clear();
      pendingSeenIdsRef.current.clear();
      console.log('Cleared seen tracking refs after purge');
    }
  }, [resetSeenKey]);

  // Flush pending seen tweets to parent
  const flushSeenTweets = useCallback(() => {
    if (pendingSeenIdsRef.current.size > 0 && onTweetsSeen) {
      const ids = Array.from(pendingSeenIdsRef.current);
      //console.log(`[DiscoveredTab] Flushing ${ids.length} seen tweets to parent:`, ids);
      pendingSeenIdsRef.current.clear();
      onTweetsSeen(ids);
    }
  }, [onTweetsSeen]);

  // Add tweet to pending seen list with debounce
  const markAsSeen = useCallback((tweetId: string) => {
    if (seenIdsRef.current.has(tweetId)) {
      //console.log(`[DiscoveredTab] Tweet ${tweetId} already in seenIdsRef, skipping`);
      return;
    }
    //console.log(`[DiscoveredTab] Marking tweet ${tweetId} as seen`);
    seenIdsRef.current.add(tweetId);
    pendingSeenIdsRef.current.add(tweetId);

    // Debounce: flush after 1 second of no new seen tweets
    if (flushTimeoutRef.current) {
      clearTimeout(flushTimeoutRef.current);
    }
    flushTimeoutRef.current = setTimeout(flushSeenTweets, 1000);
  }, [flushSeenTweets]);

  // Set up Intersection Observer for scroll tracking
  useEffect(() => {
    if (!onTweetsSeen) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          const tweetId = entry.target.getAttribute('data-tweet-id');
          console.log(`[IntersectionObserver] Tweet ${tweetId}: isIntersecting=${entry.isIntersecting}, ratio=${entry.intersectionRatio.toFixed(2)}`);
          if (entry.isIntersecting) {
            if (tweetId) {
              markAsSeen(tweetId);
            }
          }
        });
      },
      {
        root: null,
        rootMargin: '0px',
        threshold: 0.1, // Tweet is "seen" when 10% visible (lowered for reliability)
      }
    );

    // Defer DOM query until after React has painted using requestAnimationFrame
    // This ensures all tweet elements are in the DOM before we try to observe them
    const rafId = requestAnimationFrame(() => {
      const tweetElements = document.querySelectorAll('[data-tweet-id]');
      console.log(`[DiscoveredTab] Observing ${tweetElements.length} tweet elements`);
      tweetElements.forEach((el) => observer.observe(el));
    });

    return () => {
      cancelAnimationFrame(rafId);
      observer.disconnect();
      // Flush any remaining seen tweets on unmount
      if (flushTimeoutRef.current) {
        clearTimeout(flushTimeoutRef.current);
      }
      flushSeenTweets();
    };
  }, [tweets, onTweetsSeen, markAsSeen, flushSeenTweets]);

  return (
    <>
      {/* Left Column */}
      <div className="flex-1 flex flex-col gap-6">
        <AnimatePresence mode="popLayout">
          {tweets.filter((tweet) => getColumnByIndex(tweets, tweet.id) === 0).map((tweet) => (
            <AnimatedListItem
              key={tweet.id}
              itemKey={tweet.id}
              variant={postingTweetIds.has(tweet.id) ? "slide-right" : "scale"}
            >
              <div data-tweet-id={tweet.id}>
                <ReplyDisplay
                  tweet={tweet}
                  myProfilePicUrl={userProfilePicUrl}
                  maxReplies={numberOfGenerations}
                  onPublish={(text, replyIndex) => onPublish(tweet.id, text, replyIndex)}
                  onSkip={() => onDelete(tweet.id)}
                  onEditReply={(newReply, replyIndex) => onEditReply(tweet.id, newReply, replyIndex)}
                  onRegenerate={() => onRegenerate(tweet.id)}
                  isDeleting={deletingTweetIds.has(tweet.id)}
                  isPosting={postingTweetIds.has(tweet.id)}
                  isRegenerating={regeneratingTweetIds.has(tweet.id)}
                />
              </div>
            </AnimatedListItem>
          ))}
        </AnimatePresence>
      </div>
      {/* Right Column */}
      <div className="flex-1 flex flex-col gap-6">
        <AnimatePresence mode="popLayout">
          {tweets.filter((tweet) => getColumnByIndex(tweets, tweet.id) === 1).map((tweet) => (
            <AnimatedListItem
              key={tweet.id}
              itemKey={tweet.id}
              variant={postingTweetIds.has(tweet.id) ? "slide-right" : "scale"}
            >
              <div data-tweet-id={tweet.id}>
                <ReplyDisplay
                  tweet={tweet}
                  myProfilePicUrl={userProfilePicUrl}
                  maxReplies={numberOfGenerations}
                  onPublish={(text, replyIndex) => onPublish(tweet.id, text, replyIndex)}
                  onSkip={() => onDelete(tweet.id)}
                  onEditReply={(newReply, replyIndex) => onEditReply(tweet.id, newReply, replyIndex)}
                  onRegenerate={() => onRegenerate(tweet.id)}
                  isDeleting={deletingTweetIds.has(tweet.id)}
                  isPosting={postingTweetIds.has(tweet.id)}
                  isRegenerating={regeneratingTweetIds.has(tweet.id)}
                />
              </div>
            </AnimatedListItem>
          ))}
        </AnimatePresence>
      </div>
    </>
  );
}
