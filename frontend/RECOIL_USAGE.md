# Recoil State Management - Usage Guide

## Overview

The application now uses [Recoil](https://recoiljs.org/) for state management. All global state atoms and selectors are defined in `src/atoms.tsx`.

## Setup

Recoil is already configured in `src/main.tsx` with `<RecoilRoot>` wrapping the entire app.

## User State Atoms

### Core User Atoms

#### `usernameState`
The current logged-in username (Twitter handle). Automatically syncs with localStorage.

```tsx
import { useRecoilState, useRecoilValue, useSetRecoilState } from 'recoil';
import { usernameState } from './atoms';

function MyComponent() {
  // Read and write
  const [username, setUsername] = useRecoilState(usernameState);

  // Read only
  const username = useRecoilValue(usernameState);

  // Write only
  const setUsername = useSetRecoilState(usernameState);

  return <div>Logged in as: {username}</div>;
}
```

#### `userInfoState`
Complete user information object from the backend.

```tsx
import { useRecoilValue, useSetRecoilState } from 'recoil';
import { userInfoState } from './atoms';

function ProfileComponent() {
  const userInfo = useRecoilValue(userInfoState);
  const setUserInfo = useSetRecoilState(userInfoState);

  // Load user info
  const loadUser = async () => {
    const info = await api.getUserInfo(username);
    setUserInfo(info);
  };

  return (
    <div>
      <img src={userInfo?.profile_pic_url} />
      <h2>{userInfo?.username}</h2>
      <p>@{userInfo?.handle}</p>
    </div>
  );
}
```

### User Selectors (Derived State)

Selectors automatically extract specific fields from `userInfoState`. They're read-only.

#### `userHandleSelector`
Get the user's Twitter handle.

```tsx
import { useRecoilValue } from 'recoil';
import { userHandleSelector } from './atoms';

function Header() {
  const handle = useRecoilValue(userHandleSelector);
  return <div>@{handle}</div>;
}
```

#### `userDisplayNameSelector`
Get the user's display name.

```tsx
import { useRecoilValue } from 'recoil';
import { userDisplayNameSelector } from './atoms';

function WelcomeMessage() {
  const displayName = useRecoilValue(userDisplayNameSelector);
  return <h1>Welcome, {displayName}!</h1>;
}
```

#### `userProfilePicSelector`
Get the user's profile picture URL.

```tsx
import { useRecoilValue } from 'recoil';
import { userProfilePicSelector } from './atoms';

function Avatar() {
  const profilePic = useRecoilValue(userProfilePicSelector);
  return <img src={profilePic} className="w-10 h-10 rounded-full" />;
}
```

#### `userAccountTypeSelector`
Get the user's account type (trial, poster, or premium).

```tsx
import { useRecoilValue } from 'recoil';
import { userAccountTypeSelector } from './atoms';

function SubscriptionBadge() {
  const accountType = useRecoilValue(userAccountTypeSelector);

  const badges = {
    trial: '🆓 Trial',
    poster: '⭐ Poster',
    premium: '💎 Premium'
  };

  return <span>{badges[accountType || 'trial']}</span>;
}
```

#### `userFollowerCountSelector`
Get the user's follower count.

```tsx
import { useRecoilValue } from 'recoil';
import { userFollowerCountSelector } from './atoms';

function FollowerCount() {
  const followers = useRecoilValue(userFollowerCountSelector);
  return <div>{followers.toLocaleString()} followers</div>;
}
```

#### `hasUserEmailSelector`
Check if the user has provided their email (useful for showing FirstTimeUserModal).

```tsx
import { useRecoilValue } from 'recoil';
import { hasUserEmailSelector } from './atoms';

function EmailPrompt() {
  const hasEmail = useRecoilValue(hasUserEmailSelector);

  if (hasEmail) return null;

  return <div>Please provide your email</div>;
}
```

#### `userStatsSelector`
Get all user lifetime statistics in one object.

```tsx
import { useRecoilValue } from 'recoil';
import { userStatsSelector } from './atoms';

function StatsDisplay() {
  const stats = useRecoilValue(userStatsSelector);

  return (
    <div>
      <p>New Follows: {stats.lifetimeNewFollows}</p>
      <p>Posts: {stats.lifetimePosts}</p>
      <p>Time Saved: {stats.scrollingTimeSaved}s</p>
    </div>
  );
}
```

## UI State Atoms

#### `isSettingsOpenState`
Control the user settings modal.

```tsx
import { useRecoilState } from 'recoil';
import { isSettingsOpenState } from './atoms';

function SettingsButton() {
  const [isOpen, setIsOpen] = useRecoilState(isSettingsOpenState);

  return (
    <>
      <button onClick={() => setIsOpen(true)}>
        Open Settings
      </button>
      {isOpen && <SettingsModal onClose={() => setIsOpen(false)} />}
    </>
  );
}
```

#### `showFirstTimeModalState`
Control the first-time user welcome modal.

```tsx
import { useRecoilState } from 'recoil';
import { showFirstTimeModalState } from './atoms';

function App() {
  const [showModal, setShowModal] = useRecoilState(showFirstTimeModalState);

  return (
    <>
      {showModal && (
        <FirstTimeUserModal onComplete={() => setShowModal(false)} />
      )}
    </>
  );
}
```

#### `activeTabState`
Track the current active tab (generated or posted tweets).

```tsx
import { useRecoilState } from 'recoil';
import { activeTabState } from './atoms';

function TabNavigation() {
  const [activeTab, setActiveTab] = useRecoilState(activeTabState);

  return (
    <div>
      <button
        onClick={() => setActiveTab('generated')}
        className={activeTab === 'generated' ? 'active' : ''}
      >
        Generated
      </button>
      <button
        onClick={() => setActiveTab('posted')}
        className={activeTab === 'posted' ? 'active' : ''}
      >
        Posted
      </button>
    </div>
  );
}
```

## Loading State Atoms

#### `isLoadingState`
Global loading state for tweet operations.

```tsx
import { useRecoilState } from 'recoil';
import { isLoadingState } from './atoms';

function LoadingIndicator() {
  const isLoading = useRecoilValue(isLoadingState);

  if (!isLoading) return null;
  return <div>Loading...</div>;
}
```

#### `loadingPhaseState`
Current loading phase (scraping or generating).

```tsx
import { useRecoilValue } from 'recoil';
import { loadingPhaseState } from './atoms';

function LoadingOverlay() {
  const phase = useRecoilValue(loadingPhaseState);

  if (!phase) return null;

  return (
    <div>
      {phase === 'scraping' && 'Scraping tweets...'}
      {phase === 'generating' && 'Generating replies...'}
    </div>
  );
}
```

#### `scrapingStatusTextState`
Detailed status text during scraping.

```tsx
import { useRecoilValue, useSetRecoilState } from 'recoil';
import { scrapingStatusTextState } from './atoms';

function ScrapingProgress() {
  const statusText = useRecoilValue(scrapingStatusTextState);
  const setStatusText = useSetRecoilState(scrapingStatusTextState);

  // Update from polling
  useEffect(() => {
    const poll = async () => {
      const status = await api.getScrapingStatus(username);
      setStatusText(status.message);
    };
    const interval = setInterval(poll, 1000);
    return () => clearInterval(interval);
  }, []);

  return <div>{statusText}</div>;
}
```

## Best Practices

### 1. Use Selectors for Derived State

Instead of this:
```tsx
const userInfo = useRecoilValue(userInfoState);
const handle = userInfo?.handle;
```

Do this:
```tsx
const handle = useRecoilValue(userHandleSelector);
```

### 2. Split Read and Write Concerns

If you only need to read:
```tsx
const username = useRecoilValue(usernameState);
```

If you only need to write:
```tsx
const setUsername = useSetRecoilState(usernameState);
```

If you need both:
```tsx
const [username, setUsername] = useRecoilState(usernameState);
```

### 3. Keep Complex Logic in Selectors

Create new selectors for complex derived state:

```tsx
// In atoms.tsx
export const isUserPremiumSelector = selector<boolean>({
  key: 'isUserPremiumSelector',
  get: ({ get }) => {
    const accountType = get(userAccountTypeSelector);
    return accountType === 'premium';
  },
});

// In component
const isPremium = useRecoilValue(isUserPremiumSelector);
```

### 4. Use Suspense for Async Selectors

For selectors that fetch data asynchronously:

```tsx
export const userSettingsQuery = selector({
  key: 'userSettingsQuery',
  get: async ({ get }) => {
    const handle = get(userHandleSelector);
    if (!handle) return null;
    return await api.getUserSettings(handle);
  },
});

// In component
function SettingsDisplay() {
  return (
    <Suspense fallback={<div>Loading settings...</div>}>
      <SettingsContent />
    </Suspense>
  );
}

function SettingsContent() {
  const settings = useRecoilValue(userSettingsQuery);
  return <div>{JSON.stringify(settings)}</div>;
}
```

### 5. Reset State on Logout

```tsx
import { useResetRecoilState } from 'recoil';
import { usernameState, userInfoState } from './atoms';

function LogoutButton() {
  const resetUsername = useResetRecoilState(usernameState);
  const resetUserInfo = useResetRecoilState(userInfoState);

  const handleLogout = () => {
    resetUsername();
    resetUserInfo();
    // Navigate to login
  };

  return <button onClick={handleLogout}>Logout</button>;
}
```

## Migration from useState

### Before (with useState in App.tsx):
```tsx
function App() {
  const [username, setUsername] = useState<string | null>(
    localStorage.getItem('username')
  );
  const [userInfo, setUserInfo] = useState<UserInfo | null>(null);

  // Pass as props to children
  return <Header username={username} userInfo={userInfo} />;
}
```

### After (with Recoil):
```tsx
function App() {
  // State is managed in Recoil, no props needed
  return <Header />;
}

function Header() {
  // Access state directly from Recoil
  const username = useRecoilValue(usernameState);
  const userInfo = useRecoilValue(userInfoState);

  return <div>@{username}</div>;
}
```

## Debugging

### Use Recoil DevTools

Install the browser extension: [Recoil DevTools](https://chrome.google.com/webstore/detail/recoil-dev-tools/dhjcdlmklknkdhnenhpkinianmmgeaof)

### Log State Changes

```tsx
import { useRecoilValue } from 'recoil';
import { userInfoState } from './atoms';

function DebugLogger() {
  const userInfo = useRecoilValue(userInfoState);

  useEffect(() => {
    console.log('User info changed:', userInfo);
  }, [userInfo]);

  return null;
}
```

### Inspect Atom Keys

All atoms have unique keys that can be used for debugging:
- `usernameState` → key: `'usernameState'`
- `userInfoState` → key: `'userInfoState'`
- etc.

## TypeScript Support

All atoms and selectors are fully typed. TypeScript will automatically infer types:

```tsx
// TypeScript knows username is string | null
const username = useRecoilValue(usernameState);

// TypeScript knows userInfo is UserInfo | null
const userInfo = useRecoilValue(userInfoState);

// TypeScript knows accountType is 'trial' | 'poster' | 'premium' | null
const accountType = useRecoilValue(userAccountTypeSelector);
```

## Common Patterns

### Loading User Info on Mount

```tsx
import { useEffect } from 'react';
import { useRecoilValue, useSetRecoilState } from 'recoil';
import { usernameState, userInfoState } from './atoms';

function App() {
  const username = useRecoilValue(usernameState);
  const setUserInfo = useSetRecoilState(userInfoState);

  useEffect(() => {
    if (username) {
      api.getUserInfo(username).then(setUserInfo);
    }
  }, [username, setUserInfo]);

  return <div>...</div>;
}
```

### Conditional Rendering Based on User State

```tsx
import { useRecoilValue } from 'recoil';
import { hasUserEmailSelector, userAccountTypeSelector } from './atoms';

function ConditionalContent() {
  const hasEmail = useRecoilValue(hasUserEmailSelector);
  const accountType = useRecoilValue(userAccountTypeSelector);

  if (!hasEmail) {
    return <EmailPrompt />;
  }

  if (accountType === 'trial') {
    return <UpgradePrompt />;
  }

  return <PremiumContent />;
}
```

### Updating User Info After API Call

```tsx
import { useSetRecoilState } from 'recoil';
import { userInfoState } from './atoms';

function UpdateEmailButton() {
  const setUserInfo = useSetRecoilState(userInfoState);

  const handleUpdate = async () => {
    const result = await api.updateUserEmail(username, newEmail);

    // Reload user info
    const updatedInfo = await api.getUserInfo(username);
    setUserInfo(updatedInfo);
  };

  return <button onClick={handleUpdate}>Update Email</button>;
}
```
