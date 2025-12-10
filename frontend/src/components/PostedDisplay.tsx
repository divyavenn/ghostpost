import { useMemo, useState } from 'react';
import { DotLottieReact } from '@lottiefiles/dotlottie-react';
import xLottie from '../assets/x.lottie';
import { QuotedTweetDisplay, TweetMediaGrid, type QuotedTweet } from './TweetMediaComponents';

export type PostType = 'original' | 'reply' | 'comment_reply';
export type TweetSource = 'app_posted' | 'external';

export interface PostedData {
  id: string;  // Posted tweet ID
  text: string;  // Your response text
  likes: number;
  retweets: number;
  quotes: number;
  replies: number;
  impressions?: number;  // View/impression count
  created_at: string;
  url: string;  // URL of your posted tweet
  response_to_thread: string[];  // Original tweet thread you responded to
  responding_to: string;  // Handle of original tweet author
  replying_to_pfp: string;  // Profile pic URL of original tweet author
  original_tweet_url: string;  // URL of original tweet
  last_metrics_update: string | null;
  media?: Array<{
    type: 'photo';
    url: string;
    alt_text?: string;
  }>;
  // Thread tracking
  parent_chain?: string[];  // Array of ancestor tweet IDs from root to immediate parent
  // Source and type classification
  source?: TweetSource;  // 'app_posted' (ghostpost) or 'external' (discovered)
  post_type?: PostType;  // 'original', 'reply', or 'comment_reply'
  // Quoted tweet (if this tweet quotes another)
  quoted_tweet?: QuotedTweet | null;
}

interface PostedDisplayProps {
  tweet: PostedData;
  myProfilePicUrl: string;
  myHandle: string;
  myUsername: string;
  onDelete: (tweetId: string) => void;
  onViewTweet?: (tweetId: string) => void;  // Callback to refresh metrics when viewing tweet
  isDeleting?: boolean;
}

export function PostedDisplay({ tweet, myProfilePicUrl, myHandle, myUsername, onDelete, onViewTweet, isDeleting = false }: PostedDisplayProps) {
  const [isDeleteHovered, setIsDeleteHovered] = useState(false);

  // Source label - ghostpost (app_posted) vs discovered externally
  const sourceLabel = tweet.source === 'external' ? '' : 'from ghostpost';
  const isGhostpost = tweet.source !== 'external';

  // Original tweet author info - only used if this is a reply
  const isReply = tweet.responding_to && tweet.responding_to.length > 0;
  const originalHandle = tweet.responding_to;
  const originalAvatar = tweet.replying_to_pfp || 'https://abs.twimg.com/sticky/default_profile_images/default_profile_400x400.png';

  // Handle click on view tweet link - open in new tab and refresh metrics
  const handleViewTweet = () => {
    if (onViewTweet) {
      onViewTweet(tweet.id);
    }
    window.open(tweet.url, '_blank', 'noopener,noreferrer');
  };

  // Thread messages from the original tweet - only show first 280 characters
  const threadMessages = useMemo(() => {
    const messages = tweet.response_to_thread ?? [];
    if (messages.length === 0) return [];

    // Combine all messages and take first 280 characters
    const fullText = messages.join(' ');
    const truncated = fullText.slice(0, 280);

    return [truncated];
  }, [tweet.response_to_thread]);

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

  return (
    <div
      className={`w-full px-[2%] pb-[4%] rounded-2xl bg-black text-white shadow-2xl transition-all ${
        isDeleting
          ? 'duration-300 scale-95 opacity-0'
          : 'duration-300 scale-100 opacity-100 translate-x-0'
      }`}
    >
      <div className="flex items-center justify-between p-5 ml-[-20px] mb-2">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => onDelete(tweet.id)}
            onMouseEnter={() => setIsDeleteHovered(true)}
            onMouseLeave={() => setIsDeleteHovered(false)}
            className="relative flex items-center gap-2 rounded-full transition-colors h-10 w-10 justify-center hover:bg-neutral-800"
            aria-label="Delete tweet from Twitter"
            title="Delete tweet from Twitter"
          >
            {isDeleteHovered ? (
              <div className="w-8 h-8 flex items-center justify-center">
                <DotLottieReact
                  src={xLottie}
                  loop
                  autoplay
                />
              </div>
            ) : (
              <span className="text-xl text-white">×</span>
            )}
          </button>
          {/* Source label */}
          <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${
            isGhostpost
              ? 'bg-sky-500/20 text-sky-400'
              : 'bg-amber-500/20 text-amber-400'
          }`}>
            {sourceLabel}
          </span>
        </div>
        <button
          type="button"
          onClick={handleViewTweet}
          className="ml-auto text-neutral-400 hover:text-sky-400 transition-colors bg-transparent border-none cursor-pointer"
          aria-label="View your posted tweet on Twitter"
          title="View on Twitter"
        >
          <i className="fa-solid fa-arrow-up-right-from-square text-sm" />
        </button>
      </div>

      <div className="px-5 py-3">
        {/* Original Tweet Thread - only show for replies */}
        {isReply && threadMessages.length > 0 && (
          <>
            <div className="space-y-4 pb-1">
              {threadMessages.map((message, index) => (
                <div key={`${tweet.id}-original-${index}`} className="relative flex gap-3">
                  {index === 0 ? (
                    <img src={originalAvatar} alt={originalHandle} className="h-12 w-12 rounded-full" />
                  ) : (
                    <div className="h-12 w-12" aria-hidden="true" />
                  )}
                  <div className="flex-1 space-y-1 pb-4">
                    {index === 0 && (
                      <div className="flex items-center gap-2 text-sm text-neutral-400">
                        <span className="text-base font-bold text-white">@{originalHandle}</span>
                      </div>
                    )}
                    <p className="whitespace-pre-wrap text-lg leading-relaxed text-white">{message}</p>

                    {index < threadMessages.length - 1 && (
                      <div className="absolute inset-x-14 bottom-0 border-t border-neutral-800" aria-hidden="true" />
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Link to original tweet */}
            {tweet.original_tweet_url && (
              <div className="pl-14 pb-4">
                <a
                  href={tweet.original_tweet_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-sky-400 hover:underline"
                >
                  View original thread
                </a>
              </div>
            )}
          </>
        )}

        {/* Your Posted Reply/Tweet */}
        {isReply && (
          <p className="text-sm text-neutral-500 pt-7">
            Your reply to <span className="text-sky-400">@{originalHandle}</span>
          </p>
        )}
        <div className={`flex gap-3 ${isReply ? 'pt-6' : 'pt-2'}`}>
          <img src={myProfilePicUrl} alt={myUsername} className="h-12 w-12 rounded-full" />
          <div className="flex-1">
            <div className="flex items-center gap-2 text-sm text-neutral-400 mb-1">
              <span className="text-base font-bold text-white">{myUsername}</span>
              <span>@{myHandle}</span>
              {tweet.created_at && <span>· {getRelativeTime(tweet.created_at)}</span>}
            </div>
            <p className="whitespace-pre-wrap text-lg leading-relaxed text-white">{tweet.text}</p>

            {/* Quoted Tweet */}
            {tweet.quoted_tweet && (
              <QuotedTweetDisplay quotedTweet={tweet.quoted_tweet} />
            )}

            {/* Media Grid */}
            {tweet.media && tweet.media.length > 0 && (
              <TweetMediaGrid media={tweet.media.map(m => ({ type: m.type, url: m.url, alt_text: m.alt_text }))} />
            )}
          </div>
        </div>

        {/* Performance Metrics */}
        <div className="flex items-center gap-8 pl-14 pt-4 text-sm text-neutral-500" aria-label="Tweet engagement">
          <div className="flex items-center gap-2">
            <i className="fa-regular fa-comment text-lg text-neutral-500" aria-hidden="true" />
            <span className="font-medium">{formatMetric(tweet.replies)}</span>
          </div>
          <div className="flex items-center gap-2">
            <i className="fa-solid fa-retweet text-lg text-neutral-500" aria-hidden="true" />
            <span className="font-medium">{formatMetric(tweet.retweets)}</span>
          </div>
          <div className="flex items-center gap-2">
            <i className="fa-regular fa-heart text-lg text-neutral-500" aria-hidden="true" />
            <span className="font-medium">{formatMetric(tweet.likes)}</span>
          </div>
          {tweet.impressions !== undefined && tweet.impressions > 0 && (
            <div className="flex items-center gap-2">
              <i className="fa-regular fa-eye text-lg text-neutral-500" aria-hidden="true" />
              <span className="font-medium">{formatMetric(tweet.impressions)}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
