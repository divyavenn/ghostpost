import { useEffect, useMemo, useRef, useState } from 'react';
import { DotLottieReact } from '@lottiefiles/dotlottie-react';

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
  isDeleting?: boolean;
  isPosting?: boolean;
  readOnly?: boolean;
}

export function TweetDisplay({ tweet, onPublish, onSkip, onEditReply, isDeleting = false, isPosting = false, readOnly = false }: TweetDisplayProps) {
  const [editedText, setEditedText] = useState(tweet.reply || '');
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [isDeleteHovered, setIsDeleteHovered] = useState(false);
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
    setHasUnsavedChanges(false);
  }, [tweet.id, tweet.reply]);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    textarea.style.height = 'auto';
    textarea.style.height = `${textarea.scrollHeight}px`;
  }, [editedText]);

  // Handle text change and mark as unsaved
  const handleTextChange = (newText: string) => {
    setEditedText(newText);

    // Mark as having unsaved changes if different from original
    if (newText !== tweet.reply) {
      setHasUnsavedChanges(true);
    } else {
      setHasUnsavedChanges(false);
    }

    // Clear existing debounce timer
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }
  };

  // Save changes manually
  const handleSave = async () => {
    if (onEditReply && editedText !== tweet.reply) {
      await onEditReply(editedText);
      setHasUnsavedChanges(false);
    }
  };

  // Handle publish - save first if needed, then publish
  const handlePublish = async () => {
    // Save changes first if there are any
    if (hasUnsavedChanges && onEditReply && editedText !== tweet.reply) {
      await onEditReply(editedText);
      setHasUnsavedChanges(false);
    }
    // Then publish
    onPublish(editedText);
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
    <div
      className={`mx-auto w-full min-w-xl max-w-[70%] px-[2%] py-[1%] rounded-2xl bg-black text-white shadow-2xl transition-all ${
        isDeleting
          ? 'duration-300 scale-95 opacity-0'
          : isPosting
          ? 'duration-400 translate-x-[150%] opacity-0'
          : 'duration-300 scale-100 opacity-100 translate-x-0'
      }`}
    >
      {!readOnly && (
        <div className="flex items-center justify-between ml-[-20px] mb-2">
          <button
            type="button"
            onClick={onSkip}
            onMouseEnter={() => setIsDeleteHovered(true)}
            onMouseLeave={() => setIsDeleteHovered(false)}
            className="relative flex h-8 w-8 items-center justify-center rounded-full transition-colors"
            aria-label="Delete"
          >
            {isDeleteHovered ? (
              <div className="w-8 h-8">
                <DotLottieReact
                  src="/src/assets/x.lottie"
                  loop
                  autoplay
                />
              </div>
            ) : (
              <span className="text-xl text-white">×</span>
            )}
          </button>
        </div>
      )}

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

        {!readOnly ? (
          <>
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
          </>
        ) : (
          editedText && (
            <>
              <p className="text-sm text-neutral-500 pt-7">
                Your reply to <span className="text-sky-400">{'@' + handle}</span>
              </p>
              <div className="flex gap-3 pt-6">
                <img src={myAvatar} alt="Your avatar" className="h-12 w-12 rounded-full" />
                <div className="flex-1">
                  <p className="whitespace-pre-wrap text-lg leading-relaxed text-white">{editedText}</p>
                </div>
              </div>
            </>
          )
        )}
      </div>

      {!readOnly && (
        <div className="flex items-center justify-end gap-3 px-5 pb-8 pt-0">
          {hasUnsavedChanges && (
            <button
              type="button"
              onClick={handleSave}
              className="rounded-full bg-neutral-700 px-5 py-2 text-sm font-semibold text-white transition hover:bg-neutral-600"
            >
              Save
            </button>
          )}
          <button
            type="button"
            onClick={handlePublish}
            className="rounded-full bg-sky-500 px-5 py-2 text-sm font-semibold text-white transition hover:bg-sky-600"
          >
            Reply
          </button>
        </div>
      )}
    </div>
  );
}
