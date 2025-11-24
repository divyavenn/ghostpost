import { atom, selector } from 'recoil';
import { type UserInfo } from './api/client';


export const usernameState = atom<string | null>({
  key: 'usernameState',
  default: localStorage.getItem('username'),
  effects: [
    ({ setSelf, onSet, trigger }) => {
      // On initialization, read from localStorage
      if (trigger === 'get') {
        const storedValue = localStorage.getItem('username');
        if (storedValue !== null) {
          setSelf(storedValue);
        }
      }

      // When value changes, update localStorage
      onSet((newValue) => {
        if (newValue) {
          localStorage.setItem('username', newValue);
        } else {
          localStorage.removeItem('username');
        }
      });
    },
  ],
});


export const userInfoState = atom<UserInfo | null>({
  key: 'userInfoState',
  default: null,
});


export const userHandleSelector = selector<string | null>({
  key: 'userHandleSelector',
  get: ({ get }) => {
    const userInfo = get(userInfoState);
    return userInfo?.handle || null;
  },
});

export const userDisplayNameSelector = selector<string | null>({
  key: 'userDisplayNameSelector',
  get: ({ get }) => {
    const userInfo = get(userInfoState);
    return userInfo?.username || null;
  },
});

export const userProfilePicSelector = selector<string | null>({
  key: 'userProfilePicSelector',
  get: ({ get }) => {
    const userInfo = get(userInfoState);
    return userInfo?.profile_pic_url || null;
  },
});

export const userAccountTypeSelector = selector<'trial' | 'poster' | 'premium' | null>({
  key: 'userAccountTypeSelector',
  get: ({ get }) => {
    const userInfo = get(userInfoState);
    return userInfo?.account_type || null;
  },
});


export const userFollowerCountSelector = selector<number>({
  key: 'userFollowerCountSelector',
  get: ({ get }) => {
    const userInfo = get(userInfoState);
    return userInfo?.follower_count || 0;
  },
});


export const hasUserEmailSelector = selector<boolean>({
  key: 'hasUserEmailSelector',
  get: ({ get }) => {
    const userInfo = get(userInfoState);
    return !!(userInfo?.email && userInfo.email.trim() !== '');
  },
});


export const userStatsSelector = selector({
  key: 'userStatsSelector',
  get: ({ get }) => {
    const userInfo = get(userInfoState);
    return {
      lifetimeNewFollows: userInfo?.lifetime_new_follows || 0,
      lifetimePosts: userInfo?.lifetime_posts || 0,
      scrollingTimeSaved: userInfo?.scrolling_time_saved || 0,
    };
  },
});


export const isSettingsOpenState = atom<boolean>({
  key: 'isSettingsOpenState',
  default: false,
});


export const showFirstTimeModalState = atom<boolean>({
  key: 'showFirstTimeModalState',
  default: false,
});


export const activeTabState = atom<'generated' | 'posted'>({
  key: 'activeTabState',
  default: 'generated',
});

/**
 * Current loading phase (scraping or generating)
 * When null, the app is not loading
 */
export const loadingPhaseState = atom<'scraping' | 'generating' | null>({
  key: 'loadingPhaseState',
  default: null,
});

/**
 * Loading status data (contains dynamic info like account names, progress)
 */
export const loadingStatusDataState = atom<{
  type: 'account' | 'query' | 'generating' | 'complete' | 'idle';
  value: string;
  summary?: string;  // Short 1-2 word summary for queries
} | null>({
  key: 'loadingStatusDataState',
  default: null,
});

/**
 * Set of node IDs that are currently typing
 * Used to disable links while their target is rendering
 */
export const typingIdsState = atom<Set<string>>({
  key: 'typingIdsState',
  default: new Set(['root']),
});
