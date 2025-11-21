import { useMemo, useState } from 'react';
import { DotLottieReact } from '@lottiefiles/dotlottie-react';
import xLottie from '../assets/x.lottie';

export interface PostedTweetData {
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
}

interface PostedTweetDisplayProps {
  tweet: PostedTweetData;
  myProfilePicUrl: string;
  myHandle: string;
  myUsername: string;
  onDelete: (tweetId: string) => void;
  isDeleting?: boolean;
}

export function PostedTweetDisplay({ tweet, myProfilePicUrl, myHandle, myUsername, onDelete, isDeleting = false }: PostedTweetDisplayProps) {
  const [isDeleteHovered, setIsDeleteHovered] = useState(false);

  // Original tweet author info
  const originalHandle = tweet.responding_to;
  const originalAvatar = tweet.replying_to_pfp || 'https://abs.twimg.com/sticky/default_profile_images/default_profile_400x400.png';

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
        <a
          href={tweet.url}
          target="_blank"
          rel="noopener noreferrer"
          className="ml-auto text-neutral-400 hover:text-sky-400 transition-colors"
          aria-label="View your posted tweet on Twitter"
          title="View on Twitter"
        >
          <i className="fa-solid fa-arrow-up-right-from-square text-sm" />
        </a>
      </div>

      <div className="px-5 py-3">
        {/* Original Tweet Thread */}
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

        {/* Your Posted Reply */}
        <p className="text-sm text-neutral-500 pt-7">
          Your reply to <span className="text-sky-400">@{originalHandle}</span>
        </p>
        <div className="flex gap-3 pt-6">
          <img src={myProfilePicUrl} alt={myUsername} className="h-12 w-12 rounded-full" />
          <div className="flex-1">
            <div className="flex items-center gap-2 text-sm text-neutral-400 mb-1">
              <span className="text-base font-bold text-white">{myUsername}</span>
              <span>@{myHandle}</span>
              {tweet.created_at && <span>· {getRelativeTime(tweet.created_at)}</span>}
            </div>
            <p className="whitespace-pre-wrap text-lg leading-relaxed text-white">{tweet.text}</p>
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
