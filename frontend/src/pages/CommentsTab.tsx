import { CommentDisplay } from '../components/CommentDisplay';
import type { PostWithComments } from '../api/client';

interface CommentsTabProps {
  postsWithComments: PostWithComments[];
  numberOfGenerations: number;
  isLoading: boolean;
  userProfilePicUrl: string;
  postingCommentIds: Set<string>;
  skippingCommentIds: Set<string>;
  regeneratingCommentIds: Set<string>;
  onPublishReply: (commentId: string, text: string, replyIndex: number) => Promise<void>;
  onSkipComment: (commentId: string) => void;
  onEditReply: (commentId: string, newReply: string, replyIndex: number) => void;
  onRegenerateReply: (commentId: string) => void;
}

export function CommentsTab({
  postsWithComments,
  numberOfGenerations,
  isLoading,
  userProfilePicUrl,
  postingCommentIds,
  skippingCommentIds,
  regeneratingCommentIds,
  onPublishReply,
  onSkipComment,
  onEditReply,
  onRegenerateReply,
}: CommentsTabProps) {
  if (isLoading) {
    return (
      <div className="w-full flex items-center justify-center h-64">
        <p className="text-neutral-400 text-lg">Loading comments...</p>
      </div>
    );
  }

  if (postsWithComments.length === 0) {
    return (
      <div className="w-full flex items-center justify-center h-64">
        <p className="text-neutral-400 text-lg">No pending comments to review</p>
      </div>
    );
  }

  return (
    <div className="w-full flex flex-col gap-6">
      {postsWithComments.map((postData) => (
        <CommentDisplay
          key={postData.post.id}
          data={postData}
          maxReplies={numberOfGenerations}
          myProfilePicUrl={userProfilePicUrl}
          onPublishReply={onPublishReply}
          onSkipComment={onSkipComment}
          onEditReply={onEditReply}
          onRegenerateReply={onRegenerateReply}
          postingCommentIds={postingCommentIds}
          skippingCommentIds={skippingCommentIds}
          regeneratingCommentIds={regeneratingCommentIds}
        />
      ))}
    </div>
  );
}
