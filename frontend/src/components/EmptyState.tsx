interface EmptyStateProps {
  onRefresh: () => void;
}

export function EmptyState({ onRefresh }: EmptyStateProps) {
  return (
    <div className="flex flex-1 items-center justify-center">
      <div className="text-center text-white">
        <p className="text-xl mb-4">No tweets found in cache</p>
        <button
          onClick={onRefresh}
          className="rounded-full bg-sky-500 px-6 py-2 text-sm font-semibold text-white transition hover:bg-sky-600"
        >
          Refresh
        </button>
      </div>
    </div>
  );
}
