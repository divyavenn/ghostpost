-- Create bread_accounts table for storing browser states of burner scraping accounts
-- These accounts are NOT tied to users and don't need full twitter_profile data

CREATE TABLE IF NOT EXISTS bread_accounts (
    handle TEXT NOT NULL,
    site TEXT NOT NULL DEFAULT 'twitter',
    state JSONB NOT NULL,  -- Browser state (cookies, localStorage, etc.)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (handle, site)
);

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_bread_accounts_handle ON bread_accounts(handle);

-- Add RLS policies (Row Level Security)
ALTER TABLE bread_accounts ENABLE ROW LEVEL SECURITY;

-- Allow service role full access
CREATE POLICY "Service role can manage bread accounts"
    ON bread_accounts
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Allow authenticated users to read bread accounts (needed for scraping jobs)
CREATE POLICY "Authenticated users can read bread accounts"
    ON bread_accounts
    FOR SELECT
    TO authenticated
    USING (true);

COMMENT ON TABLE bread_accounts IS 'Browser states for burner Twitter accounts used for automated scraping';
COMMENT ON COLUMN bread_accounts.handle IS 'Twitter handle of the bread account';
COMMENT ON COLUMN bread_accounts.site IS 'Site identifier (e.g., twitter)';
COMMENT ON COLUMN bread_accounts.state IS 'Playwright browser storage state (cookies, localStorage, etc.)';
