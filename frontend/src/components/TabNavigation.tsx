interface TabNavigationProps {
  activeTab: 'discovered' | 'posted' | 'comments';
  onTabChange: (tab: 'discovered' | 'posted' | 'comments') => void;
  discoveredCount: number;
  postedCount: number;
  commentsCount?: number;
}

export function TabNavigation({ activeTab, onTabChange, discoveredCount, postedCount, commentsCount = 0 }: TabNavigationProps) {
  return (
    <div className="flex justify-center gap-4 pt-2 pb-4">
      <button
        onClick={() => onTabChange('discovered')}
        className={`px-6 py-2 text-sm font-semibold transition rounded-full ${
          activeTab === 'discovered'
            ? 'bg-sky-500 text-white'
            : 'bg-neutral-800 text-neutral-400 hover:bg-neutral-700 hover:text-white'
        }`}
      >
        Discovered ({discoveredCount})
      </button>
      <button
        onClick={() => onTabChange('posted')}
        className={`px-6 py-2 text-sm font-semibold transition rounded-full ${
          activeTab === 'posted'
            ? 'bg-sky-500 text-white'
            : 'bg-neutral-800 text-neutral-400 hover:bg-neutral-700 hover:text-white'
        }`}
      >
        Posted ({postedCount})
      </button>
      <button
        onClick={() => onTabChange('comments')}
        className={`px-6 py-2 text-sm font-semibold transition rounded-full ${
          activeTab === 'comments'
            ? 'bg-sky-500 text-white'
            : 'bg-neutral-800 text-neutral-400 hover:bg-neutral-700 hover:text-white'
        }`}
      >
        Comments {commentsCount > 0 && `(${commentsCount})`}
      </button>
    </div>
  );
}
