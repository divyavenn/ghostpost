import { useState, useEffect, useRef, type KeyboardEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useRecoilValue, useSetRecoilState } from 'recoil';
import styled, { keyframes } from 'styled-components';
import { usernameState, userInfoState } from '../atoms';
import { api } from '../api/client';
import { Background } from '../components/Background';
import { TabNavigation } from '../components/TabNavigation';

const theme = {
  colors: {
    background: '#0f172a',
    text: '#E5E5E5',
    textSecondary: 'rgba(229, 229, 229, 0.6)',
    accent: '#38bdf8',
  },
  fonts: {
    mono: '"Geist Mono", monospace',
  },
};

const fadeIn = keyframes`
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
`;

const Container = styled.div`
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 40px 20px;
`;

const ChatContainer = styled.div`
  max-width: 600px;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 24px;
`;

const Bubble = styled.div<{ $delay?: number }>`
  animation: ${fadeIn} 0.4s ease forwards;
  animation-delay: ${({ $delay }) => $delay || 0}ms;
  opacity: 0;
`;

const Message = styled.div`
  color: ${theme.colors.text};
  font-family: ${theme.fonts.mono};
  font-size: 1.5rem;
  line-height: 1.6;
  text-align: center;
`;

const SubMessage = styled.div`
  color: ${theme.colors.textSecondary};
  font-family: ${theme.fonts.mono};
  font-size: 1.2rem;
  margin-top: 8px;
  text-align: center;
`;

const Input = styled.input`
  width: 100%;
  background: transparent;
  border: none;
  border-bottom: 2px solid rgba(255, 255, 255, 0.2);
  padding: 10px 0;
  color: ${theme.colors.accent};
  font-family: ${theme.fonts.mono};
  font-size: 1.2rem;
  outline: none;
  margin-top: 16px;

  &:focus {
    border-bottom-color: ${theme.colors.accent};
  }

  &::placeholder {
    color: ${theme.colors.textSecondary};
  }
`;

const TextArea = styled.textarea`
  width: 100%;
  background: transparent;
  border: none;
  border-bottom: 2px solid rgba(255, 255, 255, 0.2);
  padding: 12px 0;
  color: ${theme.colors.text};
  font-family: ${theme.fonts.mono};
  font-size: 1.1rem;
  outline: none;
  margin-top: 16px;
  resize: none;
  min-height: 80px;
  overflow-y: hidden;
  field-sizing: content;

  &:focus {
    border-bottom-color: ${theme.colors.accent};
  }

  &::placeholder {
    color: ${theme.colors.textSecondary};
  }
`;

const SocialGrid = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 16px;
`;

const SocialOption = styled.button<{ $selected: boolean }>`
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  background: ${({ $selected }) => $selected ? 'rgba(56, 189, 248, 0.15)' : 'rgba(255, 255, 255, 0.05)'};
  border: 1px solid ${({ $selected }) => $selected ? theme.colors.accent : 'rgba(255, 255, 255, 0.1)'};
  border-radius: 9999px;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    background: ${({ $selected }) => $selected ? 'rgba(56, 189, 248, 0.2)' : 'rgba(255, 255, 255, 0.08)'};
  }

  svg {
    width: 20px;
    height: 20px;
    color: ${({ $selected }) => $selected ? theme.colors.accent : theme.colors.textSecondary};
  }

  span {
    font-family: ${theme.fonts.mono};
    font-size: 0.9rem;
    color: ${({ $selected }) => $selected ? theme.colors.text : theme.colors.textSecondary};
  }
`;

const ContinueHint = styled.div`
  color: ${theme.colors.textSecondary};
  font-family: ${theme.fonts.mono};
  font-size: 0.75rem;
  margin-top: 16px;
  opacity: 0.7;
`;

const TabExplanationBox = styled.div`
  margin-top: 24px;
  padding: 20px;
  animation: ${fadeIn} 0.3s ease forwards;

  h4 {
    color: ${theme.colors.text};
    font-family: ${theme.fonts.mono};
    font-size: 1.3rem;
    margin: 0 0 8px 0;
    font-weight: 500;
  }

  p {
    color: ${theme.colors.textSecondary};
    font-family: ${theme.fonts.mono};
    font-size: 1.2rem;
    margin: 0;
    line-height: 1.6;
    white-space: pre-line;
  }
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
  margin-top: 24px;
  transition: all 0.2s ease;

  &:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
`;

const ErrorText = styled.div`
  color: #ff6b6b;
  font-family: ${theme.fonts.mono};
  font-size: 0.85rem;
  margin-top: 8px;
`;

const Spinner = styled.div`
  width: 24px;
  height: 24px;
  border: 2px solid rgba(255, 255, 255, 0.1);
  border-top-color: ${theme.colors.accent};
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 16px 0;

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
`;

const ProgressContainer = styled.div`
  position: fixed;
  top: 40px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 16px;
  z-index: 100;
`;

const ProgressBar = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
`;

const ProgressDot = styled.div<{ $active: boolean; $completed: boolean }>`
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: ${({ $active, $completed }) =>
    $active ? theme.colors.accent :
    $completed ? 'rgba(56, 189, 248, 0.5)' :
    'rgba(255, 255, 255, 0.2)'};
  transition: all 0.3s ease;
`;

const NavButton = styled.button<{ $visible: boolean }>`
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 50%;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  opacity: ${({ $visible }) => $visible ? 1 : 0};
  pointer-events: ${({ $visible }) => $visible ? 'auto' : 'none'};
  transition: all 0.2s ease;

  &:hover {
    background: rgba(255, 255, 255, 0.1);
    border-color: ${theme.colors.accent};
  }

  svg {
    width: 16px;
    height: 16px;
    color: ${theme.colors.textSecondary};
  }
`;

const StepLabel = styled.div`
  color: ${theme.colors.textSecondary};
  font-family: ${theme.fonts.mono};
  font-size: 0.75rem;
  margin-left: 8px;
`;

const AccountTagsContainer = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
`;

const AccountTag = styled.div<{ $validating?: boolean; $invalid?: boolean }>`
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: ${({ $invalid }) => $invalid ? 'rgba(255, 107, 107, 0.1)' : 'rgba(255, 255, 255, 0.08)'};
  border: 1px solid ${({ $invalid, $validating }) =>
    $invalid ? 'rgba(255, 107, 107, 0.3)' :
    $validating ? theme.colors.accent :
    'rgba(255, 255, 255, 0.15)'};
  border-radius: 9999px;
  font-family: ${theme.fonts.mono};
  font-size: 0.9rem;
  color: ${({ $invalid, $validating }) =>
    $invalid ? '#ff6b6b' :
    $validating ? theme.colors.accent :
    theme.colors.text};
  animation: ${({ $validating }) => $validating ? 'pulse 1.5s ease-in-out infinite' : 'none'};

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }
`;

const RemoveTagButton = styled.button`
  background: transparent;
  border: none;
  color: ${theme.colors.textSecondary};
  cursor: pointer;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  font-size: 14px;
  transition: color 0.2s ease;

  &:hover {
    color: #ff6b6b;
  }
`;

const ValidationSpinner = styled.div`
  width: 12px;
  height: 12px;
  border: 2px solid rgba(56, 189, 248, 0.3);
  border-top-color: ${theme.colors.accent};
  border-radius: 50%;
  animation: spin 0.8s linear infinite;

  @keyframes spin {
    to { transform: rotate(360deg); }
  }
`;

type Social = 'twitter' | 'reddit' | 'linkedin' | 'substack';

type Step = 'welcome' | 'name' | 'email' | 'socials' | 'intent' | 'accounts' | 'tabs' | 'loading' | 'complete';

export function Onboarding() {
  const navigate = useNavigate();
  const username = useRecoilValue(usernameState);
  const setUserInfo = useSetRecoilState(userInfoState);

  const [step, setStep] = useState<Step>('welcome');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [selectedSocials, setSelectedSocials] = useState<Social[]>(['twitter']);
  const [intent, setIntent] = useState('');
  const [accounts, setAccounts] = useState<{ [handle: string]: boolean | null }>({});
  const [newAccountInput, setNewAccountInput] = useState('');
  const [validatingHandle, setValidatingHandle] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [explainTabIndex, setExplainTabIndex] = useState(0); // 0=discovered, 1=posted, 2=posts, 3=comments, 4=done
  const [maxStepReached, setMaxStepReached] = useState(0); // Track furthest step for forward navigation

  const inputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const accountInputRef = useRef<HTMLInputElement>(null);

  // Steps that show in progress bar (excluding welcome, loading, complete)
  const navigableSteps: Step[] = ['name', 'email', 'socials', 'intent', 'accounts', 'tabs'];
  const currentStepIndex = navigableSteps.indexOf(step);
  const showProgressBar = navigableSteps.includes(step);
  const canGoForward = currentStepIndex < maxStepReached;

  const goBack = () => {
    if (currentStepIndex > 0) {
      setError(null);
      setStep(navigableSteps[currentStepIndex - 1]);
    }
  };

  const goForward = () => {
    if (canGoForward) {
      setError(null);
      setStep(navigableSteps[currentStepIndex + 1]);
    }
  };

  // Track the furthest step reached for forward navigation
  useEffect(() => {
    if (currentStepIndex > maxStepReached) {
      setMaxStepReached(currentStepIndex);
    }
  }, [currentStepIndex, maxStepReached]);

  // Auto-focus inputs when step changes
  useEffect(() => {
    setTimeout(() => {
      if (step === 'name' || step === 'email') {
        inputRef.current?.focus();
      } else if (step === 'intent') {
        textareaRef.current?.focus();
      } else if (step === 'accounts') {
        accountInputRef.current?.focus();
      }
    }, 500);
  }, [step]);

  // Handle welcome step auto-advance
  useEffect(() => {
    if (step === 'welcome') {
      const timer = setTimeout(() => setStep('name'), 2000);
      return () => clearTimeout(timer);
    }
  }, [step]);

  const toggleSocial = (social: Social) => {
    setSelectedSocials(prev =>
      prev.includes(social)
        ? prev.filter(s => s !== social)
        : [...prev, social]
    );
  };

  const handleKeyDown = (e: KeyboardEvent, nextStep: Step, validate?: () => boolean) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      e.stopPropagation();
      if (validate && !validate()) return;
      setError(null);
      setStep(nextStep);
    }
  };

  const advanceStep = (nextStep: Step, validate?: () => boolean) => {
    if (validate && !validate()) return;
    setError(null);
    setStep(nextStep);
  };

  // Auto-resize textarea to fit content (fallback for browsers without field-sizing)
  const autoResize = (textarea: HTMLTextAreaElement) => {
    textarea.style.height = 'auto';
    textarea.style.height = `${textarea.scrollHeight}px`;
  };

  const handleAddAccount = async () => {
    if (!newAccountInput.trim()) return;

    if (!username) {
      setError('Please log in first before adding accounts');
      return;
    }

    const cleanHandle = newAccountInput.replace('@', '').trim();

    // Check if already exists
    if (cleanHandle in accounts) {
      setNewAccountInput('');
      return;
    }

    // Add with null (validating), then validate
    setAccounts(prev => ({ ...prev, [cleanHandle]: null }));
    setValidatingHandle(cleanHandle);
    setNewAccountInput('');

    try {
      const validation = await api.validateTwitterHandle(username, cleanHandle);

      if (validation.valid) {
        setAccounts(prev => ({ ...prev, [cleanHandle]: true }));
      } else {
        setAccounts(prev => ({ ...prev, [cleanHandle]: false }));
        const errorMsg = validation.error || `@${cleanHandle} is invalid or doesn't exist`;
        setError(errorMsg);
        setTimeout(() => setError(null), 5000);
      }
    } catch (e) {
      console.error('Failed to validate handle:', e);
      setAccounts(prev => ({ ...prev, [cleanHandle]: false }));
      setError(`Failed to validate @${cleanHandle}: ${e instanceof Error ? e.message : 'Network error'}`);
      setTimeout(() => setError(null), 5000);
    } finally {
      setValidatingHandle(null);
    }
  };

  const handleRemoveAccount = (handle: string) => {
    setAccounts(prev => {
      const newAccounts = { ...prev };
      delete newAccounts[handle];
      return newAccounts;
    });
  };

  const validateName = () => {
    if (!name.trim()) {
      setError('Please enter your name');
      return false;
    }
    return true;
  };

  const validateEmail = () => {
    if (!email.trim() || !email.includes('@')) {
      setError('Please enter a valid email');
      return false;
    }
    return true;
  };

  const validateIntent = () => {
    if (!intent.trim()) {
      setError('Please describe your intent');
      return false;
    }
    return true;
  };

  const handleSubmit = async () => {
    if (!username) {
      setError('No username found. Please log in again.');
      return;
    }

    setStep('loading');

    try {
      // Update user email
      console.log('Updating email...');
      await api.updateUserEmail(username, email);

      // Update survey data (name, interested socials)
      console.log('Updating survey data...');
      await api.updateSurveyData(username, {
        name: name.trim(),
        interested_socials: selectedSocials,
      });

      // Update intent (this also regenerates queries in background)
      console.log('Updating intent and generating queries...');
      await api.updateIntent(username, intent.trim());

      // Add valid accounts to follow
      const validAccounts = Object.entries(accounts)
        .filter(([, isValid]) => isValid === true)
        .map(([handle]) => handle);

      console.log('Adding accounts:', validAccounts);
      for (const account of validAccounts) {
        try {
          await api.addAccount(username, account, false);
        } catch (e) {
          console.warn(`Failed to add account ${account}:`, e);
        }
      }

      // Get user info and update state
      console.log('Fetching updated user info...');
      const userInfo = await api.getUserInfo(username);
      setUserInfo(userInfo);
      console.log('User info updated:', userInfo);

      // Start all background jobs
      console.log('Starting all background jobs...');
      try {
        await api.runBackgroundJobs(username);
      } catch (e) {
        console.warn('Failed to start background jobs:', e);
      }

      setStep('complete');
    } catch (e) {
      console.error('Onboarding error:', e);
      setError(e instanceof Error ? e.message : 'Something went wrong');
      setStep('tabs'); // Go back to allow retry
    }
  };

  const renderStep = () => {
    switch (step) {
      case 'welcome':
        return (
          <Bubble>
            <Message>Welcome to GhostPoster</Message>
            <SubMessage>Let's get you set up...</SubMessage>
          </Bubble>
        );

      case 'name':
        return (
          <Bubble>
            <Message>What's your name?</Message>
            <Input
              ref={inputRef}
              type="text"
              placeholder="Type your name..."
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => handleKeyDown(e, 'email', validateName)}
            />
            {error && <ErrorText>{error}</ErrorText>}
            <ContinueHint>Press Enter to continue</ContinueHint>
          </Bubble>
        );

      case 'email':
        return (
          <>
            <Bubble $delay={0}>
              <Message>Nice to meet you, {name}!</Message>
            </Bubble>
            <Bubble $delay={300}>
              <Message>What's your email?</Message>
              <SubMessage>Authentication and important notifications only</SubMessage>
              <Input
                ref={inputRef}
                type="email"
                placeholder="your@email.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                onKeyDown={(e) => handleKeyDown(e, 'socials', validateEmail)}
              />
              {error && <ErrorText>{error}</ErrorText>}
              <ContinueHint>Press Enter to continue</ContinueHint>
            </Bubble>
          </>
        );

      case 'socials':
        return (
          <Bubble>
            <Message>Which social platforms are you interested in integrating?</Message>
            <SubMessage>We support Twitter for now, but more are coming up!</SubMessage>
            <SocialGrid>
              <SocialOption
                $selected={selectedSocials.includes('twitter')}
                onClick={() => toggleSocial('twitter')}
              >
                <svg viewBox="0 0 24 24" fill="currentColor">
                  <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
                </svg>
                <span>Twitter</span>
              </SocialOption>
              <SocialOption
                $selected={selectedSocials.includes('reddit')}
                onClick={() => toggleSocial('reddit')}
              >
                <svg viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0zm5.01 4.744c.688 0 1.25.561 1.25 1.249a1.25 1.25 0 0 1-2.498.056l-2.597-.547-.8 3.747c1.824.07 3.48.632 4.674 1.488.308-.309.73-.491 1.207-.491.968 0 1.754.786 1.754 1.754 0 .716-.435 1.333-1.01 1.614a3.111 3.111 0 0 1 .042.52c0 2.694-3.13 4.87-7.004 4.87-3.874 0-7.004-2.176-7.004-4.87 0-.183.015-.366.043-.534A1.748 1.748 0 0 1 4.028 12c0-.968.786-1.754 1.754-1.754.463 0 .898.196 1.207.49 1.207-.883 2.878-1.43 4.744-1.487l.885-4.182a.342.342 0 0 1 .14-.197.35.35 0 0 1 .238-.042l2.906.617a1.214 1.214 0 0 1 1.108-.701zM9.25 12C8.561 12 8 12.562 8 13.25c0 .687.561 1.248 1.25 1.248.687 0 1.248-.561 1.248-1.249 0-.688-.561-1.249-1.249-1.249zm5.5 0c-.687 0-1.248.561-1.248 1.25 0 .687.561 1.248 1.249 1.248.688 0 1.249-.561 1.249-1.249 0-.687-.562-1.249-1.25-1.249zm-5.466 3.99a.327.327 0 0 0-.231.094.33.33 0 0 0 0 .463c.842.842 2.484.913 2.961.913.477 0 2.105-.056 2.961-.913a.361.361 0 0 0 .029-.463.33.33 0 0 0-.464 0c-.547.533-1.684.73-2.512.73-.828 0-1.979-.196-2.512-.73a.326.326 0 0 0-.232-.095z" />
                </svg>
                <span>Reddit</span>
              </SocialOption>
              <SocialOption
                $selected={selectedSocials.includes('linkedin')}
                onClick={() => toggleSocial('linkedin')}
              >
                <svg viewBox="0 0 24 24" fill="currentColor">
                  <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
                </svg>
                <span>LinkedIn</span>
              </SocialOption>
              <SocialOption
                $selected={selectedSocials.includes('substack')}
                onClick={() => toggleSocial('substack')}
              >
                <svg viewBox="0 0 24 24" fill="currentColor">
                  <path d="M22.539 8.242H1.46V5.406h21.08v2.836zM1.46 10.812V24L12 18.11 22.54 24V10.812H1.46zM22.54 0H1.46v2.836h21.08V0z" />
                </svg>
                <span>Substack</span>
              </SocialOption>
            </SocialGrid>
            <ContinueHint
              style={{ cursor: 'pointer', textDecoration: 'underline' }}
              onClick={() => advanceStep('intent')}
            >
              Press Enter or click here to continue
            </ContinueHint>
          </Bubble>
        );

      case 'intent':
        return (
          <Bubble>
            <Message>Who are you, what's your area of expertise, and why are you trying to grow?
            </Message>
            <SubMessage>Be as specific as you can, our web agents use this to filter for relevant posts. You can update this any time in settings.</SubMessage>
            <TextArea
              ref={textareaRef}
              placeholder="e.g., I'm a founder building automation software for copywriting agencies/ I'm an author promoting my health and wellness book about the importance of sleep"
              value={intent}
              onChange={(e) => {
                setIntent(e.target.value);
                autoResize(e.target);
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  e.stopPropagation();
                  advanceStep('accounts', validateIntent);
                }
              }}
            />
            {error && <ErrorText>{error}</ErrorText>}
            <ContinueHint>Press Enter to continue (Shift+Enter for new line)</ContinueHint>
          </Bubble>
        );

      case 'accounts':
        return (
          <Bubble>
            <Message>Any specific X accounts you want to engage with?</Message>
            <SubMessage>"(You can always add or remove these in settings.)"</SubMessage>
            <Input
              ref={accountInputRef}
              type="text"
              placeholder="@handle"
              value={newAccountInput}
              onChange={(e) => setNewAccountInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  e.stopPropagation();
                  if (newAccountInput.trim()) {
                    handleAddAccount();
                  } else {
                    advanceStep('tabs');
                  }
                }
              }}
            />
            {Object.keys(accounts).length > 0 && (
              <AccountTagsContainer>
                {Object.entries(accounts).map(([handle, isValid]) => {
                  const isValidating = validatingHandle === handle;
                  const isInvalid = isValid === false;

                  return (
                    <AccountTag
                      key={handle}
                      $validating={isValidating}
                      $invalid={isInvalid}
                    >
                      {isValidating && <ValidationSpinner />}
                      @{handle}
                      {isInvalid && <span title="Invalid account">⚠</span>}
                      <RemoveTagButton onClick={() => handleRemoveAccount(handle)}>
                        ×
                      </RemoveTagButton>
                    </AccountTag>
                  );
                })}
              </AccountTagsContainer>
            )}
            {error && <ErrorText>{error}</ErrorText>}
            <ContinueHint>
              {Object.keys(accounts).length > 0
                ? 'Add more accounts or press Enter with empty input to continue'
                : 'Type a handle and press Enter, or press Enter to skip'}
            </ContinueHint>
          </Bubble>
        );

      case 'tabs': {
        const tabNames: Array<'discovered' | 'posted' | 'posts' | 'comments'> = ['discovered', 'posted', 'posts', 'comments'];
        const tabExplanations: Record<string, string> = {
          discovered: 'Every day, we find the most high-traction posts on social media relevant to your brand. Engaging with these is the best way to organically get the word out and improve your search rankings. \n\nThey\'re all in one place in your Discovered Tab.',
          posted: 'We keep track of all your posts and learn from what\'s performing well to make our web agents smarter. \n \n Your top posts automatically get reposted to other platforms',
          posts: 'Standalone drafts from your CLI and extension land here first. Review the text, optional image, and optional link, then approve to send to the desktop post_all task.',
          comments: 'Replying to comments is vital for keeping engagement high.\n\n With Ghostpost you can build relationships with your audience with a single click.'
        };
        const activeTabName = explainTabIndex < tabNames.length ? tabNames[explainTabIndex] : 'discovered';

        return (
          <Bubble>
            <Message>Here's how GhostPoster works:</Message>
            <div style={{ marginTop: '24px' }}>
              <TabNavigation
                activeTab={activeTabName}
                onTabChange={(tab) => setExplainTabIndex(tabNames.indexOf(tab))}
                discoveredCount={0}
                postedCount={0}
                postsCount={0}
                commentsCount={0}
              />
            </div>
            {explainTabIndex < tabNames.length && (
              <TabExplanationBox key={explainTabIndex}>
                <p>{tabExplanations[activeTabName]}</p>
              </TabExplanationBox>
            )}
            <ContinueHint>
              {explainTabIndex < tabNames.length - 1
                ? 'Press Enter to see next tab'
                : 'Press Enter to continue'}
            </ContinueHint>
          </Bubble>
        );
      }

      case 'loading':
        return (
          <Bubble>
            <Message>Setting things up...</Message>
            <Spinner />
            <SubMessage>This will just take a moment.</SubMessage>
          </Bubble>
        );

      case 'complete':
        return (
          <Bubble>
            <Message>Our web agents are getting to work!</Message>
            <SubMessage>
              They'll scan socials automatically every 24 hours. Check back later for curated engagement opportunities.
            </SubMessage>
            <Button onClick={() => navigate('/')}>
              Go to Dashboard
            </Button>
          </Bubble>
        );
    }
  };

  // Global keydown for socials and tabs steps
  useEffect(() => {
    const handleGlobalKeyDown = (e: globalThis.KeyboardEvent) => {
      if (e.key === 'Enter') {
        if (step === 'socials') {
          advanceStep('intent');
        } else if (step === 'tabs') {
          e.preventDefault();
          if (explainTabIndex < 3) {
            // Advance through tabs: 0 → 1 → 2 → 3
            setExplainTabIndex(prev => prev + 1);
          } else if (explainTabIndex === 3) {
            // After final tab explanation, auto-submit
            handleSubmit();
          }
        }
      }
    };

    window.addEventListener('keydown', handleGlobalKeyDown);
    return () => window.removeEventListener('keydown', handleGlobalKeyDown);
  }, [step, explainTabIndex]);

  return (
    <Background>
      {showProgressBar && (
        <ProgressContainer>
          <NavButton $visible={currentStepIndex > 0} onClick={goBack}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M15 18l-6-6 6-6" />
            </svg>
          </NavButton>
          <ProgressBar>
            {navigableSteps.map((s, i) => (
              <ProgressDot
                key={s}
                $active={i === currentStepIndex}
                $completed={i <= maxStepReached && i !== currentStepIndex}
              />
            ))}
          </ProgressBar>
          <StepLabel>{currentStepIndex + 1} / {navigableSteps.length}</StepLabel>
          <NavButton $visible={canGoForward} onClick={goForward}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M9 18l6-6-6-6" />
            </svg>
          </NavButton>
        </ProgressContainer>
      )}
      <Container>
        <ChatContainer>
          {renderStep()}
        </ChatContainer>
      </Container>
    </Background>
  );
}

export default Onboarding;
