# User Data Repair Tool

## Overview

The `repair_user_data.py` script validates and repairs entries in `user_info.json` according to the data models defined in `data_validation.py`.

## Features

- ✅ Validates all user entries against the `User` model from `data_validation.py`
- 🔧 Interactively prompts for corrections when validation errors are found
- 💾 Safely saves repaired data using atomic file updates
- ⏭️ Allows skipping individual users or fields
- 🔒 Creates backups before saving changes

## Usage

### Basic Usage

```bash
python repair_user_data.py
```

or

```bash
uv run python repair_user_data.py
```

### What the Script Does

1. **Loads** all entries from `cache/user_info.json`
2. **Validates** each entry against the `User` model
3. **Reports** validation errors for each invalid entry
4. **Prompts** you to fix each error interactively
5. **Confirms** before saving changes

### Example Session

```
============================================================
USER DATA REPAIR TOOL
============================================================
Reading from: /Users/.../backend/cache/user_info.json

Found 3 user entries

============================================================
Checking user: john_doe
============================================================
✅ User 'john_doe' is valid

============================================================
Checking user: broken_user
============================================================
❌ User 'broken_user' has validation errors:
  - email: Field required (type: missing)
  - follower_count: Field required (type: missing)

Current data: {
  "handle": "broken_user",
  "username": "broken_user",
  "account_type": "trial"
}

Repair this user? (y/n/skip): y

--- Repairing field: email ---
Enter value for 'email' (str | None) [optional, press Enter to skip]: user@example.com
✅ Updated 'email' = user@example.com

--- Repairing field: follower_count ---
Enter value for 'follower_count' (int | None) [optional, press Enter to skip]: 100
✅ Updated 'follower_count' = 100

✅ User 'broken_user' successfully repaired and validated!

============================================================
SAVING CHANGES
============================================================
Save 3 entries to user_info.json? (y/n): y
✅ Successfully saved repaired data
```

## Input Format Guidelines

### String Fields
Just type the value:
```
Enter value for 'email': user@example.com
```

### Integer Fields
Type a number:
```
Enter value for 'follower_count': 100
```

### Boolean Fields
Type `true`, `yes`, `1`, `y` for true, anything else for false:
```
Enter value for 'some_flag': yes
```

### List Fields
Either:
- JSON array: `["item1", "item2"]`
- Comma-separated: `item1, item2, item3`

```
Enter value for 'models': ["gpt-4", "claude-3"]
# or
Enter value for 'queries': AI news, tech updates
```

### Dictionary Fields
Use JSON format:
```
Enter value for 'relevant_accounts': {"elonmusk": true, "user2": false}
```

### Optional Fields
Press Enter to skip:
```
Enter value for 'email' [optional, press Enter to skip]:
```

## User Model Fields

### Required Fields
- `handle` (str): Twitter handle
- `username` (str): Twitter username

### Optional Fields
- `uid` (int): User ID
- `email` (str): Email address
- `profile_pic_url` (str): Profile picture URL
- `follower_count` (int): Number of followers
- `account_type` (str): "trial", "poster", or "premium" (default: "trial")
- `models` (list[str]): List of AI models to use
- `relevant_accounts` (dict): Accounts to track (handle -> verified boolean)
- `queries` (list[str]): Search queries
- `max_tweets_retrieve` (int): Max tweets per scrape (default: 30)
- `number_of_generations` (int): Number of reply generations (default: 2)
- `scrapes_left` (int): Remaining scrapes
- `posts_left` (int): Remaining posts
- `lifetime_new_follows` (int): Total new follows (default: 0)
- `lifetime_posts` (int): Total posts made (default: 0)
- `scrolling_time_saved` (int): Time saved in seconds (default: 0)

## Testing

To test the validation without modifying files, run the demo:

```bash
python test_repair_demo.py
```

This shows how the validator detects issues without making any changes.

## Safety Features

1. **Atomic Updates**: Uses `atomic_file_update()` to ensure file integrity
2. **Confirmation**: Always asks before saving changes
3. **Skip Option**: Can skip individual users or repair attempts
4. **Error Logging**: All validation errors are logged to `errors.jsonl`
5. **Current Value Display**: Shows existing values when prompting for changes

## Error Handling

If a repaired entry still has validation errors after your fixes:
- You'll see the remaining errors
- You can choose to retry the repair
- Or keep the entry with errors (logged but not blocking)

## Integration with Backend

This script uses:
- `backend.data_validation.User` - The validation model
- `backend.utils.load_user_info_entries()` - To read user data
- `backend.utils.atomic_file_update()` - To safely save changes
- `backend.config.USER_INFO_FILE` - File path configuration

All repairs are automatically logged to `cache/errors.jsonl` for monitoring.

## Common Issues

### Issue: "Field required"
**Solution**: The field is missing from the entry. Enter a value when prompted, or press Enter if it's optional.

### Issue: "Input should be a valid integer"
**Solution**: The field value has the wrong type. Enter the correct type (e.g., number instead of text).

### Issue: "Invalid literal for account_type"
**Solution**: `account_type` must be exactly "trial", "poster", or "premium" (case-sensitive).

## Exit Codes

- `0`: Success (all entries valid or repairs saved)
- `1`: Error (file not found, save failed, or changes not confirmed)
