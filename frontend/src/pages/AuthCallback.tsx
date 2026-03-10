import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSetRecoilState } from 'recoil';
import { supabase } from '../lib/supabase';
import { supabaseSessionState, supabaseUserState, twitterConnectedState } from '../atoms';
import { api } from '../api/client';
import styled from 'styled-components';

const Container = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: #0f172a;
  color: white;
  font-family: 'Geist Mono', monospace;
`;

const Spinner = styled.div`
  width: 40px;
  height: 40px;
  border: 3px solid rgba(255, 255, 255, 0.1);
  border-top-color: #38bdf8;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 20px;

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
`;

const Message = styled.div`
  font-size: 1.1rem;
  color: rgba(255, 255, 255, 0.8);
`;

const ErrorMessage = styled.div`
  color: #ff6b6b;
  margin-top: 20px;
  text-align: center;
  max-width: 400px;
`;

export function AuthCallback() {
  const navigate = useNavigate();
  const setSession = useSetRecoilState(supabaseSessionState);
  const setUser = useSetRecoilState(supabaseUserState);
  const setTwitterConnected = useSetRecoilState(twitterConnectedState);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handleCallback = async () => {
      try {
        // Get session from URL hash (Supabase puts tokens in the hash)
        const { data: { session }, error: sessionError } = await supabase.auth.getSession();

        if (sessionError) {
          throw sessionError;
        }

        if (!session) {
          throw new Error('No session found. Please try logging in again.');
        }

        // Store in Recoil state
        setSession(session);
        setUser(session.user);

        // Sync user with backend (creates user if not exists)
        try {
          const syncResult = await api.syncSupabaseUser(session.access_token);

          // Check if user already has a linked handle
          if (syncResult.twitter_handle) {
            // Has linked handle - store username and go to main app
            localStorage.setItem('username', syncResult.twitter_handle);
            setTwitterConnected(true);
            navigate('/');
          } else {
            // No linked handle/device yet - go to daemon setup flow
            setTwitterConnected(false);
            navigate('/install-daemon');
          }
        } catch (syncError) {
          console.error('Failed to sync user with backend:', syncError);
          // Still allow user to proceed to daemon setup
          setTwitterConnected(false);
          navigate('/install-daemon');
        }
      } catch (err) {
        console.error('Auth callback error:', err);
        setError(err instanceof Error ? err.message : 'Authentication failed');
      }
    };

    handleCallback();
  }, [navigate, setSession, setUser, setTwitterConnected]);

  if (error) {
    return (
      <Container>
        <ErrorMessage>
          {error}
          <br />
          <br />
          <a href="/login" style={{ color: '#38bdf8' }}>
            Return to login
          </a>
        </ErrorMessage>
      </Container>
    );
  }

  return (
    <Container>
      <Spinner />
      <Message>Completing sign in...</Message>
    </Container>
  );
}

export default AuthCallback;
