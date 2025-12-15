import { useState } from 'react';
import styled from 'styled-components';
import { useNavigate } from 'react-router-dom';
import { useSetRecoilState } from 'recoil';
import { usernameState } from '../atoms';
import { LoginLoading } from '../components/LoginLoading';
import { Background } from '../components/Background';
import { TextTree } from '../components/TextTree';

// --- Theme ---
const theme = {
  colors: {
    background: '#0f172a',
    text: '#E5E5E5',
    textSecondary: 'rgba(229, 229, 229, 0.6)',
    link: '#E5E5E5',
    linkHover: '#ffffff',
  },
  fonts: {
    body: '"Fraunces", serif',
    mono: '"Geist Mono", monospace',
  },
};

// --- Styled Components ---
const LoginButton = styled.button`
  position: fixed;
  top: 40px;
  right: 40px;
  display: flex;
  align-items: center;
  gap: 8px;
  background: #ffffff;
  border: none;
  border-radius: 9999px;
  color: #000000;
  padding: 10px 30px;
  font-family: ${theme.fonts.mono};
  font-size: 1.2rem;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.2s ease;

  &:hover {
    background: #e7e7e7;
  }

  svg {
    width: 18px;
    height: 18px;
  }
`;

const ContactText = styled.div`
  position: fixed;
  bottom: 100px;
  left: 50%;
  transform: translateX(-50%);
  text-align: center;
  font-family: ${theme.fonts.mono};
  font-size: 1.3rem;
  color: ${theme.colors.textSecondary};

  a {
    color: ${theme.colors.link};
    text-decoration: none;
    border-bottom: 1px solid transparent;
    transition: border-color 0.2s ease;

    &:hover {
      border-bottom-color: ${theme.colors.linkHover};
    }
  }
`;

const TextContainer = styled.div`
  max-width: 1000px;
  margin: 0 auto;
  margin-top: 2%;
  padding: 40px 20px;
  font-size: 1.8rem;
  line-height: 2.2;
  letter-spacing: -0.01em;
  text-align: center;
  flex: 1;

  @media (max-width: 768px) {
    font-size: 1.4rem;
    line-height: 1.9;
  }
`;

// --- Main Component ---
export function Login() {
  const navigate = useNavigate();
  const setUsername = useSetRecoilState(usernameState);
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // --- Auth Logic ---
  const handleLogin = async () => {
    try {
      setError(null);
      setIsLoggingIn(true);

      const loginTab = window.open('/login-loading', '_blank');
      if (!loginTab) {
        setError('Please allow popups to continue with login');
        setIsLoggingIn(false);
        return;
      }

      const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '';
      const frontendUrl = window.location.origin;

      const response = await fetch(`${apiBaseUrl}/auth/twitter/login-url`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ frontend_url: frontendUrl })
      });

      if (!response.ok) throw new Error('Failed to get login URL');

      const { login_url, session_id } = await response.json();

      let messageSent = false;
      const sendLoginUrl = () => {
        if (messageSent) return;
        messageSent = true;
        loginTab.postMessage({ type: 'LOGIN_URL', url: login_url }, window.location.origin);
      };

      const handleReadyMessage = (event: MessageEvent) => {
        if (event.origin !== window.location.origin) return;
        if (event.data.type === 'LOGIN_PAGE_READY') {
          window.removeEventListener('message', handleReadyMessage);
          sendLoginUrl();
        }
      };

      window.addEventListener('message', handleReadyMessage);

      setTimeout(() => {
        window.removeEventListener('message', handleReadyMessage);
        sendLoginUrl();
      }, 1000);

      const pollInterval = setInterval(async () => {
        try {
          const statusResponse = await fetch(`${apiBaseUrl}/auth/twitter/cookie-status/${session_id}`);
          if (!statusResponse.ok) return;

          const status = await statusResponse.json();

          if ((status.status === 'success' || status.status === 'complete') && status.username) {
            clearInterval(pollInterval);
            try { loginTab.close(); } catch (e) { console.warn(e); }
            window.focus();
            setUsername(status.username);
            setIsLoggingIn(false);
            navigate('/', { replace: true });
          } else if (status.status === 'extension_required') {
            clearInterval(pollInterval);
            try { loginTab.close(); } catch (e) { console.warn(e); }
            setIsLoggingIn(false);
            setError('Browser Extension Required');
          }
        } catch (error) {
          console.error('Polling error:', error);
        }
      }, 2000);

      setTimeout(() => clearInterval(pollInterval), 300000);
    } catch (error) {
      console.error('Login failed:', error);
      setError(`Login failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
      setIsLoggingIn(false);
    }
  };

  if (isLoggingIn) return <LoginLoading />;

  return (
      <Background>
        <LoginButton onClick={handleLogin}>
          Log in with
          <svg viewBox="0 0 24 24" aria-hidden="true" fill="currentColor">
            <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
          </svg>
        </LoginButton>

        <TextContainer>
          {error && (
            <div style={{
              color: '#ff6b6b',
              marginBottom: '40px',
              fontSize: '1rem',
              fontFamily: theme.fonts.mono
            }}>
              {error}
            </div>
          )}

          <TextTree />
        </TextContainer>

        <ContactText>
          questions? email <a href="mailto:divya@aibread.com">divya@aibread.com</a>
        </ContactText>
      </Background>
  );
}

export default Login;
