/**
 * RecoilStateDebug - Development component to verify Recoil state synchronization
 *
 * This component displays all Recoil atoms in real-time to verify that
 * App.tsx is correctly syncing local state to global Recoil atoms.
 *
 * Usage:
 * Add to App.tsx temporarily: <RecoilStateDebug />
 *
 * Remove this component in production builds.
 */

import { useRecoilValue } from 'recoil';
import {
  usernameState,
  userInfoState,
  userHandleSelector,
  userDisplayNameSelector,
  userProfilePicSelector,
  userAccountTypeSelector,
  userFollowerCountSelector,
  hasUserEmailSelector,
  userStatsSelector,
  isSettingsOpenState,
  showFirstTimeModalState,
  activeTabState,
  loadingPhaseState,
  loadingStatusDataState,
} from '../atoms';

export function RecoilStateDebug() {
  // Read all atoms
  const username = useRecoilValue(usernameState);
  const userInfo = useRecoilValue(userInfoState);
  const handle = useRecoilValue(userHandleSelector);
  const displayName = useRecoilValue(userDisplayNameSelector);
  const profilePic = useRecoilValue(userProfilePicSelector);
  const accountType = useRecoilValue(userAccountTypeSelector);
  const followerCount = useRecoilValue(userFollowerCountSelector);
  const hasEmail = useRecoilValue(hasUserEmailSelector);
  const stats = useRecoilValue(userStatsSelector);
  const isSettingsOpen = useRecoilValue(isSettingsOpenState);
  const showFirstTimeModal = useRecoilValue(showFirstTimeModalState);
  const activeTab = useRecoilValue(activeTabState);
  const loadingPhase = useRecoilValue(loadingPhaseState);
  const loadingStatusData = useRecoilValue(loadingStatusDataState);

  // Derived state: isLoading can be determined from loadingPhase
  const isLoading = loadingPhase !== null;

  return (
    <div className="fixed bottom-4 right-4 bg-slate-900 border border-slate-700 rounded-lg p-4 max-w-md max-h-96 overflow-y-auto text-xs font-mono shadow-2xl z-50">
      <div className="flex items-center justify-between mb-3 pb-2 border-b border-slate-700">
        <h3 className="text-white font-bold text-sm">🔍 Recoil State Debug</h3>
        <span className="text-green-400 text-xs">● Live</span>
      </div>

      <div className="space-y-3">
        {/* User State */}
        <div>
          <h4 className="text-blue-400 font-semibold mb-1">User State</h4>
          <div className="space-y-1 pl-2">
            <div className="text-slate-300">
              <span className="text-slate-500">username:</span>{' '}
              {username || <span className="text-red-400">null</span>}
            </div>
            <div className="text-slate-300">
              <span className="text-slate-500">handle:</span>{' '}
              {handle || <span className="text-red-400">null</span>}
            </div>
            <div className="text-slate-300">
              <span className="text-slate-500">displayName:</span>{' '}
              {displayName || <span className="text-red-400">null</span>}
            </div>
            <div className="text-slate-300">
              <span className="text-slate-500">accountType:</span>{' '}
              <span className={
                accountType === 'premium' ? 'text-purple-400' :
                accountType === 'poster' ? 'text-blue-400' :
                'text-yellow-400'
              }>
                {accountType || 'null'}
              </span>
            </div>
            <div className="text-slate-300">
              <span className="text-slate-500">followers:</span>{' '}
              {followerCount.toLocaleString()}
            </div>
            <div className="text-slate-300">
              <span className="text-slate-500">hasEmail:</span>{' '}
              {hasEmail ? <span className="text-green-400">true</span> : <span className="text-red-400">false</span>}
            </div>
            {profilePic && (
              <div className="flex items-center gap-2 mt-1">
                <span className="text-slate-500">profilePic:</span>
                <img src={profilePic} className="w-6 h-6 rounded-full" alt="Profile" />
              </div>
            )}
          </div>
        </div>

        {/* Stats */}
        <div>
          <h4 className="text-green-400 font-semibold mb-1">Stats</h4>
          <div className="space-y-1 pl-2">
            <div className="text-slate-300">
              <span className="text-slate-500">lifetimePosts:</span> {stats.lifetimePosts}
            </div>
            <div className="text-slate-300">
              <span className="text-slate-500">lifetimeNewFollows:</span> {stats.lifetimeNewFollows}
            </div>
            <div className="text-slate-300">
              <span className="text-slate-500">scrollingTimeSaved:</span> {stats.scrollingTimeSaved}s
            </div>
          </div>
        </div>

        {/* UI State */}
        <div>
          <h4 className="text-purple-400 font-semibold mb-1">UI State</h4>
          <div className="space-y-1 pl-2">
            <div className="text-slate-300">
              <span className="text-slate-500">activeTab:</span>{' '}
              <span className="text-blue-400">{activeTab}</span>
            </div>
            <div className="text-slate-300">
              <span className="text-slate-500">isSettingsOpen:</span>{' '}
              {isSettingsOpen ? <span className="text-green-400">true</span> : <span className="text-slate-500">false</span>}
            </div>
            <div className="text-slate-300">
              <span className="text-slate-500">showFirstTimeModal:</span>{' '}
              {showFirstTimeModal ? <span className="text-green-400">true</span> : <span className="text-slate-500">false</span>}
            </div>
          </div>
        </div>

        {/* Loading State */}
        <div>
          <h4 className="text-orange-400 font-semibold mb-1">Loading State</h4>
          <div className="space-y-1 pl-2">
            <div className="text-slate-300">
              <span className="text-slate-500">isLoading:</span>{' '}
              {isLoading ? <span className="text-orange-400">true</span> : <span className="text-slate-500">false</span>}
            </div>
            <div className="text-slate-300">
              <span className="text-slate-500">loadingPhase:</span>{' '}
              {loadingPhase || <span className="text-slate-500">null</span>}
            </div>
            <div className="text-slate-300">
              <span className="text-slate-500">statusData:</span>{' '}
              {loadingStatusData ? (
                <span className="text-slate-400 italic">
                  {loadingStatusData.type}
                  {loadingStatusData.value && ` - ${loadingStatusData.value}`}
                </span>
              ) : (
                <span className="text-slate-500">null</span>
              )}
            </div>
          </div>
        </div>

        {/* Raw UserInfo */}
        {userInfo && (
          <div>
            <h4 className="text-yellow-400 font-semibold mb-1">Raw UserInfo</h4>
            <pre className="text-slate-400 text-[10px] bg-slate-950 p-2 rounded overflow-x-auto">
              {JSON.stringify(userInfo, null, 2)}
            </pre>
          </div>
        )}
      </div>

      <div className="mt-3 pt-2 border-t border-slate-700 text-slate-500 text-[10px]">
        All values update in real-time as App.tsx local state changes.
      </div>
    </div>
  );
}
