import styled, { keyframes } from 'styled-components';
import { useEffect, useState } from 'react';

interface PulsingTextProps {
  text: string;
  className?: string;
}

const pulse = keyframes`
  0%, 100% {
    color: #E5E5E5;
  }
  50% {
    color: #60a5fa;
  }
`;

const PulsingSpan = styled.span`
  display: inline;
  animation: ${pulse} 2s ease-in-out infinite;
`;

export function PulsingText({ text, className = '' }: PulsingTextProps) {
  return (
    <PulsingSpan className={className}>
      {text}
    </PulsingSpan>
  );
}


interface ClickablePulsingTextProps {
  children: React.ReactNode;
  onClick?: () => void;
}

const Clickable = styled.span`
  color: #E5E5E5;
  cursor: pointer;
  border-bottom: 1px solid transparent;
  transition: border-color 0.2s ease;

  &:hover {
    border-bottom-color: #ffffff;
  }
`;

export function ClickablePulsingText({ children, onClick}: ClickablePulsingTextProps) {
  return (
    <Clickable onClick={onClick}>
      <PulsingText text={String(children)} />
    </Clickable>
  );
}



interface AnimatedTextProps {
  text: string;
  className?: string;
}

const LetterSpan = styled.span<{ $color: string; $yOffset: number }>`
  display: inline-block;
  transition: all 0.2s ease;
  color: ${props => props.$color};
  transform: translateY(${props => props.$yOffset}px);
`;

export function AnimatedText({ text, className = '' }: AnimatedTextProps) {
  const [activeIndex, setActiveIndex] = useState(0);
  const letters = text.split('');

  useEffect(() => {
    const interval = setInterval(() => {
      setActiveIndex((prev) => (prev + 1) % (letters.length + 3)); // +3 for the dots
    }, 150);

    return () => clearInterval(interval);
  }, [letters.length]);

  const getLetterColor = (index: number) => {
    const blueShades = [
      '#7dd3fc', // sky-300
      '#38bdf8', // sky-400
      '#0ea5e9', // sky-500
      '#60a5fa', // blue-400
      '#3b82f6', // blue-500
      '#22d3ee', // cyan-400
      '#06b6d4', // cyan-500
    ];

    // Calculate distance from active index
    const distance = Math.abs(index - activeIndex);

    if (distance === 0) return blueShades[6]; // brightest
    if (distance === 1) return blueShades[5];
    if (distance === 2) return blueShades[4];
    if (distance === 3) return blueShades[3];

    return '#E5E5E5'; // default white
  };

  const getLetterYOffset = (index: number) => {
    const distance = Math.abs(index - activeIndex);

    if (distance === 0) return -8; // -translate-y-2 = -8px
    if (distance === 1) return -4; // -translate-y-1 = -4px

    return 0;
  };

  const dots = ['·', '·', '·'];

  return (
    <span className={className} style={{ display: 'inline' }}>
      {letters.map((letter, index) => (
        <LetterSpan
          key={index}
          $color={getLetterColor(index)}
          $yOffset={getLetterYOffset(index)}
        >
          {letter === ' ' ? '\u00A0' : letter}
        </LetterSpan>
      ))}
      {dots.map((dot, index) => {
        const dotIndex = letters.length + index;
        const isVisible = activeIndex >= dotIndex && activeIndex < dotIndex + 3;
        return (
          <LetterSpan
            key={`dot-${index}`}
            $color={isVisible ? getLetterColor(dotIndex) : 'transparent'}
            $yOffset={getLetterYOffset(dotIndex)}
          >
            {dot}
          </LetterSpan>
        );
      })}
    </span>
  );
}


interface ExternalLinkTextProps {
  children: React.ReactNode;
  url?: string;
}

const ExternalLinkSpan = styled.a`
  color: #E5E5E5;
  text-decoration: underline;
  cursor: pointer;
  transition: color 0.2s ease;

  &:hover {
    color: #60a5fa;
  }
`;

export function ExternalLinkText({ children, url }: ExternalLinkTextProps) {
  if (!url) {
    return <span>{children}</span>;
  }

  return (
    <ExternalLinkSpan
      href={url}
      target="_blank"
      rel="noopener noreferrer"
    >
      {children}
    </ExternalLinkSpan>
  );
}
