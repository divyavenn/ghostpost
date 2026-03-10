import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import styled from 'styled-components';
import { Background } from '../components/Background';
import { TextTree } from '../components/TextTree';
import { signInWithEmail, signUpWithEmail, resetPassword } from '../lib/supabase';
import { api } from '../api/client';

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
  background: #ffffff;
  color: #000000;
  border: none;
  border-radius: 9999px;
  padding: 12px 32px;
  font-family: ${theme.fonts.mono};
  font-size: 1rem;
  font-weight: 500;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  }
`;

const Overlay = styled.div`
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
`;

const Modal = styled.div`
  background: ${theme.colors.background};
  padding: 32px;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  min-width: 320px;
  max-width: 400px;
  position: relative;
`;

const CloseButton = styled.button`
  position: absolute;
  top: 12px;
  right: 12px;
  background: none;
  border: none;
  color: ${theme.colors.textSecondary};
  font-size: 1.5rem;
  cursor: pointer;
  line-height: 1;
  padding: 4px 8px;

  &:hover {
    color: ${theme.colors.text};
  }
`;

const FormTitle = styled.h2`
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
  transition: border-color 0.2s ease;
  box-sizing: border-box;

  &:focus {
    border-color: rgba(255, 255, 255, 0.5);
  }

  &::placeholder {
    color: ${theme.colors.textSecondary};
  }
`;

const SubmitButton = styled.button`
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
  transition: transform 0.2s ease, box-shadow 0.2s ease;
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

const ToggleText = styled.p`
  color: ${theme.colors.textSecondary};
  font-family: ${theme.fonts.mono};
  font-size: 0.85rem;
  margin: 16px 0 0 0;
  text-align: center;

  button {
    background: none;
    border: none;
    color: ${theme.colors.link};
    cursor: pointer;
    text-decoration: underline;
    font-family: inherit;
    font-size: inherit;

    &:hover {
      color: ${theme.colors.linkHover};
    }
  }
`;

const ForgotPasswordButton = styled.button`
  background: none;
  border: none;
  color: ${theme.colors.textSecondary};
  font-family: ${theme.fonts.mono};
  font-size: 0.8rem;
  cursor: pointer;
  text-align: right;
  padding: 0;
  margin-top: -4px;

  &:hover {
    color: ${theme.colors.text};
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

const ErrorMessage = styled.div`
  color: #ff6b6b;
  font-size: 0.85rem;
  font-family: ${theme.fonts.mono};
  padding: 10px;
  background: rgba(255, 107, 107, 0.1);
  border-radius: 6px;
  text-align: center;
`;

const SuccessMessage = styled.div`
  color: #6bff6b;
  font-size: 0.85rem;
  font-family: ${theme.fonts.mono};
  padding: 10px;
  background: rgba(107, 255, 107, 0.1);
  border-radius: 6px;
  text-align: center;
`;

// --- Main Component ---
type AuthMode = 'signin' | 'signup' | 'forgot';

export function Login() {
  const navigate = useNavigate();
  const [showModal, setShowModal] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [mode, setMode] = useState<AuthMode>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setIsLoading(true);

    try {
      if (mode === 'forgot') {
        const { error } = await resetPassword(email);
        if (error) {
          setError(error.message);
        } else {
          setSuccess('Check your email for a password reset link!');
        }
      } else if (mode === 'signup') {
        const { data, error } = await signUpWithEmail(email, password);
        if (error) {
          setError(error.message);
        } else if (data.user) {
          if (data.user.identities?.length === 0) {
            setError('An account with this email already exists.');
          } else {
            setSuccess('Check your email to confirm your account!');
          }
        }
      } else {
        const { data, error } = await signInWithEmail(email, password);
        if (error) {
          setError(error.message);
        } else if (data.session) {
          // Sync with backend and route into daemon setup if needed
          try {
            const syncResult = await api.syncSupabaseUser(data.session.access_token);
            if (syncResult.twitter_handle) {
              // Existing linked handle - go straight to home
              localStorage.setItem('username', syncResult.twitter_handle);
              navigate('/');
            } else {
              // Need daemon setup
              navigate('/install-daemon');
            }
          } catch {
            // If sync fails, continue into daemon setup flow
            navigate('/install-daemon');
          }
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setIsLoading(false);
    }
  };

  const openModal = () => {
    setShowModal(true);
    setError(null);
    setSuccess(null);
  };

  const closeModal = () => {
    setShowModal(false);
    setError(null);
    setSuccess(null);
    setMode('signin');
  };

  const switchMode = (newMode: AuthMode) => {
    setMode(newMode);
    setError(null);
    setSuccess(null);
  };

  const getTitle = () => {
    if (mode === 'forgot') return 'Reset Password';
    if (mode === 'signup') return 'Create Account';
    return 'Sign In';
  };

  return (
    <Background>
      <LoginButton onClick={openModal}>Login</LoginButton>

      {showModal && (
        <Overlay onClick={closeModal}>
          <Modal onClick={(e) => e.stopPropagation()}>
            <CloseButton onClick={closeModal}>&times;</CloseButton>
            <FormTitle>{getTitle()}</FormTitle>

            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <Input
                type="email"
                placeholder="Email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
              {mode !== 'forgot' && (
                <Input
                  type="password"
                  placeholder="Password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={6}
                />
              )}

              {mode === 'signin' && (
                <ForgotPasswordButton type="button" onClick={() => switchMode('forgot')}>
                  Forgot password?
                </ForgotPasswordButton>
              )}

              {error && <ErrorMessage>{error}</ErrorMessage>}
              {success && <SuccessMessage>{success}</SuccessMessage>}

              <SubmitButton type="submit" disabled={isLoading}>
                {mode === 'forgot' ? 'Send Reset Link' : mode === 'signup' ? 'Sign Up' : 'Sign In'}
              </SubmitButton>
            </form>

            <ToggleText>
              {mode === 'forgot' ? (
                <>
                  Remember your password?{' '}
                  <button onClick={() => switchMode('signin')}>Sign In</button>
                </>
              ) : mode === 'signup' ? (
                <>
                  Already have an account?{' '}
                  <button onClick={() => switchMode('signin')}>Sign In</button>
                </>
              ) : (
                <>
                  Don't have an account?{' '}
                  <button onClick={() => switchMode('signup')}>Sign Up</button>
                </>
              )}
            </ToggleText>
          </Modal>
        </Overlay>
      )}

      <TextContainer>
        <TextTree />
      </TextContainer>

      <ContactText>
        questions? email <a href="mailto:divya@aibread.com">divya@aibread.com</a>
      </ContactText>
    </Background>
  );
}

export default Login;
