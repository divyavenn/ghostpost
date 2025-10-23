import { type UserInfo } from '../api/client';

interface StatsDashboardProps {
  userInfo: UserInfo;
}

export function StatsDashboard({ userInfo }: StatsDashboardProps) {
  // Format time saved to hours and minutes
  const formatTimeSaved = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    if (hours > 0 && minutes > 0) {
      return `${hours}h ${minutes}m`;
    } else if (hours > 0) {
      return `${hours}h`;
    } else {
      return `${minutes}m`;
    }
  };

  return (
    <div className="flex justify-center gap-4 py-4 px-6">
      {/* Lifetime Posts */}
      <div className="bg-gradient-to-br from-blue-500/20 to-blue-600/20 rounded-lg px-6 py-3 border border-blue-500/30 min-w-[140px]">
        <div className="text-blue-200 text-xs font-medium mb-1">Lifetime Posts</div>
        <div className="text-white text-2xl font-bold">{userInfo.lifetime_posts || 0}</div>
      </div>

      {/* Lifetime New Follows */}
      <div className="bg-gradient-to-br from-green-500/20 to-green-600/20 rounded-lg px-6 py-3 border border-green-500/30 min-w-[140px]">
        <div className="text-green-200 text-xs font-medium mb-1">New Followers</div>
        <div className="text-white text-2xl font-bold">{userInfo.lifetime_new_follows || 0}</div>
      </div>

      {/* Scrolling Time Saved */}
      <div className="bg-gradient-to-br from-purple-500/20 to-purple-600/20 rounded-lg px-6 py-3 border border-purple-500/30 min-w-[140px]">
        <div className="text-purple-200 text-xs font-medium mb-1">Time Saved</div>
        <div className="text-white text-2xl font-bold">
          {userInfo.scrolling_time_saved ? formatTimeSaved(userInfo.scrolling_time_saved) : '0m'}
        </div>
      </div>
    </div>
  );
}
