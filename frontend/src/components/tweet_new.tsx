import { useEffect, useMemo, useRef, useState } from 'react';
import { DotLottieReact } from '@lottiefiles/dotlottie-react';
import { AnimatedText } from './WordStyles';
import xLottie from '../assets/x.lottie';

export interface TweetData {
  id: string;
  cache_id?: string;
  posted_tweet_id?: string;  // Twitter's ID for posted tweets (for deletion)
  text: string;
  likes: number;
  retweets: number;
  quotes: number;
  replies: number;  // Count of replies to the original tweet
  impressions?: number;  // View/impression count
  handle: string;
  score: number;
  username: string;
  followers: number;
  reply?: string; // Deprecated - kept for backward compatibility
  generated_replies?: Array<[string, string]>; // Array of tuples: [reply_text, model_name]
  created_at: string;
  url: string;
  thread?: string[];
  author_profile_pic_url?: string;
  scraped_from?: {
    type: 'account' | 'query';
    value: string;
    summary?: string;  // Short 1-2 word summary for queries
  };
  media?: Array<{
    type: 'photo';
    url: string;
    alt_text?: string;
  }>;
  quoted_tweet?: {
    text: string;
    author_name: string;
    author_handle: string;
    author_profile_pic_url?: string;
    media?: Array<{type: 'photo'; url: string; alt_text?: string}>;
    created_at: string;
    url: string;
  };
}

interface TweetDisplayProps {
  tweet: TweetData;
  myProfilePicUrl: string;
  maxReplies?: number; // Maximum number of replies to display (from user settings)
  onPublish: (text: string, replyIndex: number) => void;
  onSkip: () => void;
  onEditReply?: (newReply: string, replyIndex: number) => void;
  onRegenerate?: () => void;
  isDeleting?: boolean;
  isPosting?: boolean;
  isRegenerating?: boolean;
  readOnly?: boolean;
  showDeleteButton?: boolean;  // Explicit control over delete button visibility
}

export function TweetDisplay({ tweet, myProfilePicUrl, maxReplies, onPublish, onSkip, onEditReply, onRegenerate, isDeleting = false, isPosting = false, readOnly = false, isRegenerating = false, showDeleteButton = !readOnly }: TweetDisplayProps) {
  // Handle both tuple format [(text, model), ...] and old format
  const allReplies = tweet.generated_replies
    ? tweet.generated_replies.map(r => Array.isArray(r) ? r[0] : r)
    : (tweet.reply ? [tweet.reply] : []);

  // Limit replies to maxReplies from user settings
  const generatedReplies = maxReplies ? allReplies.slice(0, maxReplies) : allReplies;

  const [editedTexts, setEditedTexts] = useState<string[]>(generatedReplies);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState<boolean[]>(generatedReplies.map(() => false));
  const [isDeleteHovered, setIsDeleteHovered] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);

  const displayName = tweet.username;
  const handle = tweet.handle;
  const userAvatar = tweet.author_profile_pic_url || 'https://abs.twimg.com/sticky/default_profile_images/default_profile_400x400.png';
  const myAvatar = myProfilePicUrl;

  const threadMessages = useMemo(() => [...(tweet.thread ?? [])], [tweet.thread]);

  // Update editedTexts when tweet or maxReplies changes
  useEffect(() => {
    const allNewReplies = tweet.generated_replies
      ? tweet.generated_replies.map(r => Array.isArray(r) ? r[0] : r)
      : (tweet.reply ? [tweet.reply] : []);
    const newReplies = maxReplies ? allNewReplies.slice(0, maxReplies) : allNewReplies;
    setEditedTexts(newReplies);
    setHasUnsavedChanges(newReplies.map(() => false));
  }, [tweet.id, tweet.reply, tweet.generated_replies, maxReplies]);

  // Handle text change for a specific reply index
  const handleTextChange = (index: number, newText: string) => {
    const newEditedTexts = [...editedTexts];
    newEditedTexts[index] = newText;
    setEditedTexts(newEditedTexts);

    // Mark as having unsaved changes if different from original (limited by maxReplies)
    const allOriginalReplies = tweet.generated_replies
      ? tweet.generated_replies.map(r => Array.isArray(r) ? r[0] : r)
      : (tweet.reply ? [tweet.reply] : []);
    const originalReplies = maxReplies ? allOriginalReplies.slice(0, maxReplies) : allOriginalReplies;
    const newHasUnsavedChanges = [...hasUnsavedChanges];
    newHasUnsavedChanges[index] = newText !== originalReplies[index];
    setHasUnsavedChanges(newHasUnsavedChanges);
  };

  // Save changes for a specific reply
  const handleSave = async (index: number) => {
    const allOriginalReplies = tweet.generated_replies
      ? tweet.generated_replies.map(r => Array.isArray(r) ? r[0] : r)
      : (tweet.reply ? [tweet.reply] : []);
    const originalReplies = maxReplies ? allOriginalReplies.slice(0, maxReplies) : allOriginalReplies;
    if (onEditReply && editedTexts[index] !== originalReplies[index]) {
      await onEditReply(editedTexts[index], index);
      const newHasUnsavedChanges = [...hasUnsavedChanges];
      newHasUnsavedChanges[index] = false;
      setHasUnsavedChanges(newHasUnsavedChanges);
    }
  };

  // Handle publish for a specific reply
  const handlePublish = async (index: number) => {
    // Save changes first if there are any
    const allOriginalReplies = tweet.generated_replies
      ? tweet.generated_replies.map(r => Array.isArray(r) ? r[0] : r)
      : (tweet.reply ? [tweet.reply] : []);
    const originalReplies = maxReplies ? allOriginalReplies.slice(0, maxReplies) : allOriginalReplies;
    if (hasUnsavedChanges[index] && onEditReply && editedTexts[index] !== originalReplies[index]) {
      await onEditReply(editedTexts[index], index);
    }
    // Then publish
    onPublish(editedTexts[index], index);
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
      className={`w-full px-[2%] pb-[4%] rounded-2xl bg-black text-white shadow-2xl transition-all ${
        isDeleting
          ? 'duration-300 scale-95 opacity-0'
          : isPosting
          ? 'duration-400 translate-x-[150%] opacity-0'
          : 'duration-300 scale-100 opacity-100 translate-x-0'
      }`}
    >
      <div className="flex items-center justify-between p-5 ml-[-20px] mb-2">
        {showDeleteButton && (
          <button
            type="button"
            onClick={onSkip}
            onMouseEnter={() => setIsDeleteHovered(true)}
            onMouseLeave={() => setIsDeleteHovered(false)}
            className="relative flex items-center gap-2 rounded-full transition-colors h-10 w-10 justify-center hover:bg-neutral-800"
            aria-label={readOnly ? "Delete tweet from Twitter" : "Delete"}
            title={readOnly ? "Delete tweet from Twitter" : "Delete"}
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
        )}
        <a
          href={tweet.url}
          target="_blank"
          rel="noopener noreferrer"
          className="ml-auto text-neutral-400 hover:text-sky-400 transition-colors"
          aria-label="View original tweet on Twitter"
          title="View on Twitter"
        >
          <i className="fa-solid fa-arrow-up-right-from-square text-sm" />
        </a>
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
                    {tweet.scraped_from && (
                      <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-neutral-800 text-xs text-neutral-400">
                        <i className={`fa-solid ${tweet.scraped_from.type === 'account' ? 'fa-user' : 'fa-magnifying-glass'}`} />
                        <span>
                          {tweet.scraped_from.type === 'account'
                            ? `@${tweet.scraped_from.value}`
                            : tweet.scraped_from.summary || tweet.scraped_from.value}
                        </span>
                      </div>
                    )}
                    {tweet.media && tweet.media.length > 0 && (
                      <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-blue-900/30 text-xs text-blue-400">
                        <i className="fa-solid fa-image" />
                        <span>{tweet.media.length} image{tweet.media.length > 1 ? 's' : ''}</span>
                      </div>
                    )}
                  </div>
                )}
                <p className="whitespace-pre-wrap text-lg leading-relaxed text-white">{message}</p>
                
                {/* Display quoted tweet if present */}
                {index === 0 && tweet.quoted_tweet && (
                  <a 
                    href={tweet.quoted_tweet.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-3 block rounded-2xl border border-neutral-700 p-3 hover:bg-neutral-900 transition no-underline"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <div className="flex items-start gap-2 mb-2">
                      <img 
                        src={tweet.quoted_tweet.author_profile_pic_url || 'https://abs.twimg.com/sticky/default_profile_images/default_profile_400x400.png'} 
                        alt={tweet.quoted_tweet.author_name}
                        className="h-5 w-5 rounded-full"
                      />
                      <div className="flex items-center gap-1 text-sm">
                        <span className="font-semibold text-neutral-300">{tweet.quoted_tweet.author_name}</span>
                        <span className="text-neutral-500">@{tweet.quoted_tweet.author_handle}</span>
                      </div>
                    </div>
                    
                    <p className="whitespace-pre-wrap text-sm text-neutral-300 mb-2">
                      {tweet.quoted_tweet.text}
                    </p>
                    
                    {/* Quoted tweet images */}
                    {tweet.quoted_tweet.media && tweet.quoted_tweet.media.length > 0 && (
                      <div className="rounded-xl overflow-hidden mt-2">
                        {tweet.quoted_tweet.media.map((media, idx) => (
                          <img 
                            key={idx}
                            src={media.url}
                            alt={media.alt_text || ''}
                            className="w-full max-h-48 object-cover"
                          />
                        ))}
                      </div>
                    )}
                  </a>
                )}
                
                {/* Display images for first message only */}
                {index === 0 && tweet.media && tweet.media.length > 0 && (
                  <div className={`mt-3 rounded-2xl overflow-hidden border border-neutral-800 ${
                    (tweet.media?.length ?? 0) === 1 ? 'max-w-2xl' : 
                    (tweet.media?.length ?? 0) === 2 ? 'grid grid-cols-2 gap-0.5' :
                    (tweet.media?.length ?? 0) === 3 ? 'grid grid-cols-2 gap-0.5' :
                    'grid grid-cols-2 gap-0.5'
                  }`}>
                    {tweet.media.map((media, mediaIndex) => (
                      <img
                        key={mediaIndex}
                        src={media.url}
                        alt={media.alt_text || `Image ${mediaIndex + 1}`}
                        className={`w-full ${
                          (tweet.media?.length ?? 0) === 1 ? 'object-contain max-h-[600px]' :
                          (tweet.media?.length ?? 0) === 3 && mediaIndex === 0 ? 'row-span-2 h-full object-cover' :
                          'h-48 object-cover'
                        }`}
                        loading="lazy"
                      />
                    ))}
                  </div>
                )}
                
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
          {tweet.impressions !== undefined && tweet.impressions > 0 && (
            <div className="flex items-center gap-2">
              <i className="fa-regular fa-eye text-lg text-neutral-500" aria-hidden="true" />
              <span className="font-medium">{formatMetric(tweet.impressions)}</span>
            </div>
          )}
        </div>

        {!readOnly ? (
          <>
            <p className="text-sm text-neutral-500 pt-7">
              Replying to <span className="text-sky-400">{'@' + handle}</span>
            </p>
            {isRegenerating ? (
              <div className="flex gap-3 pt-6">
                <img src={myAvatar} alt="Your avatar" className="h-12 w-12 rounded-full" />
                <div className="flex-1">
                  <div className="w-full min-h-[6rem] flex items-start pt-2">
                    <AnimatedText
                      text="Regenerating replies"
                      className="text-lg"
                    />
                  </div>
                </div>
              </div>
            ) : (
              <div className="pt-6">
                {/* Single profile picture at the top */}
                <div className="flex gap-3">
                  <img src={myAvatar} alt="Your avatar" className="h-12 w-12 rounded-full flex-shrink-0" />
                  <div className="flex-1 space-y-4">
                    {editedTexts.map((text, index) => (
                      <div
                        key={index}
                        className="group"
                      >
                        {index > 0 && <div className="border-t border-neutral-700 mb-4" />}
                        <div className="flex items-center gap-8">
                          <div className="relative flex-1">
                            <textarea
                              ref={index === 0 ? textareaRef : undefined}
                              placeholder="Post your reply"
                              value={text}
                              onChange={(e) => handleTextChange(index, e.target.value)}
                              className="w-full min-h-[6rem] max-h-[12rem] resize-none overflow-y-auto bg-transparent text-lg text-white outline-none placeholder:text-neutral-600 pr-2 scrollbar-thin scrollbar-thumb-neutral-700 scrollbar-track-transparent hover:scrollbar-thumb-neutral-600"
                              style={{
                                maskImage: 'linear-gradient(to bottom, black calc(100% - 20px), transparent 100%)',
                                WebkitMaskImage: 'linear-gradient(to bottom, black calc(100% - 20px), transparent 100%)'
                              }}
                            />
                            {/* Fade overlay at bottom */}
                            <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-9 bg-gradient-to-t from-black to-transparent" />
                          </div>
                          <button
                            type="button"
                            onClick={() => handlePublish(index)}
                            className="rounded-full bg-sky-500 px-5 py-2 text-sm font-semibold text-white transition hover:bg-sky-600 self-start mt-7 flex-shrink-0"
                          >
                            Post
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </>
        ) : (
          editedTexts.length > 0 && editedTexts.some(text => text) && (
            <>
              <p className="text-sm text-neutral-500 pt-7">
                Your reply to <span className="text-sky-400">{'@' + handle}</span>
              </p>
              <div className="pt-6">
                <div className="flex gap-3">
                  <img src={myAvatar} alt="Your avatar" className="h-12 w-12 rounded-full flex-shrink-0" />
                  <div className="flex-1 space-y-4">
                    {editedTexts.map((text, index) => (
                      text && (
                        <div key={index}>
                          {index > 0 && <div className="border-t border-neutral-700 mb-4" />}
                          <div className="relative max-h-[12rem] overflow-y-auto scrollbar-thin scrollbar-thumb-neutral-700 scrollbar-track-transparent hover:scrollbar-thumb-neutral-600">
                            <p className="whitespace-pre-wrap text-lg leading-relaxed text-white">{text}</p>
                            {/* Fade overlay at bottom */}
                            <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-6 bg-gradient-to-t from-black to-transparent" />
                          </div>
                        </div>
                      )
                    ))}
                  </div>
                </div>
              </div>
            </>
          )
        )}
      </div>

      {!readOnly && (
        <div className="flex items-center justify-center gap-3 px-5 pb-8 pt-4">
          <button
            type="button"
            onClick={async () => {
              // Save all replies that have unsaved changes
              for (let i = 0; i < editedTexts.length; i++) {
                if (hasUnsavedChanges[i]) {
                  await handleSave(i);
                }
              }
            }}
            disabled={!hasUnsavedChanges.some(changed => changed)}
            className={`rounded-full px-5 py-2 text-sm font-semibold transition ${
              hasUnsavedChanges.some(changed => changed)
                ? 'bg-neutral-700 text-white hover:bg-neutral-600'
                : 'bg-neutral-800 text-neutral-500 cursor-not-allowed'
            }`}
          >
            Save All
          </button>
          {onRegenerate && (
            <button
              type="button"
              onClick={onRegenerate}
              className="rounded-full bg-neutral-700 px-5 py-2 text-sm font-semibold text-white transition hover:bg-neutral-600 flex items-center gap-2"
            >
              <i className="fa-solid fa-rotate-right" />
              Regenerate
            </button>
          )}
        </div>
      )}
    </div>
  );
}
