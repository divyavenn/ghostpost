import { useEffect, useRef, useCallback } from 'react';
import { AnimatePresence } from 'framer-motion';
import { ReplyDisplay, type ReplyData } from '../components/ReplyDisplay';
import { AnimatedListItem } from '../components/AnimatedListItem';

interface GeneratedTabProps {
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
}

export function GeneratedTab({
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
}: GeneratedTabProps) {
  // Track which tweets have been seen in this session (debounce)
  const seenIdsRef = useRef<Set<string>>(new Set());
  // Batch seen tweets for debounced API call
  const pendingSeenIdsRef = useRef<Set<string>>(new Set());
  const flushTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Flush pending seen tweets to parent
  const flushSeenTweets = useCallback(() => {
    if (pendingSeenIdsRef.current.size > 0 && onTweetsSeen) {
      const ids = Array.from(pendingSeenIdsRef.current);
      pendingSeenIdsRef.current.clear();
      onTweetsSeen(ids);
    }
  }, [onTweetsSeen]);

  // Add tweet to pending seen list with debounce
  const markAsSeen = useCallback((tweetId: string) => {
    if (seenIdsRef.current.has(tweetId)) return;
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
          if (entry.isIntersecting) {
            const tweetId = entry.target.getAttribute('data-tweet-id');
            if (tweetId) {
              markAsSeen(tweetId);
            }
          }
        });
      },
      {
        root: null,
        rootMargin: '0px',
        threshold: 0.5, // Tweet is "seen" when 50% visible
      }
    );

    // Observe all tweet elements
    const tweetElements = document.querySelectorAll('[data-tweet-id]');
    tweetElements.forEach((el) => observer.observe(el));

    return () => {
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
          {tweets.filter((_, index) => index % 2 === 0).map((tweet) => (
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
          {tweets.filter((_, index) => index % 2 === 1).map((tweet) => (
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
