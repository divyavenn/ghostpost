import { Background } from '../components/Background';
import { useNavigate } from 'react-router-dom';

export function Login() {
  const navigate = useNavigate();

  const handleLogin = async () => {
    try {
      console.log('Starting Twitter login...');

      // Step 1: Open loading page IMMEDIATELY (synchronously) to avoid popup blockers
      const loginTab = window.open('/login-loading', '_blank');

      if (!loginTab) {
        alert('Please allow popups to continue with login');
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
            const installExtension = confirm(
              `Browser Extension Required\n\n` +
              `The GhostPoster browser extension is required to complete login.\n\n` +
              `Please install the extension and try logging in again.\n\n` +
              `Click OK to open the Chrome Web Store.`
            );

            if (installExtension) {
              // Placeholder URL - replace with actual Chrome Web Store link when published
              window.open('https://google.com', '_blank');
            }
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
      alert(`Login failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  return (
    <Background className="flex flex-col min-h-screen p-6">
      {/* Hero Section - Top */}
      <div className="flex-1 flex flex-col items-center justify-center text-center max-w-6xl mx-auto">
        <h1 className="text-8xl font-bold text-white mb-6">
          Nobody knows<br />
          <span className="text-gray-400">you exist.</span>
        </h1>
        <p className="text-3xl text-gray-400 mb-12">We can fix that.</p>

        {/* Logo */}
        <div className="mb-8">
          <img
            src="/ghostposter_logo.png"
            alt="GhostPoster"
            className="h-32 w-auto object-contain animate-flicker"
          />
        </div>

        {/* Login Button */}
        <button
          onClick={handleLogin}
          className="rounded-full bg-sky-500 px-8 py-3 text-lg font-semibold text-white transition hover:bg-sky-600"
        >
          Login with Twitter
        </button>
      </div>

      {/* Cards Section - Bottom */}
      <div className="w-full max-w-6xl mx-auto pb-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {/* Card 1 */}
          <div className="p-8">
            <div className="text-gray-500 text-sm mb-4">01</div>
            <h3 className="text-xl font-bold text-white mb-4">
              We build you a bespoke<br />language model
            </h3>
            <p className="text-gray-400">
              Your unique style <span className="underline">baked in.</span>
            </p>
          </div>

          {/* Card 2 */}
          <div className="p-8">
            <div className="text-gray-500 text-sm mb-4">02</div>
            <h3 className="text-xl font-bold text-white mb-4">
              It finds people who<br />would love your brand
            </h3>
            <p className="text-gray-400">
              And tells them in <span className="font-bold">your voice.</span>
            </p>
          </div>

          {/* Card 3 */}
          <div className="p-8">
            <div className="text-gray-500 text-sm mb-4">03</div>
            <h3 className="text-xl font-bold text-white mb-4">
              No AI slop, no spam.
            </h3>
            <p className="text-gray-400">
              Just <span className="font-bold">influence</span> that scales and<br />
              the reputation you deserve.
            </p>
          </div>
        </div>

        <div className="text-center mt-8">
          <p className="text-gray-500 text-lg">Ready to be seen?</p>
        </div>
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
