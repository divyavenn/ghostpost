import { useEffect, useState } from 'react';
import { type StandalonePendingPost } from '../api/client';

interface PostsTabProps {
  posts: StandalonePendingPost[];
  pendingActionDraftIds: Set<string>;
  onApprovePost: (draftId: string) => Promise<void> | void;
  onSavePost: (
    draftId: string,
    payload: { text?: string; image_url?: string | null; link_url?: string | null }
  ) => Promise<void> | void;
  onDiscardPost: (draftId: string) => Promise<void> | void;
}

interface StandalonePostCardProps {
  post: StandalonePendingPost;
  isActionPending: boolean;
  onApprovePost: (draftId: string) => Promise<void> | void;
  onSavePost: (
    draftId: string,
    payload: { text?: string; image_url?: string | null; link_url?: string | null }
  ) => Promise<void> | void;
  onDiscardPost: (draftId: string) => Promise<void> | void;
}

function StandalonePostCard({
  post,
  isActionPending,
  onApprovePost,
  onSavePost,
  onDiscardPost,
}: StandalonePostCardProps) {
  const [draftText, setDraftText] = useState(post.text);
  const [draftImageUrl, setDraftImageUrl] = useState(post.image_url || '');
  const [draftLinkUrl, setDraftLinkUrl] = useState(post.link_url || '');

  useEffect(() => {
    setDraftText(post.text);
    setDraftImageUrl(post.image_url || '');
    setDraftLinkUrl(post.link_url || '');
  }, [post.text, post.image_url, post.link_url]);

  const canEdit = post.status === 'awaiting_approval' || post.status === 'failed';
  const canApprove = post.status === 'awaiting_approval' || post.status === 'failed';
  const hasChanges =
    draftText !== post.text
    || draftImageUrl !== (post.image_url || '')
    || draftLinkUrl !== (post.link_url || '');

  return (
    <div className="rounded-xl border border-neutral-800 bg-black/60 p-4">
      <div className="flex items-center justify-between pb-3">
        <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${
          post.status === 'awaiting_approval'
            ? 'bg-amber-500/20 text-amber-400'
            : post.status === 'failed'
              ? 'bg-red-500/20 text-red-400'
              : post.status === 'completed'
                ? 'bg-emerald-500/20 text-emerald-400'
                : 'bg-sky-500/20 text-sky-400'
        }`}>
          {post.status.replace('_', ' ')}
        </span>
        {post.desktop_job_id && (
          <span className="text-[10px] text-neutral-500">task: post_all</span>
        )}
      </div>

      {post.error && (
        <div className="mb-3 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
          {post.error}
        </div>
      )}

      <textarea
        value={draftText}
        onChange={(e) => setDraftText(e.target.value)}
        disabled={!canEdit || isActionPending}
        className="w-full min-h-[110px] rounded-lg bg-neutral-900 border border-neutral-700 p-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-sky-500 resize-y"
      />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 pt-3">
        <input
          type="text"
          value={draftLinkUrl}
          onChange={(e) => setDraftLinkUrl(e.target.value)}
          disabled={!canEdit || isActionPending}
          placeholder="Optional link URL"
          className="rounded-lg bg-neutral-900 border border-neutral-700 p-2 text-xs text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
        />
        <input
          type="text"
          value={draftImageUrl}
          onChange={(e) => setDraftImageUrl(e.target.value)}
          disabled={!canEdit || isActionPending}
          placeholder="Optional image URL"
          className="rounded-lg bg-neutral-900 border border-neutral-700 p-2 text-xs text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
        />
      </div>

      {draftImageUrl && (
        <div className="pt-3">
          <img
            src={draftImageUrl}
            alt="Post preview"
            className="max-h-64 rounded-lg border border-neutral-800 object-contain bg-neutral-950"
            loading="lazy"
            onError={(e) => {
              (e.currentTarget as HTMLImageElement).style.display = 'none';
            }}
          />
        </div>
      )}

      {draftLinkUrl && (
        <div className="pt-3 text-xs">
          <a
            href={draftLinkUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sky-400 hover:text-sky-300 break-all"
          >
            {draftLinkUrl}
          </a>
        </div>
      )}

      <div className="flex items-center gap-2 pt-4">
        <button
          type="button"
          disabled={!hasChanges || isActionPending || !canEdit}
          onClick={() => onSavePost(post.draft_id, {
            text: draftText,
            image_url: draftImageUrl || null,
            link_url: draftLinkUrl || null,
          })}
          className="px-3 py-1.5 text-xs rounded-md bg-neutral-700 text-white disabled:opacity-50"
        >
          Save
        </button>
        <button
          type="button"
          disabled={isActionPending || !canApprove}
          onClick={() => onApprovePost(post.draft_id)}
          className="px-3 py-1.5 text-xs rounded-md bg-sky-600 text-white disabled:opacity-50"
        >
          Approve
        </button>
        <button
          type="button"
          disabled={isActionPending}
          onClick={() => onDiscardPost(post.draft_id)}
          className="px-3 py-1.5 text-xs rounded-md bg-red-600/80 text-white disabled:opacity-50"
        >
          Discard
        </button>
      </div>
    </div>
  );
}

export function PostsTab({
  posts,
  pendingActionDraftIds,
  onApprovePost,
  onSavePost,
  onDiscardPost,
}: PostsTabProps) {
  if (posts.length === 0) {
    return (
      <div className="w-full flex items-center justify-center h-64">
        <p className="text-neutral-400 text-lg">No standalone posts to approve</p>
      </div>
    );
  }

  return (
    <div className="w-full flex flex-col gap-4">
      {posts.map((post) => (
        <StandalonePostCard
          key={post.id}
          post={post}
          isActionPending={pendingActionDraftIds.has(post.draft_id)}
          onApprovePost={onApprovePost}
          onSavePost={onSavePost}
          onDiscardPost={onDiscardPost}
        />
      ))}
    </div>
  );
}
