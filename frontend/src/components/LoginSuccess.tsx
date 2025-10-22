import { useEffect, useState } from 'react';
import { DotLottieReact } from '@lottiefiles/dotlottie-react';
import { AnimatedText } from './AnimatedText';

export function LoginSuccess() {
  const [countdown, setCountdown] = useState(3);

  useEffect(() => {
    // Extract username and session_id from URL params
    const params = new URLSearchParams(window.location.search);
    const username = params.get('username');
    const sessionId = params.get('session_id');

    // Add meta tags for browser extension to read
    if (username) {
      const metaUsername = document.createElement('meta');
      metaUsername.name = 'twitter-username';
      metaUsername.content = username;
      document.head.appendChild(metaUsername);
    }

    if (sessionId) {
      const metaSessionId = document.createElement('meta');
      metaSessionId.name = 'session-id';
      metaSessionId.content = sessionId;
      document.head.appendChild(metaSessionId);
    }

    const metaSuccess = document.createElement('meta');
    metaSuccess.name = 'twitter-oauth-success';
    metaSuccess.content = 'true';
    document.head.appendChild(metaSuccess);

    console.log('LoginSuccess: Added meta tags for extension', { username, sessionId });
  }, []);

  useEffect(() => {
    // Countdown timer
    const countdownInterval = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(countdownInterval);
          // Close the tab after countdown
          setTimeout(() => {
            window.close();
          }, 500);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(countdownInterval);
  }, []);

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-900">
      <div className="text-center max-w-[600px] p-10">
        {/* Success checkmark animation */}
        <svg
          className="w-[120px] h-[120px] mx-auto mb-8 animate-[fill_0.4s_ease-in-out_0.4s_forwards,scale_0.3s_ease-in-out_0.9s_both]"
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 52 52"
          style={{
            strokeWidth: 3,
            stroke: '#22c55e',
            strokeMiterlimit: 10
          }}
        >
          <circle
            className="animate-[stroke_0.6s_cubic-bezier(0.65,0,0.45,1)_forwards]"
            cx="26"
            cy="26"
            r="25"
            fill="none"
            style={{
              strokeDasharray: 166,
              strokeDashoffset: 166,
              strokeWidth: 3,
              stroke: '#22c55e'
            }}
          />
          <path
            className="animate-[stroke_0.3s_cubic-bezier(0.65,0,0.45,1)_0.8s_forwards]"
            fill="none"
            d="M14.1 27.2l7.1 7.2 16.7-16.8"
            style={{
              transformOrigin: '50% 50%',
              strokeDasharray: 48,
              strokeDashoffset: 48
            }}
          />
        </svg>

        {/* Cat Lottie animation */}
        <div className="w-[300px] h-[300px] mx-auto mb-8">
          <DotLottieReact
            src="/cat.lottie"
            loop
            autoplay
          />
        </div>

        {/* Success message */}
        <div className="mb-8">
          <AnimatedText text="Login Successful!" className="text-[32px] font-bold" />
        </div>

        <p className="text-xl text-green-400 font-semibold mb-4">
          Cleaning things up...
        </p>

        <p className="text-base opacity-70 text-slate-300">
          {countdown > 0
            ? `This tab will close in ${countdown} second${countdown !== 1 ? 's' : ''}...`
            : 'Closing...'}
        </p>
      </div>

      <style>{`
        @keyframes stroke {
          100% {
            stroke-dashoffset: 0;
          }
        }

        @keyframes scale {
          0%, 100% {
            transform: none;
          }
          50% {
            transform: scale3d(1.1, 1.1, 1);
          }
        }

        @keyframes fill {
          100% {
            box-shadow: inset 0px 0px 0px 60px rgba(34, 197, 94, 0.2);
          }
        }
      `}</style>
    </div>
  );
}
