# First-Time User Flow Documentation

## Overview

When a user logs in for the first time, the system now automatically:
1. **Auto-generates a unique `uid`** (local user ID, not Twitter's ID)
2. **Shows a welcome modal** asking for their email address
3. **Provides setup instructions** to configure accounts and topics

## Backend Changes

### 1. User Model Updates (backend/backend/data_validation.py)

```python
class User(BaseModel):
  # account info
  uid: int | None = None  # Auto-generated on first creation
  email: str | None = None  # Collected after first login
```

Both `uid` and `email` are now optional to support first-time user creation.

### 2. Auto-Generated UID (backend/backend/utils.py:369-375)

```python
# Set default values for new users
if is_new_user:
    target.setdefault("account_type", "trial")
    target.setdefault("scrapes_left", 3)
    target.setdefault("posts_left", 3)

    # Auto-generate uid if not provided
    if "uid" not in target or target["uid"] is None:
        # Find max uid and add 1
        existing_uids = [e.get("uid") for e in entries if e.get("uid") is not None]
        max_uid = max(existing_uids) if existing_uids else 0
        target["uid"] = max_uid + 1
        notify(f"🆔 Auto-generated uid={target['uid']} for new user @{handle}")
```

**Logic:**
- Scans all existing users to find the maximum UID
- Assigns `max_uid + 1` to the new user
- Ensures unique, incrementing UIDs

### 3. Email Update Endpoint (backend/backend/user.py:238-263)

```python
@router.patch("/{handle}/email")
async def update_user_email_endpoint(handle: str, payload: UpdateEmailRequest) -> dict:
    """Update user email address (typically used by first-time users)."""
```

**Endpoint:** `PATCH /api/user/{handle}/email`

**Request Body:**
```json
{
  "email": "user@example.com"
}
```

**Response:**
```json
{
  "message": "Email updated successfully",
  "email": "user@example.com"
}
```

## Frontend Changes

### 1. FirstTimeUserModal Component (frontend/src/components/FirstTimeUserModal.tsx)

**Features:**
- Welcome message with username
- Email input field with validation
- Setup instructions:
  1. Go to User Settings
  2. Set up accounts to track and topics of interest
  3. Start discovering tweets
- "Skip for now" option
- Loading state during submission

**Props:**
```typescript
interface FirstTimeUserModalProps {
  username: string;
  onComplete: (email: string) => Promise<void>;
}
```

### 2. App Integration (frontend/src/App.tsx)

**State:**
```typescript
const [showFirstTimeModal, setShowFirstTimeModal] = useState(false);
```

**Detection Logic (in `loadUserInfo`):**
```typescript
// Check if user needs to provide email (first-time users)
if (!info.email || info.email.trim() === '') {
  setShowFirstTimeModal(true);
}
```

**Handler:**
```typescript
const handleFirstTimeModalComplete = async (email: string) => {
  if (!username) return;

  try {
    if (email) {
      await api.updateUserEmail(username, email);
    }
    setShowFirstTimeModal(false);
    await loadUserInfo(username);
  } catch (error) {
    console.error('Failed to save email:', error);
    throw error; // Re-throw to let modal show error
  }
};
```

### 3. API Client (frontend/src/api/client.ts:242-252)

```typescript
updateUserEmail: async (handle: string, email: string): Promise<{ message: string; email: string }> => {
  const response = await fetch(`${API_BASE_URL}/user/${encodeURIComponent(handle)}/email`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ email }),
  });
  if (!response.ok) throw new Error('Failed to update user email');
  return response.json();
}
```

## User Flow

### First-Time Login

1. **User completes OAuth login** via Twitter
2. **Backend creates user record** in `user_info.json`:
   ```json
   {
     "uid": 4,  // Auto-generated
     "handle": "newuser",
     "username": "New User",
     "profile_pic_url": "https://...",
     "follower_count": 100,
     "email": null,  // Not set yet
     "account_type": "trial",
     "scrapes_left": 3,
     "posts_left": 3,
     "models": [],
     "relevant_accounts": {},
     "queries": []
   }
   ```

3. **Frontend loads user info** and detects missing email
4. **FirstTimeUserModal appears** with:
   - Personalized welcome message
   - Email input field
   - Setup instructions
   - Skip option

5. **User enters email** and clicks "Continue"
6. **Frontend calls** `PATCH /api/user/{handle}/email`
7. **Backend updates** user record with email
8. **Modal closes** and user can use the app

9. **Settings modal auto-opens** if user has no accounts/queries configured

### Subsequent Logins

- Email is already set → No modal shown
- User proceeds directly to app
- Settings modal only shows if accounts/queries not configured

## Default Values for New Users

| Field | Value | Description |
|-------|-------|-------------|
| `uid` | Auto-generated | Unique incremental ID |
| `email` | `null` | Collected via modal |
| `account_type` | `"trial"` | Free tier |
| `scrapes_left` | `3` | Free scrapes |
| `posts_left` | `3` | Free posts |
| `models` | `[]` | No AI models selected |
| `relevant_accounts` | `{}` | No accounts tracked |
| `queries` | `[]` | No search queries |
| `max_tweets_retrieve` | `30` | Default limit |
| `number_of_generations` | `2` | Reply variations |
| `lifetime_new_follows` | `0` | Metric starts at 0 |
| `lifetime_posts` | `0` | Metric starts at 0 |
| `scrolling_time_saved` | `0` | Metric starts at 0 |

## Testing

### Test UID Generation

```bash
uv run python -c "
from backend.utils import write_user_info, load_user_info_entries

new_user = {
    'handle': 'test_user',
    'username': 'Test User',
    'profile_pic_url': 'https://example.com/pic.jpg',
    'follower_count': 10
}

write_user_info(new_user)

entries = load_user_info_entries()
test_user = next((e for e in entries if e['handle'] == 'test_user'), None)
print(f'Created user with uid={test_user.get(\"uid\")}')
"
```

### Test Email Update

```bash
curl -X PATCH http://localhost:8000/api/user/test_user/email \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'
```

## Error Handling

### Backend
- Missing user: 404 error
- Invalid email format: Validated by Pydantic (optional field)
- Database write failures: Logged to `errors.jsonl`

### Frontend
- Network errors: Shown in modal with retry option
- Missing username: Modal won't render
- Skip option: Allows empty email to be submitted

## UI/UX Considerations

1. **Non-blocking**: User can skip email entry
2. **Persistent**: Modal shows every login until email is provided
3. **Helpful**: Provides clear next steps for setup
4. **Styled**: Matches app's dark theme with modern design
5. **Accessible**: Auto-focus on email field, keyboard navigation

## Future Enhancements

- [ ] Email validation via confirmation link
- [ ] Re-show modal for users who skipped
- [ ] Collect additional profile data (location, interests)
- [ ] Welcome tutorial/onboarding flow
- [ ] Email preferences (notifications, updates)
