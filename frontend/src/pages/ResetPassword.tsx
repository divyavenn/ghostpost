import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import styled from 'styled-components';
import { type AuthChangeEvent, type Session } from '@supabase/supabase-js';
import { supabase } from '../lib/supabase';
import { Background } from '../components/Background';

const theme = {
  colors: {
    background: '#0f172a',
    text: '#E5E5E5',
    textSecondary: 'rgba(229, 229, 229, 0.6)',
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

const Modal = styled.div`
  background: ${theme.colors.background};
  padding: 32px;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  min-width: 320px;
  max-width: 400px;
`;

const Title = styled.h2`
  color: ${theme.colors.text};
  font-family: ${theme.fonts.mono};
  font-size: 1.3rem;
  margin: 0 0 20px 0;
  font-weight: 500;
  text-align: center;
`;

const Input = styled.input`
  width: 100%;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  padding: 14px 16px;
  color: ${theme.colors.text};
  font-family: ${theme.fonts.mono};
  font-size: 1rem;
  outline: none;
  box-sizing: border-box;

  &:focus {
    border-color: rgba(255, 255, 255, 0.5);
  }

  &::placeholder {
    color: ${theme.colors.textSecondary};
  }
`;

const Button = styled.button`
  width: 100%;
  background: #ffffff;
  color: #000000;
  border: none;
  border-radius: 9999px;
  padding: 14px 24px;
  font-family: ${theme.fonts.mono};
  font-size: 1rem;
  font-weight: 500;
  cursor: pointer;
  margin-top: 8px;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
    transform: none;
  }
`;

const Message = styled.div<{ $isError?: boolean }>`
  color: ${({ $isError }) => ($isError ? '#ff6b6b' : '#6bff6b')};
  font-size: 0.85rem;
  font-family: ${theme.fonts.mono};
  padding: 10px;
  background: ${({ $isError }) =>
    $isError ? 'rgba(255, 107, 107, 0.1)' : 'rgba(107, 255, 107, 0.1)'};
  border-radius: 6px;
  text-align: center;
  margin-top: 12px;
`;

const Spinner = styled.div`
  width: 30px;
  height: 30px;
  border: 3px solid rgba(255, 255, 255, 0.1);
  border-top-color: #38bdf8;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 20px auto;

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
`;

export function ResetPassword() {
  const navigate = useNavigate();
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [sessionReady, setSessionReady] = useState(false);

  useEffect(() => {
    // Listen for auth state changes - Supabase will process the URL token
    const { data: { subscription } } = supabase.auth.onAuthStateChange(async (event: AuthChangeEvent, session: Session | null) => {
      console.log('Auth event:', event, session);

      if (event === 'PASSWORD_RECOVERY') {
        // User clicked the reset link and Supabase processed it
        setSessionReady(true);
        setIsLoading(false);
      } else if (event === 'SIGNED_IN' && session) {
        // Session established from recovery token
        setSessionReady(true);
        setIsLoading(false);
      }
    });

    // Also check current session after a short delay
    const checkSession = async () => {
      // Give Supabase time to process the URL hash
      await new Promise(resolve => setTimeout(resolve, 500));

      const { data: { session } } = await supabase.auth.getSession();
      if (session) {
        setSessionReady(true);
      } else {
        setError('Invalid or expired reset link. Please request a new one.');
      }
      setIsLoading(false);
    };

    checkSession();

    return () => {
      subscription.unsubscribe();
    };
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (password.length < 6) {
      setError('Password must be at least 6 characters');
      return;
    }

    setIsSubmitting(true);

    try {
      const { error } = await supabase.auth.updateUser({ password });
      if (error) {
        setError(error.message);
      } else {
        setSuccess(true);
        setTimeout(() => navigate('/login'), 2000);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <Background>
        <Container>
          <Modal>
            <Title>Processing...</Title>
            <Spinner />
          </Modal>
        </Container>
      </Background>
    );
  }

  return (
    <Background>
      <Container>
        <Modal>
          <Title>Set New Password</Title>

          {success ? (
            <Message>Password updated! Redirecting to login...</Message>
          ) : !sessionReady ? (
            <>
              <Message $isError>{error || 'Session not found'}</Message>
              <Button onClick={() => navigate('/login')} style={{ marginTop: '16px' }}>
                Back to Login
              </Button>
            </>
          ) : (
            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <Input
                type="password"
                placeholder="New password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
              />
              <Input
                type="password"
                placeholder="Confirm password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                minLength={6}
              />

              {error && <Message $isError>{error}</Message>}

              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting ? 'Updating...' : 'Update Password'}
              </Button>
            </form>
          )}
        </Modal>
      </Container>
    </Background>
  );
}

export default ResetPassword;
