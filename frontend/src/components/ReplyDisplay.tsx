import { useEffect, useMemo, useRef, useState } from 'react';
import styled, { css } from 'styled-components';
import { DotLottieReact } from '@lottiefiles/dotlottie-react';
import { AnimatedText } from './WordStyles';
import xLottie from '../assets/x.lottie';

export interface OtherReply {
  text: string;
  author_handle: string;
  author_name: string;
  likes: number;
}

export interface ReplyData {
  id: string;
  cache_id?: string;
  posted_tweet_id?: string;
  text: string;
  likes: number;
  retweets: number;
  quotes: number;
  replies: number;
  impressions?: number;
  handle: string;
  score: number;
  username: string;
  followers: number;
  reply?: string;
  generated_replies?: Array<[string, string]>;
  other_replies?: OtherReply[];
  created_at: string;
  url: string;
  thread?: string[];
  author_profile_pic_url?: string;
  scraped_from?: {
    type: 'account' | 'query' | 'home_timeline';
    value: string;
    summary?: string;
  };
  media?: Array<{
    type: 'photo';
    url: string;
    alt_text?: string;
  }>;
  parent_media?: Array<{
    type: 'photo';
    url: string;
    alt_text?: string;
  }>;
  quoted_tweet?: {
    text: string;
    author_name: string;
    author_handle: string;
    author_profile_pic_url?: string;
    media?: Array<{type: 'photo'; url: string; alt_text?: string}>;
    created_at: string;
    url: string;
  };
  /** Flag to indicate this tweet has been locally edited and should not be overwritten by polling */
  edited?: boolean;
}

interface ReplyDisplayProps {
  tweet: ReplyData;
  myProfilePicUrl: string;
  maxReplies?: number;
  onPublish: (text: string, replyIndex: number) => void;
  onSkip: () => void;
  onEditReply?: (newReply: string, replyIndex: number) => void;
  onRegenerate?: () => void;
  isDeleting?: boolean;
  isPosting?: boolean;
  isRegenerating?: boolean;
  readOnly?: boolean;
  showDeleteButton?: boolean;
  isJobRunning?: boolean;
}

// Styled Components
const Container = styled.div<{ $isDeleting: boolean; $isPosting: boolean }>`
  width: 100%;
  padding-left: 2%;
  padding-right: 2%;
  padding-bottom: 4%;
  border-radius: 1rem;
  background-color: black;
  color: white;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
  transition: all 0.3s;

  ${({ $isDeleting }) => $isDeleting && css`
    transform: scale(0.95);
    opacity: 0;
  `}

  ${({ $isPosting }) => $isPosting && css`
    transition-duration: 0.4s;
    transform: translateX(150%);
    opacity: 0;
  `}

  ${({ $isDeleting, $isPosting }) => !$isDeleting && !$isPosting && css`
    transform: scale(1) translateX(0);
    opacity: 1;
  `}
`;

const Header = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.25rem;
  margin-left: -20px;
  margin-bottom: 0.5rem;
`;

const DeleteButton = styled.button`
  position: relative;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  border-radius: 9999px;
  transition: background-color 0.2s;
  height: 2.5rem;
  width: 2.5rem;
  justify-content: center;
  background: transparent;
  border: none;
  cursor: pointer;

  &:hover {
    background-color: #262626;
  }
`;

const LottieContainer = styled.div`
  width: 2rem;
  height: 2rem;
  display: flex;
  align-items: center;
  justify-content: center;
`;

const DeleteIcon = styled.span`
  font-size: 1.25rem;
  color: white;
`;

const ExternalLink = styled.a`
  margin-left: auto;
  color: #a3a3a3;
  transition: color 0.2s;

  &:hover {
    color: #38bdf8;
  }

  i {
    font-size: 0.875rem;
  }
`;

const ContentWrapper = styled.div`
  padding: 0.75rem 1.25rem;
`;

const ThreadContainer = styled.div`
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding-bottom: 0.25rem;
`;

const ThreadMessage = styled.div`
  position: relative;
  display: flex;
  gap: 0.75rem;
`;

const Avatar = styled.img`
  height: 3rem;
  width: 3rem;
  border-radius: 9999px;
`;

const AvatarPlaceholder = styled.div`
  height: 3rem;
  width: 3rem;
`;

const MessageContent = styled.div`
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding-bottom: 1rem;
`;

const MetaInfo = styled.div`
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: #a3a3a3;
`;

const DisplayName = styled.span`
  font-size: 1rem;
  font-weight: 700;
  color: white;
`;

const Badge = styled.div`
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.125rem 0.5rem;
  border-radius: 9999px;
  background-color: #262626;
  font-size: 0.75rem;
  color: #a3a3a3;
`;

const MediaBadge = styled(Badge)`
  background-color: rgba(30, 58, 138, 0.3);
  color: #60a5fa;
`;

const TweetText = styled.p`
  white-space: pre-wrap;
  font-size: 1.125rem;
  line-height: 1.75;
  color: white;
  margin: 0;
`;

const QuotedTweetLink = styled.a`
  margin-top: 0.75rem;
  display: block;
  border-radius: 1rem;
  border: 1px solid #404040;
  padding: 0.75rem;
  transition: background-color 0.2s;
  text-decoration: none;

  &:hover {
    background-color: #171717;
  }
`;

const QuotedTweetHeader = styled.div`
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
`;

const QuotedTweetAvatar = styled.img`
  height: 1.25rem;
  width: 1.25rem;
  border-radius: 9999px;
`;

const QuotedTweetMeta = styled.div`
  display: flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.875rem;
`;

const QuotedTweetAuthor = styled.span`
  font-weight: 600;
  color: #d4d4d4;
`;

const QuotedTweetHandle = styled.span`
  color: #737373;
`;

const QuotedTweetText = styled.p`
  white-space: pre-wrap;
  font-size: 0.875rem;
  color: #d4d4d4;
  margin: 0 0 0.5rem 0;
`;

const QuotedTweetMedia = styled.div`
  border-radius: 0.75rem;
  overflow: hidden;
  margin-top: 0.5rem;

  img {
    width: 100%;
    max-height: 12rem;
    object-fit: cover;
  }
`;

const MediaGrid = styled.div<{ $count: number }>`
  margin-top: 0.75rem;
  border-radius: 1rem;
  overflow: hidden;
  border: 1px solid #262626;

  ${({ $count }) => $count === 1 && css`
    max-width: 42rem;
  `}

  ${({ $count }) => $count >= 2 && css`
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 2px;
  `}
`;

const MediaImage = styled.img<{ $count: number; $index: number }>`
  width: 100%;

  ${({ $count }) => $count === 1 && css`
    object-fit: contain;
    max-height: 600px;
  `}

  ${({ $count, $index }) => $count === 3 && $index === 0 && css`
    grid-row: span 2;
    height: 100%;
    object-fit: cover;
  `}

  ${({ $count, $index }) => ($count >= 2 && !($count === 3 && $index === 0)) && css`
    height: 12rem;
    object-fit: cover;
  `}
`;

const ThreadDivider = styled.div`
  position: absolute;
  left: 3.5rem;
  right: 3.5rem;
  bottom: 0;
  border-top: 1px solid #262626;
`;

const EngagementBar = styled.div`
  display: flex;
  align-items: center;
  gap: 2rem;
  padding-left: 3.5rem;
  font-size: 0.875rem;
  color: #737373;
`;

const EngagementItem = styled.div`
  display: flex;
  align-items: center;
  gap: 0.5rem;

  i {
    font-size: 1.125rem;
    color: #737373;
  }

  span {
    font-weight: 500;
  }
`;

const ReplyingToText = styled.p`
  font-size: 0.875rem;
  color: #737373;
  padding-top: 1.75rem;
  margin: 0;

  span {
    color: #38bdf8;
  }
`;

const ReplySection = styled.div`
  display: flex;
  gap: 0.75rem;
  padding-top: 1.5rem;
`;

const ReplyAvatar = styled.img`
  height: 3rem;
  width: 3rem;
  border-radius: 9999px;
  flex-shrink: 0;
`;

const RepliesContainer = styled.div`
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 1rem;
`;

const ReplyDivider = styled.div`
  border-top: 1px solid #404040;
  margin-bottom: 1rem;
`;

const ReplyInputRow = styled.div`
  display: flex;
  align-items: center;
  gap: 2rem;
`;

const TextareaWrapper = styled.div`
  position: relative;
  flex: 1;
`;

const ReplyTextarea = styled.textarea`
  width: 100%;
  min-height: 6rem;
  resize: none;
  overflow-y: hidden;
  background: transparent;
  font-size: 1.125rem;
  color: white;
  outline: none;
  border: none;
  padding-right: 0.5rem;
  padding-bottom: 2rem;
  font-family: inherit;
  field-sizing: content;

  &::placeholder {
    color: #525252;
  }

  &::-webkit-scrollbar {
    width: 4px;
  }

  &::-webkit-scrollbar-track {
    background: transparent;
  }

  &::-webkit-scrollbar-thumb {
    background: #404040;
    border-radius: 2px;
  }

  &:hover::-webkit-scrollbar-thumb {
    background: #525252;
  }
`;

const FadeOverlay = styled.div`
  pointer-events: none;
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 1.5rem;
  background: linear-gradient(to top, black, transparent);
`;

const PostButton = styled.button`
  border-radius: 9999px;
  background-color: #0ea5e9;
  padding: 0.5rem 1.25rem;
  font-size: 0.875rem;
  font-weight: 600;
  color: white;
  transition: background-color 0.2s;
  border: none;
  cursor: pointer;
  align-self: flex-start;
  margin-top: 1.75rem;
  flex-shrink: 0;

  &:hover {
    background-color: #0284c7;
  }
`;

const ReadOnlyReply = styled.div`
  position: relative;
  max-height: 12rem;
  overflow-y: auto;

  &::-webkit-scrollbar {
    width: 4px;
  }

  &::-webkit-scrollbar-track {
    background: transparent;
  }

  &::-webkit-scrollbar-thumb {
    background: #404040;
    border-radius: 2px;
  }

  &:hover::-webkit-scrollbar-thumb {
    background: #525252;
  }
`;

const ReadOnlyText = styled.p`
  white-space: pre-wrap;
  font-size: 1.125rem;
  line-height: 1.75;
  color: white;
  margin: 0;
`;

const OtherRepliesSection = styled.div`
  margin-top: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid #262626;
`;

const OtherRepliesButton = styled.button`
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: #a3a3a3;
  transition: color 0.2s;
  width: 100%;
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 0;

  &:hover {
    color: #d4d4d4;
  }

  i {
    font-size: 0.75rem;
    transition: transform 0.2s;
  }

  span {
    font-weight: 500;
  }
`;

const OtherReplyPreview = styled.div`
  margin-top: 0.75rem;
  position: relative;
`;

const OtherReplyRow = styled.div`
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
`;

const OtherReplyAvatar = styled.div`
  height: 1.5rem;
  width: 1.5rem;
  border-radius: 9999px;
  background-color: #404040;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;

  i {
    font-size: 0.75rem;
    color: #a3a3a3;
  }
`;

const OtherReplyContent = styled.div`
  flex: 1;
  min-width: 0;
`;

const OtherReplyMeta = styled.div`
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: #737373;
`;

const OtherReplyAuthor = styled.span`
  font-weight: 500;
  color: #a3a3a3;
`;

const OtherReplyHandle = styled.span`
  color: #525252;
`;

const OtherReplyLikes = styled.span`
  display: flex;
  align-items: center;
  gap: 0.25rem;
`;

const OtherReplyText = styled.p<{ $preview?: boolean }>`
  font-size: 1.125rem;
  line-height: 1.75;
  color: ${({ $preview }) => $preview ? '#a3a3a3' : '#d4d4d4'};
  margin: 0.25rem 0 0 0;
  white-space: pre-wrap;

  ${({ $preview }) => $preview && css`
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  `}
`;

const OtherRepliesList = styled.div`
  margin-top: 1rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  max-height: 20rem;
  overflow-y: auto;
  padding-right: 0.5rem;

  &::-webkit-scrollbar {
    width: 4px;
  }

  &::-webkit-scrollbar-track {
    background: transparent;
  }

  &::-webkit-scrollbar-thumb {
    background: #404040;
    border-radius: 2px;
  }
`;

const FadeToBlack = styled.div`
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 5rem;
  background: linear-gradient(to top, black, transparent);
  pointer-events: none;
`;

const ActionButtons = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 1rem 1.25rem 2rem;
`;

const SaveButton = styled.button<{ $disabled: boolean }>`
  border-radius: 9999px;
  padding: 0.5rem 1.25rem;
  font-size: 0.875rem;
  font-weight: 600;
  transition: background-color 0.2s;
  border: none;

  ${({ $disabled }) => $disabled ? css`
    background-color: #262626;
    color: #737373;
    cursor: not-allowed;
  ` : css`
    background-color: #404040;
    color: white;
    cursor: pointer;

    &:hover {
      background-color: #525252;
    }
  `}
`;

const RegenerateButton = styled.button`
  border-radius: 9999px;
  background-color: #404040;
  padding: 0.5rem 1.25rem;
  font-size: 0.875rem;
  font-weight: 600;
  color: white;
  transition: background-color 0.2s;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.5rem;

  &:hover {
    background-color: #525252;
  }
`;

const RegeneratingContainer = styled.div`
  display: flex;
  gap: 0.75rem;
  padding-top: 1.5rem;
`;

const RegeneratingContent = styled.div`
  flex: 1;
  width: 100%;
  min-height: 6rem;
  display: flex;
  align-items: flex-start;
  padding-top: 0.5rem;
`;

// Helper function to get a display label for query sources
function getQueryDisplayLabel(scrapedFrom: ReplyData['scraped_from']): string {
  if (!scrapedFrom || scrapedFrom.type !== 'query') {
    return 'Custom Query';
  }

  const summary = scrapedFrom.summary;
  const query = scrapedFrom.value;

  // If no summary or summary is null/empty, show fallback
  if (!summary) {
    return 'Custom Query';
  }

  // If summary equals the full query (migration default), show fallback
  if (summary === query) {
    return 'Custom Query';
  }

  // Otherwise use the summary
  return summary;
}

export function ReplyDisplay({ tweet, myProfilePicUrl, maxReplies, onPublish, onSkip, onEditReply, onRegenerate, isDeleting = false, isPosting = false, readOnly = false, isRegenerating = false, showDeleteButton = !readOnly, isJobRunning = false }: ReplyDisplayProps) {
  const allReplies = tweet.generated_replies
    ? tweet.generated_replies.map(r => Array.isArray(r) ? r[0] : r)
    : (tweet.reply ? [tweet.reply] : []);

  const generatedReplies = maxReplies ? allReplies.slice(0, maxReplies) : allReplies;
  const hasNoReplies = generatedReplies.length === 0 || generatedReplies.every(r => !r);
  const isGeneratingReplies = hasNoReplies && isJobRunning && !readOnly;

  const [editedTexts, setEditedTexts] = useState<string[]>(generatedReplies);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState<boolean[]>(generatedReplies.map(() => false));
  const [isDeleteHovered, setIsDeleteHovered] = useState(false);
  const [otherRepliesExpanded, setOtherRepliesExpanded] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);
  // Ref to track if user has made any local edits (survives useEffect dependency changes)
  const hasDirtyEditsRef = useRef(false);

  const displayName = tweet.username;
  const handle = tweet.handle;
  const userAvatar = tweet.author_profile_pic_url || 'https://abs.twimg.com/sticky/default_profile_images/default_profile_400x400.png';
  const myAvatar = myProfilePicUrl;

  const threadMessages = useMemo(() => [...(tweet.thread ?? [])], [tweet.thread]);

  useEffect(() => {
    // Don't reset local edits if:
    // 1. Tweet is marked as edited in parent state (being saved to backend)
    // 2. User has made local edits that haven't been saved yet (hasDirtyEditsRef)
    // This prevents polling from overwriting unsaved changes
    if (tweet.edited || hasDirtyEditsRef.current) {
      return;
    }

    const allNewReplies = tweet.generated_replies
      ? tweet.generated_replies.map(r => Array.isArray(r) ? r[0] : r)
      : (tweet.reply ? [tweet.reply] : []);
    const newReplies = maxReplies ? allNewReplies.slice(0, maxReplies) : allNewReplies;
    setEditedTexts(newReplies);
    setHasUnsavedChanges(newReplies.map(() => false));
  }, [tweet.id, tweet.reply, tweet.generated_replies, maxReplies, tweet.edited]);

  const handleTextChange = (index: number, newText: string) => {
    const newEditedTexts = [...editedTexts];
    newEditedTexts[index] = newText;
    setEditedTexts(newEditedTexts);

    const allOriginalReplies = tweet.generated_replies
      ? tweet.generated_replies.map(r => Array.isArray(r) ? r[0] : r)
      : (tweet.reply ? [tweet.reply] : []);
    const originalReplies = maxReplies ? allOriginalReplies.slice(0, maxReplies) : allOriginalReplies;
    const newHasUnsavedChanges = [...hasUnsavedChanges];
    const hasChanged = newText !== originalReplies[index];
    newHasUnsavedChanges[index] = hasChanged;
    setHasUnsavedChanges(newHasUnsavedChanges);

    // Update dirty ref based on whether any changes remain unsaved
    hasDirtyEditsRef.current = newHasUnsavedChanges.some(changed => changed);

    // Auto-save to backend after 1.5 seconds of no typing
    // This ensures edits persist even if UI re-renders from polling
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }
    if (hasChanged && onEditReply) {
      debounceTimerRef.current = setTimeout(() => {
        onEditReply(newText, index);
        // Mark as saved locally
        setHasUnsavedChanges(prev => {
          const updated = [...prev];
          updated[index] = false;
          return updated;
        });
        hasDirtyEditsRef.current = false;
      }, 1500);
    }
  };

  const handleSave = async (index: number) => {
    const allOriginalReplies = tweet.generated_replies
      ? tweet.generated_replies.map(r => Array.isArray(r) ? r[0] : r)
      : (tweet.reply ? [tweet.reply] : []);
    const originalReplies = maxReplies ? allOriginalReplies.slice(0, maxReplies) : allOriginalReplies;
    if (onEditReply && editedTexts[index] !== originalReplies[index]) {
      onEditReply(editedTexts[index], index);
      const newHasUnsavedChanges = [...hasUnsavedChanges];
      newHasUnsavedChanges[index] = false;
      setHasUnsavedChanges(newHasUnsavedChanges);

      // Clear dirty ref if no more unsaved changes remain
      if (!newHasUnsavedChanges.some(changed => changed)) {
        hasDirtyEditsRef.current = false;
      }
    }
  };

  const handlePublish = (index: number) => {
    const allOriginalReplies = tweet.generated_replies
      ? tweet.generated_replies.map(r => Array.isArray(r) ? r[0] : r)
      : (tweet.reply ? [tweet.reply] : []);
    const originalReplies = maxReplies ? allOriginalReplies.slice(0, maxReplies) : allOriginalReplies;
    if (hasUnsavedChanges[index] && onEditReply && editedTexts[index] !== originalReplies[index]) {
      onEditReply(editedTexts[index], index);
    }
    onPublish(editedTexts[index], index);
  };

  useEffect(() => {
    const timer = debounceTimerRef.current;
    return () => {
      if (timer) {
        clearTimeout(timer);
      }
    };
  }, []);

  const getRelativeTime = (dateStr: string): string => {
    try {
      const tweetDate = new Date(dateStr);
      const now = new Date();
      const diffHours = Math.floor((now.getTime() - tweetDate.getTime()) / (1000 * 60 * 60));

      if (diffHours < 1) return 'now';
      if (diffHours < 24) return `${diffHours}h`;
      if (diffHours < 48) return '1d';
      return `${Math.floor(diffHours / 24)}d`;
    } catch {
      return '';
    }
  };

  const formatMetric = (value: number): string => {
    if (value >= 1000000) return `${(value / 1000000).toFixed(1).replace(/\.0$/, '')}M`;
    if (value >= 1000) return `${(value / 1000).toFixed(1).replace(/\.0$/, '')}K`;
    return String(value);
  };

  return (
    <Container $isDeleting={isDeleting} $isPosting={isPosting}>
      <Header>
        {showDeleteButton && (
          <DeleteButton
            type="button"
            onClick={onSkip}
            onMouseEnter={() => setIsDeleteHovered(true)}
            onMouseLeave={() => setIsDeleteHovered(false)}
            aria-label={readOnly ? "Delete tweet from Twitter" : "Delete"}
            title={readOnly ? "Delete tweet from Twitter" : "Delete"}
          >
            {isDeleteHovered ? (
              <LottieContainer>
                <DotLottieReact
                  src={xLottie}
                  loop
                  autoplay
                />
              </LottieContainer>
            ) : (
              <DeleteIcon>×</DeleteIcon>
            )}
          </DeleteButton>
        )}
        <ExternalLink
          href={tweet.url}
          target="_blank"
          rel="noopener noreferrer"
          aria-label="View original tweet on Twitter"
          title="View on Twitter"
        >
          <i className="fa-solid fa-arrow-up-right-from-square" />
        </ExternalLink>
      </Header>

      <ContentWrapper>
        <ThreadContainer>
          {threadMessages.map((message, index) => (
            <ThreadMessage key={`${tweet.id}-${index}`}>
              {index === 0 ? (
                <Avatar src={userAvatar} alt={displayName} />
              ) : (
                <AvatarPlaceholder aria-hidden="true" />
              )}
              <MessageContent>
                {index === 0 && (
                  <MetaInfo>
                    <DisplayName>{displayName}</DisplayName>
                    <span>{'@' + handle}</span>
                    {tweet.created_at && <span>· {getRelativeTime(tweet.created_at)}</span>}
                    {tweet.scraped_from && (
                      <Badge>
                        <i className={`fa-solid ${
                          tweet.scraped_from.type === 'account' ? 'fa-user' :
                          tweet.scraped_from.type === 'home_timeline' ? 'fa-house' :
                          'fa-magnifying-glass'
                        }`} />
                        <span>
                          {tweet.scraped_from.type === 'account'
                            ? `@${tweet.scraped_from.value}`
                            : tweet.scraped_from.type === 'home_timeline'
                            ? 'For You'
                            : getQueryDisplayLabel(tweet.scraped_from)}
                        </span>
                      </Badge>
                    )}
                    {/* Show parent media badge - prefer parent_media, fallback to media for backward compatibility */}
                    {((tweet.parent_media && tweet.parent_media.length > 0) || (tweet.media && tweet.media.length > 0 && !tweet.parent_media)) && (
                      <MediaBadge>
                        <i className="fa-solid fa-image" />
                        <span>{(tweet.parent_media || tweet.media)!.length} image{(tweet.parent_media || tweet.media)!.length > 1 ? 's' : ''}</span>
                      </MediaBadge>
                    )}
                  </MetaInfo>
                )}
                <TweetText>{message}</TweetText>

                {index === 0 && tweet.quoted_tweet && (
                  <QuotedTweetLink
                    href={tweet.quoted_tweet.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <QuotedTweetHeader>
                      <QuotedTweetAvatar
                        src={tweet.quoted_tweet.author_profile_pic_url || 'https://abs.twimg.com/sticky/default_profile_images/default_profile_400x400.png'}
                        alt={tweet.quoted_tweet.author_name}
                      />
                      <QuotedTweetMeta>
                        <QuotedTweetAuthor>{tweet.quoted_tweet.author_name}</QuotedTweetAuthor>
                        <QuotedTweetHandle>@{tweet.quoted_tweet.author_handle}</QuotedTweetHandle>
                      </QuotedTweetMeta>
                    </QuotedTweetHeader>

                    <QuotedTweetText>
                      {tweet.quoted_tweet.text}
                    </QuotedTweetText>

                    {tweet.quoted_tweet.media && tweet.quoted_tweet.media.length > 0 && (
                      <QuotedTweetMedia>
                        {tweet.quoted_tweet.media.map((media, idx) => (
                          <img
                            key={idx}
                            src={media.url}
                            alt={media.alt_text || ''}
                          />
                        ))}
                      </QuotedTweetMedia>
                    )}
                  </QuotedTweetLink>
                )}

                {/* Show parent media at the end of the thread (last message) */}
                {index === threadMessages.length - 1 && (() => {
                  // Use parent_media if available, fallback to media for backward compatibility
                  const parentMediaToShow = tweet.parent_media || tweet.media;
                  return parentMediaToShow && parentMediaToShow.length > 0 && (
                    <MediaGrid $count={parentMediaToShow.length}>
                      {parentMediaToShow.map((mediaItem, mediaIndex) => (
                        <MediaImage
                          key={mediaIndex}
                          src={mediaItem.url}
                          alt={mediaItem.alt_text || `Image ${mediaIndex + 1}`}
                          $count={parentMediaToShow.length}
                          $index={mediaIndex}
                          loading="lazy"
                        />
                      ))}
                    </MediaGrid>
                  );
                })()}

                {index < threadMessages.length - 1 && (
                  <ThreadDivider aria-hidden="true" />
                )}
              </MessageContent>
            </ThreadMessage>
          ))}
        </ThreadContainer>

        <EngagementBar aria-label="Tweet engagement">
          <EngagementItem>
            <i className="fa-regular fa-comment" aria-hidden="true" />
            <span>{formatMetric(tweet.replies)}</span>
          </EngagementItem>
          <EngagementItem>
            <i className="fa-solid fa-retweet" aria-hidden="true" />
            <span>{formatMetric(tweet.retweets)}</span>
          </EngagementItem>
          <EngagementItem>
            <i className="fa-regular fa-heart" aria-hidden="true" />
            <span>{formatMetric(tweet.likes)}</span>
          </EngagementItem>
          {tweet.impressions !== undefined && tweet.impressions > 0 && (
            <EngagementItem>
              <i className="fa-regular fa-eye" aria-hidden="true" />
              <span>{formatMetric(tweet.impressions)}</span>
            </EngagementItem>
          )}
        </EngagementBar>

        {!readOnly ? (
          <>
            <ReplyingToText>
              Replying to <span>{'@' + handle}</span>
            </ReplyingToText>
            {isRegenerating ? (
              <RegeneratingContainer>
                <ReplyAvatar src={myAvatar} alt="Your avatar" />
                <RegeneratingContent>
                  <AnimatedText
                    text="Regenerating replies"
                    className="text-lg"
                  />
                </RegeneratingContent>
              </RegeneratingContainer>
            ) : isGeneratingReplies ? (
              <RegeneratingContainer>
                <ReplyAvatar src={myAvatar} alt="Your avatar" />
                <RegeneratingContent>
                  <AnimatedText
                    text="Generating replies"
                    className="text-lg"
                  />
                </RegeneratingContent>
              </RegeneratingContainer>
            ) : (
              <ReplySection>
                <ReplyAvatar src={myAvatar} alt="Your avatar" />
                <RepliesContainer>
                  {editedTexts.map((text, index) => (
                    <div key={index}>
                      {index > 0 && <ReplyDivider />}
                      <ReplyInputRow>
                        <TextareaWrapper>
                          <ReplyTextarea
                            ref={index === 0 ? textareaRef : undefined}
                            placeholder="Post your reply"
                            value={text}
                            onChange={(e) => handleTextChange(index, e.target.value)}
                          />
                          <FadeOverlay />
                        </TextareaWrapper>
                        <PostButton
                          type="button"
                          onClick={() => handlePublish(index)}
                        >
                          Post
                        </PostButton>
                      </ReplyInputRow>
                    </div>
                  ))}
                </RepliesContainer>
              </ReplySection>
            )}
          </>
        ) : (
          editedTexts.length > 0 && editedTexts.some(text => text) && (
            <>
              <ReplyingToText>
                Your reply to <span>{'@' + handle}</span>
              </ReplyingToText>
              <ReplySection>
                <ReplyAvatar src={myAvatar} alt="Your avatar" />
                <RepliesContainer>
                  {editedTexts.map((text, index) => (
                    text && (
                      <div key={index}>
                        {index > 0 && <ReplyDivider />}
                        <ReadOnlyReply>
                          <ReadOnlyText>{text}</ReadOnlyText>
                          <FadeOverlay />
                        </ReadOnlyReply>
                      </div>
                    )
                  ))}
                  {/* Show reply's own media at the end of the reply section (readOnly mode) */}
                  {tweet.media && tweet.media.length > 0 && tweet.parent_media && (
                    <MediaGrid $count={tweet.media.length}>
                      {tweet.media.map((mediaItem, mediaIndex) => (
                        <MediaImage
                          key={mediaIndex}
                          src={mediaItem.url}
                          alt={mediaItem.alt_text || `Image ${mediaIndex + 1}`}
                          $count={tweet.media?.length ?? 0}
                          $index={mediaIndex}
                          loading="lazy"
                        />
                      ))}
                    </MediaGrid>
                  )}
                </RepliesContainer>
              </ReplySection>
            </>
          )
        )}

        {tweet.other_replies && tweet.other_replies.length > 0 && (
          <OtherRepliesSection>
            <OtherRepliesButton
              type="button"
              onClick={() => setOtherRepliesExpanded(!otherRepliesExpanded)}
            >
              <i className={`fa-solid fa-chevron-${otherRepliesExpanded ? 'up' : 'down'}`} />
              <span>
                {otherRepliesExpanded ? 'Hide' : 'Show'} top replies ({tweet.other_replies.length})
              </span>
            </OtherRepliesButton>

            {!otherRepliesExpanded && tweet.other_replies[0] && (
              <OtherReplyPreview>
                <OtherReplyRow>
                  <OtherReplyAvatar>
                    <i className="fa-solid fa-user" />
                  </OtherReplyAvatar>
                  <OtherReplyContent>
                    <OtherReplyMeta>
                      <OtherReplyAuthor>@{tweet.other_replies[0].author_handle}</OtherReplyAuthor>
                      <span>·</span>
                      <OtherReplyLikes>
                        <i className="fa-regular fa-heart" />
                        {tweet.other_replies[0].likes}
                      </OtherReplyLikes>
                    </OtherReplyMeta>
                    <OtherReplyText $preview>
                      {tweet.other_replies[0].text.replace(/^@\w+\s*/, '')}
                    </OtherReplyText>
                  </OtherReplyContent>
                </OtherReplyRow>
                <FadeToBlack />
              </OtherReplyPreview>
            )}

            {otherRepliesExpanded && (
              <OtherRepliesList>
                {tweet.other_replies.map((reply, idx) => (
                  <OtherReplyRow key={idx}>
                    <OtherReplyAvatar>
                      <i className="fa-solid fa-user" />
                    </OtherReplyAvatar>
                    <OtherReplyContent>
                      <OtherReplyMeta>
                        <OtherReplyAuthor>{reply.author_name}</OtherReplyAuthor>
                        <OtherReplyHandle>@{reply.author_handle}</OtherReplyHandle>
                        <span>·</span>
                        <OtherReplyLikes>
                          <i className="fa-regular fa-heart" />
                          {reply.likes}
                        </OtherReplyLikes>
                      </OtherReplyMeta>
                      <OtherReplyText>
                        {reply.text.replace(/^@\w+\s*/, '')}
                      </OtherReplyText>
                    </OtherReplyContent>
                  </OtherReplyRow>
                ))}
              </OtherRepliesList>
            )}
          </OtherRepliesSection>
        )}
      </ContentWrapper>

      {!readOnly && (
        <ActionButtons>
          <SaveButton
            type="button"
            onClick={async () => {
              for (let i = 0; i < editedTexts.length; i++) {
                if (hasUnsavedChanges[i]) {
                  await handleSave(i);
                }
              }
            }}
            disabled={!hasUnsavedChanges.some(changed => changed)}
            $disabled={!hasUnsavedChanges.some(changed => changed)}
          >
            Save All
          </SaveButton>
          {onRegenerate && (
            <RegenerateButton
              type="button"
              onClick={onRegenerate}
            >
              <i className="fa-solid fa-rotate-right" />
              Regenerate
            </RegenerateButton>
          )}
        </ActionButtons>
      )}
    </Container>
  );
}
