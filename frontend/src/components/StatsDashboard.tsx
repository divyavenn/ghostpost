import { type UserInfo } from '../api/client';
import { AnimatedNumber } from './AnimatedNumber';

interface StatsDashboardProps {
  userInfo: UserInfo;
}

export function StatsDashboard({ userInfo }: StatsDashboardProps) {
  // Calculate minutes saved from seconds
  const minutesSaved = userInfo.scrolling_time_saved
    ? Math.round(userInfo.scrolling_time_saved / 60)
    : 0;

  return (
    <div className="flex justify-center py-4">
      <div className="bg-black/40 backdrop-blur-sm rounded-2xl px-12 py-6 max-w-3xl">
        <div className="mb-6">
          <h2 className="text-white text-lg font-[Geisz Mono]">stats</h2>
        </div>
        <div className="grid grid-cols-3 gap-12">
          {/* Lifetime Posts */}
          <div className="text-center">
            <div className="text-orange-400 text-5xl font-bold mb-2">
              <AnimatedNumber
                value={userInfo.lifetime_posts || 0}
                className="text-orange-400 text-5xl font-bold"
              />
            </div>
            <div className="text-white text-sm">tweets posted</div>
          </div>

          {/* Lifetime New Follows */}
          <div className="text-center">
            <div className="text-blue-400 text-5xl font-bold mb-2">
              <AnimatedNumber
                value={userInfo.lifetime_new_follows || 0}
                className="text-blue-400 text-5xl font-bold"
              />
            </div>
            <div className="text-white text-sm">new followers</div>
          </div>

          {/* Scrolling Time Saved */}
          <div className="text-center">
            <div className="text-white text-5xl font-bold mb-2">
              <AnimatedNumber
                value={minutesSaved}
                className="text-white text-5xl font-bold"
              />
            </div>
            <div className="text-white text-sm">minutes saved</div>
          </div>
        </div>
      </div>
    </div>
  );
}
