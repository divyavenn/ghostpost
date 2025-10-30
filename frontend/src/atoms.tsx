import { atom, selector } from 'recoil';
import { type UserInfo } from './api/client';


export const usernameState = atom<string | null>({
  key: 'usernameState',
  default: localStorage.getItem('username'),
  effects: [
    ({ onSet }) => {
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
 * Whether the app is currently loading tweets
 */
export const isLoadingState = atom<boolean>({
  key: 'isLoadingState',
  default: false,
});

/**
 * Current loading phase (scraping or generating)
 */
export const loadingPhaseState = atom<'scraping' | 'generating' | null>({
  key: 'loadingPhaseState',
  default: null,
});

/**
 * Loading status text for scraping phase
 */
export const scrapingStatusTextState = atom<string>({
  key: 'scrapingStatusTextState',
  default: 'Scraping tweets',
});
