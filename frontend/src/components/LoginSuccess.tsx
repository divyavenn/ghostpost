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

        {/* Cat Lottie animation */}
        <div className="w-[400px] h-[400px] mx-auto mb-8 mt-[-200px]">
          <DotLottieReact
            src="/cat.lottie"
            loop
            autoplay
          />
        </div>

        {/* Success message */}
        <div className="mt-[-70px] mb-8">
          <AnimatedText text="Taking you back to GhostPost!" className="text-[20px]" />
        </div>

        <p className="text-base opacity-70 text-slate-300">
          {countdown > 0
            ? `Login Sucessful! This tab will close in ${countdown} second${countdown !== 1 ? 's' : ''}...`
            : 'Login Sucessful! Closing...'}
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
