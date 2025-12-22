-- GhostPoster Supabase Schema
-- Run this in Supabase SQL Editor

-- =============================================================================
-- DROP EXISTING TABLES (in reverse dependency order)
-- =============================================================================
DROP TABLE IF EXISTS browser_states CASCADE;
DROP TABLE IF EXISTS twitter_background_tasks_log CASCADE;
DROP TABLE IF EXISTS twitter_background_tasks CASCADE;
DROP TABLE IF EXISTS error_logs CASCADE;
DROP TABLE IF EXISTS twitter_activity_log CASCADE;
DROP TABLE IF EXISTS twitter_comments CASCADE;
DROP TABLE IF EXISTS twitter_posted_tweets CASCADE;
DROP TABLE IF EXISTS twitter_seen_tweets CASCADE;
DROP TABLE IF EXISTS twitter_queries CASCADE;
DROP TABLE IF EXISTS twitter_relevant_accounts CASCADE;
DROP TABLE IF EXISTS twitter_tokens CASCADE;
DROP TABLE IF EXISTS twitter_profiles CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- Also drop old table names if they exist
DROP TABLE IF EXISTS background_tasks CASCADE;
DROP TABLE IF EXISTS activity_logs CASCADE;
DROP TABLE IF EXISTS comments CASCADE;
DROP TABLE IF EXISTS posted_tweets CASCADE;
DROP TABLE IF EXISTS seen_tweets CASCADE;
DROP TABLE IF EXISTS queries CASCADE;
DROP TABLE IF EXISTS relevant_accounts CASCADE;
DROP TABLE IF EXISTS tokens CASCADE;

-- =============================================================================
-- USERS TABLE (extends auth.users with application-specific data)
-- =============================================================================
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    account_type TEXT DEFAULT 'trial' CHECK (account_type IN ('trial', 'poster', 'premium')),

    -- User-level settings (shared across all Twitter profiles)
    models TEXT[] DEFAULT '{}',
    knowledge_base JSONB,  -- Optional knowledge base for the user
    intent TEXT DEFAULT ''
);

-- =============================================================================
-- TWITTER PROFILES TABLE (per-Twitter-account data)
-- =============================================================================
CREATE TABLE IF NOT EXISTS twitter_profiles (
    handle TEXT PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Profile info
    username TEXT,
    profile_pic_url TEXT,
    follower_count INTEGER DEFAULT 0,

    -- Per-profile settings
    ideal_num_posts INTEGER DEFAULT 30,
    number_of_generations INTEGER DEFAULT 2,
    min_impressions_filter INTEGER DEFAULT 2000,
    manual_minimum_impressions INTEGER,
    intent_filter_examples JSONB DEFAULT '[]',
    intent_filter_last_updated TIMESTAMPTZ,

    -- Metrics
    lifetime_new_follows INTEGER DEFAULT 0,
    lifetime_posts INTEGER DEFAULT 0,
    scrolling_time_saved INTEGER DEFAULT 0,
    scrapes_left INTEGER,
    posts_left INTEGER,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for twitter_profiles
CREATE INDEX IF NOT EXISTS idx_twitter_profiles_user_id ON twitter_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_twitter_profiles_handle ON twitter_profiles(handle);

-- =============================================================================
-- TWITTER TOKENS TABLE (per Twitter profile, 1:1 relationship)
-- =============================================================================
CREATE TABLE IF NOT EXISTS twitter_tokens (
    handle TEXT PRIMARY KEY REFERENCES twitter_profiles(handle) ON DELETE CASCADE,
    access_token TEXT,
    refresh_token TEXT,
    expires_at DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- TWITTER RELEVANT ACCOUNTS TABLE (per Twitter profile)
-- =============================================================================
CREATE TABLE IF NOT EXISTS twitter_relevant_accounts (
    handle TEXT NOT NULL REFERENCES twitter_profiles(handle) ON DELETE CASCADE,
    account_handle TEXT NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY(handle, account_handle)
);

-- Index on handle FK for fast lookups
CREATE INDEX IF NOT EXISTS idx_twitter_relevant_accounts_handle ON twitter_relevant_accounts(handle);

-- =============================================================================
-- TWITTER QUERIES TABLE (per Twitter profile)
-- =============================================================================
CREATE TABLE IF NOT EXISTS twitter_queries (
    handle TEXT NOT NULL REFERENCES twitter_profiles(handle) ON DELETE CASCADE,
    query TEXT NOT NULL,
    summary TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY(handle, query)
);

-- Index on handle FK for fast lookups
CREATE INDEX IF NOT EXISTS idx_twitter_queries_handle ON twitter_queries(handle);

-- =============================================================================
-- TWITTER SEEN TWEETS TABLE (per Twitter profile)
-- =============================================================================
CREATE TABLE IF NOT EXISTS twitter_seen_tweets (
    handle TEXT NOT NULL REFERENCES twitter_profiles(handle) ON DELETE CASCADE,
    tweet_id TEXT NOT NULL,
    seen_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY(handle, tweet_id)
);

-- Indexes for fast lookups and cleanup (handle is already indexed as part of PK)
CREATE INDEX IF NOT EXISTS idx_twitter_seen_tweets_time ON twitter_seen_tweets(handle, seen_at);

-- =============================================================================
-- TWITTER POSTED TWEETS TABLE (per Twitter profile)
-- =============================================================================
CREATE TABLE IF NOT EXISTS twitter_posted_tweets (
    tweet_id TEXT PRIMARY KEY,
    handle TEXT NOT NULL REFERENCES twitter_profiles(handle) ON DELETE CASCADE,
    text TEXT,

    -- Performance metrics
    likes INTEGER DEFAULT 0,
    retweets INTEGER DEFAULT 0,
    quotes INTEGER DEFAULT 0,
    replies INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    score REAL DEFAULT 0,

    -- Metadata
    created_at TIMESTAMPTZ,
    url TEXT,
    last_metrics_update TIMESTAMPTZ,

    -- Media and parent info (JSONB for flexibility)
    media JSONB DEFAULT '[]',
    parent_chain JSONB DEFAULT '[]',
    response_to_thread JSONB DEFAULT '[]',
    responding_to TEXT,
    replying_to_pfp TEXT,
    original_tweet_url TEXT,
    parent_media JSONB DEFAULT '[]',

    -- Source and monitoring
    source TEXT DEFAULT 'app_posted' CHECK (source IN ('app_posted', 'external')),
    monitoring_state TEXT DEFAULT 'active' CHECK (monitoring_state IN ('active', 'warm', 'cold')),
    post_type TEXT DEFAULT 'reply' CHECK (post_type IN ('original', 'reply', 'comment_reply')),

    -- Activity tracking
    last_activity_at TIMESTAMPTZ,
    last_scraped_reply_ids JSONB DEFAULT '[]',

    -- Resurrection
    resurrected_via TEXT DEFAULT 'none' CHECK (resurrected_via IN ('none', 'notification', 'search')),

    -- Quoted tweet
    quoted_tweet JSONB
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_twitter_posted_tweets_handle ON twitter_posted_tweets(handle);
CREATE INDEX IF NOT EXISTS idx_twitter_posted_tweets_state ON twitter_posted_tweets(handle, monitoring_state);
CREATE INDEX IF NOT EXISTS idx_twitter_posted_tweets_score ON twitter_posted_tweets(handle, score DESC);
CREATE INDEX IF NOT EXISTS idx_twitter_posted_tweets_created ON twitter_posted_tweets(handle, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_twitter_posted_tweets_type ON twitter_posted_tweets(handle, post_type);

-- =============================================================================
-- TWITTER COMMENTS TABLE (per Twitter profile)
-- =============================================================================
CREATE TABLE IF NOT EXISTS twitter_comments (
    tweet_id TEXT PRIMARY KEY,
    handle TEXT NOT NULL REFERENCES twitter_profiles(handle) ON DELETE CASCADE,
    text TEXT,

    -- Commenter info
    commenter_handle TEXT,
    commenter_username TEXT,
    author_profile_pic_url TEXT,
    followers INTEGER DEFAULT 0,

    -- Performance metrics
    likes INTEGER DEFAULT 0,
    retweets INTEGER DEFAULT 0,
    quotes INTEGER DEFAULT 0,
    replies INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,

    -- Metadata
    created_at TIMESTAMPTZ,
    url TEXT,
    last_metrics_update TIMESTAMPTZ,

    -- Parent chain and reply info
    parent_chain JSONB DEFAULT '[]',
    in_reply_to_status_id TEXT,

    -- Comment-specific
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'replied', 'skipped')),
    generated_replies JSONB DEFAULT '[]',
    edited BOOLEAN DEFAULT FALSE,

    -- Monitoring
    source TEXT DEFAULT 'external',
    monitoring_state TEXT DEFAULT 'active',
    last_activity_at TIMESTAMPTZ,
    resurrected_via TEXT DEFAULT 'none',
    last_scraped_reply_ids JSONB DEFAULT '[]',

    -- Optional fields
    thread JSONB DEFAULT '[]',
    other_replies JSONB DEFAULT '[]',
    quoted_tweet JSONB,
    media JSONB DEFAULT '[]',
    engagement_type TEXT DEFAULT 'reply' CHECK (engagement_type IN ('reply', 'quote_tweet'))
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_twitter_comments_handle ON twitter_comments(handle);
CREATE INDEX IF NOT EXISTS idx_twitter_comments_status ON twitter_comments(handle, status);
CREATE INDEX IF NOT EXISTS idx_twitter_comments_parent ON twitter_comments(in_reply_to_status_id);
CREATE INDEX IF NOT EXISTS idx_twitter_comments_created ON twitter_comments(handle, created_at DESC);

-- =============================================================================
-- TWITTER ACTIVITY LOG TABLE (per Twitter profile)
-- =============================================================================
CREATE TABLE IF NOT EXISTS twitter_activity_log (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    handle TEXT REFERENCES twitter_profiles(handle) ON DELETE SET NULL,
    action TEXT NOT NULL,
    tweet_id TEXT,
    metadata JSONB DEFAULT '{}'
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_twitter_activity_log_handle ON twitter_activity_log(handle);
CREATE INDEX IF NOT EXISTS idx_twitter_activity_log_time ON twitter_activity_log(handle, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_twitter_activity_log_action ON twitter_activity_log(action);

-- =============================================================================
-- ERROR LOGS TABLE (linked to users via auth.users)
-- =============================================================================
CREATE TABLE IF NOT EXISTS error_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    message TEXT,
    status_code INTEGER,
    function_name TEXT,
    exception TEXT
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_error_logs_user_id ON error_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_error_logs_time ON error_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_error_logs_function ON error_logs(function_name);

-- =============================================================================
-- TWITTER BACKGROUND TASKS LOG TABLE (per Twitter profile)
-- =============================================================================
CREATE TABLE IF NOT EXISTS twitter_background_tasks_log (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    handle TEXT REFERENCES twitter_profiles(handle) ON DELETE SET NULL,
    task_type TEXT NOT NULL,
    details JSONB DEFAULT '{}'
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_twitter_background_tasks_log_handle ON twitter_background_tasks_log(handle);
CREATE INDEX IF NOT EXISTS idx_twitter_background_tasks_log_time ON twitter_background_tasks_log(timestamp DESC);

-- =============================================================================
-- BROWSER STATES TABLE (per user, with site field)
-- =============================================================================
CREATE TABLE IF NOT EXISTS browser_states (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    site TEXT NOT NULL,  -- e.g., 'twitter', 'linkedin', etc.
    state JSONB NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, site)
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_browser_states_user_id ON browser_states(user_id);
CREATE INDEX IF NOT EXISTS idx_browser_states_user_site ON browser_states(user_id, site);

-- =============================================================================
-- HELPER FUNCTIONS
-- =============================================================================

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to twitter_profiles table
DROP TRIGGER IF EXISTS update_twitter_profiles_updated_at ON twitter_profiles;
CREATE TRIGGER update_twitter_profiles_updated_at
    BEFORE UPDATE ON twitter_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Apply trigger to twitter_tokens table
DROP TRIGGER IF EXISTS update_twitter_tokens_updated_at ON twitter_tokens;
CREATE TRIGGER update_twitter_tokens_updated_at
    BEFORE UPDATE ON twitter_tokens
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- ROW LEVEL SECURITY (Recommended for Supabase Auth)
-- =============================================================================
-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE twitter_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE twitter_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE twitter_relevant_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE twitter_queries ENABLE ROW LEVEL SECURITY;
ALTER TABLE twitter_seen_tweets ENABLE ROW LEVEL SECURITY;
ALTER TABLE twitter_posted_tweets ENABLE ROW LEVEL SECURITY;
ALTER TABLE twitter_comments ENABLE ROW LEVEL SECURITY;
ALTER TABLE twitter_activity_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE browser_states ENABLE ROW LEVEL SECURITY;
ALTER TABLE error_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE twitter_background_tasks_log ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only access their own data
CREATE POLICY "Users can access own data" ON users
    FOR ALL USING (auth.uid() = id);

CREATE POLICY "Users can access own twitter profiles" ON twitter_profiles
    FOR ALL USING (user_id = auth.uid());

CREATE POLICY "Users can access own tokens" ON twitter_tokens
    FOR ALL USING (handle IN (SELECT handle FROM twitter_profiles WHERE user_id = auth.uid()));

CREATE POLICY "Users can access own relevant accounts" ON twitter_relevant_accounts
    FOR ALL USING (handle IN (SELECT handle FROM twitter_profiles WHERE user_id = auth.uid()));

CREATE POLICY "Users can access own queries" ON twitter_queries
    FOR ALL USING (handle IN (SELECT handle FROM twitter_profiles WHERE user_id = auth.uid()));

CREATE POLICY "Users can access own seen tweets" ON twitter_seen_tweets
    FOR ALL USING (handle IN (SELECT handle FROM twitter_profiles WHERE user_id = auth.uid()));

CREATE POLICY "Users can access own posted tweets" ON twitter_posted_tweets
    FOR ALL USING (handle IN (SELECT handle FROM twitter_profiles WHERE user_id = auth.uid()));

CREATE POLICY "Users can access own comments" ON twitter_comments
    FOR ALL USING (handle IN (SELECT handle FROM twitter_profiles WHERE user_id = auth.uid()));

CREATE POLICY "Users can access own activity log" ON twitter_activity_log
    FOR ALL USING (handle IN (SELECT handle FROM twitter_profiles WHERE user_id = auth.uid()));

CREATE POLICY "Users can access own browser states" ON browser_states
    FOR ALL USING (user_id = auth.uid());

CREATE POLICY "Users can access own error logs" ON error_logs
    FOR ALL USING (user_id = auth.uid());

CREATE POLICY "Users can access own background tasks log" ON twitter_background_tasks_log
    FOR ALL USING (handle IN (SELECT handle FROM twitter_profiles WHERE user_id = auth.uid()));

-- =============================================================================
-- SERVICE ROLE BYPASS (for backend API calls)
-- =============================================================================
-- The service role key bypasses RLS, so your backend can access all data
-- Make sure to use SUPABASE_SERVICE_ROLE_KEY (not anon key) in your backend
