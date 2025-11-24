import { useEffect, useState } from 'react';
import { DotLottieReact } from '@lottiefiles/dotlottie-react';
import { AnimatedText } from './WordStyles';

export function LoginLoading() {
  const [message, setMessage] = useState("You'll be redirected to X in a moment...");
  const [animatedText, setAnimatedText] = useState('Asking X to log you in');
  const [showSuccess, setShowSuccess] = useState(false);

  const messages = [
    'Asking Elon to let you in...',
    'Preparing secure takeoff...',
    'Taking you to the everything app...'
  ];

  useEffect(() => {
    // Notify parent that we're ready to receive messages
    if (window.opener) {
      window.opener.postMessage({ type: 'LOGIN_PAGE_READY' }, window.location.origin);
      console.log('LoginLoading: Sent LOGIN_PAGE_READY to opener');
    }

    // Cycle through messages
    let messageIndex = 0;
    const messageInterval = setInterval(() => {
      messageIndex = (messageIndex + 1) % messages.length;
      setAnimatedText(messages[messageIndex]);
    }, 4000);

    // Listen for login URL from opener window
    const handleMessage = (event: MessageEvent) => {
      console.log('LoginLoading: Received message:', event.data);

      // Security: verify origin
      if (event.origin !== window.location.origin) {
        console.warn('LoginLoading: Ignoring message from different origin:', event.origin);
        return;
      }

      if (event.data.type === 'LOGIN_URL') {
        console.log('LoginLoading: Redirecting to OAuth URL:', event.data.url);
        clearInterval(messageInterval);
        setAnimatedText('Redirecting to X');
        setMessage('Opening login page...');

        setTimeout(() => {
          window.location.href = event.data.url;
        }, 500);
      }

      if (event.data.type === 'LOGIN_SUCCESS') {
        console.log('LoginLoading: Login successful for:', event.data.username);
        clearInterval(messageInterval);
        setShowSuccess(true);
        setAnimatedText('Login Successful');
        setMessage(`Welcome back, @${event.data.username}`);

        // Close tab after 2 seconds
        setTimeout(() => {
          setMessage('This tab will close automatically...');
          setTimeout(() => {
            window.close();
          }, 1000);
        }, 2000);
      }
    };

    window.addEventListener('message', handleMessage);
    console.log('LoginLoading: Message listener added');

    // Fallback: if no message received in 10 seconds, something went wrong
    const fallbackTimeout = setTimeout(() => {
      if (window.location.pathname === '/login-loading') {
        setAnimatedText('Taking longer than expected');
        setMessage('Please wait...');
      }
    }, 10000);

    return () => {
      clearInterval(messageInterval);
      window.removeEventListener('message', handleMessage);
      clearTimeout(fallbackTimeout);
    };
  }, []);

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-900">
      <div className="text-center max-w-[600px] p-10">
        {/* Success checkmark (hidden by default) */}
        {showSuccess && (
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
        )}

        {/* Lottie animation */}
        {!showSuccess && (
          <div className="w-[300px] h-[300px] mx-auto mb-8">
            <DotLottieReact
              src="/running.lottie"
              loop
              autoplay
            />
          </div>
        )}

        {/* Animated text */}
        <div className="mb-8 mt-[-80px]">
          <AnimatedText text={animatedText} className="text-[28px]" />
        </div>

        <p className="text-base opacity-70 mt-5 text-slate-300">
          {message}
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
