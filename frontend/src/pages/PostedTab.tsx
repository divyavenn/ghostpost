import { useMemo, useState } from 'react';
import { AnimatePresence } from 'framer-motion';
import { DotLottieReact } from '@lottiefiles/dotlottie-react';
import xLottie from '../assets/x.lottie';
import { type PostedData, type TweetSource } from '../components/PostedDisplay';
import { PostingInProgress, type PostingItem } from '../components/PostingInProgress';
import { AnimatedListItem } from '../components/AnimatedListItem';
import { QuotedTweetDisplay } from '../components/TweetMediaComponents';

/** A thread is a group of tweets in the same conversation replying to the same person */
interface ThreadGroup {
  groupKey: string;  // conversation_root + responding_to handle
  respondingTo: string;  // Handle of person being replied to
  respondingToPfp: string;  // Profile pic of person being replied to
  originalTweetUrl: string;  // URL of original tweet
  tweets: PostedData[];
}

interface PostedTabProps {
  postedTweets: PostedData[];
  postingQueue: PostingItem[];
  userProfilePicUrl: string;
  userHandle: string;
  userUsername: string;
  deletingTweetIds: Set<string>;
  isLoadingMore: boolean;
  onDelete: (tweetId: string) => void;
  onViewTweet: (tweetId: string) => void;
  onApprovePendingDraft: (draftId: string) => Promise<void> | void;
  onSavePendingDraft: (draftId: string, text: string) => Promise<void> | void;
  onDiscardPendingDraft: (draftId: string) => Promise<void> | void;
  pendingActionDraftIds: Set<string>;
}

/** Group tweets by immediate parent (what we're directly replying to) */
function groupTweetsIntoThreads(tweets: PostedData[]): ThreadGroup[] {
  const conversationMap = new Map<string, {
    tweets: PostedData[];
    respondingTo: string;
    respondingToPfp: string;
    originalTweetUrl: string;
  }>();
  const groupFirstTimestamp = new Map<string, string>();

  for (const tweet of tweets) {
    const parentChain = tweet.parent_chain || [];
    const respondingTo = tweet.responding_to || '';

    // Use IMMEDIATE PARENT (last item in parent_chain) for grouping, not conversation root
    // This separates:
    // - Replies to the original tweet (parent = original tweet ID)
    // - Replies to comments (parent = comment ID)
    const immediateParent = parentChain.length > 0
      ? parentChain[parentChain.length - 1]
      : tweet.id;

    // Group key: immediate parent + who we're replying to
    // This ensures replies to different tweets/comments are separate groups
    const groupKey = `${immediateParent}::${respondingTo}`;

    if (!conversationMap.has(groupKey)) {
      conversationMap.set(groupKey, {
        tweets: [],
        respondingTo: respondingTo,
        respondingToPfp: tweet.replying_to_pfp || '',
        originalTweetUrl: tweet.original_tweet_url || '',
      });
    }
    conversationMap.get(groupKey)!.tweets.push(tweet);

    const existingTime = groupFirstTimestamp.get(groupKey);
    if (!existingTime || tweet.created_at < existingTime) {
      groupFirstTimestamp.set(groupKey, tweet.created_at);
    }
  }

  const threads: ThreadGroup[] = [];
  for (const [groupKey, data] of conversationMap) {
    data.tweets.sort((a, b) => a.created_at.localeCompare(b.created_at));
    threads.push({
      groupKey,
      respondingTo: data.respondingTo,
      respondingToPfp: data.respondingToPfp,
      originalTweetUrl: data.originalTweetUrl,
      tweets: data.tweets,
    });
  }

  threads.sort((a, b) => {
    const aTime = groupFirstTimestamp.get(a.groupKey) || '';
    const bTime = groupFirstTimestamp.get(b.groupKey) || '';
    return bTime.localeCompare(aTime);
  });

  return threads;
}

interface ThreadCardProps {
  thread: ThreadGroup;
  userProfilePicUrl: string;
  userHandle: string;
  userUsername: string;
  deletingTweetIds: Set<string>;
  onDelete: (tweetId: string) => void;
  onViewTweet: (tweetId: string) => void;
}

function ThreadCard({
  thread,
  userProfilePicUrl,
  userHandle,
  userUsername,
  deletingTweetIds,
  onDelete,
  onViewTweet,
}: ThreadCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [deleteHoveredId, setDeleteHoveredId] = useState<string | null>(null);
  const [expandedContextIds, setExpandedContextIds] = useState<Set<string>>(new Set());
  const [expandedTweetIds, setExpandedTweetIds] = useState<Set<string>>(new Set());

  const toggleContextExpanded = (tweetId: string) => {
    setExpandedContextIds(prev => {
      const next = new Set(prev);
      if (next.has(tweetId)) {
        next.delete(tweetId);
      } else {
        next.add(tweetId);
      }
      return next;
    });
  };

  const toggleTweetExpanded = (tweetId: string) => {
    setExpandedTweetIds(prev => {
      const next = new Set(prev);
      if (next.has(tweetId)) {
        next.delete(tweetId);
      } else {
        next.add(tweetId);
      }
      return next;
    });
  };

  const isThread = thread.tweets.length > 1;
  const firstTweet = thread.tweets[0];
  const visibleTweets = isExpanded ? thread.tweets : [firstTweet];

  const getRelativeTime = (dateStr: string): string => {
    try {
      const tweetDate = new Date(dateStr);
      const now = new Date();
      const diffHours = Math.floor((now.getTime() - tweetDate.getTime()) / (1000 * 60 * 60));
      if (diffHours < 1) return 'now';
      if (diffHours < 24) return `${diffHours}h`;
      if (diffHours < 48) return '1d';
      return `${Math.floor(diffHours / 24)}d`;
    } catch {
      return '';
    }
  };

  const formatMetric = (value: number): string => {
    if (value >= 1000000) return `${(value / 1000000).toFixed(1).replace(/\.0$/, '')}M`;
    if (value >= 1000) return `${(value / 1000).toFixed(1).replace(/\.0$/, '')}K`;
    return String(value);
  };

  const getSourceLabel = (source?: TweetSource) => {
    return source === 'external' ? 'discovered' : 'ghostpost';
  };

  const isGhostpost = (source?: TweetSource) => source !== 'external';

  const handleViewTweet = (tweet: PostedData) => {
    onViewTweet(tweet.id);
    window.open(tweet.url, '_blank', 'noopener,noreferrer');
  };

  return (
    <div className="w-full px-[2%] pb-[4%] rounded-2xl bg-black text-white shadow-2xl">
      {/* Header with delete button and source label */}
      <div className="flex items-center justify-between p-5 ml-[-20px] mb-2">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => onDelete(firstTweet.id)}
            onMouseEnter={() => setDeleteHoveredId(firstTweet.id)}
            onMouseLeave={() => setDeleteHoveredId(null)}
            disabled={deletingTweetIds.has(firstTweet.id)}
            className={`relative flex items-center gap-2 rounded-full transition-colors h-10 w-10 justify-center ${
              deletingTweetIds.has(firstTweet.id) ? 'opacity-50 cursor-not-allowed' : 'hover:bg-neutral-800'
            }`}
            aria-label="Delete tweet from Twitter"
            title={deletingTweetIds.has(firstTweet.id) ? "Deleting..." : "Delete tweet from Twitter"}
          >
            {deleteHoveredId === firstTweet.id ? (
              <div className="w-8 h-8 flex items-center justify-center">
                <DotLottieReact src={xLottie} loop autoplay />
              </div>
            ) : (
              <span className="text-xl text-white">×</span>
            )}
          </button>
          <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${
            isGhostpost(firstTweet.source)
              ? 'bg-sky-500/20 text-sky-400'
              : 'bg-amber-500/20 text-amber-400'
          }`}>
            {getSourceLabel(firstTweet.source)}
          </span>
          {isThread && (
            <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-400">
              {thread.tweets.length} in thread
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={() => handleViewTweet(firstTweet)}
          className="ml-auto text-neutral-400 hover:text-sky-400 transition-colors bg-transparent border-none cursor-pointer"
          aria-label="View on Twitter"
          title="View on Twitter"
        >
          <i className="fa-solid fa-arrow-up-right-from-square text-sm" />
        </button>
      </div>

      <div className="px-5 py-3">
        {/* Your replies in this thread */}
        <div className="flex flex-col gap-4">
          {visibleTweets.map((tweet, index) => (
            <div key={tweet.id} className="flex flex-col gap-2">
              {/* Show what this reply is responding to */}
              {tweet.responding_to && tweet.response_to_thread.length > 0 && (() => {
                const contextText = tweet.response_to_thread.join(' ');
                const isContextExpanded = expandedContextIds.has(tweet.id);
                // Rough check if text is likely more than 3 lines (~150 chars)
                const isLongContext = contextText.length > 150;

                return (
                  <div className="flex gap-3 pb-2 mb-2 border-b border-neutral-800">
                    <img
                      src={tweet.replying_to_pfp || 'https://abs.twimg.com/sticky/default_profile_images/default_profile_400x400.png'}
                      alt={tweet.responding_to}
                      className="h-8 w-8 rounded-full flex-shrink-0"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 text-xs text-neutral-400 mb-1">
                        <span className="font-semibold text-neutral-300">@{tweet.responding_to}</span>
                        {tweet.original_tweet_url && (
                          <a
                            href={tweet.original_tweet_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sky-500 hover:text-sky-400"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <i className="fa-solid fa-arrow-up-right-from-square text-[10px]" />
                          </a>
                        )}
                      </div>
                      <div className="relative">
                        <p className={`text-sm text-neutral-400 whitespace-pre-wrap ${
                          !isContextExpanded && isLongContext ? 'line-clamp-3' : ''
                        }`}>
                          {contextText}
                        </p>
                        {/* Fade overlay when collapsed */}
                        {!isContextExpanded && isLongContext && (
                          <div className="absolute bottom-0 left-0 right-0 h-8 bg-gradient-to-t from-black to-transparent pointer-events-none" />
                        )}
                      </div>
                      {/* Toggle button */}
                      {isLongContext && (
                        <button
                          onClick={() => toggleContextExpanded(tweet.id)}
                          className="text-xs text-sky-500 hover:text-sky-400 mt-1 transition-colors"
                        >
                          {isContextExpanded ? 'Show less' : 'Show more'}
                        </button>
                      )}
                    </div>
                  </div>
                );
              })()}

              {/* Your reply */}
              <div className="relative flex gap-3">
                {index === 0 || !isExpanded ? (
                  <img src={userProfilePicUrl} alt={userUsername} className="h-10 w-10 rounded-full flex-shrink-0" />
                ) : (
                  <div className="h-10 w-10 flex-shrink-0" aria-hidden="true" />
                )}
                <div className="flex-1 space-y-1 pb-2">
                  <div className="flex items-center gap-2 text-sm text-neutral-400">
                    <span className="font-bold text-white">{userUsername}</span>
                    <span className="text-neutral-500">@{userHandle}</span>
                    {tweet.created_at && <span className="text-neutral-600">· {getRelativeTime(tweet.created_at)}</span>}
                    {index > 0 && (
                      <button
                        type="button"
                        onClick={() => onDelete(tweet.id)}
                        className="ml-auto text-neutral-500 hover:text-red-400 transition-colors"
                        title="Delete this reply"
                      >
                        <i className="fa-solid fa-xmark text-xs" />
                      </button>
                    )}
                  </div>
                  {/* Tweet text with truncation */}
                  {(() => {
                    const isTweetExpanded = expandedTweetIds.has(tweet.id);
                    const isLongTweet = tweet.text.length > 200;

                    return (
                      <>
                        <div className="relative">
                          <p className={`whitespace-pre-wrap text-base leading-relaxed text-white ${
                            !isTweetExpanded && isLongTweet ? 'line-clamp-3' : ''
                          }`}>
                            {tweet.text}
                          </p>
                          {/* Fade overlay when collapsed */}
                          {!isTweetExpanded && isLongTweet && (
                            <div className="absolute bottom-0 left-0 right-0 h-8 bg-gradient-to-t from-black to-transparent pointer-events-none" />
                          )}
                        </div>
                        {/* Toggle button */}
                        {isLongTweet && (
                          <button
                            onClick={() => toggleTweetExpanded(tweet.id)}
                            className="text-xs text-sky-500 hover:text-sky-400 mt-1 transition-colors"
                          >
                            {isTweetExpanded ? 'Show less' : 'Show more'}
                          </button>
                        )}
                      </>
                    );
                  })()}

                  {/* Quoted Tweet */}
                  {tweet.quoted_tweet && (
                    <QuotedTweetDisplay quotedTweet={tweet.quoted_tweet} />
                  )}

                  {/* Media Grid */}
                  {tweet.media && tweet.media.length > 0 && (
                    <div
                      className={`mt-2 rounded-xl overflow-hidden border border-neutral-800 ${
                        tweet.media.length >= 2 ? 'grid grid-cols-2 gap-0.5' : 'max-w-md'
                      }`}
                    >
                      {tweet.media.map((media, mediaIndex) => (
                        <img
                          key={mediaIndex}
                          src={media.url}
                          alt={media.alt_text || `Image ${mediaIndex + 1}`}
                          className={`w-full ${
                            tweet.media?.length === 1
                              ? 'object-contain max-h-[400px]'
                              : 'h-32 object-cover'
                          }`}
                          loading="lazy"
                        />
                      ))}
                    </div>
                  )}

                  {/* Engagement metrics for this specific reply */}
                  <div className="flex items-center gap-4 pt-2 text-xs text-neutral-500">
                    <span className="flex items-center gap-1">
                      <i className="fa-regular fa-comment" />
                      {formatMetric(tweet.replies)}
                    </span>
                    <span className="flex items-center gap-1">
                      <i className="fa-solid fa-retweet" />
                      {formatMetric(tweet.retweets)}
                    </span>
                    <span className="flex items-center gap-1">
                      <i className="fa-regular fa-heart" />
                      {formatMetric(tweet.likes)}
                    </span>
                    {tweet.impressions && tweet.impressions > 0 && (
                      <span className="flex items-center gap-1">
                        <i className="fa-regular fa-eye" />
                        {formatMetric(tweet.impressions)}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Divider between thread messages */}
              {isExpanded && index < visibleTweets.length - 1 && (
                <div className="border-t border-neutral-800 my-2" aria-hidden="true" />
              )}
            </div>
          ))}
        </div>

        {/* Expand/Collapse for threads */}
        {isThread && !isExpanded && (
          <button
            onClick={() => setIsExpanded(true)}
            className="mt-3 w-full px-3 py-2 text-xs text-sky-400 hover:text-sky-300 transition-colors bg-neutral-900/50 hover:bg-neutral-800/50 rounded-lg border border-neutral-800 hover:border-neutral-700"
          >
            <i className="fa-solid fa-plus mr-2" />
            Show {thread.tweets.length - 1} more {thread.tweets.length - 1 === 1 ? 'reply' : 'replies'}
          </button>
        )}

        {isThread && isExpanded && (
          <button
            onClick={() => setIsExpanded(false)}
            className="mt-3 w-full px-3 py-2 text-xs text-neutral-400 hover:text-neutral-300 transition-colors bg-neutral-900/50 hover:bg-neutral-800/50 rounded-lg border border-neutral-800 hover:border-neutral-700"
          >
            <i className="fa-solid fa-minus mr-2" />
            Collapse thread
          </button>
        )}
      </div>
    </div>
  );
}

export function PostedTab({
  postedTweets,
  postingQueue,
  userProfilePicUrl,
  userHandle,
  userUsername,
  deletingTweetIds,
  isLoadingMore,
  onDelete,
  onViewTweet,
  onApprovePendingDraft,
  onSavePendingDraft,
  onDiscardPendingDraft,
  pendingActionDraftIds,
}: PostedTabProps) {
  const threads = useMemo(() => groupTweetsIntoThreads(postedTweets), [postedTweets]);

  // Show empty state only if no posted tweets AND no items in posting queue
  if (postedTweets.length === 0 && postingQueue.length === 0) {
    return (
      <div className="w-full flex items-center justify-center h-64">
        <p className="text-neutral-400 text-lg">No tweets posted yet</p>
      </div>
    );
  }

  // Distribute threads across 3 columns
  const columns: ThreadGroup[][] = [[], [], []];
  threads.forEach((thread, index) => {
    columns[index % 3].push(thread);
  });

  // Distribute posting queue items across columns (put all in first column for visibility)
  const postingQueueByColumn: PostingItem[][] = [[], [], []];
  postingQueue.forEach((item, index) => {
    postingQueueByColumn[index % 3].push(item);
  });

  return (
    <div className="w-full">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {columns.map((columnThreads, colIndex) => (
          <div key={colIndex} className="flex flex-col gap-6">
            <AnimatePresence mode="popLayout">
              {/* Posting in progress items at the top */}
              {postingQueueByColumn[colIndex].map((item) => (
                <AnimatedListItem
                  key={item.id}
                  itemKey={item.id}
                  variant="scale"
                >
                  <PostingInProgress
                    item={item}
                    myProfilePicUrl={userProfilePicUrl}
                    myHandle={userHandle}
                    myUsername={userUsername}
                    onApproveDraft={onApprovePendingDraft}
                    onSaveDraft={onSavePendingDraft}
                    onDiscardDraft={onDiscardPendingDraft}
                    isActionPending={!!item.draftId && pendingActionDraftIds.has(item.draftId)}
                  />
                </AnimatedListItem>
              ))}

              {/* Posted tweets */}
              {columnThreads.map((thread) => (
                <AnimatedListItem
                  key={thread.groupKey}
                  itemKey={thread.groupKey}
                  variant="scale"
                >
                  <ThreadCard
                    thread={thread}
                    userProfilePicUrl={userProfilePicUrl}
                    userHandle={userHandle}
                    userUsername={userUsername}
                    deletingTweetIds={deletingTweetIds}
                    onDelete={onDelete}
                    onViewTweet={onViewTweet}
                  />
                </AnimatedListItem>
              ))}
            </AnimatePresence>
          </div>
        ))}
      </div>

      {isLoadingMore && (
        <div className="w-full flex justify-center py-8">
          <div className="text-neutral-400 text-sm">Loading more tweets...</div>
        </div>
      )}
    </div>
  );
}
