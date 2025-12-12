import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';

interface PremiumFeatureModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function PremiumFeatureModal({ isOpen, onClose }: PremiumFeatureModalProps) {
  const navigate = useNavigate();

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
            className="bg-slate-900 border border-purple-700 rounded-xl p-8 max-w-md mx-4 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="text-center">
              <div className="mb-4 text-4xl">*</div>
              <h2 className="text-2xl font-semibold text-white mb-3">
                This is a premium feature!
              </h2>
              <p className="text-slate-300 mb-6">
                AI-generated replies and auto-posting are available on the Premium plan.
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
                  className="px-6 py-2 bg-purple-700 hover:bg-purple-600 text-white rounded-lg transition font-semibold"
                >
                  View Pricing
                </button>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
