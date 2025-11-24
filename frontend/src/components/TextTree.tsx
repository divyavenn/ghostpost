import { useState, useEffect, useMemo, useCallback } from 'react';
import styled from 'styled-components';
import { useRecoilState, useRecoilValue, useSetRecoilState } from 'recoil';
import { Text, Typewriter } from './Typewriter';
import { ClickablePulsingText } from './WordStyles';
import { typingIdsState } from '../atoms';

// --- Types ---
export type DisplayType = 'retype' | 'next-sentence' | 'new-sentence' | 'new-paragraph';

export interface TextNode {
  id: string;
  words: Text[];
}

// --- Styled Components ---
const Paragraph = styled.p`
  margin-bottom: 2rem;

  &:last-child {
    margin-bottom: 0;
  }
`;

const TypewriterText = styled.span`
  display: inline;
`;

// --- Link Class ---
class Link extends Text {
  constructor(
    text: string,
    target: string,
    displayType: DisplayType,
    onNavigate: (target: string, displayType: DisplayType) => void,
    onDelete?: (target: string) => void
  ) {
    super(text);
    this.target = target; // Store the target id
    this.displayType = displayType; // Store the display type
    this.renderWith = ClickablePulsingText;
    this.onClick = () => onNavigate(target, displayType);
    if (onDelete) {
      this.onClickAgain = 'toggle';
      this.undoClick = () => onDelete(target);
    }
  }
}

const extractTextContent = (words: Text[]): string => {
  return words.map(word => word.text).join('');
};

// --- Text Tree Builder ---
const buildTextTree = (
  onNavigate: (target: string, displayType: DisplayType) => void,
  onDelete: (target: string) => void
): Record<string, TextNode> => ({
  root: {
    id: 'root',
    words: [
      new Text('Hello. Welcome to '),
      new Link('Ghostpost', 'ghostpost', 'retype', onNavigate),
      new Text('.'),
    ],
  },
  ghostpost: {
    id: 'ghostpost',
    words: [
      new Link('Ghostpost', 'what-is-ghostpost', 'new-paragraph', onNavigate, onDelete),
      new Text(' lets you become your own '),
      new Link('ghostwriter', 'ghostwriter', 'new-paragraph', onNavigate, onDelete),
      new Text('/'),
      new Link('copywriter', 'copywriter', 'new-paragraph', onNavigate, onDelete),
      new Text('/'),
      new Link('social media expert', 'social-media', 'new-paragraph', onNavigate, onDelete),
      new Text('.'),
    ],
  },
  'what-is-ghostpost': {
    id: 'what-is-ghostpost',
    words: [
      new Text('Ghostpost is an AI that watches the internet for you. It finds '),
      new Link('high-signal conversations', 'high-signal', 'new-paragraph', onNavigate, onDelete),
      new Text(' and speaks in your voice, everywhere.'),
    ],
  },
  'high-signal': {
    id: 'high-signal',
    words: [
      new Text('High-signal means worth your time. Our agents analyze tweets, Reddit threads, and LinkedIn posts to find opportunities where your expertise matters. No doomscrolling required.'),
    ],
  },
  ghostwriter: {
    id: 'ghostwriter',
    words: [
      new Text('A ghostwriter Our AI learns from every edit you make. It builds a '),
      new Link('persistent model', 'persistent-model', 'new-paragraph', onNavigate, onDelete),
      new Text(' of how you think and write.'),
    ],
  },
  'persistent-model': {
    id: 'persistent-model',
    words: [
      new Text('Every post you approve, every edit you make, every delete you issue teaches the model. It gets better on its own. Upload interviews, podcasts, blog posts—anything that sounds like you.'),
    ],
  },
  copywriter: {
    id: 'copywriter',
    words: [
      new Text('A copywriter sells without selling. Our agents draft replies that add value, build trust, and position you as an expert. '),
      new Link('Grow your audience', 'grow-audience', 'new-paragraph', onNavigate, onDelete),
      new Text(' without trying to grow your audience.'),
    ],
  },
  'grow-audience': {
    id: 'grow-audience',
    words: [
      new Text('The best way to grow is to be consistently helpful in public. Ghostpost handles the discovery and drafting. You handle the approval and authenticity.'),
    ],
  },
  'social-media': {
    id: 'social-media',
    words: [
      new Text('Social media experts monitor the internet for relevant conversation Ghostpost does both. It monitors X (Twitter), Reddit, LinkedIn, and finds threads where your voice belongs.'),
    ],
  },
});

// --- Erase Hook ---
const useEraser = (text: string, speed: number = 30) => {
  const [displayedText, setDisplayedText] = useState(text);
  const [isComplete, setIsComplete] = useState(false);

  useEffect(() => {
    let currentLength = text.length;

    const eraseInterval = setInterval(() => {
      if (currentLength >= 0) {
        setDisplayedText(text.slice(0, currentLength));
        currentLength--;
      } else {
        setIsComplete(true);
        clearInterval(eraseInterval);
      }
    }, speed);

    return () => clearInterval(eraseInterval);
  }, [text, speed]);

  return { displayedText, isComplete };
};

// --- Sentence Component ---
const Sentence = ({ words }: { words: Text[] }) => {
  const [, forceUpdate] = useState(0);
  const typingIds = useRecoilValue(typingIdsState);

  // Subscribe to typingIds changes for words in this sentence
  useEffect(() => {
    // Force re-render when typingIds changes and affects any word in this sentence
    const hasAffectedWord = words.some(word => word.target && typingIds.has(word.target));
    if (hasAffectedWord) {
      forceUpdate(n => n + 1);
    }
  }, [typingIds, words]);

  const handleWordClick = (word: Text, originalOnClick?: () => void) => {
    // Call the original onClick handler
    if (originalOnClick) {
      originalOnClick();
    }

    // Toggle the word's clicked state
    word.clicked = !word.clicked;

    // Force re-render
    forceUpdate(n => n + 1);
  };

  return (
    <>
      {words.map((word, index) => {
        const WrapperComponent = word.renderWith;
        if (WrapperComponent) {
          // Check if this link's target is currently typing
          const isTargetTyping = word.target && typingIds.has(word.target);

          // If target is typing, render as plain text
          if (isTargetTyping) {
            return <span key={index}>{word.text}</span>;
          }

          // First click - not yet clicked
          if (!word.clicked) {
            return <WrapperComponent key={index} onClick={() => handleWordClick(word, word.onClick)}>{word.text}</WrapperComponent>;
          }
          // Already clicked - check behavior
          else {
            // Toggle behavior: call undoClick on second click
            if (word.onClickAgain === 'toggle' && word.undoClick) {
              return <WrapperComponent key={index} onClick={() => handleWordClick(word, word.undoClick)}>{word.text}</WrapperComponent>;
            }
            // Repeat behavior: call onClick again on second click
            else if (word.onClickAgain === 'repeat' && word.onClick) {
              return <WrapperComponent key={index} onClick={() => handleWordClick(word, word.onClick)}>{word.text}</WrapperComponent>;
            }
            // No behavior (null/undefined): render as plain text
            else {
              return <span key={index}>{word.text}</span>;
            }
          }
        }
        return <span key={index}>{word.text}</span>;
      })}
    </>
  );
};

// --- Segment Component ---
const SegmentComponent = ({
  node,
  isDone,
  isDeleting,
  onComplete
}: {
  node: TextNode;
  isDone: boolean;
  isDeleting: boolean;
  onComplete: () => void;
}) => {
  if (isDeleting) {
    return (
      <Typewriter
        sentence={node.words}
        onComplete={onComplete}
        inline
        delete
      />
    );
  }

  if (isDone) {
    return <Sentence words={node.words} />;
  }

  return (
    <Typewriter
      sentence={node.words}
      onComplete={onComplete}
      nodeId={node.id}
      inline
    />
  );
};

// --- Paragraph Component ---
const ParagraphComponent = ({
  sentences,
  deletingIds,
  onDeleteComplete
}: {
  sentences: TextNode[];
  deletingIds: Set<string>;
  onDeleteComplete: (id: string) => void;
}) => {
  const [completionState, setCompletionState] = useState<boolean[]>([]);

  // Update completion state when sentences change
  useEffect(() => {
    setCompletionState(prev => {
      // Only expand the array if we have more sentences than completion states
      if (prev.length >= sentences.length) {
        return prev;
      }
      // Preserve existing states and add false for new sentences
      const newState = [...prev];
      while (newState.length < sentences.length) {
        newState.push(false);
      }
      return newState;
    });
  }, [sentences.length]);

  const handleSegmentComplete = (index: number) => {
    setCompletionState(prev => {
      const newState = [...prev];
      newState[index] = true;
      return newState;
    });
  };

  return (
    <Paragraph>
      {sentences.map((node, idx) => {
        if (!node) return null;

        const isDeleting = deletingIds.has(node.id);

        return (
          <SegmentComponent
            key={`${node.id}-${idx}`}
            node={node}
            isDone={completionState[idx] || false}
            isDeleting={isDeleting}
            onComplete={() => {
              if (isDeleting) {
                onDeleteComplete(node.id);
              } else {
                handleSegmentComplete(idx);
              }
            }}
          />
        );
      })}
    </Paragraph>
  );
};

// --- Main TextTree Component ---
interface TextTreeProps {
  className?: string;
}

export function TextTree({ className }: TextTreeProps) {
  const [paragraphs, setParagraphs] = useState<string[][]>([
    ['root']
  ]);

  const [isErasing, setIsErasing] = useState(false);
  const [textToErase, setTextToErase] = useState('');
  const [nextAction, setNextAction] = useState<{ target: string; displayType: DisplayType } | null>(null);
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set());
  const setTypingIds = useSetRecoilState(typingIdsState);

  // Memoize the textTree so Word instances persist across renders
  const finalTextTree = useMemo(() => {
    // Dummy navigate/delete handlers for initial build
    const dummyNavigate = () => {};
    const dummyDelete = () => {};

    return buildTextTree(dummyNavigate, dummyDelete);
  }, []);

  // DFS to find all descendants of a node
  const findAllDescendants = useCallback((nodeId: string, visited = new Set<string>()): string[] => {
    if (visited.has(nodeId)) return [];

    visited.add(nodeId);
    const descendants: string[] = [nodeId];
    const node = finalTextTree[nodeId];

    if (!node) return descendants;

    // Find all Link words in this node and recursively get their descendants
    node.words.forEach(word => {
      if (word.target) {
        // This is a Link - recursively find its descendants
        const childDescendants = findAllDescendants(word.target, visited);
        childDescendants.forEach(desc => {
          if (!descendants.includes(desc)) {
            descendants.push(desc);
          }
        });
      }
    });

    return descendants;
  }, [finalTextTree]);

  const handleNavigate = useCallback((targetId: string, displayType: DisplayType) => {
    // Add target to typing state
    setTypingIds(prev => new Set(prev).add(targetId));

    if (displayType === 'retype') {
      // Erase everything and show new node
      setParagraphs(prev => {
        const textContent = prev
          .map(p => p.map(sentenceId => extractTextContent(finalTextTree[sentenceId]?.words || [])).join(''))
          .join(' ');
        setTextToErase(textContent);
        return prev;
      });
      setNextAction({ target: targetId, displayType });
      setIsErasing(true);
    } else if (displayType === 'new-paragraph') {
      // Add new paragraph
      setParagraphs(prev => [
        ...prev,
        [targetId]
      ]);
    } else if (displayType === 'next-sentence' || displayType === 'new-sentence') {
      // Add to current paragraph
      setParagraphs(prev => {
        const newParagraphs = [...prev];
        const lastParagraph = [...newParagraphs[newParagraphs.length - 1]];
        lastParagraph.push(targetId);
        newParagraphs[newParagraphs.length - 1] = lastParagraph;
        return newParagraphs;
      });
    }
  }, [finalTextTree, setTypingIds]);

  const handleDelete = useCallback((targetId: string) => {
    const allToDelete = findAllDescendants(targetId);

    // Reset clicked state for all words in nodes being deleted
    allToDelete.forEach(id => {
      const node = finalTextTree[id];
      if (node) {
        node.words.forEach(word => {
          if (word.target) {
            word.clicked = false;
          }
        });
      }
    });

    // Remove deleted nodes from typingIds
    setTypingIds(prev => {
      const newSet = new Set(prev);
      allToDelete.forEach(id => newSet.delete(id));
      return newSet;
    });

    setDeletingIds(prev => {
      const newSet = new Set(prev);
      allToDelete.forEach(id => newSet.add(id));
      return newSet;
    });
  }, [findAllDescendants, finalTextTree, setTypingIds]);

  // Attach the real handlers to the tree after it's created
  useEffect(() => {
    Object.values(finalTextTree).forEach(node => {
      node.words.forEach(word => {
        if (word.target && word.displayType) {
          // This is a Link - update its handlers
          word.onClick = () => handleNavigate(word.target!, word.displayType as DisplayType);
          if (word.onClickAgain === 'toggle') {
            word.undoClick = () => handleDelete(word.target!);
          }
        }
      });
    });
  }, [finalTextTree, handleNavigate, handleDelete]);

  const handleDeleteComplete = useCallback((id: string) => {
    // Remove the sentence from paragraphs
    setParagraphs(prev => {
      return prev
        .map(p => p.filter(sentenceId => sentenceId !== id))
        .filter(p => p.length > 0); // Remove empty paragraphs
    });
    // Remove from deletingIds
    setDeletingIds(prev => {
      const newSet = new Set(prev);
      newSet.delete(id);
      return newSet;
    });
    // Remove from typingIds
    setTypingIds(prev => {
      const newSet = new Set(prev);
      newSet.delete(id);
      return newSet;
    });
  }, [setTypingIds]);

  const { displayedText: erasedText, isComplete: eraseComplete } = useEraser(
    isErasing ? textToErase : '',
    10
  );

  useEffect(() => {
    if (isErasing && eraseComplete && nextAction) {
      setIsErasing(false);
      setParagraphs([[nextAction.target]]);
      setNextAction(null);
    }
  }, [eraseComplete, isErasing, nextAction]);

  return (
    <div className={className}>
      {isErasing ? (
        <TypewriterText>{erasedText}</TypewriterText>
      ) : (
        <>
          {paragraphs.map((sentenceIds, idx) => (
            <ParagraphComponent
              key={`p-${idx}`}
              sentences={sentenceIds.map(id => finalTextTree[id]).filter(Boolean)}
              deletingIds={deletingIds}
              onDeleteComplete={handleDeleteComplete}
            />
          ))}
        </>
      )}
    </div>
  );
}
