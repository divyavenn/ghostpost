import { useState } from 'react';
import {motion, AnimatePresence} from 'framer-motion';

interface FirstTimeUserModalProps {
  username: string;
  onComplete: (email: string) => Promise<void>;
}

export default function FirstTimeUserModal({ username, onComplete }: FirstTimeUserModalProps) {
  const [email, setEmail] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!email || !email.includes('@')) {
      setError('Please enter a valid email address');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      await onComplete(email);
    } catch (err) {
      setError('Failed to save email. Please try again.');
      setIsSubmitting(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 backdrop-blur-md"
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 20 }}
        transition={{ duration: 0.3, ease: [0.23, 1, 0.32, 1] }}
        className="relative w-full max-w-md mx-4 bg-gradient-to-br from-slate-900 via-slate-900 to-blue-950 border border-slate-700/50 rounded-2xl shadow-2xl overflow-hidden"
      >
        {/* Subtle gradient overlay */}
        <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-transparent pointer-events-none" />
        
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1, duration: 0.4 }}
          className="relative p-6 border-b border-slate-700/50"
        >
          <h2 className="text-white flex items-center gap-2">
            Welcome to GhostPoster!
            <motion.span
              animate={{ rotate: [0, 14, -8, 14, 0] }}
              transition={{ delay: 0.3, duration: 0.5 }}
            >
              👋
            </motion.span>
          </h2>
        </motion.div>

        {/* Content */}
        <div className="relative p-6 space-y-4">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.4 }}
            className="space-y-2"
          >
            <p className="text-slate-200">
              Hi <span className="text-blue-300">@{username}</span>,
              we're excited to have you here!
            </p>
            <p className="text-slate-400">
              Before you get started, please provide your email address so we can keep you updated.
            </p>
          </motion.div>

          <motion.form
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3, duration: 0.4 }}
            onSubmit={handleSubmit}
            className="space-y-4"
          >
            <div>
              <label htmlFor="email" className="block text-slate-300 mb-2">
                Email Address
              </label>
              <motion.div
                whileFocus={{ scale: 1.01 }}
                transition={{ duration: 0.2 }}
              >
                <input
                  type="email"
                  id="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="your@email.com"
                  className="w-full px-4 py-3 bg-slate-800/50 border border-slate-600/50 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 focus:bg-slate-800/80 transition-all duration-200"
                  disabled={isSubmitting}
                  autoFocus
                />
              </motion.div>
              <AnimatePresence>
                {error && (
                  <motion.p
                    initial={{ opacity: 0, height: 0, marginTop: 0 }}
                    animate={{ opacity: 1, height: 'auto', marginTop: 8 }}
                    exit={{ opacity: 0, height: 0, marginTop: 0 }}
                    className="text-red-400"
                  >
                    {error}
                  </motion.p>
                )}
              </AnimatePresence>
            </div>

            <motion.button
              type="submit"
              disabled={isSubmitting || !email}
              whileHover={{ scale: !isSubmitting && email ? 1.02 : 1 }}
              whileTap={{ scale: !isSubmitting && email ? 0.98 : 1 }}
              transition={{ duration: 0.2 }}
              className="w-full px-4 py-3 bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 disabled:from-slate-700 disabled:to-slate-700 disabled:cursor-not-allowed text-white rounded-xl transition-all duration-200 flex items-center justify-center shadow-lg shadow-blue-500/20 disabled:shadow-none"
            >
              {isSubmitting ? (
                <>
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                    className="w-5 h-5 border-2 border-white border-t-transparent rounded-full mr-2"
                  />
                  Saving...
                </>
              ) : (
                'Continue'
              )}
            </motion.button>
          </motion.form>

          {/* Instructions */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4, duration: 0.4 }}
            className="mt-6 p-4 bg-slate-800/30 border border-slate-700/30 rounded-xl backdrop-blur-sm"
          >
            <h3 className="text-slate-200 mb-2 flex items-center gap-2">
              📋 Next Steps:
            </h3>
            <ul className="space-y-2 text-slate-400">
              <motion.li
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.5, duration: 0.3 }}
                className="flex items-start"
              >
                <span className="mr-2">1.</span>
                <span>Go to <span className="text-blue-400">User Settings</span> to configure your preferences</span>
              </motion.li>
              <motion.li
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.6, duration: 0.3 }}
                className="flex items-start"
              >
                <span className="mr-2">2.</span>
                <span>Set up <span className="text-blue-400">accounts to track</span> and <span className="text-blue-400">topics of interest</span></span>
              </motion.li>
              <motion.li
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.7, duration: 0.3 }}
                className="flex items-start"
              >
                <span className="mr-2">3.</span>
                <span>Start discovering tweets and generating replies!</span>
              </motion.li>
            </ul>
          </motion.div>
        </div>
      </motion.div>
    </motion.div>
  );
}