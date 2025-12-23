import { useState } from 'react';
import styled from 'styled-components';
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
  const [error, setError] = useState<string | null>(null);

  // --- Auth Logic ---
  const handleLogin = async () => {
    try {
      setError(null);

      const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '';
      const frontendUrl = window.location.origin;

      const response = await fetch(`${apiBaseUrl}/auth/twitter/login-url`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ frontend_url: frontendUrl })
      });

      if (!response.ok) throw new Error('Failed to get login URL');

      const { login_url } = await response.json();

      // Navigate to Twitter OAuth in the same tab
      // After OAuth, Twitter redirects to our callback, which redirects to /login-success
      window.location.href = login_url;
    } catch (error) {
      console.error('Login failed:', error);
      setError(`Login failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

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
