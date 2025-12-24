import { useState } from 'react';
import styled, { css } from 'styled-components';
import { motion, AnimatePresence } from 'framer-motion';
import { type PostWithComments as CommentGroupData, type CommentWithContext } from '../api/client';
import { AnimatedText } from './WordStyles';
import { QuotedTweetDisplay, TweetMediaGrid } from './TweetMediaComponents';
import { JobProgressButton } from './JobProgressButton';

const Container = styled.div<{ $expanded: boolean }>`
  width: 100%;
  padding-left: 2%;
  padding-right: 2%;
  padding-bottom: 2%;
  border-radius: 1rem;
  background-color: black;
  color: white;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
  display: flex;
  flex-direction: column;
  max-height: ${({ $expanded }) => $expanded ? '90vh' : '75vh'};
  transition: max-height 0.3s ease;
`;

const PostSection = styled.div<{ $expanded: boolean }>`
  padding: 1rem 1.25rem 1.5rem 1.25rem;
  flex: ${({ $expanded }) => $expanded ? '0 0 auto' : '0 0 auto'};
  max-height: ${({ $expanded }) => $expanded ? 'none' : '14rem'};
  min-height: 0;
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: ${({ $expanded }) => $expanded ? 'visible' : 'hidden'};
  transition: all 0.3s ease;
`;

const PostHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.75rem;
  flex-shrink: 0;
`;

const PostLabel = styled.div`
  font-size: 0.875rem;
  color: #737373;
  display: flex;
  align-items: center;
  gap: 0.5rem;
`;

const CommentsCount = styled.span`
  background: rgba(14, 165, 233, 0.15);
  color: #38bdf8;
  padding: 0.125rem 0.5rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 500;
`;

const ExpandButton = styled.button`
  background: transparent;
  border: none;
  color: #737373;
  font-size: 0.75rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.25rem 0.5rem;
  border-radius: 0.25rem;
  transition: all 0.2s;

  &:hover {
    color: white;
    background: #262626;
  }

  i {
    font-size: 0.625rem;
  }
`;

const PostContentWrapper = styled.div`
  flex: 1;
  min-height: 0;
  position: relative;
  overflow: hidden;
`;

const PostContent = styled.div`
  display: flex;
  gap: 0.75rem;
`;

const Avatar = styled.img`
  height: 2.5rem;
  width: 2.5rem;
  border-radius: 9999px;
  flex-shrink: 0;
`;

const SmallAvatar = styled.img`
  height: 2.25rem;
  width: 2.25rem;
  border-radius: 9999px;
  flex-shrink: 0;
`;

const PostBody = styled.div`
  flex: 1;
  min-width: 0;
`;

const PostText = styled.p`
  white-space: pre-wrap;
  font-size: 1rem;
  line-height: 1.5;
  color: white;
  margin: 0 0 0.5rem 0;
`;

const PostFade = styled.div`
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 3rem;
  background: linear-gradient(to top, black, transparent);
  pointer-events: none;
`;

const PostStats = styled.div`
  display: flex;
  align-items: center;
  gap: 1.5rem;
  font-size: 0.8rem;
  color: #737373;
  flex-shrink: 0;
  margin-top: 0.5rem;

  i {
    font-size: 0.9rem;
    color: #737373;
  }

  span {
    font-weight: 500;
  }
`;

const StatItem = styled.div`
  display: flex;
  align-items: center;
  gap: 0.375rem;
`;

const PostLink = styled.a`
  color: #38bdf8;
  font-size: 0.75rem;
  text-decoration: none;
  margin-left: auto;

  &:hover {
    text-decoration: underline;
  }
`;

const Divider = styled.div`
  border-top: 1px solid #262626;
  margin: 0 1.25rem;
  flex-shrink: 0;
`;

const CommentsScrollArea = styled.div`
  flex: 2;
  overflow-y: auto;
  min-height: 0;
  padding: 1rem 1.25rem;

  &::-webkit-scrollbar {
    width: 6px;
  }

  &::-webkit-scrollbar-track {
    background: transparent;
  }

  &::-webkit-scrollbar-thumb {
    background: #404040;
    border-radius: 3px;
  }

  &:hover::-webkit-scrollbar-thumb {
    background: #525252;
  }
`;

const CommentsGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.75rem;

  @media (max-width: 1200px) {
    grid-template-columns: repeat(2, 1fr);
  }

  @media (max-width: 768px) {
    grid-template-columns: 1fr;
  }
`;

const CommentCard = styled.div<{ $isDeleting?: boolean; $isPosting?: boolean }>`
  background: #0a0a0a;
  border-radius: 0.75rem;
  padding: 1rem;
  transition: all 0.3s ease;
  display: flex;
  flex-direction: column;

  ${({ $isDeleting }) => $isDeleting && css`
    transform: scale(0.95);
    opacity: 0;
  `}

  ${({ $isPosting }) => $isPosting && css`
    transition-duration: 0.4s;
    transform: translateX(150%);
    opacity: 0;
  `}
`;

const CommentHeader = styled.div`
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
`;

const AuthorInfo = styled.div`
  flex: 1;
  min-width: 0;
`;

const Username = styled.span`
  font-size: 0.875rem;
  font-weight: 600;
  color: white;
  display: block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
`;

const Handle = styled.span`
  color: #737373;
  font-size: 0.75rem;
`;

const QuoteTweetBadge = styled.span`
  background: rgba(34, 197, 94, 0.15);
  color: #22c55e;
  padding: 0.125rem 0.5rem;
  border-radius: 9999px;
  font-size: 0.625rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 0.25rem;
  white-space: nowrap;

  i {
    font-size: 0.5rem;
  }
`;

const CommentLink = styled.a`
  color: #525252;
  font-size: 0.875rem;
  transition: color 0.2s;
  flex-shrink: 0;

  &:hover {
    color: #38bdf8;
  }
`;

const CommentText = styled.p<{ $expanded?: boolean }>`
  white-space: pre-wrap;
  font-size: 0.9375rem;
  line-height: 1.5;
  color: #e5e5e5;
  margin: 0 0 0.5rem 0;
  flex: 1;
  ${({ $expanded }) => !$expanded && css`
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  `}
`;

const ExpandTextButton = styled.button`
  background: transparent;
  border: none;
  color: #737373;
  font-size: 0.75rem;
  cursor: pointer;
  padding: 0;
  margin-bottom: 0.5rem;
  transition: color 0.2s;

  &:hover {
    color: #a3a3a3;
  }
`;

const CommentStats = styled.div`
  display: flex;
  align-items: center;
  gap: 1rem;
  font-size: 0.75rem;
  color: #737373;
  margin-bottom: 0.75rem;

  i {
    font-size: 0.875rem;
  }
`;

const ReplySection = styled.div`
  border-top: 1px solid #262626;
  padding-top: 0.75rem;
  margin-top: auto;
`;

const ReplyPreview = styled.div`
  display: flex;
  gap: 0.5rem;
  align-items: flex-start;
`;

const ReplyTextPreview = styled.p`
  font-size: 0.875rem;
  line-height: 1.4;
  color: #a3a3a3;
  margin: 0;
  flex: 1;
  white-space: pre-wrap;
  cursor: text;
  padding: 0.5rem;
  border-radius: 0.375rem;
  transition: background-color 0.2s;

  &:hover {
    background: #171717;
  }
`;

const InlineEditTextarea = styled.textarea`
  flex: 1;
  min-height: 4rem;
  resize: none;
  background: #171717;
  font-size: 0.875rem;
  line-height: 1.4;
  color: white;
  outline: none;
  border: 1px solid #0ea5e9;
  border-radius: 0.375rem;
  padding: 0.5rem;
  font-family: inherit;
`;

const ActionButtons = styled.div`
  display: flex;
  align-items: center;
  gap: 0.25rem;
  margin-top: 0.5rem;
  justify-content: flex-end;
`;

const IconButton = styled.button<{ $variant?: 'primary' | 'danger' | 'secondary' }>`
  width: 2rem;
  height: 2rem;
  border-radius: 9999px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 0.875rem;

  ${({ $variant }) => {
    switch ($variant) {
      case 'primary':
        return css`
          background: #0ea5e9;
          color: white;
          &:hover { background: #0284c7; }
        `;
      case 'danger':
        return css`
          background: transparent;
          color: #737373;
          &:hover { color: #ef4444; background: rgba(239, 68, 68, 0.1); }
        `;
      default:
        return css`
          background: transparent;
          color: #737373;
          &:hover { color: white; background: #404040; }
        `;
    }
  }}

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`;

const BottomBar = styled.div`
  padding: 1rem 1.25rem;
  border-top: 1px solid #262626;
  display: flex;
  justify-content: center;
  flex-shrink: 0;
`;

const PostAllButton = styled.button`
  border-radius: 9999px;
  background-color: #0ea5e9;
  padding: 0.625rem 2rem;
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
    background-color: #0284c7;
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`;

const ReplyAvatar = styled.img`
  height: 1.5rem;
  width: 1.5rem;
  border-radius: 9999px;
  flex-shrink: 0;
`;

const RegeneratingState = styled.div`
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0;
`;

const ThreadContextSection = styled.div`
  margin-top: 0.5rem;
  border-top: 1px solid #262626;
  padding-top: 0.5rem;
`;

const ThreadContextToggle = styled.button`
  display: flex;
  align-items: center;
  gap: 0.375rem;
  font-size: 0.75rem;
  color: #737373;
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 0.25rem 0;
  transition: color 0.2s;

  &:hover {
    color: #a3a3a3;
  }

  i {
    font-size: 0.625rem;
  }
`;

const ThreadContextList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-top: 0.5rem;
  padding: 0.5rem;
  background: #111;
  border-radius: 0.5rem;
`;

const ThreadContextItem = styled.div`
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
`;

const ThreadContextHeader = styled.div`
  display: flex;
  align-items: center;
  gap: 0.375rem;
  font-size: 0.75rem;
`;

const ThreadContextAvatar = styled.img`
  height: 1.25rem;
  width: 1.25rem;
  border-radius: 9999px;
`;

const ThreadContextName = styled.span`
  font-weight: 500;
  color: #a3a3a3;
`;

const ThreadContextHandle = styled.span`
  color: #525252;
`;

const ThreadContextText = styled.p`
  font-size: 0.8125rem;
  line-height: 1.4;
  color: #a3a3a3;
  margin: 0;
  white-space: pre-wrap;
`;

const ThreadContextMediaGrid = styled.div`
  display: flex;
  gap: 0.25rem;
  margin-top: 0.25rem;
  border-radius: 0.375rem;
  overflow: hidden;
`;

const ThreadContextMediaImage = styled.img`
  max-width: 100%;
  max-height: 6rem;
  object-fit: cover;
  border-radius: 0.375rem;
`;

interface CommentItemProps {
  comment: CommentWithContext;
  maxReplies: number;
  myProfilePicUrl?: string;
  originalPostId: string;  // The user's original post ID to exclude from thread context
  onPublish: (text: string, replyIndex: number) => void;
  onSkip: () => void;
  onEditReply?: (newReply: string, replyIndex: number) => void;
  onRegenerate?: () => void;
  isDeleting?: boolean;
  isPosting?: boolean;
  isRegenerating?: boolean;
}

function CommentItem({
  comment,
  maxReplies,
  myProfilePicUrl,
  originalPostId,
  onPublish,
  onSkip,
  onEditReply,
  onRegenerate,
  isDeleting = false,
  isPosting = false,
  isRegenerating = false,
}: CommentItemProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editText, setEditText] = useState('');
  const [isTextExpanded, setIsTextExpanded] = useState(false);
  const [isThreadContextExpanded, setIsThreadContextExpanded] = useState(false);

  // Rough heuristic: if text is longer than ~150 chars, it's likely truncatable
  const isTextTruncatable = comment.text.length > 150;

  // Filter thread context to exclude:
  // 1. The original post (already shown in PostSection)
  // 2. The current comment (shown below the thread context)
  // This shows only intermediate parents between the original post and this comment
  const filteredThreadContext = (comment.thread_context || []).filter(
    ctx => ctx.id !== originalPostId && ctx.id !== comment.id
  );

  // Check if there's thread context to show (parent tweets in the conversation)
  const hasThreadContext = filteredThreadContext.length > 0;

  const generatedReplies = comment.generated_replies || [];
  const displayedReplies = generatedReplies.slice(0, maxReplies);
  const selectedReply = displayedReplies[0];

  const formatMetric = (value: number): string => {
    if (value >= 1000000) return `${(value / 1000000).toFixed(1).replace(/\.0$/, '')}M`;
    if (value >= 1000) return `${(value / 1000).toFixed(1).replace(/\.0$/, '')}K`;
    return String(value);
  };

  const handleStartEdit = () => {
    if (selectedReply) {
      setEditText(selectedReply[0]);
      setIsEditing(true);
    }
  };

  const handleBlurSave = () => {
    // Auto-save on blur if text changed
    if (onEditReply && editText.trim() && selectedReply && editText !== selectedReply[0]) {
      onEditReply(editText, 0);
    }
    setIsEditing(false);
  };

  const handlePublish = () => {
    if (selectedReply) {
      onPublish(selectedReply[0], 0);
    }
  };

  return (
    <CommentCard $isDeleting={isDeleting} $isPosting={isPosting}>
      {/* Thread context section - shows parent tweets between original post and this comment */}
      {hasThreadContext && (
        <ThreadContextSection style={{ borderTop: 'none', marginTop: 0, paddingTop: 0, marginBottom: '0.75rem' }}>
          <ThreadContextToggle onClick={() => setIsThreadContextExpanded(!isThreadContextExpanded)}>
            <i className={`fa-solid fa-chevron-${isThreadContextExpanded ? 'up' : 'down'}`} />
            <span>{isThreadContextExpanded ? 'Hide' : 'Show'} conversation ({filteredThreadContext.length})</span>
          </ThreadContextToggle>
          {isThreadContextExpanded && (
            <ThreadContextList>
              {filteredThreadContext.map((ctx, idx) => (
                <ThreadContextItem key={ctx.id || idx}>
                  <ThreadContextHeader>
                    <ThreadContextAvatar
                      src={ctx.author_profile_pic_url || 'https://abs.twimg.com/sticky/default_profile_images/default_profile_400x400.png'}
                      alt={ctx.username}
                      onError={(e) => {
                        (e.target as HTMLImageElement).src = 'https://abs.twimg.com/sticky/default_profile_images/default_profile_400x400.png';
                      }}
                    />
                    <ThreadContextName>{ctx.username}</ThreadContextName>
                    <ThreadContextHandle>@{ctx.handle}</ThreadContextHandle>
                    {ctx.is_user && <span style={{ color: '#0ea5e9', fontSize: '0.625rem' }}>• You</span>}
                  </ThreadContextHeader>
                  {ctx.deleted ? (
                    <ThreadContextText style={{ fontStyle: 'italic', color: '#525252' }}>
                      This tweet was deleted
                    </ThreadContextText>
                  ) : (
                    <ThreadContextText>{ctx.text}</ThreadContextText>
                  )}
                  {/* Show media for this tweet in thread context */}
                  {ctx.media && ctx.media.length > 0 && (
                    <ThreadContextMediaGrid>
                      {ctx.media.map((mediaItem, mediaIdx) => (
                        <ThreadContextMediaImage
                          key={mediaIdx}
                          src={mediaItem.url}
                          alt={mediaItem.alt_text || `Image ${mediaIdx + 1}`}
                          loading="lazy"
                        />
                      ))}
                    </ThreadContextMediaGrid>
                  )}
                </ThreadContextItem>
              ))}
            </ThreadContextList>
          )}
        </ThreadContextSection>
      )}

      <CommentHeader>
        <SmallAvatar
          src={comment.author_profile_pic_url || 'https://abs.twimg.com/sticky/default_profile_images/default_profile_400x400.png'}
          alt={comment.username}
          onError={(e) => {
            (e.target as HTMLImageElement).src = 'https://abs.twimg.com/sticky/default_profile_images/default_profile_400x400.png';
          }}
        />
        <AuthorInfo>
          <Username>{comment.username}</Username>
          <Handle>@{comment.handle}</Handle>
        </AuthorInfo>
        {comment.engagement_type === 'quote_tweet' && (
          <QuoteTweetBadge title="This user quoted your tweet">
            <i className="fa-solid fa-quote-left" />
            Quoted
          </QuoteTweetBadge>
        )}
        {comment.url && (
          <CommentLink href={comment.url} target="_blank" rel="noopener noreferrer" title="View on X">
            <i className="fa-solid fa-arrow-up-right-from-square" />
          </CommentLink>
        )}
      </CommentHeader>

      <CommentText $expanded={isTextExpanded}>{comment.text}</CommentText>
      {isTextTruncatable && (
        <ExpandTextButton onClick={() => setIsTextExpanded(!isTextExpanded)}>
          {isTextExpanded ? 'Show less' : 'Show more'}
        </ExpandTextButton>
      )}

      {/* Display media if present */}
      {comment.media && comment.media.length > 0 && (
        <TweetMediaGrid media={comment.media} compact />
      )}

      {/* Display quoted tweet if present */}
      {comment.quoted_tweet && (
        <QuotedTweetDisplay quotedTweet={comment.quoted_tweet} compact />
      )}

      <CommentStats>
        <StatItem>
          <i className="fa-regular fa-heart" aria-hidden="true" />
          <span>{formatMetric(comment.likes)}</span>
        </StatItem>
        <StatItem>
          <i className="fa-regular fa-comment" aria-hidden="true" />
          <span>{formatMetric(comment.replies)}</span>
        </StatItem>
      </CommentStats>

      <ReplySection>
        {isRegenerating ? (
          <RegeneratingState>
            {myProfilePicUrl && <ReplyAvatar src={myProfilePicUrl} alt="You" />}
            <AnimatedText text="Generating reply" className="text-sm" />
          </RegeneratingState>
        ) : selectedReply ? (
          <>
            <ReplyPreview>
              {myProfilePicUrl && <ReplyAvatar src={myProfilePicUrl} alt="You" />}
              {isEditing ? (
                <InlineEditTextarea
                  value={editText}
                  onChange={(e) => setEditText(e.target.value)}
                  onBlur={handleBlurSave}
                  autoFocus
                  placeholder="Edit your reply..."
                  onKeyDown={(e) => {
                    if (e.key === 'Escape') {
                      setIsEditing(false);
                      setEditText('');
                    }
                  }}
                />
              ) : (
                <ReplyTextPreview onClick={handleStartEdit}>
                  {selectedReply[0]}
                </ReplyTextPreview>
              )}
            </ReplyPreview>
            <ActionButtons>
              {onRegenerate && (
                <IconButton
                  $variant="secondary"
                  onClick={onRegenerate}
                  disabled={isRegenerating}
                  title="Regenerate reply"
                >
                  <i className="fa-solid fa-rotate-right" />
                </IconButton>
              )}
              <IconButton
                $variant="danger"
                onClick={onSkip}
                disabled={isDeleting}
                title="Skip comment"
              >
                <i className="fa-solid fa-xmark" />
              </IconButton>
              <IconButton
                $variant="primary"
                onClick={handlePublish}
                disabled={isPosting}
                title="Post reply"
              >
                <i className="fa-solid fa-paper-plane" />
              </IconButton>
            </ActionButtons>
          </>
        ) : (
          <ActionButtons style={{ justifyContent: 'center' }}>
            {onRegenerate && (
              <IconButton
                $variant="secondary"
                onClick={onRegenerate}
                disabled={isRegenerating}
                title="Generate reply"
                style={{ width: 'auto', padding: '0.5rem 1rem', gap: '0.5rem' }}
              >
                <i className="fa-solid fa-wand-magic-sparkles" />
              </IconButton>
            )}
            <IconButton
              $variant="danger"
              onClick={onSkip}
              disabled={isDeleting}
              title="Skip comment"
            >
              <i className="fa-solid fa-xmark" />
            </IconButton>
          </ActionButtons>
        )}
      </ReplySection>
    </CommentCard>
  );
}

interface CommentDisplayProps {
  data: CommentGroupData;
  maxReplies?: number;
  myProfilePicUrl?: string;
  onPublishReply: (commentId: string, text: string, replyIndex: number) => Promise<void>;
  onSkipComment: (commentId: string) => void;
  onEditReply?: (commentId: string, newReply: string, replyIndex: number) => void;
  onRegenerateReply?: (commentId: string) => void;
  postingCommentIds: Set<string>;
  skippingCommentIds: Set<string>;
  regeneratingCommentIds: Set<string>;
}

// Animation variants for comment cards during Post All
const commentCardVariants = {
  normal: {
    opacity: 1,
    scale: 1,
    boxShadow: '0 0 0 0px rgba(14, 165, 233, 0)',
  },
  queued: {
    opacity: [0.7, 0.5, 0.7],
    scale: 1,
    transition: {
      opacity: {
        repeat: Infinity,
        duration: 1.5,
        ease: 'easeInOut',
      },
    },
  },
  posting: {
    opacity: 1,
    scale: 1,
    boxShadow: [
      '0 0 0 2px rgba(14, 165, 233, 0.3)',
      '0 0 0 4px rgba(14, 165, 233, 0.5)',
      '0 0 0 2px rgba(14, 165, 233, 0.3)',
    ],
    transition: {
      boxShadow: {
        repeat: Infinity,
        duration: 0.8,
        ease: 'easeInOut',
      },
    },
  },
};

export function CommentDisplay({
  data,
  maxReplies = 2,
  myProfilePicUrl,
  onPublishReply,
  onSkipComment,
  onEditReply,
  onRegenerateReply,
  postingCommentIds,
  skippingCommentIds,
  regeneratingCommentIds,
}: CommentDisplayProps) {
  const { post, comments } = data;
  const [isPostingAll, setIsPostingAll] = useState(false);
  const [isPostExpanded, setIsPostExpanded] = useState(false);
  const [postingProgress, setPostingProgress] = useState<{
    current: number;
    total: number;
    currentCommentId: string | null;
  } | null>(null);

  const formatMetric = (value: number): string => {
    if (value >= 1000000) return `${(value / 1000000).toFixed(1).replace(/\.0$/, '')}M`;
    if (value >= 1000) return `${(value / 1000).toFixed(1).replace(/\.0$/, '')}K`;
    return String(value);
  };

  // Get comments that have generated replies ready to post
  const commentsWithReplies = comments.filter(c =>
    c.generated_replies && c.generated_replies.length > 0
  );

  const handlePostAll = async () => {
    const total = commentsWithReplies.length;
    if (total === 0) return;

    setIsPostingAll(true);
    setPostingProgress({ current: 0, total, currentCommentId: null });

    // Post each comment sequentially and wait for each to complete
    for (let i = 0; i < commentsWithReplies.length; i++) {
      const comment = commentsWithReplies[i];
      setPostingProgress({ current: i, total, currentCommentId: comment.id });

      const reply = comment.generated_replies?.[0];
      if (reply) {
        try {
          await onPublishReply(comment.id, reply[0], 0);
        } catch (error) {
          console.error('Failed to post reply:', error);
          // Continue with remaining posts even if one fails
        }
        // Small delay between posts for rate limiting
        await new Promise(resolve => setTimeout(resolve, 300));
      }

      setPostingProgress({ current: i + 1, total, currentCommentId: null });
    }

    setIsPostingAll(false);
    setPostingProgress(null);
  };

  return (
    <Container $expanded={isPostExpanded}>
      <PostSection $expanded={isPostExpanded}>
        <PostHeader>
          <PostLabel>
            Your Post
            <CommentsCount>{comments.length} comment{comments.length !== 1 ? 's' : ''}</CommentsCount>
          </PostLabel>
          <ExpandButton onClick={() => setIsPostExpanded(!isPostExpanded)}>
            <i className={`fa-solid fa-chevron-${isPostExpanded ? 'up' : 'down'}`} />
            {isPostExpanded ? 'Less' : 'More'}
          </ExpandButton>
        </PostHeader>
        <PostContentWrapper>
          <PostContent>
            {myProfilePicUrl && (
              <Avatar
                src={myProfilePicUrl}
                alt="Your post"
              />
            )}
            <PostBody>
              <PostText>{post.text}</PostText>
            </PostBody>
          </PostContent>
          {!isPostExpanded && <PostFade />}
        </PostContentWrapper>
        <PostStats>
          <StatItem>
            <i className="fa-regular fa-comment" aria-hidden="true" />
            <span>{formatMetric(post.replies)}</span>
          </StatItem>
          <StatItem>
            <i className="fa-solid fa-retweet" aria-hidden="true" />
            <span>{formatMetric(post.retweets)}</span>
          </StatItem>
          <StatItem>
            <i className="fa-regular fa-heart" aria-hidden="true" />
            <span>{formatMetric(post.likes)}</span>
          </StatItem>
          {post.impressions > 0 && (
            <StatItem>
              <i className="fa-regular fa-eye" aria-hidden="true" />
              <span>{formatMetric(post.impressions)}</span>
            </StatItem>
          )}
          {post.url && (
            <PostLink href={post.url} target="_blank" rel="noopener noreferrer">
              View on X →
            </PostLink>
          )}
        </PostStats>
      </PostSection>

      <Divider />

      <CommentsScrollArea>
        <CommentsGrid>
          <AnimatePresence mode="popLayout">
            {comments.map((comment) => {
              // Check if this comment is queued in Post All
              const commentIndexInQueue = commentsWithReplies.findIndex(c => c.id === comment.id);
              const isQueued = postingProgress !== null && commentIndexInQueue >= postingProgress.current;
              const isCurrentlyPosting = postingProgress?.currentCommentId === comment.id;

              // Determine animation state
              const animateState = isCurrentlyPosting
                ? 'posting'
                : isQueued
                  ? 'queued'
                  : 'normal';

              return (
                <motion.div
                  key={comment.id}
                  variants={commentCardVariants}
                  animate={animateState}
                  exit={{ opacity: 0, x: 100, transition: { duration: 0.3 } }}
                  layout
                  style={{ borderRadius: '0.75rem' }}
                >
                  <CommentItem
                    comment={comment}
                    maxReplies={maxReplies}
                    myProfilePicUrl={myProfilePicUrl}
                    originalPostId={post.id}
                    onPublish={(text, replyIndex) => onPublishReply(comment.id, text, replyIndex)}
                    onSkip={() => onSkipComment(comment.id)}
                    onEditReply={onEditReply ? (newReply, replyIndex) => onEditReply(comment.id, newReply, replyIndex) : undefined}
                    onRegenerate={onRegenerateReply ? () => onRegenerateReply(comment.id) : undefined}
                    isDeleting={skippingCommentIds.has(comment.id)}
                    isPosting={postingCommentIds.has(comment.id)}
                    isRegenerating={regeneratingCommentIds.has(comment.id)}
                  />
                </motion.div>
              );
            })}
          </AnimatePresence>
        </CommentsGrid>
      </CommentsScrollArea>

      {commentsWithReplies.length > 1 && (
        <BottomBar>
          <JobProgressButton
            username=""
            jobNames={[]}
            onClick={handlePostAll}
            label={`Post All (${commentsWithReplies.length})`}
            loadingLabel="Posting..."
            localProgress={postingProgress ? {
              current: postingProgress.current,
              total: postingProgress.total,
              displayText: `Posting ${postingProgress.current}/${postingProgress.total}`,
            } : null}
            disabled={commentsWithReplies.length === 0}
          />
        </BottomBar>
      )}
    </Container>
  );
}

export type { CommentDisplayProps };
