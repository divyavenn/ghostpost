import { motion } from 'framer-motion';

export interface PostingItem {
  id: string;  // Unique ID for this posting attempt
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
}

export function PostingInProgress({
  item,
  myProfilePicUrl,
  myHandle,
  myUsername
}: PostingInProgressProps) {
  // Combine thread text for display
  const threadPreview = item.originalThreadText?.join(' ').slice(0, 200) || '';

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
              posting...
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
