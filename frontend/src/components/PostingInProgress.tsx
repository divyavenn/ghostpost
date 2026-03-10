import { motion } from 'framer-motion';
import { useEffect, useState } from 'react';

export type PostingStatus = 'awaiting_approval' | 'queued' | 'running' | 'failed' | 'completed';
export interface PostingItem {
  id: string;  // Unique ID for this posting attempt
  draftId?: string;
  status?: PostingStatus;
  error?: string | null;
  originalTweetId: string;  // ID of the tweet being replied to (for rollback)
  text: string;  // The reply text being posted
  respondingTo: string;  // Handle of who we're replying to
  originalTweetUrl?: string;  // URL of the original tweet
  originalThreadText?: string[];  // Original tweet thread text
  source: 'discovered' | 'comments';  // Where this came from (for rollback)
  startedAt: number;  // Timestamp when posting started
}

interface PostingInProgressProps {
  item: PostingItem;
  myProfilePicUrl: string;
  myHandle: string;
  myUsername: string;
  onApproveDraft?: (draftId: string) => Promise<void> | void;
  onSaveDraft?: (draftId: string, text: string) => Promise<void> | void;
  onDiscardDraft?: (draftId: string) => Promise<void> | void;
  isActionPending?: boolean;
}

export function PostingInProgress({
  item,
  myProfilePicUrl,
  myHandle,
  myUsername,
  onApproveDraft,
  onSaveDraft,
  onDiscardDraft,
  isActionPending = false,
}: PostingInProgressProps) {
  const [draftText, setDraftText] = useState(item.text);
  useEffect(() => {
    setDraftText(item.text);
  }, [item.text]);

  const status = item.status || 'queued';
  const threadPreview = item.originalThreadText?.join(' ').slice(0, 200) || '';
  const isDraft = status === 'awaiting_approval' || status === 'failed';
  const canEdit = status === 'awaiting_approval' || status === 'failed';
  const canApprove = status === 'awaiting_approval' || status === 'failed';

  if (status === 'completed') {
    return (
      <div className="w-full px-[2%] pb-[4%] rounded-2xl bg-black text-white shadow-2xl border border-emerald-500/30">
        <div className="flex items-center justify-between p-5 mb-2">
          <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400">
            posted
          </span>
        </div>
        <div className="px-5 py-3">
          <div className="flex gap-3">
            <img src={myProfilePicUrl} alt={myUsername} className="h-12 w-12 rounded-full" />
            <div className="flex-1">
              <div className="flex items-center gap-2 text-sm text-neutral-400 mb-1">
                <span className="text-base font-bold text-white">{myUsername}</span>
                <span>@{myHandle}</span>
              </div>
              <p className="whitespace-pre-wrap text-lg leading-relaxed text-white">{item.text}</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (isDraft) {
    const hasChanges = draftText !== item.text;
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.98 }}
        animate={{ opacity: 1, scale: 1 }}
        className={`w-full px-[2%] pb-[4%] rounded-2xl bg-black text-white shadow-2xl border ${
          status === 'failed' ? 'border-red-500/30' : 'border-amber-500/30'
        }`}
      >
        <div className="flex items-center justify-between p-5 mb-2">
          <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${
            status === 'failed'
              ? 'bg-red-500/20 text-red-400'
              : 'bg-amber-500/20 text-amber-400'
          }`}>
            {status === 'failed' ? 'failed - edit & retry' : 'awaiting approval'}
          </span>
        </div>

        <div className="px-5 py-3">
          {item.respondingTo && threadPreview && (
            <p className="text-sm text-neutral-500 pb-3">
              Replying to <span className="text-sky-400">@{item.respondingTo}</span>
            </p>
          )}

          {item.error && (
            <div className="mb-3 text-xs text-red-300 bg-red-500/10 border border-red-500/20 rounded-lg p-2">
              {item.error}
            </div>
          )}

          <textarea
            value={draftText}
            onChange={(e) => setDraftText(e.target.value)}
            disabled={!canEdit || isActionPending}
            className="w-full min-h-[120px] rounded-lg bg-neutral-900 border border-neutral-700 p-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-sky-500 resize-y"
          />

          <div className="flex items-center gap-2 pt-3">
            <button
              type="button"
              disabled={!hasChanges || isActionPending || !item.draftId}
              onClick={() => {
                if (item.draftId && onSaveDraft) onSaveDraft(item.draftId, draftText);
              }}
              className="px-3 py-1.5 text-xs rounded-md bg-neutral-700 text-white disabled:opacity-50"
            >
              Save
            </button>
            <button
              type="button"
              disabled={!canApprove || isActionPending || !item.draftId}
              onClick={() => {
                if (item.draftId && onApproveDraft) onApproveDraft(item.draftId);
              }}
              className="px-3 py-1.5 text-xs rounded-md bg-sky-600 text-white disabled:opacity-50"
            >
              {status === 'failed' ? 'Retry' : 'Approve'}
            </button>
            <button
              type="button"
              disabled={isActionPending || !item.draftId}
              onClick={() => {
                if (item.draftId && onDiscardDraft) onDiscardDraft(item.draftId);
              }}
              className="px-3 py-1.5 text-xs rounded-md bg-red-600/80 text-white disabled:opacity-50"
            >
              Discard
            </button>
          </div>
        </div>
      </motion.div>
    );
  }

  const postingLabel = status === 'running' ? 'posting...' : 'queued for desktop...';

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ duration: 0.3 }}
      className="w-full px-[2%] pb-[4%] rounded-2xl bg-black text-white shadow-2xl relative overflow-hidden"
    >
      {/* Animated gradient overlay */}
      <motion.div
        className="absolute inset-0 bg-gradient-to-r from-transparent via-sky-500/10 to-transparent"
        animate={{
          x: ['-100%', '100%'],
        }}
        transition={{
          repeat: Infinity,
          duration: 1.5,
          ease: 'linear',
        }}
      />

      {/* Blur overlay */}
      <div className="absolute inset-0 backdrop-blur-[2px] bg-black/20 z-10" />

      {/* Content (slightly blurred) */}
      <div className="relative z-0 filter blur-[1px]">
        <div className="flex items-center justify-between p-5 ml-[-20px] mb-2">
          <div className="flex items-center gap-2">
            {/* Animated posting indicator */}
            <motion.div
              className="h-10 w-10 flex items-center justify-center"
              animate={{ rotate: 360 }}
              transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}
            >
              <i className="fa-solid fa-circle-notch text-sky-400 text-xl" />
            </motion.div>
            <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-sky-500/20 text-sky-400">
              {postingLabel}
            </span>
          </div>
        </div>

        <div className="px-5 py-3">
          {/* Original Tweet Preview */}
          {item.respondingTo && threadPreview && (
            <>
              <div className="space-y-4 pb-1">
                <div className="relative flex gap-3">
                  <div className="h-12 w-12 rounded-full bg-neutral-800" />
                  <div className="flex-1 space-y-1 pb-4">
                    <div className="flex items-center gap-2 text-sm text-neutral-400">
                      <span className="text-base font-bold text-white">@{item.respondingTo}</span>
                    </div>
                    <p className="whitespace-pre-wrap text-lg leading-relaxed text-white opacity-60">
                      {threadPreview}...
                    </p>
                  </div>
                </div>
              </div>
            </>
          )}

          {/* Your Reply */}
          {item.respondingTo && (
            <p className="text-sm text-neutral-500 pt-7">
              Your reply to <span className="text-sky-400">@{item.respondingTo}</span>
            </p>
          )}
          <div className={`flex gap-3 ${item.respondingTo ? 'pt-6' : 'pt-2'}`}>
            <img src={myProfilePicUrl} alt={myUsername} className="h-12 w-12 rounded-full" />
            <div className="flex-1">
              <div className="flex items-center gap-2 text-sm text-neutral-400 mb-1">
                <span className="text-base font-bold text-white">{myUsername}</span>
                <span>@{myHandle}</span>
                <span>· now</span>
              </div>
              <p className="whitespace-pre-wrap text-lg leading-relaxed text-white">{item.text}</p>
            </div>
          </div>

          {/* Placeholder metrics */}
          <div className="flex items-center gap-8 pl-14 pt-4 text-sm text-neutral-600" aria-label="Tweet engagement">
            <div className="flex items-center gap-2">
              <i className="fa-regular fa-comment text-lg" aria-hidden="true" />
              <span className="font-medium">-</span>
            </div>
            <div className="flex items-center gap-2">
              <i className="fa-solid fa-retweet text-lg" aria-hidden="true" />
              <span className="font-medium">-</span>
            </div>
            <div className="flex items-center gap-2">
              <i className="fa-regular fa-heart text-lg" aria-hidden="true" />
              <span className="font-medium">-</span>
            </div>
          </div>
        </div>
      </div>

      {/* Posting status bar */}
      <motion.div
        className="absolute bottom-0 left-0 right-0 h-1 bg-sky-500/30 z-20"
      >
        <motion.div
          className="h-full bg-sky-500"
          initial={{ width: '0%' }}
          animate={{ width: '100%' }}
          transition={{ duration: 3, ease: 'easeOut' }}
        />
      </motion.div>
    </motion.div>
  );
}
