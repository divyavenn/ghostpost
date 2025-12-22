import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import styled from 'styled-components';
import { Background } from '../components/Background';
import { getAccessToken } from '../lib/supabase';

const Container = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 2rem;
`;

const Title = styled.h1`
  color: white;
  font-family: 'Fraunces', serif;
  font-size: 2.5rem;
  font-weight: 400;
  margin-bottom: 1rem;
  text-align: center;
`;

const Description = styled.p`
  color: rgba(255, 255, 255, 0.7);
  font-family: 'Geist Mono', monospace;
  font-size: 1.1rem;
  margin-bottom: 2.5rem;
  text-align: center;
  max-width: 450px;
  line-height: 1.6;
`;

const ConnectButton = styled.button`
  display: flex;
  align-items: center;
  gap: 12px;
  background: #ffffff;
  border: none;
  border-radius: 9999px;
  color: #000000;
  padding: 14px 36px;
  font-family: 'Geist Mono', monospace;
  font-size: 1.2rem;
  font-weight: 500;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
    transform: none;
  }

  svg {
    width: 22px;
    height: 22px;
  }
`;

const ErrorMessage = styled.div`
  color: #ff6b6b;
  margin-bottom: 1.5rem;
  font-family: 'Geist Mono', monospace;
  font-size: 0.9rem;
`;

const XIcon = () => (
  <svg viewBox="0 0 24 24" fill="currentColor">
    <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
  </svg>
);

export function ConnectTwitter() {
  const navigate = useNavigate();
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleConnectTwitter = async () => {
    // Check if we have a session
    const accessToken = await getAccessToken();
    if (!accessToken) {
      navigate('/login');
      return;
    }

    setIsConnecting(true);
    setError(null);

    try {
      const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '';
      const frontendUrl = window.location.origin;

      // Start Twitter OAuth, passing Supabase JWT for backend to link accounts
      const response = await fetch(`${apiBaseUrl}/auth/twitter/login-url`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${accessToken}`,
        },
        body: JSON.stringify({ frontend_url: frontendUrl }),
      });

      if (!response.ok) {
        throw new Error('Failed to start Twitter connection');
      }

      const { login_url } = await response.json();
      window.location.href = login_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to connect Twitter');
      setIsConnecting(false);
    }
  };

  return (
    <Background>
      <Container>
        <Title>Connect Your X Account</Title>
        <Description>
          GhostPoster needs access to your X (Twitter) account to discover relevant tweets and post replies on your behalf.
        </Description>

        {error && <ErrorMessage>{error}</ErrorMessage>}

        <ConnectButton onClick={handleConnectTwitter} disabled={isConnecting}>
          {isConnecting ? (
            'Connecting...'
          ) : (
            <>
              <XIcon />
              Connect X Account
            </>
          )}
        </ConnectButton>
      </Container>
    </Background>
  );
}

export default ConnectTwitter;
