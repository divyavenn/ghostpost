import React, { useState, useEffect, useCallback, useRef } from 'react';
import styled, { keyframes } from 'styled-components';
import { useRecoilValue, useSetRecoilState } from 'recoil';
import {
  motion,
  useMotionValue,
  useMotionValueEvent,
  useScroll,
  animate,
  MotionValue,
} from 'framer-motion';
import { Text, Typewriter } from './Typewriter';
import type { DisplayType } from './Typewriter';
import { MediaComponent } from './MediaComponents';
import type { MediaData } from './MediaComponents';
import { ClickablePulsingText, ExternalLinkText } from './WordStyles';
import { typingIdsState } from '../atoms';
import screenshotImage from '../assets/screenshot.png';

export interface TextNode {
  id: string;
  words: Text[];
  media?: MediaData;
}

// --- Helper Functions to Create Links ---
function Link(text: string, target: string, displayType: DisplayType = 'new-paragraph', isDeletable = false): Text {
  const word = new Text(text);
  word.target = target;
  word.displayType = displayType;
  word.isDeletable = isDeletable;
  word.clicked = false; // Initialize as not clicked
  word.renderWith = ClickablePulsingText;
  return word;
}

function ExternalLink(text: string, url: string): Text {
  const word = new Text(text);
  word.url = url;
  word.renderWith = ExternalLinkText;
  return word;
}


// --- Styled Components ---
const Paragraph = styled.div`
  margin-bottom: 2rem;

  &:last-child {
    margin-bottom: 0;
  }
`;

const TypewriterText = styled.span`
  display: inline;
`;

// --- Animations ---
const highlightFlash = keyframes`
  0% { background-color: transparent; }
  25% { background-color: rgba(96, 165, 250, 0.3); }
  75% { background-color: rgba(96, 165, 250, 0.3); }
  100% { background-color: transparent; }
`;

const HighlightWrapper = styled.span<{ $isHighlighted: boolean }>`
  display: inline;
  animation: ${props => props.$isHighlighted ? highlightFlash : 'none'} 1.5s ease-in-out;
  border-radius: 4px;
`;

const TreeContainer = styled(motion.div)`
  height: 60vh;
  overflow-y: auto;
  overflow-x: hidden;
  /* Hide scrollbar */
  scrollbar-width: none; /* Firefox */
  -ms-overflow-style: none; /* IE/Edge */
  &::-webkit-scrollbar {
    display: none; /* Chrome, Safari, Opera */
  }
`;

// Scroll-linked vertical fade mask
const top = `0%`;
const bottom = `100%`;
const topInset = `25%`;
const bottomInset = `75%`;
const transparent = `#0000`;
const opaque = `#000`;

function useScrollOverflowMask(scrollYProgress: MotionValue<number>) {
  const maskImage = useMotionValue(
    `linear-gradient(180deg, ${opaque}, ${opaque} ${top}, ${opaque} ${bottomInset}, ${transparent})`
  );

  useMotionValueEvent(scrollYProgress, "change", (value: number) => {
    if (value === 0) {
      // At top: fade only at bottom
      animate(
        maskImage,
        `linear-gradient(180deg, ${opaque}, ${opaque} ${top}, ${opaque} ${bottomInset}, ${transparent})`
      );
    } else if (value >= 0.99) {
      // At bottom: fade only at top
      animate(
        maskImage,
        `linear-gradient(180deg, ${transparent}, ${opaque} ${topInset}, ${opaque} ${bottom}, ${opaque})`
      );
    } else if (
      scrollYProgress.getPrevious() === 0 ||
      (scrollYProgress.getPrevious() ?? 0) >= 0.99
    ) {
      // In middle: fade both top and bottom
      animate(
        maskImage,
        `linear-gradient(180deg, ${transparent}, ${opaque} ${topInset}, ${opaque} ${bottomInset}, ${transparent})`
      );
    }
  });

  return maskImage;
}


// --- Text Tree Data (Pure Data - No Callbacks) ---
const TEXT_TREE: Record<string, TextNode> = {
  root: {
    id: 'root',
    words: [
      new Text('Hello. Welcome to '),
      Link('Ghostpost', 'ghostpost', 'new-paragraph'),
      new Text('.')
    ]
  },
  ghostpost: {
    id: 'ghostpost',
    words: [
      new Text('Ghostpost puts '),
      Link('your voice ', 'your-voice', 'new-paragraph'),
      new Text('everywhere'),
      Link(' it needs to be.', 'web-agents', 'new-paragraph'),
      new Text(' You become your own '),
      Link('ghostwriter', 'ghostwriter', 'new-paragraph'),
      new Text(' + '),
      Link('copywriter', 'copywriter', 'new-paragraph'),
      new Text(' + '),
      Link('social media expert', 'social-media', 'new-paragraph'),
      new Text('.'),
    ],
  },
  extension: {
    id: 'extension',
    words: [
      new Text('Our extension '),
      ExternalLink('breadscraper', 'https://chromewebstore.google.com/detail/markdownload/cfifpopoddilhgdjiffnlmlhkkankgjd'),
      new Text(` helps your agents navigate socials using your own browser state + lets you upload the contents of any article, video, voice note, PDF, or memo to your model's knowledge base with one click`),
    ],
    media: {
      type: 'image',
      url: screenshotImage
    }
  },
  ghostwriter: {
    id: 'ghostwriter',
    words: [
      new Text(`A good ghostwriter learns about your life and writes about it in a compelling way.
        Ghostpost lets you skip the long, lossy conversations you would need to teach someone about your work. You can give your `),
      Link('custom model', 'your-voice', 'new-paragraph'),
      new Text(' new info just by clicking on our '),
      Link('chrome extension.', 'extension', 'new-paragraph')
    ],
  },
  'your-voice': {
    id: 'your-voice',
    words: [
      new Text(`We train an bespoke LLM to write how you talk. The best part? The model automatically
        learns from every approval and edit you make to get better and better with time. `),
      new Text(`Armed with `),
      Link('complete knowledge', 'ghostwriter', 'new-paragraph'),
      new Text(' about your product and mission, your custom LLM engages with social media posts for you.')
    ],
  },
  copywriter: {
    id: 'copywriter',
    words: [
      new Text('A great copywriter knows how to find people whose pain points you solve and make you the obvious choice. Ghostphost automates this using '),
      Link('web agents.', 'web-agents', 'new-paragraph')
    ],
  },
  'social-media': {
    id: 'social-media',
    words: [
      new Text(`The best social media experts grow your audience by 1) monitoring the internet for relevant conversations and 2) being helpful and authentic in public.
        Ghostphost functions as a powerful social media team, handling all `),
      Link('the discovery', 'web-agents', 'new-paragraph'),
      new Text(' and '),
      Link('drafting. ', 'your-voice', 'new-paragraph'),
      new Text('All you have to do is edit and approve.')
    ],
  },
  'web-agents': {
    id: 'web-agents',
    words: [
      new Text('Web agents monitor all major socials, collect '),
      Link('high-signal conversations', 'high-signal', 'next-sentence'),
      new Text(', and puts them in one place for you to see. Updating these web agents is as easy as talking to them, giving you ultimate control over your brand presence. '),
    ],
  },
  'high-signal': {
    id: 'high-signal',
    words: [
      new Text('High-signal means worth your time. Our agents analyze tweets, Reddit threads, and LinkedIn posts to find opportunities where your expertise matters. No doomscrolling required.'),
    ],
  }
};

// --- Helper Function ---
const extractTextContent = (words: Text[]): string => {
  return words.map(word => word.text).join('');
};

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
const Sentence = ({
  words,
  onNavigate
}: {
  words: Text[];
  onNavigate?: (target: string, displayType: DisplayType) => void;
}) => {
  const typingIds = useRecoilValue(typingIdsState);

  return (
    <>
      {words.map((word, index) => {
        // Check if word has a custom renderWith component
        if (word.renderWith) {
          const WrapperComponent = word.renderWith;

          // For external links (has url property)
          if (word.url) {
            return <WrapperComponent key={index} url={word.url}>{word.text}</WrapperComponent>;
          }

          // For internal links (has target property)
          if (word.target && onNavigate) {
            // Check if this link's target is currently typing
            const isTargetTyping = typingIds.has(word.target);

            // If target is typing, render as plain text
            if (isTargetTyping) {
              return <span key={index}>{word.text}</span>;
            }

            // Render as clickable link with custom wrapper
            return (
              <WrapperComponent
                key={index}
                onClick={() => onNavigate(word.target!, word.displayType || 'new-paragraph')}
              >
                {word.text}
              </WrapperComponent>
            );
          }
        }

        // Plain text
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
  onComplete,
  onNavigate,
  onDelete
}: {
  node: TextNode;
  isDone: boolean;
  isDeleting: boolean;
  onComplete: () => void;
  onNavigate?: (target: string, displayType: DisplayType) => void;
  onDelete?: (target: string) => void;
}) => {
  if (isDeleting) {
    return (
      <Typewriter
        sentence={node.words}
        onComplete={onComplete}
        inline
        delete
        onNavigate={onNavigate}
        onDelete={onDelete}
      />
    );
  }

  if (isDone) {
    return <Sentence words={node.words} onNavigate={onNavigate} />;
  }

  return (
    <Typewriter
      sentence={node.words}
      onComplete={onComplete}
      nodeId={node.id}
      inline
      onNavigate={onNavigate}
      onDelete={onDelete}
    />
  );
};

// --- Paragraph Component ---
const ParagraphComponent = ({
  sentences,
  deletingIds,
  onDeleteComplete,
  highlightedNodeId,
  nodeRefs,
  onNavigate,
  onDelete
}: {
  sentences: TextNode[];
  deletingIds: Set<string>;
  onDeleteComplete: (id: string) => void;
  highlightedNodeId: string | null;
  nodeRefs: React.MutableRefObject<Record<string, React.RefObject<HTMLSpanElement>>>;
  onNavigate?: (target: string, displayType: DisplayType) => void;
  onDelete?: (target: string) => void;
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
        const isDone = completionState[idx] || false;

        // Create ref if it doesn't exist
        if (!nodeRefs.current[node.id]) {
          nodeRefs.current[node.id] = React.createRef<HTMLSpanElement>();
        }

        return (
          <React.Fragment key={`${node.id}-${idx}`}>
            <HighlightWrapper
              $isHighlighted={highlightedNodeId === node.id}
              ref={nodeRefs.current[node.id]}
            >
              <SegmentComponent
                node={node}
                isDone={isDone}
                isDeleting={isDeleting}
                onComplete={() => {
                  if (isDeleting) {
                    onDeleteComplete(node.id);
                  } else {
                    handleSegmentComplete(idx);
                  }
                }}
                onNavigate={onNavigate}
                onDelete={onDelete}
              />
            </HighlightWrapper>
            {/* Render media below the text when segment is done and not deleting */}
            {node.media && isDone && !isDeleting && (
              <MediaComponent media={node.media} />
            )}
          </React.Fragment>
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
  const [highlightedNodeId, setHighlightedNodeId] = useState<string | null>(null);
  const nodeRefs = useRef<Record<string, React.RefObject<HTMLSpanElement>>>({});
  const containerRef = useRef<HTMLDivElement>(null);

  // Scroll-linked fade effect - track scroll within the container
  const { scrollYProgress } = useScroll({ container: containerRef });
  const maskImage = useScrollOverflowMask(scrollYProgress);

  // Use the constant text tree (no need for dummy functions!)
  const finalTextTree = TEXT_TREE;

  // Scroll a node to 15% below top of container (waits for ref if needed)
  const scrollToNode = useCallback((nodeId: string) => {
    const attemptScroll = () => {
      const ref = nodeRefs.current[nodeId];
      const element = ref?.current;

      if (!element || !containerRef.current) {
        // Ref not ready yet, try again
        requestAnimationFrame(attemptScroll);
        return;
      }

      const container = containerRef.current;
      const containerHeight = container.clientHeight;
      const scrollTarget = element.offsetTop - (containerHeight * 0.30);

      container.scrollTo({
        top: scrollTarget,
        behavior: 'smooth'
      });
    };

    // Start attempting to scroll
    requestAnimationFrame(attemptScroll);
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
    // Check if node already exists in paragraphs and is not being deleted
    const nodeExists = paragraphs.some(paragraph => paragraph.includes(targetId));
    const isBeingDeleted = deletingIds.has(targetId);

    if (nodeExists && !isBeingDeleted) {
      // Node exists and is visible - scroll to it and highlight it
      setHighlightedNodeId(targetId);
      scrollToNode(targetId);
      setTimeout(() => setHighlightedNodeId(null), 1500);
      return;
    }

    // If the node is being deleted (e.g., was a child of a deleted parent), cancel its deletion
    if (isBeingDeleted) {
      setDeletingIds(prev => {
        const newSet = new Set(prev);
        newSet.delete(targetId);
        return newSet;
      });
    }

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
      // Scroll to the new paragraph
      scrollToNode(targetId);
    } else if (displayType === 'next-sentence' || displayType === 'new-sentence') {
      // Add to current paragraph
      setParagraphs(prev => {
        const newParagraphs = [...prev];
        const lastParagraph = [...newParagraphs[newParagraphs.length - 1]];
        lastParagraph.push(targetId);
        newParagraphs[newParagraphs.length - 1] = lastParagraph;
        return newParagraphs;
      });
      // Scroll to the new sentence
      scrollToNode(targetId);
    }
  }, [paragraphs, deletingIds, finalTextTree, setTypingIds, scrollToNode]);

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

  // Center the root node on initial mount
  useEffect(() => {
    scrollToNode('root');
  }, [scrollToNode]);

  return (
    <TreeContainer ref={containerRef} style={{ maskImage }} className={className}>
      <div style={{ paddingTop: '50vh', paddingBottom: '50vh' }}>
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
                highlightedNodeId={highlightedNodeId}
                nodeRefs={nodeRefs}
                onNavigate={handleNavigate}
                onDelete={handleDelete}
              />
            ))}
          </>
        )}
      </div>
    </TreeContainer>
  );
}
