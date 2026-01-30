-- Update twitter_relevant_accounts table to support new format
-- Add user_id column and rename enabled to validated

-- Add user_id column (nullable for backward compatibility)
ALTER TABLE twitter_relevant_accounts
ADD COLUMN IF NOT EXISTS user_id TEXT;

-- Rename enabled to validated (keeping semantic meaning clear)
ALTER TABLE twitter_relevant_accounts
RENAME COLUMN enabled TO validated;

-- Add index for user_id lookups
CREATE INDEX IF NOT EXISTS idx_relevant_accounts_user_id
ON twitter_relevant_accounts(user_id);

COMMENT ON COLUMN twitter_relevant_accounts.user_id IS 'Twitter user ID for the relevant account (for API calls)';
COMMENT ON COLUMN twitter_relevant_accounts.validated IS 'Whether this account has been validated/verified';
