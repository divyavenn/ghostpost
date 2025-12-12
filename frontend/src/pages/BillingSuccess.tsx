import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';

export function BillingSuccess() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [countdown, setCountdown] = useState(5);

  const sessionId = searchParams.get('session_id');

  useEffect(() => {
    // Auto-redirect after countdown
    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          navigate('/');
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [navigate]);

  return (
    <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="max-w-md mx-4 text-center"
      >
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ type: 'spring', delay: 0.2 }}
          className="text-6xl mb-6"
        >
          <i className="fas fa-check-circle text-green-400"></i>
        </motion.div>

        <h1 className="text-3xl font-bold mb-4">Payment Successful!</h1>

        <p className="text-slate-400 mb-8">
          Thank you for subscribing! Your account has been upgraded to the Paid
          tier. You now have automatic background discovery.
        </p>

        <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 mb-8">
          <h3 className="text-lg font-semibold mb-3">What's included:</h3>
          <ul className="text-left space-y-2 text-slate-300">
            <li className="flex items-center gap-2">
              <i className="fas fa-check text-green-400"></i>
              Automatic background discovery
            </li>
            <li className="flex items-center gap-2">
              <i className="fas fa-check text-green-400"></i>
              Unlimited accounts to track
            </li>
            <li className="flex items-center gap-2">
              <i className="fas fa-check text-green-400"></i>
              Unlimited search queries
            </li>
          </ul>
        </div>

        <button
          onClick={() => navigate('/')}
          className="w-full py-3 px-6 bg-sky-600 hover:bg-sky-500 text-white rounded-lg font-semibold transition"
        >
          Go to Dashboard
        </button>

        <p className="text-slate-500 text-sm mt-4">
          Redirecting in {countdown} seconds...
        </p>

        {sessionId && (
          <p className="text-slate-600 text-xs mt-2">
            Session: {sessionId.slice(0, 20)}...
          </p>
        )}
      </motion.div>
    </div>
  );
}
