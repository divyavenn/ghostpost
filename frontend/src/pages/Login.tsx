import React, { useState, useEffect, useRef } from 'react';
import styled, { keyframes, css, createGlobalStyle, ThemeProvider } from 'styled-components';
import { motion, useInView } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { useSetRecoilState } from 'recoil';
import { usernameState } from '../atoms';
import { LoginLoading } from '../components/LoginLoading';

// --- Theme & Global Styles ---

const theme = {
  colors: {
    background: '#050505', // Rich black
    textPrimary: '#E5E5E5', // Off-white
    textSecondary: 'rgba(229, 229, 229, 0.6)', // Faded off-white
    accent: 'rgba(255, 255, 255, 0.15)', // Subtle grey
    accentSecondary: 'rgba(255, 255, 255, 0.08)', // Very subtle grey
    surface: 'rgba(20, 20, 20, 0.4)',
    surfaceHover: 'rgba(30, 30, 30, 0.6)',
    border: 'rgba(255, 255, 255, 0.08)',
    glow: '0 0 20px rgba(255, 255, 255, 0.05)',
    textInvert: '#050505',
    accentFill: '#E5E5E5',
  },
  fonts: {
    header: '"Fraunces", serif',
    body: '"Inter", sans-serif',
    code: '"Space Mono", monospace',
  },
};

const GlobalStyle = createGlobalStyle`
  body {
    margin: 0;
    padding: 0;
    background-color: ${theme.colors.background};
    color: ${theme.colors.textPrimary};
    font-family: ${theme.fonts.body};
    overflow-x: hidden;
    cursor: none; /* Hide default cursor */
  }

  * {
    box-sizing: border-box;
  }

  ::selection {
    background: ${theme.colors.textPrimary};
    color: ${theme.colors.background};
  }
  
  a, button, input, [role="button"] {
    cursor: none; /* Ensure custom cursor is used everywhere */
  }
`;

// --- Animations ---

const cursorBlink = keyframes`
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
`;

const logScroll = keyframes`
  0% { transform: translateY(0); }
  100% { transform: translateY(-100%); }
`;

// --- Styled Components ---

const PageContainer = styled.div`
  min-height: 100vh;
  background: ${theme.colors.background};
  position: relative;
  overflow: hidden;
  
  /* Film Grain */
  &::before {
    content: "";
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
    z-index: 9998;
    opacity: 0.05;
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E");
  }
`;

const CustomCursor = styled.div`
  position: fixed;
  top: 0;
  left: 0;
  width: 20px;
  height: 20px;
  border: 1px solid ${theme.colors.textPrimary};
  border-radius: 50%;
  pointer-events: none;
  z-index: 9999;
  transform: translate(-50%, -50%);
  transition: width 0.2s, height 0.2s, background-color 0.2s;
  mix-blend-mode: difference;

  &.hovering {
    width: 50px;
    height: 50px;
    background-color: ${theme.colors.textPrimary};
    opacity: 0.5;
  }
  
  &::after {
    content: '';
    position: absolute;
    top: 50%;
    left: 50%;
    width: 4px;
    height: 4px;
    background: ${theme.colors.textPrimary};
    border-radius: 50%;
    transform: translate(-50%, -50%);
  }
`;

const BackgroundLogs = styled.div`
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 0;
  opacity: 0.03;
  font-family: ${theme.fonts.code};
  font-size: 10px;
  line-height: 1.5;
  color: ${theme.colors.textPrimary};
  overflow: hidden;
  display: flex;
  justify-content: space-between;
`;

const LogColumn = styled.div<{ $speed: number }>`
  width: 30%;
  animation: ${logScroll} ${props => props.$speed}s linear infinite;
`;

const ContentWrapper = styled.div`
  position: relative;
  z-index: 1;
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 24px;
`;

const Header = styled.header`
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  z-index: 1000;
  padding: 24px 0;
  background: linear-gradient(to bottom, ${theme.colors.background} 0%, transparent 100%);
  backdrop-filter: blur(5px);
`;

const HeaderContent = styled.div`
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
`;

const Logo = styled.img`
  height: 40px;
  width: auto;
  /* Invert logo to match new dark theme if it's black, otherwise leave it */
  filter: brightness(0) invert(1); 
  opacity: 0.9;
`;

const Button = styled(motion.button)<{ $variant?: 'primary' | 'secondary' }>`
  padding: 14px 28px;
  border-radius: 20px;
  font-family: ${theme.fonts.code};
  font-weight: bold;
  font-size: 0.9rem;
  transition: all 0.4s cubic-bezier(0.19, 1, 0.22, 1);
  text-transform: uppercase;
  letter-spacing: 1.5px;
  position: relative;
  overflow: hidden;
  z-index: 1;
  border: none;

  ${props => props.$variant === 'secondary' ? css`
    background: transparent;
    color: ${theme.colors.textSecondary};
    border: 1px solid ${theme.colors.border};

    &:hover {
      color: ${theme.colors.textPrimary};
      border-color: ${theme.colors.textPrimary};
    }
  ` : css`
    background: transparent;
    color: ${theme.colors.textPrimary};
    border: 1px solid ${theme.colors.textPrimary};

    &::before {
      content: '';
      position: absolute;
      bottom: 0;
      left: 0;
      width: 100%;
      height: 0%;
      background: ${theme.colors.accentFill};
      transition: all 0.4s cubic-bezier(0.19, 1, 0.22, 1);
      z-index: -1;
    }

    &:hover {
      color: ${theme.colors.textInvert};
      &::before {
        height: 100%;
      }
    }
  `}
`;

const HeroSection = styled.section`
  min-height: 90vh;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding-top: 60px;
`;

const Headline = styled(motion.h1)`
  font-family: ${theme.fonts.header};
  font-weight: 300;
  font-size: clamp(3.5rem, 6vw, 6rem);
  line-height: 1.1;
  margin-bottom: 24px;
  color: ${theme.colors.textPrimary};
  letter-spacing: -0.02em;
`;

const SubHeadline = styled(motion.div)`
  font-family: ${theme.fonts.header};
  font-weight: 300;
  font-size: clamp(1.8rem, 3vw, 3rem);
  color: ${theme.colors.textSecondary};
  margin-bottom: 40px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
`;

const RotatingWordContainer = styled.span`
  color: ${theme.colors.textPrimary};
  position: relative;
  display: inline-block;
  min-width: 300px;
  font-family: ${theme.fonts.code};
  font-style: normal;
  font-size: 0.8em; /* Adjust monospace size to fit serif flow */
  letter-spacing: -0.5px;
  
  &::after {
    content: '';
    display: inline-block;
    width: 10px; 
    height: 1.2em;
    background: ${theme.colors.textPrimary};
    margin-left: 8px;
    vertical-align: middle;
    animation: ${cursorBlink} 1s step-end infinite;
  }
`;

const Description = styled(motion.p)`
  font-family: ${theme.fonts.body};
  font-size: 1.1rem;
  line-height: 1.7;
  color: ${theme.colors.textSecondary};
  max-width: 540px;
  margin-bottom: 56px;
`;

const ButtonGroup = styled(motion.div)`
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
`;

const ScrollSection = styled(motion.section)`
  min-height: 60vh;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 120px 0;
`;

const SectionTitle = styled.h2`
  font-family: ${theme.fonts.header};
  font-weight: 300;
  font-size: clamp(2.5rem, 4vw, 4rem);
  margin-bottom: 32px;
  color: ${theme.colors.textPrimary};
  letter-spacing: -0.01em;
`;

const PillContainer = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 32px;
`;

const Pill = styled(motion.div)`
  padding: 10px 20px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.03);

  border: none;
  color: ${theme.colors.textSecondary};
  font-family: ${theme.fonts.code};
  font-size: 0.85rem;
  cursor: default;
  letter-spacing: 0.5px;
  transition: all 0.3s ease;

  &:hover {
    border-color: ${theme.colors.textPrimary};
    color: ${theme.colors.textPrimary};
    background: rgba(255, 255, 255, 0.08);
  }
`;

const Grid = styled.div`
  display: grid;
  grid-template-columns: 1fr;
  gap: 40px;
  margin-top: 60px;
  
  @media (min-width: 768px) {
    grid-template-columns: 1fr 1fr;
  }
`;

// Export Card for use in the component
const Card = styled(motion.div)<{ $featured?: boolean }>`
  background: ${props => props.$featured ? 'rgba(255, 255, 255, 0.03)' : 'transparent'};
  border: 1px solid ${theme.colors.border};
  padding: 48px;
  transition: all 0.3s ease;
  position: relative;
  
  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
    opacity: 0;
    transition: opacity 0.3s ease;
  }

  &:hover {
    border-color: rgba(255, 255, 255, 0.2);
    background: rgba(255, 255, 255, 0.02);
    &::before { opacity: 1; }
  }
`;

const TimelineContainer = styled.div`
  position: relative;
  padding-left: 30px;
  margin-top: 40px;
  border-left: 1px solid ${theme.colors.border};
`;

const TimelineItem = styled(motion.div)`
  position: relative;
  margin-bottom: 48px;
  
  &::before {
    content: '';
    position: absolute;
    left: -35px;
    top: 6px;
    width: 9px;
    height: 9px;
    background: ${theme.colors.background};
    border: 1px solid ${theme.colors.textSecondary};
    transform: rotate(45deg); /* Diamond shape */
  }
  
  &:hover::before {
    background: ${theme.colors.textPrimary};
    border-color: ${theme.colors.textPrimary};
  }
`;

// --- Helper Components ---

const words = ["ghostwriter", "marketer", "strategist", "copywriter"];

const RotatingWords = () => {
  const [index, setIndex] = useState(0);
  const [displayText, setDisplayText] = useState("");
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    const currentWord = words[index];
    const speed = isDeleting ? 30 : 80; // Faster typing for "code" feel
    
    const timer = setTimeout(() => {
      if (!isDeleting && displayText === currentWord) {
        setTimeout(() => setIsDeleting(true), 2000);
      } else if (isDeleting && displayText === "") {
        setIsDeleting(false);
        setIndex((prev) => (prev + 1) % words.length);
      } else {
        setDisplayText(prev => 
          isDeleting 
            ? prev.slice(0, -1) 
            : currentWord.slice(0, prev.length + 1)
        );
      }
    }, speed);

    return () => clearTimeout(timer);
  }, [displayText, isDeleting, index]);

  return <RotatingWordContainer>{displayText}</RotatingWordContainer>;
};

const Section = ({ children, delay = 0 }: { children: React.ReactNode, delay?: number }) => {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-100px" });

  return (
    <ScrollSection
      ref={ref}
      initial={{ opacity: 0, y: 30 }}
      animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 30 }}
      transition={{ duration: 1.0, delay, ease: [0.16, 1, 0.3, 1] }} // Apple-esque ease
    >
      {children}
    </ScrollSection>
  );
};

const Cursor = () => {
  const cursorRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const cursor = cursorRef.current;
    if (!cursor) return;

    const moveCursor = (e: MouseEvent) => {
      cursor.style.left = `${e.clientX}px`;
      cursor.style.top = `${e.clientY}px`;
    };

    const handleMouseOver = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (target.tagName === 'BUTTON' || target.tagName === 'A' || target.getAttribute('role') === 'button') {
        cursor.classList.add('hovering');
      } else {
        cursor.classList.remove('hovering');
      }
    };

    window.addEventListener('mousemove', moveCursor);
    document.addEventListener('mouseover', handleMouseOver);

    return () => {
      window.removeEventListener('mousemove', moveCursor);
      document.removeEventListener('mouseover', handleMouseOver);
    };
  }, []);

  return <CustomCursor ref={cursorRef} />;
};

const TextHoverAnimation = ({ children }: { children: React.ReactElement | string }) => {
  const [isHovered, setIsHovered] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  
  // Extract text content if children is a string
  const textContent = typeof children === 'string' ? children : (children.props.children as string);
  const letters = textContent.split('');

  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isHovered) {
      interval = setInterval(() => {
        setActiveIndex((prev) => (prev + 1) % (letters.length + 5));
      }, 50);
    } else {
      setActiveIndex(-1);
    }
    return () => clearInterval(interval);
  }, [isHovered, letters.length]);

  const getLetterStyle = (index: number) => {
    if (!isHovered) return {};
    
    const distance = Math.abs(index - activeIndex);
    const maxDistance = 3;
    
    if (distance > maxDistance) return {};

    const intensity = 1 - distance / maxDistance;
    const yOffset = -5 * intensity;
    
    // Blue shades from AnimatedText component
    const blueShades = [
      '#7dd3fc', // sky-300
      '#38bdf8', // sky-400
      '#0ea5e9', // sky-500
      '#60a5fa', // blue-400
      '#3b82f6', // blue-500
      '#22d3ee', // cyan-400
      '#06b6d4', // cyan-500
    ];

    // Map distance to color (0 = brightest/last, maxDistance = first)
    // In AnimatedText: distance 0 -> blueShades[6], distance 1 -> blueShades[5], etc.
    const colorIndex = Math.max(0, blueShades.length - 1 - distance);
    const color = blueShades[colorIndex];

    return {
      display: 'inline-block',
      transform: `translateY(${yOffset}px)`,
      color: distance <= maxDistance ? color : theme.colors.textSecondary,
      transition: 'transform 0.1s, color 0.1s'
    };
  };

  const animatedContent = (
    <span 
      onMouseEnter={() => setIsHovered(true)} 
      onMouseLeave={() => setIsHovered(false)}
      style={{ display: 'inline-block' }}
    >
      {letters.map((letter, i) => (
        <span key={i} style={{ transition: 'all 0.2s ease', ...getLetterStyle(i) }}>
          {letter === ' ' ? '\u00A0' : letter}
        </span>
      ))}
    </span>
  );

  if (typeof children === 'string') {
    return animatedContent;
  }

  // Clone the element and replace its children with the animated content
  return React.cloneElement(children, {}, animatedContent);
};

const LogStream = () => {
  const [logs, setLogs] = useState<string[]>([]);
  
  useEffect(() => {
    // Generate some fake "system logs"
    const verbs = ['INITIALIZING', 'PARSING', 'ANALYZING', 'OPTIMIZING', 'GENERATING', 'FETCHING'];
    const nouns = ['CONTEXT_WINDOW', 'USER_VECTORS', 'SENTIMENT_GRAPH', 'ENGAGEMENT_METRICS', 'REPLY_TREE'];
    const statuses = ['OK', 'PENDING', 'CACHED', 'SYNCED'];
    
    const newLogs = Array.from({ length: 50 }, () => {
      const timestamp = new Date().toISOString();
      const verb = verbs[Math.floor(Math.random() * verbs.length)];
      const noun = nouns[Math.floor(Math.random() * nouns.length)];
      const status = statuses[Math.floor(Math.random() * statuses.length)];
      return `[${timestamp}] ${verb} :: ${noun} ... ${status}`;
    });
    
    setLogs(newLogs);
  }, []);

  return (
    <BackgroundLogs>
      <LogColumn $speed={40}>
        {logs.map((log, i) => <div key={`c1-${i}`}>{log}</div>)}
        {logs.map((log, i) => <div key={`c1-dup-${i}`}>{log}</div>)}
      </LogColumn>
      <LogColumn $speed={60} style={{ textAlign: 'right', opacity: 0.5 }}>
        {logs.slice().reverse().map((log, i) => <div key={`c2-${i}`}>{log}</div>)}
        {logs.slice().reverse().map((log, i) => <div key={`c2-dup-${i}`}>{log}</div>)}
      </LogColumn>
    </BackgroundLogs>
  );
};


// --- Main Component ---

export function Login() {
  const navigate = useNavigate();
  const setUsername = useSetRecoilState(usernameState);
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // --- Auth Logic (Preserved) ---
  const handleLogin = async () => {
    try {
      setError(null);
      setIsLoggingIn(true);
      console.log('Starting Twitter login...');

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

          if (status.status === 'success' && status.username) {
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
            setError('Browser Extension Required. The GhostPoster browser extension is required to complete login.');
          }
        } catch (error) {
          console.error('Polling error:', error);
        }
      }, 2000);

      setTimeout(() => {
        clearInterval(pollInterval);
      }, 300000);

    } catch (error) {
      console.error('Login failed:', error);
      setError(`Login failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
      setIsLoggingIn(false);
    }
  };

  if (isLoggingIn) return <LoginLoading />;

  return (
    <ThemeProvider theme={theme}>
      <GlobalStyle />
      <PageContainer>
        <Cursor />
        <LogStream />

        <ContentWrapper>
          <Header>
            <HeaderContent>
              <Logo src="/ghostposter_logo.png" alt="GhostPost" />
              <Button onClick={handleLogin}>Log In</Button>
            </HeaderContent>
          </Header>

      {error && (
            <motion.div 
              initial={{ opacity: 0, y: -20 }}
              animate={{ opacity: 1, y: 0 }}
              style={{ 
                background: 'rgba(255, 50, 50, 0.1)', 
                border: '1px solid rgba(255, 50, 50, 0.3)', 
                color: '#ff6b6b', 
                padding: '16px', 
                fontFamily: theme.fonts.code,
                fontSize: '0.9rem',
                textAlign: 'center',
                marginBottom: '20px'
              }}
            >
          {error}
            </motion.div>
          )}

          <HeroSection>
            <Headline
              initial={{ opacity: 0, y: 40 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
            >
              Nobody knows you exist.<br />
              We can change that.
            </Headline>
            
            <SubHeadline
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.4, duration: 1.0 }}
            >
              Become your own <RotatingWords />
            </SubHeadline>

            <Description
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.6, duration: 1.0 }}
            >
              Ghostpost is your AI ghostwriting layer. It watches the internet, finds high-signal conversations, and speaks in your voice, everywhere.
            </Description>

            <ButtonGroup
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.8, duration: 1.0 }}
            >
              <Button onClick={handleLogin}>
                Login
              </Button>
              <Button $variant="secondary" onClick={() => document.getElementById('how-it-works')?.scrollIntoView({ behavior: 'smooth' })}>
                how it works
              </Button>
            </ButtonGroup>
          </HeroSection>

          <div id="how-it-works">
            <Section>
              <SectionTitle>Agents that learn on their own.</SectionTitle>
              <Description>
                With ghostwriting agents that know everything about you and get better on their own. They build a persistent model of your voice from your posts, edits, and approvals.
              </Description>
            </Section>

            <Section>
              <SectionTitle>Your voice, everywhere.</SectionTitle>
              <PillContainer>
                <Pill whileHover={{ scale: 1.05 }}>X (Twitter) replies & DMs</Pill>
                <Pill whileHover={{ scale: 1.05 }}>Reddit threads</Pill>
                <Pill whileHover={{ scale: 1.05 }}>LinkedIn comments</Pill>
                <Pill whileHover={{ scale: 1.05 }}>Blog outlines</Pill>
                <Pill whileHover={{ scale: 1.05 }}>Email drafts</Pill>
              </PillContainer>
            </Section>
            <Section>
              <div style={{ padding: '40px 0', borderTop: `1px solid ${theme.colors.border}` }}>
                <SectionTitle>
                  <TextHoverAnimation>Creator Package</TextHoverAnimation>
                </SectionTitle>
                <h4 style={{ fontFamily: theme.fonts.body, fontSize: '1.2rem', marginBottom: '20px', color: theme.colors.textPrimary }}>Grow on socials without scrolling.</h4>
                <p style={{ color: theme.colors.textSecondary, marginBottom: '40px', maxWidth: '700px' }}>
                  Ghostpost gathers relevant tweets, Reddit threads, and LinkedIn posts in one place. You get high-signal engagement opportunities without doomscrolling. We handle the orchestration; you focus on communication.
                </p>

                <h5 style={{ fontFamily: theme.fonts.code, color: theme.colors.textPrimary, letterSpacing: '1px', fontSize: '0.9rem' }}>HOW IT WORKS</h5>
                <TimelineContainer>
                  <TimelineItem>
                    <strong style={{ color: theme.colors.textPrimary, fontFamily: theme.fonts.header, fontWeight: 300, fontSize: '1.2rem' }}>Chat with our interface</strong>
                  </TimelineItem>
                  <TimelineItem>
                    <strong style={{ color: theme.colors.textPrimary, fontFamily: theme.fonts.header, fontWeight: 300, fontSize: '1.2rem' }}>Add the Breadscraper extension</strong>
                  </TimelineItem>
                  <TimelineItem>
                    <strong style={{ color: theme.colors.textPrimary, fontFamily: theme.fonts.header, fontWeight: 300, fontSize: '1.2rem' }}>Log into your social accounts</strong>
                  </TimelineItem>
                  <TimelineItem>
                    <strong style={{ color: theme.colors.textPrimary, fontFamily: theme.fonts.header, fontWeight: 300, fontSize: '1.2rem' }}>Agents analyze & curate</strong>
                    <p style={{ fontSize: '0.9rem', color: theme.colors.textSecondary, marginTop: '8px', fontFamily: theme.fonts.code }}>
                      Our web agents find high-signal opportunities for you.
                    </p>
                  </TimelineItem>
                  <TimelineItem>
                    <strong style={{ color: theme.colors.textPrimary, fontFamily: theme.fonts.header, fontWeight: 300, fontSize: '1.2rem' }}>Respond & Grow</strong>
                    <p style={{ fontSize: '0.9rem', color: theme.colors.textSecondary, marginTop: '8px', fontFamily: theme.fonts.code }}>
                      Write yourself, generate with AI, or use a bespoke model.
                    </p>
                  </TimelineItem>
                </TimelineContainer>
      </div>
            </Section>

            <Section>
              <div style={{ padding: '40px 0', borderTop: `1px solid ${theme.colors.border}` }}>
                <SectionTitle style={{ fontSize: '2rem' }}>
                  <TextHoverAnimation>Founder Package</TextHoverAnimation>
                </SectionTitle>
                <h4 style={{ fontFamily: theme.fonts.body, fontSize: '1.2rem', marginBottom: '20px', color: theme.colors.textPrimary }}>Your AI Head of Communications.</h4>
                <p style={{ color: theme.colors.textSecondary, marginBottom: '40px', maxWidth: '700px' }}>
                  A bespoke LLM that maintains a living database of your life, company, and product. It engages on social media, writes blogs, and drafts emails in your exact style.
                </p>

                <Grid style={{ marginTop: '30px', gap: '20px' }}>
                  {[
                    { title: "Deep Context", text: "Ingests videos, documents, memos, and blogs to inform every word it writes." },
                    { title: "Agentic Interface", text: "Auto-reply on social media with an agent that understands your strategy." },
                    { title: "Active Learning", text: "Every edit you make re-trains the model. It gets smarter with every approval." },
                    { title: "True Identity", text: "A persistent identity model of YOU that writes like a human, not a generic AI." }
                  ].map((item, i) => (
                    <div key={i} style={{ background: 'rgba(255,255,255,0.02)', padding: '24px', border: `1px solid ${theme.colors.border}` }}>
                      <h5 style={{ color: theme.colors.textPrimary, marginBottom: '12px', fontFamily: theme.fonts.code, fontSize: '0.9rem' }}>{item.title}</h5>
                      <p style={{ fontSize: '1rem', color: theme.colors.textSecondary, fontFamily: theme.fonts.header, fontWeight: 300 }}>
                        {item.text}
                      </p>
                    </div>
                  ))}
                </Grid>
              </div>
            </Section>
      </div>

          <footer style={{ borderTop: `1px solid ${theme.colors.border}`, padding: '40px 0', marginTop: '60px', textAlign: 'center', color: theme.colors.textSecondary, fontFamily: theme.fonts.code, fontSize: '0.8rem' }}>
            <p>&copy; {new Date().getFullYear()} Bread Technologies</p>
          </footer>

        </ContentWrapper>
      </PageContainer>
    </ThemeProvider>
  );
}

export default Login;

