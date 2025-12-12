import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';

interface PaidFeatureModalProps {
  isOpen: boolean;
  onClose: () => void;
  actionType?: 'scrape' | 'post';
  remaining?: number;
  onAction?: () => void;
}

export function PaidFeatureModal({
  isOpen,
  onClose,
  actionType,
  remaining = 0,
  onAction
}: PaidFeatureModalProps) {
  const navigate = useNavigate();
  const hasUsageLeft = remaining > 0;
  const actionLabel = actionType === 'scrape' ? 'Scrape' : 'Post';

  const handleViewPricing = () => {
    onClose();
    navigate('/pricing');
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          onClick={onClose}
        >
          <motion.div
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.95, opacity: 0 }}
            transition={{ type: 'spring', duration: 0.3 }}
            className="bg-slate-900 border border-slate-700 rounded-xl p-8 max-w-md mx-4 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="text-center">
              <div className="mb-4 text-4xl">
                {hasUsageLeft ? '' : ''}
              </div>

              {actionType ? (
                <>
                  {hasUsageLeft ? (
                    <>
                      <h2 className="text-2xl font-semibold text-white mb-3">
                        {remaining} {actionType === 'scrape' ? 'scrape' : 'post'}{remaining !== 1 ? 's' : ''} remaining
                      </h2>
                      <p className="text-slate-300 mb-6">
                        You have {remaining} trial {actionType === 'scrape' ? 'scrape' : 'post'}{remaining !== 1 ? 's' : ''} left.
                        Upgrade for unlimited access.
                      </p>
                      <div className="flex gap-3 justify-center">
                        <button
                          onClick={handleViewPricing}
                          className="px-6 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg transition"
                        >
                          View Pricing
                        </button>
                        <button
                          onClick={() => {
                            onAction?.();
                            onClose();
                          }}
                          className="px-6 py-2 bg-sky-600 hover:bg-sky-500 text-white rounded-lg transition font-semibold"
                        >
                          {actionLabel}
                        </button>
                      </div>
                    </>
                  ) : (
                    <>
                      <h2 className="text-2xl font-semibold text-white mb-3">
                        Upgrade to paid to keep {actionType === 'scrape' ? 'scraping' : 'posting'}
                      </h2>
                      <p className="text-slate-300 mb-6">
                        You've used all your trial {actionType === 'scrape' ? 'scrapes' : 'posts'}.
                        Upgrade for unlimited access.
                      </p>
                      <div className="flex gap-3 justify-center">
                        <button
                          onClick={onClose}
                          className="px-6 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg transition"
                        >
                          Close
                        </button>
                        <button
                          onClick={handleViewPricing}
                          className="px-6 py-2 bg-sky-600 hover:bg-sky-500 text-white rounded-lg transition font-semibold"
                        >
                          View Pricing
                        </button>
                      </div>
                    </>
                  )}
                </>
              ) : (
                <>
                  <h2 className="text-2xl font-semibold text-white mb-3">
                    This is a paid feature!
                  </h2>
                  <p className="text-slate-300 mb-6">
                    Upgrade to unlock this feature.
                  </p>
                  <div className="flex gap-3 justify-center">
                    <button
                      onClick={onClose}
                      className="px-6 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg transition"
                    >
                      Close
                    </button>
                    <button
                      onClick={handleViewPricing}
                      className="px-6 py-2 bg-sky-600 hover:bg-sky-500 text-white rounded-lg transition font-semibold"
                    >
                      View Pricing
                    </button>
                  </div>
                </>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
