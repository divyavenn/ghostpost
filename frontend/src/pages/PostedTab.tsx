import { PostedTweetDisplay, type PostedTweetData } from '../components/posted_tweet';

interface PostedTabProps {
  postedTweets: PostedTweetData[];
  userProfilePicUrl: string;
  userHandle: string;
  userUsername: string;
  deletingTweetIds: Set<string>;
  isLoadingMore: boolean;
  onDelete: (tweetId: string) => void;
  onViewTweet: (tweetId: string) => void;
}

export function PostedTab({
  postedTweets,
  userProfilePicUrl,
  userHandle,
  userUsername,
  deletingTweetIds,
  isLoadingMore,
  onDelete,
  onViewTweet,
}: PostedTabProps) {
  if (postedTweets.length === 0) {
    return (
      <div className="w-full flex items-center justify-center h-64">
        <p className="text-neutral-400 text-lg">No tweets posted yet</p>
      </div>
    );
  }

  return (
    <>
      {/* Left Column */}
      <div className="flex-1 flex flex-col gap-6">
        {postedTweets.filter((_, index) => index % 2 === 0).map((tweet) => (
          <PostedTweetDisplay
            key={tweet.id}
            tweet={tweet}
            myProfilePicUrl={userProfilePicUrl}
            myHandle={userHandle}
            myUsername={userUsername}
            onDelete={(tweetId) => onDelete(tweetId)}
            onViewTweet={onViewTweet}
            isDeleting={deletingTweetIds.has(tweet.id)}
          />
        ))}
      </div>
      {/* Right Column */}
      <div className="flex-1 flex flex-col gap-6">
        {postedTweets.filter((_, index) => index % 2 === 1).map((tweet) => (
          <PostedTweetDisplay
            key={tweet.id}
            tweet={tweet}
            myProfilePicUrl={userProfilePicUrl}
            myHandle={userHandle}
            myUsername={userUsername}
            onDelete={(tweetId) => onDelete(tweetId)}
            onViewTweet={onViewTweet}
            isDeleting={deletingTweetIds.has(tweet.id)}
          />
        ))}
      </div>

      {/* Loading indicator for infinite scroll */}
      {isLoadingMore && (
        <div className="w-full flex justify-center py-8">
          <div className="text-neutral-400 text-sm">Loading more tweets...</div>
        </div>
      )}
    </>
  );
}
