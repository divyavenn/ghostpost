import { useSearchParams, useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import styled from 'styled-components';
import { Background } from '../components/Background';
import { getSession } from '../lib/supabase';

const theme = {
  colors: {
    background: '#0f172a',
    text: '#E5E5E5',
    textSecondary: 'rgba(229, 229, 229, 0.6)',
    error: '#ff6b6b',
  },
  fonts: {
    mono: '"Geist Mono", monospace',
  },
};

const Container = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
`;

const Card = styled.div`
  background: ${theme.colors.background};
  padding: 40px;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  max-width: 450px;
  text-align: center;
`;

const ErrorIcon = styled.div`
  font-size: 3rem;
  margin-bottom: 20px;
`;

const Title = styled.h1`
  color: ${theme.colors.error};
  font-family: ${theme.fonts.mono};
  font-size: 1.5rem;
  margin: 0 0 16px 0;
`;

const Message = styled.p`
  color: ${theme.colors.textSecondary};
  font-family: ${theme.fonts.mono};
  font-size: 0.95rem;
  line-height: 1.6;
  margin: 0 0 24px 0;
`;

const ErrorCode = styled.code`
  display: block;
  background: rgba(255, 107, 107, 0.1);
  color: ${theme.colors.error};
  padding: 12px;
  border-radius: 8px;
  font-family: ${theme.fonts.mono};
  font-size: 0.85rem;
  margin-bottom: 24px;
  word-break: break-all;
`;

const Button = styled.button`
  background: #ffffff;
  color: #000000;
  border: none;
  border-radius: 9999px;
  padding: 14px 32px;
  font-family: ${theme.fonts.mono};
  font-size: 1rem;
  font-weight: 500;
  cursor: pointer;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  }
`;

const errorMessages: Record<string, string> = {
  access_denied: 'You cancelled the login or denied access.',
  missing_code: 'Twitter did not return an authorization code.',
  invalid_state: 'The login session expired. Please try again.',
  token_exchange_failed: 'Failed to complete authentication with Twitter.',
  incomplete_tokens: 'Twitter returned an incomplete response.',
  user_info_failed: 'Could not fetch your Twitter profile. Please try again.',
  no_handle: 'Could not determine your Twitter username.',
};

export function LoginError() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [hasSession, setHasSession] = useState<boolean | null>(null);

  const errorCode = searchParams.get('error') || 'unknown';
  const errorDescription = searchParams.get('error_description');

  const friendlyMessage = errorMessages[errorCode] || 'An unexpected error occurred during login.';

  // Check if user still has a Supabase session
  useEffect(() => {
    const checkSession = async () => {
      const { session } = await getSession();
      setHasSession(!!session);
    };
    checkSession();
  }, []);

  const handleTryAgain = () => {
    // If user has Supabase session, go to connect-twitter page
    // Otherwise, go to login page
    if (hasSession) {
      navigate('/connect-twitter');
    } else {
      navigate('/login');
    }
  };

  return (
    <Background>
      <Container>
        <Card>
          <ErrorIcon>:(</ErrorIcon>
          <Title>Login Failed</Title>
          <Message>{friendlyMessage}</Message>
          {errorDescription && (
            <ErrorCode>{errorDescription}</ErrorCode>
          )}
          <ErrorCode>Error: {errorCode}</ErrorCode>
          <Button onClick={handleTryAgain}>
            {hasSession ? 'Connect Twitter' : 'Try Again'}
          </Button>
        </Card>
      </Container>
    </Background>
  );
}

export default LoginError;
