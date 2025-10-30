# Local State → Recoil Synchronization Pattern

## Overview

App.tsx maintains local `useState` for backwards compatibility while **automatically syncing** all state changes to global Recoil atoms. This allows:

1. **Existing code continues to work** without modification
2. **New components can access state** via Recoil hooks
3. **Gradual migration** from local state to global state
4. **Zero breaking changes** to existing components

## How It Works

### 1. Dual State Management

App.tsx maintains both local state and Recoil state:

```tsx
function App() {
  // Local state (existing)
  const [username, setUsername] = useState<string | null>(
    localStorage.getItem('username')
  );
  const [userInfo, setUserInfo] = useState<UserInfo | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  // ... etc

  // Recoil setters (new)
  const setRecoilUsername = useSetRecoilState(usernameState);
  const setRecoilUserInfo = useSetRecoilState(userInfoState);
  const setRecoilIsLoading = useSetRecoilState(isLoadingState);
  // ... etc
}
```

### 2. Automatic Synchronization

`useEffect` hooks automatically sync local state → Recoil:

```tsx
// Sync username to Recoil whenever it changes
useEffect(() => {
  setRecoilUsername(username);
}, [username, setRecoilUsername]);

// Sync userInfo to Recoil whenever it changes
useEffect(() => {
  setRecoilUserInfo(userInfo);
}, [userInfo, setRecoilUserInfo]);
```

**This means:**
- When `setUsername(...)` is called in App.tsx → Recoil `usernameState` updates automatically
- When `setUserInfo(...)` is called in App.tsx → Recoil `userInfoState` updates automatically
- All components using Recoil hooks get the latest values immediately

## Synced State

### User State
| Local State | Recoil Atom | Auto-Synced |
|------------|-------------|-------------|
| `username` | `usernameState` | ✅ |
| `userInfo` | `userInfoState` | ✅ |

### UI State
| Local State | Recoil Atom | Auto-Synced |
|------------|-------------|-------------|
| `isSettingsOpen` | `isSettingsOpenState` | ✅ |
| `showFirstTimeModal` | `showFirstTimeModalState` | ✅ |
| `activeTab` | `activeTabState` | ✅ |

### Loading State
| Local State | Recoil Atom | Auto-Synced |
|------------|-------------|-------------|
| `isLoading` | `isLoadingState` | ✅ |
| `loadingPhase` | `loadingPhaseState` | ✅ |
| `scrapingStatusText` | `scrapingStatusTextState` | ✅ |

## Usage Patterns

### Pattern 1: Existing Components (No Changes Needed)

Components that receive props from App.tsx continue to work:

```tsx
// Header.tsx - receives props as before
function Header({ username }: { username: string }) {
  return <div>@{username}</div>;
}

// In App.tsx - still passes props
<Header username={username} />
```

**No changes required!** The state sync happens automatically in the background.

### Pattern 2: New Components (Use Recoil Directly)

New components can access state directly without props:

```tsx
// NewComponent.tsx - uses Recoil
import { useRecoilValue } from 'recoil';
import { userHandleSelector, userAccountTypeSelector } from '../atoms';

function NewComponent() {
  const handle = useRecoilValue(userHandleSelector);
  const accountType = useRecoilValue(userAccountTypeSelector);

  return (
    <div>
      <p>@{handle}</p>
      <span>{accountType}</span>
    </div>
  );
}

// In App.tsx - no props needed!
<NewComponent />
```

### Pattern 3: Deep Child Components (No Prop Drilling)

Components deep in the tree can access state without props:

```tsx
// Before: Props passed through multiple levels
<App username={username}>
  <Dashboard username={username}>
    <Sidebar username={username}>
      <UserMenu username={username}>
        <Profile username={username} />  {/* Finally uses it */}
      </UserMenu>
    </Sidebar>
  </Dashboard>
</App>

// After: Direct access at any level
<App>
  <Dashboard>
    <Sidebar>
      <UserMenu>
        <Profile />  {/* Uses Recoil directly */}
      </UserMenu>
    </Sidebar>
  </Dashboard>
</App>

// Profile.tsx
import { useRecoilValue } from 'recoil';
import { usernameState } from '../atoms';

function Profile() {
  const username = useRecoilValue(usernameState);
  return <div>@{username}</div>;
}
```

## Testing the Synchronization

### Use the Debug Component

Add to App.tsx temporarily:

```tsx
import { RecoilStateDebug } from './components/RecoilStateDebug';

function App() {
  // ... existing code

  return (
    <Background>
      {/* Your app content */}

      {/* Debug panel - remove in production */}
      <RecoilStateDebug />
    </Background>
  );
}
```

This shows **live updates** of all Recoil atoms as you interact with the app.

### Verify Sync is Working

1. **Open the app** in browser
2. **Look for the debug panel** in bottom-right corner
3. **Interact with the app:**
   - Login → See `username` and `userInfo` update in debug panel
   - Open settings → See `isSettingsOpen` change to true
   - Switch tabs → See `activeTab` change
   - Scrape tweets → See `isLoading` and `loadingPhase` update
4. **Check that values update in real-time**

### Test in Browser Console

```javascript
// In React DevTools or browser console
// Find the Recoil atoms and verify they match App.tsx state
```

## Migration Strategy

### Phase 1: Dual State (Current) ✅

- Local state in App.tsx
- Recoil atoms automatically synced
- Both work simultaneously
- **Zero breaking changes**

### Phase 2: Gradual Adoption (Next)

Start using Recoil in:
1. New components first
2. Deeply nested components (avoid prop drilling)
3. Shared components used in multiple places

Example:
```tsx
// Old: Props everywhere
<UserBadge username={username} accountType={accountType} />

// New: Recoil
<UserBadge />  // Gets data from Recoil internally
```

### Phase 3: Full Migration (Future)

Eventually remove local state from App.tsx:

```tsx
// Instead of:
const [username, setUsername] = useState<string | null>(null);
const setRecoilUsername = useSetRecoilState(usernameState);
useEffect(() => setRecoilUsername(username), [username]);

// Just use:
const [username, setUsername] = useRecoilState(usernameState);
```

## Best Practices

### 1. Keep Sync Effects at Top of Component

Place all sync effects together for clarity:

```tsx
function App() {
  // 1. Local state
  const [username, setUsername] = useState(...);
  const [userInfo, setUserInfo] = useState(...);

  // 2. Recoil setters
  const setRecoilUsername = useSetRecoilState(usernameState);
  const setRecoilUserInfo = useSetRecoilState(userInfoState);

  // 3. Sync effects
  useEffect(() => setRecoilUsername(username), [username, setRecoilUsername]);
  useEffect(() => setRecoilUserInfo(userInfo), [userInfo, setRecoilUserInfo]);

  // 4. Rest of component logic
  const loadData = async () => { ... };
}
```

### 2. Use Selectors for Derived State

Don't compute in components, use selectors:

```tsx
// ❌ Don't do this in every component
const handle = userInfo?.handle;
const accountType = userInfo?.account_type;

// ✅ Use selectors instead
const handle = useRecoilValue(userHandleSelector);
const accountType = useRecoilValue(userAccountTypeSelector);
```

### 3. Read-Only Access Uses `useRecoilValue`

If component only needs to read:

```tsx
// ❌ Don't use useState hook if only reading
const [username] = useRecoilState(usernameState);

// ✅ Use value hook instead
const username = useRecoilValue(usernameState);
```

### 4. Document Which Components Use Recoil

Add comments to components:

```tsx
/**
 * UserDashboard - Uses Recoil for state
 *
 * Atoms used:
 * - userInfoState (read)
 * - activeTabState (read/write)
 */
function UserDashboard() {
  // ... component code
}
```

## Debugging Tips

### Check if Sync is Working

1. **Use RecoilStateDebug component** (shows live values)
2. **React DevTools** → Components → Look for Recoil atoms
3. **Browser console:**
   ```javascript
   // Check Recoil state
   window.__RECOIL_STATE__  // If debug tools installed
   ```

### Common Issues

#### Issue: Recoil state is `null` but local state has value

**Cause:** Sync effect hasn't run yet (component just mounted)

**Solution:** Effects run after render, this is normal. State will sync on next tick.

#### Issue: Recoil state is stale

**Cause:** Component might be using cached value

**Solution:** Ensure you're using `useRecoilValue()` not storing in local var:

```tsx
// ❌ Don't do this
const username = useRecoilValue(usernameState);
const cachedUsername = username;  // This won't update

// ✅ Do this
const username = useRecoilValue(usernameState);  // Always fresh
```

#### Issue: Updates are slow

**Cause:** Too many components subscribed to the same atom

**Solution:** Use selectors to narrow subscriptions:

```tsx
// ❌ Subscribes to all userInfo changes
const userInfo = useRecoilValue(userInfoState);
return <div>{userInfo?.handle}</div>;

// ✅ Only subscribes to handle changes
const handle = useRecoilValue(userHandleSelector);
return <div>{handle}</div>;
```

## Performance Considerations

### Sync Effects are Cheap

The sync effects only run when state actually changes:
- `useEffect` with dependency array
- React optimizes no-op updates
- Minimal performance impact

### Recoil Optimizations

Recoil automatically:
- Only re-renders components using changed atoms
- Batches updates for performance
- Memoizes selector computations

### Best for Performance

Use specific selectors instead of full objects:

```tsx
// Less efficient - subscribes to all userInfo changes
const userInfo = useRecoilValue(userInfoState);
const handle = userInfo?.handle;
const accountType = userInfo?.account_type;

// More efficient - only subscribes to specific values
const handle = useRecoilValue(userHandleSelector);
const accountType = useRecoilValue(userAccountTypeSelector);
```

## Example: Real-World Usage

### Creating a User Badge Component

```tsx
// UserBadge.tsx
import { useRecoilValue } from 'recoil';
import {
  userHandleSelector,
  userProfilePicSelector,
  userAccountTypeSelector
} from '../atoms';

export function UserBadge() {
  const handle = useRecoilValue(userHandleSelector);
  const profilePic = useRecoilValue(userProfilePicSelector);
  const accountType = useRecoilValue(userAccountTypeSelector);

  const badgeColor = {
    trial: 'bg-yellow-500',
    poster: 'bg-blue-500',
    premium: 'bg-purple-500'
  }[accountType || 'trial'];

  return (
    <div className="flex items-center gap-2">
      <img src={profilePic} className="w-8 h-8 rounded-full" />
      <span>@{handle}</span>
      <span className={`${badgeColor} px-2 py-1 rounded text-xs`}>
        {accountType}
      </span>
    </div>
  );
}
```

**Use anywhere without props:**

```tsx
// Header.tsx
<UserBadge />

// Sidebar.tsx
<UserBadge />

// Settings.tsx
<UserBadge />
```

## Summary

✅ **Local state in App.tsx** automatically syncs to Recoil
✅ **Existing components** continue working unchanged
✅ **New components** can use Recoil directly
✅ **No prop drilling** for deeply nested components
✅ **Gradual migration** possible without breaking changes
✅ **Type-safe** with full TypeScript support
✅ **Testable** with debug component included

The sync pattern provides the best of both worlds: backwards compatibility + modern state management.
