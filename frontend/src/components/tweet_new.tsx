import { useEffect, useMemo, useRef, useState } from 'react';

export interface TweetData {
  id: string;
  cache_id?: string;
  text: string;
  likes: number;
  retweets: number;
  quotes: number;
  replies: number;
  handle: string;
  score: number;
  username: string;
  followers: number;
  reply?: string;
  created_at: string;
  url: string;
  thread?: string[];
}

interface TweetDisplayProps {
  tweet: TweetData;
  replyText: string;
  onPublish: (text: string) => void;
  onSkip: () => void;
  onEditReply?: (newReply: string) => void;
}

export function TweetDisplay({ tweet, onPublish, onSkip, onEditReply }: TweetDisplayProps) {
  const [editedText, setEditedText] = useState(tweet.reply || '');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);

  const displayName = tweet.username;
  const handle = tweet.handle;
  const userAvatar = 'https://abs.twimg.com/sticky/default_profile_images/default_profile_200x200.png';
  const myAvatar = 'https://pbs.twimg.com/profile_images/1803721062133211138/s3Zbrfw__normal.jpg';

  const threadMessages = useMemo(() => [...(tweet.thread ?? [])], [tweet.thread]);

  // Update editedText when tweet changes
  useEffect(() => {
    setEditedText(tweet.reply || '');
  }, [tweet.id, tweet.reply]);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    textarea.style.height = 'auto';
    textarea.style.height = `${textarea.scrollHeight}px`;
  }, [editedText]);

  // Debounced API call when text changes
  const handleTextChange = (newText: string) => {
    setEditedText(newText);

    // Clear existing timer
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    // Set new timer to call API after 1 second of no typing
    debounceTimerRef.current = setTimeout(() => {
      if (onEditReply && newText !== tweet.reply) {
        onEditReply(newText);
      }
    }, 1000);
  };

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

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
    <div className="mx-auto w-full min-w-xl max-w-[70%] px-[2%] py-[1%] rounded-2xl bg-black text-white shadow-2xl">
      <div className="flex items-center justify-between px-5 py-3">
        <button
          type="button"
          onClick={onSkip}
          className="rounded-full p-2 text-xl leading-none text-white transition hover:bg-neutral-900"
          aria-label="Close"
        >
          ×
        </button>
      </div>

      <div className="px-5 py-3">
        <div className="space-y-4 pb-1">
          {threadMessages.map((message, index) => (
            <div key={`${tweet.id}-${index}`} className="relative flex gap-3">
              {index === 0 ? (
                <img src={userAvatar} alt={displayName} className="h-12 w-12 rounded-full" />
              ) : (
                <div className="h-12 w-12" aria-hidden="true" />
              )}
              <div className="flex-1 space-y-1 pb-4">
                {index === 0 && (
                  <div className="flex items-center gap-2 text-sm text-neutral-400">
                    <span className="text-base font-bold text-white">{displayName}</span>
                    <span>{'@' + handle}</span>
                    {tweet.created_at && <span>· {getRelativeTime(tweet.created_at)}</span>}
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

        <div className="flex items-center gap-8 pl-14 text-sm text-neutral-500" aria-label="Tweet engagement">
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
        </div>

        <p className="text-sm text-neutral-500 pt-7">
          Replying to <span className="text-sky-400">{'@' + handle}</span>
        </p>
        <div className="flex gap-3 pt-6">
          <img src={myAvatar} alt="Your avatar" className="h-12 w-12 rounded-full" />
          <div className="flex-1">
            <textarea
              ref={textareaRef}
              placeholder="Post your reply"
              value={editedText}
              onChange={(e) => handleTextChange(e.target.value)}
              className="w-full min-h-[6rem] resize-none overflow-hidden bg-transparent text-lg text-white outline-none placeholder:text-neutral-600"
            />
          </div>
        </div>
      </div>

      <div className="flex items-center justify-end px-5 pb-8 pt-0">
        <button
          type="button"
          onClick={() => onPublish(editedText)}
          className="rounded-full bg-sky-500 px-5 py-2 text-sm font-semibold text-white transition hover:bg-sky-600"
        >
          Reply
        </button>
      </div>
    </div>
  );
}
