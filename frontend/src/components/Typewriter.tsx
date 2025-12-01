import { useState, useEffect, useRef } from 'react';
import styled, { keyframes } from 'styled-components';
import { useSetRecoilState } from 'recoil';
import { typingIdsState } from '../atoms';
import { ClickablePulsingText, ExternalLinkText } from './WordStyles';



export type MultipleClickBehaviors = 'repeat' | 'toggle'
export type DisplayType = 'new-paragraph' | 'next-sentence' | 'new-sentence' | 'retype';


export class Text {
  text: string;
  target?: string; // For Link instances - the target node id
  displayType?: DisplayType; // For Link instances - how to display the target
  url?: string; // For ExternalLink instances
  isDeletable?: boolean; // For Link instances - whether the link can be deleted
  clicked?: boolean; // For Link instances - track if link has been clicked
  renderWith?: React.ComponentType<{ children: React.ReactNode; onClick?: () => void; url?: string }>;

  constructor(text: string) {
    this.text = text;
  }
}

interface TypingTextProps {
  word: Text;
  shouldStart: boolean;
  onComplete: () => void;
  shouldDelete?: boolean;
  onNavigate?: (target: string, displayType: DisplayType) => void;
  onDelete?: (target: string) => void;
}

interface TypewriterProps {
  sentence: Text[];
  onComplete?: () => void;
  inline?: boolean;
  className?: string;
  delete?: boolean;
  nodeId?: string;
  onNavigate?: (target: string, displayType: DisplayType) => void;
  onDelete?: (target: string) => void;
}

const blink = keyframes`
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
`;

const Cursor = styled.span`
  display: inline-block;
  width: 2px;
  height: 1em;
  background-color: currentColor;
  margin-left: 2px;
  animation: ${blink} 1s step-end infinite;
  vertical-align: text-bottom;
`;

// Get a random typing speed to simulate human typing
const getRandomTypingSpeed = (isDeleting = false) => {
  // Make deletion almost instant
  if (isDeleting) return 1;

  const baseline = 5;
  const rand = Math.random();

  let speed;
  if (rand < 0.1) speed = baseline + Math.random() * baseline * 10;
  else if (rand < 0.3) speed = baseline + Math.random() * baseline * 6;
  else speed = baseline + Math.random() * baseline * 4;

  return speed;
};


// Word component - handles typing out a single word
const TypeWord = ({ word, shouldStart, onComplete, shouldDelete = false, onNavigate, onDelete: _onDelete }: TypingTextProps) => {
  const [visibleChars, setVisibleChars] = useState(shouldDelete ? word.text.length : 0);
  const [isComplete, setIsComplete] = useState(false);
  const onCompleteRef = useRef(onComplete);

  // Keep ref up to date
  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);

  useEffect(() => {
    if (!shouldStart) return;

    let charIndex = shouldDelete ? word.text.length : 0;
    const targetIndex = shouldDelete ? 0 : word.text.length;

    const animateChar = () => {
      if (shouldDelete) {
        if (charIndex > targetIndex) {
          charIndex--;
          setVisibleChars(charIndex);
          setTimeout(animateChar, getRandomTypingSpeed(true));
        } else {
          setIsComplete(true);
          onCompleteRef.current();
        }
      } else {
        if (charIndex < targetIndex) {
          charIndex++;
          setVisibleChars(charIndex);
          setTimeout(animateChar, getRandomTypingSpeed(false));
        } else {
          setIsComplete(true);
          onCompleteRef.current();
        }
      }
    };

    animateChar();
  }, [shouldStart, word.text, shouldDelete]);

  // If complete and not deleting, render with appropriate wrapper
  if (isComplete && !shouldDelete) {
    // Check if this is an external link (has url property)
    if (word.url) {
      return <ExternalLinkText url={word.url}>{word.text}</ExternalLinkText>;
    }

    // Check if this is an internal link (has target property)
    if (word.target && onNavigate) {
      return (
        <ClickablePulsingText
          onClick={() => onNavigate(word.target!, word.displayType || 'new-paragraph')}
        >
          {word.text}
        </ClickablePulsingText>
      );
    }
  }

  // Otherwise show plain text (typing or plain text)
  const visibleText = word.text.slice(0, visibleChars);
  return <span>{visibleText}</span>;
};

export const Typewriter = ({
  sentence,
  onComplete,
  inline = false,
  className,
  delete: shouldDelete = false,
  nodeId,
  onNavigate,
  onDelete,
}: TypewriterProps) => {
  const [currentWordIndex, setCurrentWordIndex] = useState(shouldDelete ? sentence.length - 1 : 0);
  const [isComplete, setIsComplete] = useState(false);
  const onCompleteRef = useRef(onComplete);
  const setTypingIds = useSetRecoilState(typingIdsState);

  // Keep ref up to date
  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);

  useEffect(() => {
    setCurrentWordIndex(shouldDelete ? sentence.length - 1 : 0);
    setIsComplete(false);

    if (sentence.length === 0) {
      setIsComplete(true);
      if (onCompleteRef.current) onCompleteRef.current();
    }
  }, [sentence, shouldDelete]);

  const handleWordComplete = () => {
    if (shouldDelete) {
      // Deleting: move to previous word
      if (currentWordIndex > 0) {
        setCurrentWordIndex(currentWordIndex - 1);
      } else {
        setIsComplete(true);
        if (onCompleteRef.current) onCompleteRef.current();
      }
    } else {
      // Typing: move to next word
      if (currentWordIndex < sentence.length - 1) {
        setCurrentWordIndex(currentWordIndex + 1);
      } else {
        setIsComplete(true);
        // Remove from typingIds when typing completes
        if (nodeId) {
          setTypingIds(prev => {
            const newSet = new Set(prev);
            newSet.delete(nodeId);
            return newSet;
          });
        }
        if (onCompleteRef.current) onCompleteRef.current();
      }
    }
  };

  const Component = inline ? 'span' : 'div';

  return (
    <Component className={className} style={{ display: inline ? 'inline' : 'block' }}>
      {sentence.map((word, index) => {
        const shouldStart = shouldDelete
          ? index >= currentWordIndex
          : index <= currentWordIndex;

        const isCurrentWord = index === currentWordIndex;

        return (
          <TypeWord
            key={index}
            word={word}
            shouldStart={shouldStart}
            shouldDelete={shouldDelete}
            onComplete={isCurrentWord ? handleWordComplete : () => {}}
            onNavigate={onNavigate}
            onDelete={onDelete}
          />
        );
      })}
      {!isComplete && <Cursor />}
    </Component>
  );
};

