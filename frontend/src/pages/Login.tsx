import { Background } from '../components/Background';
import { useNavigate } from 'react-router-dom';
import { useState } from 'react';
import { LoginLoading } from '../components/LoginLoading';
import { LoginCarousel } from '../components/LoginCarousel';
import { loginCards } from '../data/loginCards';

export function Login() {
  const navigate = useNavigate();
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLogin = async () => {
    try {
      setError(null);
      setIsLoggingIn(true);
      console.log('Starting Twitter login...');

      // Step 1: Open loading page IMMEDIATELY (synchronously) to avoid popup blockers
      const loginTab = window.open('/login-loading', '_blank');

      if (!loginTab) {
        setError('Please allow popups to continue with login');
        setIsLoggingIn(false);
        return;
      }

      // Step 2: Get Twitter login URL from backend
      // VITE_API_BASE_URL already includes /api in production
      const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '';

      // Send current frontend URL so backend knows where to redirect
      const frontendUrl = window.location.origin; // e.g., http://localhost:5173

      const response = await fetch(`${apiBaseUrl}/auth/twitter/login-url`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          frontend_url: frontendUrl
        })
      });

      if (!response.ok) {
        throw new Error('Failed to get login URL');
      }

      const { login_url, session_id } = await response.json();
      console.log('Got login URL, session:', session_id);

      // Step 3: Wait for login page to be ready, then send login URL
      let messageSent = false;
      const sendLoginUrl = () => {
        if (messageSent) return; // Prevent duplicate sends
        messageSent = true;
        console.log('Sending LOGIN_URL to tab:', login_url);
        loginTab.postMessage({
          type: 'LOGIN_URL',
          url: login_url
        }, window.location.origin);
      };

      // Listen for ready message from login tab
      const handleReadyMessage = (event: MessageEvent) => {
        console.log('Received message from login tab:', event.data);
        if (event.origin !== window.location.origin) {
          console.warn('Ignoring message from different origin:', event.origin);
          return;
        }
        if (event.data.type === 'LOGIN_PAGE_READY') {
          console.log('Login page is ready, sending URL');
          window.removeEventListener('message', handleReadyMessage);
          sendLoginUrl();
        }
      };

      window.addEventListener('message', handleReadyMessage);
      console.log('Waiting for LOGIN_PAGE_READY from child window...');

      // Fallback: send after 1000ms if no ready message received
      setTimeout(() => {
        console.log('Fallback timeout: sending login URL anyway');
        window.removeEventListener('message', handleReadyMessage);
        sendLoginUrl();
      }, 1000);

      // Step 4: Poll backend for cookie import completion
      const pollInterval = setInterval(async () => {
        try {
          const statusResponse = await fetch(
            `${apiBaseUrl}/auth/twitter/cookie-status/${session_id}`
          );

          if (!statusResponse.ok) return; // Keep polling

          const status = await statusResponse.json();
          console.log('Cookie import status:', status);

          if (status.status === 'success' && status.username) {
            clearInterval(pollInterval);
            console.log('✅ Login successful for:', status.username);

            // Close the login tab
            try {
              loginTab.close();
              console.log('Closed login tab');
            } catch (e) {
              console.warn('Could not close login tab:', e);
            }

            // Bring main window back into focus
            window.focus();

            // Save username and navigate to app
            localStorage.setItem('username', status.username);
            setIsLoggingIn(false);
            navigate('/', { replace: true });
          } else if (status.status === 'extension_required') {
            clearInterval(pollInterval);
            console.log('⚠️ Extension not detected');

            // Close the login tab
            try {
              loginTab.close();
            } catch (e) {
              console.warn('Could not close login tab:', e);
            }

            // Show extension install prompt
            setIsLoggingIn(false);
            setError('Browser Extension Required. The GhostPoster browser extension is required to complete login. Please install the extension and try logging in again.');
          }
        } catch (error) {
          console.error('Polling error:', error);
          // Keep polling even on errors
        }
      }, 2000); // Poll every 2 seconds

      // Timeout after 5 minutes
      setTimeout(() => {
        clearInterval(pollInterval);
        console.log('Login polling timeout');
      }, 300000);

    } catch (error) {
      console.error('Login failed:', error);
      setError(`Login failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
      setIsLoggingIn(false);
    }
  };

  // Show loading screen while logging in
  if (isLoggingIn) {
    return <LoginLoading />;
  }

  return (
    <Background className="relative min-h-screen flex flex-col items-center justify-center overflow-hidden">
      {/* Error Message */}
      {error && (
        <div className="fixed top-8 left-1/2 -translate-x-1/2 z-[2000] bg-red-500/90 backdrop-blur-sm text-white px-6 py-3 rounded-lg font-semibold max-w-md text-center">
          {error}
        </div>
      )}

      {/* Wheel Carousel - Behind everything */}
      <div className="absolute">
        <LoginCarousel cards={loginCards} />
      </div>

      {/* Logo and Login Button Overlay - In front of cards but behind lightbox */}
      <div className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-[1000] flex flex-col items-center text-center pointer-events-none">
        {/* Logo */}
        <img
          src="/ghostposter_logo.png"
          alt="GhostPoster"
          className="h-24 w-auto object-contain mb-8 animate-flicker"
        />


        {/* Login Button */}
        <button
          onClick={handleLogin}
          className="rounded-full bg-sky-500 px-10 py-4 text-xl font-semibold text-white transition-all hover:bg-sky-600 hover:scale-105 shadow-2xl pointer-events-auto"
        >
          Login with Twitter
        </button>

        {/* Scroll Indicator */}
        <div className="mt-12 text-gray-500 text-sm">Scroll to explore</div>
      </div>

      {/* Bottom CTA */}
      <div className="fixed bottom-8 left-1/2 -translate-x-1/2 text-center z-[1500] pointer-events-none">
        <p className="text-gray-400 text-base">Ready to be seen?</p>
      </div>

      <style>{`
        @keyframes flicker {
          0%, 100% { opacity: 1; }
          2% { opacity: 0.8; }
          4% { opacity: 1; }
          8% { opacity: 0.9; }
          10% { opacity: 1; }
          12% { opacity: 0.7; }
          14% { opacity: 1; }
          18% { opacity: 0.95; }
          20% { opacity: 1; }
          70% { opacity: 1; }
          72% { opacity: 0.85; }
          74% { opacity: 1; }
          76% { opacity: 0.9; }
          78% { opacity: 1; }
        }

        .animate-flicker {
          animation: flicker 4s infinite;
        }
      `}</style>
    </Background>
  );
}
