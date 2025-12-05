import { TweetDisplay, type TweetData } from '../components/TweetDisplay';

interface GeneratedTabProps {
  tweets: TweetData[];
  userProfilePicUrl: string;
  numberOfGenerations: number;
  deletingTweetIds: Set<string>;
  postingTweetIds: Set<string>;
  regeneratingTweetIds: Set<string>;
  onPublish: (tweetId: string, text: string, replyIndex: number) => void;
  onDelete: (tweetId: string) => void;
  onEditReply: (tweetId: string, newReply: string, replyIndex: number) => void;
  onRegenerate: (tweetId: string) => void;
}

export function GeneratedTab({
  tweets,
  userProfilePicUrl,
  numberOfGenerations,
  deletingTweetIds,
  postingTweetIds,
  regeneratingTweetIds,
  onPublish,
  onDelete,
  onEditReply,
  onRegenerate,
}: GeneratedTabProps) {
  return (
    <>
      {/* Left Column */}
      <div className="flex-1 flex flex-col gap-6">
        {tweets.filter((_, index) => index % 2 === 0).map((tweet) => (
          <TweetDisplay
            key={tweet.id}
            tweet={tweet}
            myProfilePicUrl={userProfilePicUrl}
            maxReplies={numberOfGenerations}
            onPublish={(text, replyIndex) => onPublish(tweet.id, text, replyIndex)}
            onSkip={() => onDelete(tweet.id)}
            onEditReply={(newReply, replyIndex) => onEditReply(tweet.id, newReply, replyIndex)}
            onRegenerate={() => onRegenerate(tweet.id)}
            isDeleting={deletingTweetIds.has(tweet.id)}
            isPosting={postingTweetIds.has(tweet.id)}
            isRegenerating={regeneratingTweetIds.has(tweet.id)}
          />
        ))}
      </div>
      {/* Right Column */}
      <div className="flex-1 flex flex-col gap-6">
        {tweets.filter((_, index) => index % 2 === 1).map((tweet) => (
          <TweetDisplay
            key={tweet.id}
            tweet={tweet}
            myProfilePicUrl={userProfilePicUrl}
            maxReplies={numberOfGenerations}
            onPublish={(text, replyIndex) => onPublish(tweet.id, text, replyIndex)}
            onSkip={() => onDelete(tweet.id)}
            onEditReply={(newReply, replyIndex) => onEditReply(tweet.id, newReply, replyIndex)}
            onRegenerate={() => onRegenerate(tweet.id)}
            isDeleting={deletingTweetIds.has(tweet.id)}
            isPosting={postingTweetIds.has(tweet.id)}
            isRegenerating={regeneratingTweetIds.has(tweet.id)}
          />
        ))}
      </div>
    </>
  );
}
