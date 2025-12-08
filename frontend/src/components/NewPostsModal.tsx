import { motion, AnimatePresence } from 'framer-motion';

interface NewPostsModalProps {
  isOpen: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  newPostsCount?: number;
}

export function NewPostsModal({ isOpen, onConfirm, onCancel, newPostsCount }: NewPostsModalProps) {
  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
          onClick={onCancel}
        >
          <motion.div
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.95, opacity: 0 }}
            transition={{ type: 'spring', duration: 0.3 }}
            className="bg-slate-900 rounded-xl p-8 max-w-md mx-4 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="text-center">
              <h2 className="text-2xl font-semibold text-white mb-3">
                Found new posts!
              </h2>
              <p className="text-slate-300 mb-6">
                {newPostsCount !== undefined && newPostsCount > 0
                  ? `${newPostsCount} new tweet${newPostsCount > 1 ? 's' : ''} found. `
                  : ''}
                Remove tweets you've already seen and ignored?
              </p>
              <div className="flex gap-4 justify-center">
                <button
                  onClick={onCancel}
                  className="px-6 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition"
                >
                  Keep all
                </button>
                <button
                  onClick={onConfirm}
                  className="px-6 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition"
                >
                  Clear seen
                </button>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
