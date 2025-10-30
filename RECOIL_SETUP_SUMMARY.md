# Recoil State Management - Setup Summary

## What Was Done

### ✅ 1. Installed Recoil
```bash
npm install recoil
```

### ✅ 2. Created State Atoms (frontend/src/atoms.tsx)

#### User State Atoms:
- `usernameState` - Current logged-in username (syncs with localStorage)
- `userInfoState` - Complete user information from backend

#### User Selectors (Derived State):
- `userHandleSelector` - Twitter handle
- `userDisplayNameSelector` - Display name
- `userProfilePicSelector` - Profile picture URL
- `userAccountTypeSelector` - Account type (trial/poster/premium)
- `userFollowerCountSelector` - Follower count
- `hasUserEmailSelector` - Whether user has provided email
- `userStatsSelector` - Lifetime statistics (follows, posts, time saved)

#### UI State Atoms:
- `isSettingsOpenState` - Settings modal open/closed
- `showFirstTimeModalState` - First-time user modal visibility
- `activeTabState` - Current tab (generated/posted)

#### Loading State Atoms:
- `isLoadingState` - Global loading state
- `loadingPhaseState` - Current phase (scraping/generating)
- `scrapingStatusTextState` - Status text during scraping

### ✅ 3. Configured RecoilRoot (frontend/src/main.tsx)

Wrapped the entire app with `<RecoilRoot>`:

```tsx
<RecoilRoot>
  <BrowserRouter>
    <Routes>
      ...
    </Routes>
  </BrowserRouter>
</RecoilRoot>
```

### ✅ 4. Updated TypeScript Interfaces (frontend/src/api/client.ts)

Added to `UserInfo` interface:
```typescript
interface UserInfo {
  // ... existing fields
  account_type?: 'trial' | 'poster' | 'premium';
  uid?: number;
}
```

## How to Use

### Basic Usage

```tsx
import { useRecoilValue, useRecoilState, useSetRecoilState } from 'recoil';
import {
  usernameState,
  userInfoState,
  userHandleSelector,
  userProfilePicSelector,
  userAccountTypeSelector
} from './atoms';

function MyComponent() {
  // Read user handle (derived from userInfoState)
  const handle = useRecoilValue(userHandleSelector);

  // Read profile pic URL
  const profilePic = useRecoilValue(userProfilePicSelector);

  // Read account type
  const accountType = useRecoilValue(userAccountTypeSelector);

  // Read and write username
  const [username, setUsername] = useRecoilState(usernameState);

  // Write-only user info
  const setUserInfo = useSetRecoilState(userInfoState);

  return (
    <div>
      <img src={profilePic} />
      <p>@{handle}</p>
      <span>{accountType}</span>
    </div>
  );
}
```

## Key Benefits

### 1. **No More Prop Drilling**
Before:
```tsx
<App username={username}>
  <Header username={username}>
    <UserMenu username={username}>
      <Profile username={username} />
    </UserMenu>
  </Header>
</App>
```

After:
```tsx
<App>
  <Header>
    <UserMenu>
      <Profile /> {/* Access username directly from Recoil */}
    </UserMenu>
  </Header>
</App>
```

### 2. **Automatic localStorage Sync**
Username is automatically persisted:
```tsx
const [username, setUsername] = useRecoilState(usernameState);
setUsername('newuser'); // Automatically saved to localStorage
```

### 3. **Derived State with Selectors**
No need to extract data manually:
```tsx
// Instead of:
const userInfo = useRecoilValue(userInfoState);
const handle = userInfo?.handle;

// Just do:
const handle = useRecoilValue(userHandleSelector);
```

### 4. **TypeScript Support**
All atoms and selectors are fully typed. TypeScript will catch errors:
```tsx
const accountType = useRecoilValue(userAccountTypeSelector);
// Type: 'trial' | 'poster' | 'premium' | null
```

### 5. **Easy to Test**
Mock Recoil state in tests:
```tsx
<RecoilRoot initializeState={({ set }) => {
  set(usernameState, 'testuser');
  set(userInfoState, mockUserInfo);
}}>
  <ComponentToTest />
</RecoilRoot>
```

## Migration Strategy

The existing App.tsx still uses `useState` for now. To migrate:

### Phase 1: Add Recoil Hooks (Current)
- ✅ Recoil is installed and configured
- ✅ Atoms are defined
- ✅ Can start using in new components

### Phase 2: Gradual Migration (Next)
- Start using Recoil in new components
- Gradually migrate existing components
- Keep backwards compatibility during transition

### Phase 3: Full Migration (Future)
- Remove useState from App.tsx
- Update all components to use Recoil
- Remove prop drilling entirely

## Example: Using in a New Component

```tsx
import { useRecoilValue } from 'recoil';
import {
  userDisplayNameSelector,
  userProfilePicSelector,
  userAccountTypeSelector,
  userStatsSelector
} from '../atoms';

function UserDashboard() {
  const displayName = useRecoilValue(userDisplayNameSelector);
  const profilePic = useRecoilValue(userProfilePicSelector);
  const accountType = useRecoilValue(userAccountTypeSelector);
  const stats = useRecoilValue(userStatsSelector);

  return (
    <div className="dashboard">
      <div className="user-info">
        <img src={profilePic} alt={displayName} />
        <h2>{displayName}</h2>
        <span className="badge">{accountType}</span>
      </div>

      <div className="stats">
        <div>Posts: {stats.lifetimePosts}</div>
        <div>New Follows: {stats.lifetimeNewFollows}</div>
        <div>Time Saved: {stats.scrollingTimeSaved}s</div>
      </div>
    </div>
  );
}
```

## Documentation

Full usage guide: `frontend/RECOIL_USAGE.md`

Includes:
- Detailed API reference for all atoms and selectors
- Best practices
- Common patterns
- Migration guide
- Debugging tips
- TypeScript support

## Next Steps

1. **Start using Recoil in new components** - No changes needed to existing code
2. **Gradually migrate components** - Replace useState with Recoil hooks
3. **Remove prop drilling** - Components access state directly
4. **Add more atoms as needed** - Follow the same pattern in atoms.tsx

## Files Changed

1. ✅ `frontend/package.json` - Added recoil dependency
2. ✅ `frontend/src/main.tsx` - Added RecoilRoot
3. ✅ `frontend/src/atoms.tsx` - Created all state atoms and selectors
4. ✅ `frontend/src/api/client.ts` - Updated UserInfo interface
5. ✅ `frontend/RECOIL_USAGE.md` - Complete usage documentation
6. ✅ `RECOIL_SETUP_SUMMARY.md` - This file

## Testing Recoil Setup

To verify Recoil is working, create a test component:

```tsx
// src/components/RecoilTest.tsx
import { useRecoilValue } from 'recoil';
import { usernameState } from '../atoms';

export function RecoilTest() {
  const username = useRecoilValue(usernameState);
  return <div>Recoil working! Username: {username}</div>;
}
```

Add to App.tsx temporarily:
```tsx
import { RecoilTest } from './components/RecoilTest';

function App() {
  return (
    <>
      <RecoilTest />
      {/* rest of app */}
    </>
  );
}
```

If you see the username displayed, Recoil is working! 🎉

## Support

- [Recoil Documentation](https://recoiljs.org/)
- [Recoil Tutorial](https://recoiljs.org/docs/introduction/getting-started)
- [Recoil API Reference](https://recoiljs.org/docs/api-reference/core/RecoilRoot)
