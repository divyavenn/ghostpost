import { useMemo, useState } from 'react';

export interface TweetData {
  id: string;
  text: string;
  likes: number;
  retweets: number;
  quotes: number;
  replies: number;
  handle: string;
  score: number;
  username: string;
  followers: number;
  reply: string;
  created_at: string;
  url: string;
  thread?: string[];
}

interface TweetDisplayProps {
  tweet: TweetData;
  replyText: string;
  onPublish: (text: string) => void;
  onSkip: () => void;
}

export default function TweetDisplay({ tweet, onPublish, onSkip }: TweetDisplayProps) {
  const [editedText, setEditedText] = useState(tweet.reply);

  // TODO: replace demo user metadata with real data once available.
  const displayName = tweet.username;
  const handle = tweet.handle;
  const verified = true;
  const userAvatar = 'https://abs.twimg.com/sticky/default_profile_images/default_profile_200x200.png';
  const myAvatar = 'https://pbs.twimg.com/profile_images/1803721062133211138/s3Zbrfw__normal.jpg';

  const threadMessages = useMemo(() => [tweet.text, ...(tweet.thread ?? [])], [tweet.text, tweet.thread]);

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

  return (
    <div className="mx-auto w-full max-w-xl rounded-2xl bg-black text-white shadow-2xl">
      <div className="flex items-center justify-between border-b border-neutral-800 px-5 py-3">
        <button
          type="button"
          onClick={onSkip}
          className="rounded-full p-2 text-xl leading-none text-white hover:bg-neutral-900"
          aria-label="Close"
        >
          ×
        </button>
        <span className="text-base font-bold text-sky-400">Drafts</span>
      </div>

      <div className="px-5 py-4">
        <div className="divide-y divide-neutral-800">
          {threadMessages.map((message, index) => (
            <div key={`${tweet.id}-${index}`} className="flex gap-3 py-4 first:pt-0">
              {index === 0 ? (
                <img src={userAvatar} alt={displayName} className="h-12 w-12 rounded-full" />
              ) : (
                <div className="h-12 w-12" aria-hidden="true" />
              )}
              <div className="flex-1 space-y-1">
                {index === 0 && (
                  <div className="flex items-center gap-2 text-sm text-neutral-400">
                    <span className="text-base font-bold text-white">{displayName}</span>
                    {verified && <span className="text-sky-400">✓</span>}
                    <span>{handle}</span>
                    {tweet.created_at && <span>· {getRelativeTime(tweet.created_at)}</span>}
                  </div>
                )}
                <p className="whitespace-pre-wrap text-[15px] leading-relaxed text-white">{message}</p>
              </div>
            </div>
          ))}
        </div>
        <p className="text-sm text-neutral-500">
          Replying to <span className="text-sky-400">{handle}</span>
        </p>
        <div className="flex gap-3 pt-4">
          <img src={myAvatar} alt="Your avatar" className="h-12 w-12 rounded-full" />
          <div className="flex-1">
            <textarea
              placeholder="Post your reply"
              value={editedText}
              onChange={(e) => setEditedText(e.target.value)}
              className="w-full resize-none bg-transparent text-lg text-white outline-none placeholder:text-neutral-600"
              rows={3}
            />
          </div>
        </div>
      </div>

      <div className="flex items-center justify-end border-t border-neutral-800 px-5 py-3">
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
