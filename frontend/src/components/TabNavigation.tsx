interface TabNavigationProps {
  activeTab: 'generated' | 'posted';
  onTabChange: (tab: 'generated' | 'posted') => void;
  generatedCount: number;
  postedCount: number;
}

export function TabNavigation({ activeTab, onTabChange, generatedCount, postedCount }: TabNavigationProps) {
  return (
    <div className="flex justify-center gap-4 pt-2 pb-4">
      <button
        onClick={() => onTabChange('generated')}
        className={`px-6 py-2 text-sm font-semibold transition rounded-full ${
          activeTab === 'generated'
            ? 'bg-sky-500 text-white'
            : 'bg-neutral-800 text-neutral-400 hover:bg-neutral-700 hover:text-white'
        }`}
      >
        Generated ({generatedCount})
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
    </div>
  );
}
