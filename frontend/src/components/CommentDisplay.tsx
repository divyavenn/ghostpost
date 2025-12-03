import { useState } from 'react';
import styled from 'styled-components';
import { type CommentData, type ThreadContext } from '../api/client';

const Card = styled.div<{ $isDeleting?: boolean; $isPosting?: boolean }>`
  background: rgba(30, 30, 30, 0.8);
  border-radius: 16px;
  padding: 20px;
  transition: all 0.3s ease;
  opacity: ${props => (props.$isDeleting || props.$isPosting) ? 0.5 : 1};
  transform: ${props => props.$isDeleting ? 'scale(0.95)' : props.$isPosting ? 'scale(1.02)' : 'scale(1)'};
`;

const ThreadContextSection = styled.div`
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
`;

const ContextItem = styled.div<{ $isUser: boolean }>`
  padding: 12px;
  margin-bottom: 8px;
  background: ${props => props.$isUser ? 'rgba(56, 189, 248, 0.1)' : 'rgba(255, 255, 255, 0.05)'};
  border-radius: 8px;
  border-left: 3px solid ${props => props.$isUser ? '#38bdf8' : 'transparent'};
`;

const ContextAuthor = styled.div<{ $isUser: boolean }>`
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
  font-size: 0.75rem;
  color: ${props => props.$isUser ? '#38bdf8' : '#a3a3a3'};
`;

const ContextText = styled.p`
  font-size: 0.875rem;
  color: #e5e5e5;
  line-height: 1.4;
  margin: 0;
`;

const CommentSection = styled.div`
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
`;

const Avatar = styled.img`
  width: 40px;
  height: 40px;
  border-radius: 50%;
  object-fit: cover;
`;

const CommentContent = styled.div`
  flex: 1;
`;

const CommentHeader = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
`;

const Username = styled.span`
  font-weight: 600;
  color: #fff;
`;

const Handle = styled.span`
  color: #737373;
  font-size: 0.875rem;
`;

const CommentText = styled.p`
  color: #e5e5e5;
  line-height: 1.5;
  margin: 0 0 8px 0;
`;

const Stats = styled.div`
  display: flex;
  gap: 16px;
  font-size: 0.75rem;
  color: #737373;
`;

const RepliesSection = styled.div`
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
`;

const ReplyOption = styled.div<{ $selected: boolean }>`
  padding: 12px;
  margin-bottom: 8px;
  background: ${props => props.$selected ? 'rgba(56, 189, 248, 0.1)' : 'rgba(255, 255, 255, 0.05)'};
  border: 1px solid ${props => props.$selected ? '#38bdf8' : 'transparent'};
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    background: rgba(56, 189, 248, 0.15);
  }
`;

const ReplyText = styled.p`
  color: #e5e5e5;
  line-height: 1.5;
  margin: 0 0 4px 0;
`;

const ModelTag = styled.span`
  font-size: 0.65rem;
  color: #737373;
  background: rgba(255, 255, 255, 0.1);
  padding: 2px 6px;
  border-radius: 4px;
`;

const EditTextarea = styled.textarea`
  width: 100%;
  min-height: 80px;
  padding: 12px;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  color: #fff;
  font-size: 0.875rem;
  resize: vertical;
  margin-bottom: 8px;

  &:focus {
    outline: none;
    border-color: #38bdf8;
  }
`;

const ButtonGroup = styled.div`
  display: flex;
  gap: 8px;
  margin-top: 12px;
`;

const Button = styled.button<{ $variant?: 'primary' | 'secondary' | 'danger' }>`
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;

  ${props => {
    switch (props.$variant) {
      case 'primary':
        return `
          background: #38bdf8;
          color: #000;
          border: none;
          &:hover { background: #7dd3fc; }
        `;
      case 'danger':
        return `
          background: transparent;
          color: #ef4444;
          border: 1px solid #ef4444;
          &:hover { background: rgba(239, 68, 68, 0.1); }
        `;
      default:
        return `
          background: rgba(255, 255, 255, 0.1);
          color: #fff;
          border: none;
          &:hover { background: rgba(255, 255, 255, 0.2); }
        `;
    }
  }}

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`;

const EmptyReplies = styled.div`
  text-align: center;
  padding: 24px;
  color: #737373;
`;

interface CommentDisplayProps {
  comment: CommentData;
  threadContext: ThreadContext[];
  myProfilePicUrl: string;
  maxReplies?: number;
  onPublish: (text: string, replyIndex: number) => void;
  onSkip: () => void;
  onEditReply?: (newReply: string, replyIndex: number) => void;
  onRegenerate?: () => void;
  isDeleting?: boolean;
  isPosting?: boolean;
  isRegenerating?: boolean;
}

export function CommentDisplay({
  comment,
  threadContext,
  myProfilePicUrl,
  maxReplies = 2,
  onPublish,
  onSkip,
  onEditReply,
  onRegenerate,
  isDeleting = false,
  isPosting = false,
  isRegenerating = false,
}: CommentDisplayProps) {
  const [selectedReplyIndex, setSelectedReplyIndex] = useState(0);
  const [isEditing, setIsEditing] = useState(false);
  const [editText, setEditText] = useState('');

  const generatedReplies = comment.generated_replies || [];
  const displayedReplies = generatedReplies.slice(0, maxReplies);

  const handleEdit = () => {
    if (displayedReplies.length > 0) {
      setEditText(displayedReplies[selectedReplyIndex][0]);
      setIsEditing(true);
    }
  };

  const handleSaveEdit = () => {
    if (onEditReply && editText.trim()) {
      onEditReply(editText, selectedReplyIndex);
    }
    setIsEditing(false);
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
    setEditText('');
  };

  const handlePublish = () => {
    const replyText = displayedReplies[selectedReplyIndex]?.[0];
    if (replyText) {
      onPublish(replyText, selectedReplyIndex);
    }
  };

  return (
    <Card $isDeleting={isDeleting} $isPosting={isPosting}>
      {/* Thread Context */}
      {threadContext.length > 1 && (
        <ThreadContextSection>
          <div style={{ fontSize: '0.75rem', color: '#737373', marginBottom: '8px' }}>
            Thread Context
          </div>
          {threadContext.slice(0, -1).map((ctx, idx) => (
            <ContextItem key={ctx.id || idx} $isUser={ctx.is_user}>
              <ContextAuthor $isUser={ctx.is_user}>
                {ctx.is_user ? 'You' : `@${ctx.handle}`}
                {ctx.deleted && ' (deleted)'}
              </ContextAuthor>
              <ContextText>{ctx.text}</ContextText>
            </ContextItem>
          ))}
        </ThreadContextSection>
      )}

      {/* Comment */}
      <CommentSection>
        <Avatar
          src={comment.author_profile_pic_url || '/default-avatar.png'}
          alt={comment.username}
          onError={(e) => {
            (e.target as HTMLImageElement).src = '/default-avatar.png';
          }}
        />
        <CommentContent>
          <CommentHeader>
            <Username>{comment.username}</Username>
            <Handle>@{comment.handle}</Handle>
          </CommentHeader>
          <CommentText>{comment.text}</CommentText>
          <Stats>
            <span>{comment.likes} likes</span>
            <span>{comment.replies} replies</span>
            {comment.followers > 0 && <span>{comment.followers.toLocaleString()} followers</span>}
          </Stats>
        </CommentContent>
      </CommentSection>

      {/* Generated Replies */}
      <RepliesSection>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
          <span style={{ fontSize: '0.875rem', color: '#a3a3a3' }}>
            Your Reply {displayedReplies.length > 1 && `(${selectedReplyIndex + 1}/${displayedReplies.length})`}
          </span>
          {onRegenerate && (
            <Button onClick={onRegenerate} disabled={isRegenerating}>
              {isRegenerating ? 'Regenerating...' : 'Regenerate'}
            </Button>
          )}
        </div>

        {displayedReplies.length === 0 ? (
          <EmptyReplies>
            No replies generated yet.
            {onRegenerate && (
              <Button onClick={onRegenerate} style={{ marginTop: '8px' }}>
                Generate Replies
              </Button>
            )}
          </EmptyReplies>
        ) : isEditing ? (
          <div>
            <EditTextarea
              value={editText}
              onChange={(e) => setEditText(e.target.value)}
              autoFocus
            />
            <ButtonGroup>
              <Button $variant="primary" onClick={handleSaveEdit}>Save</Button>
              <Button onClick={handleCancelEdit}>Cancel</Button>
            </ButtonGroup>
          </div>
        ) : (
          <>
            {displayedReplies.map(([text, model], idx) => (
              <ReplyOption
                key={idx}
                $selected={selectedReplyIndex === idx}
                onClick={() => setSelectedReplyIndex(idx)}
              >
                <ReplyText>{text}</ReplyText>
                <ModelTag>{model}</ModelTag>
              </ReplyOption>
            ))}

            <ButtonGroup>
              <Button $variant="primary" onClick={handlePublish} disabled={isPosting}>
                {isPosting ? 'Posting...' : 'Post Reply'}
              </Button>
              <Button onClick={handleEdit}>Edit</Button>
              <Button $variant="danger" onClick={onSkip} disabled={isDeleting}>
                Skip
              </Button>
            </ButtonGroup>
          </>
        )}
      </RepliesSection>
    </Card>
  );
}

export type { CommentDisplayProps };
