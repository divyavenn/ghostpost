-- Complete setup: Drop and recreate users + RAG tables with UUID
-- WARNING: This will DELETE ALL DATA in users, files, memories, and feedback tables!
-- Only run this if you're okay losing existing user data or on a fresh database

-- =============================================================================
-- ENABLE EXTENSIONS
-- =============================================================================
CREATE EXTENSION IF NOT EXISTS vector;

-- =============================================================================
-- DROP EXISTING TABLES
-- =============================================================================
DROP TABLE IF EXISTS feedback CASCADE;
DROP TABLE IF EXISTS memories CASCADE;
DROP TABLE IF EXISTS files CASCADE;
DROP TABLE IF EXISTS browser_states CASCADE;
DROP TABLE IF EXISTS twitter_background_tasks_log CASCADE;
DROP TABLE IF EXISTS twitter_activity_log CASCADE;
DROP TABLE IF EXISTS twitter_comments CASCADE;
DROP TABLE IF EXISTS twitter_posted_tweets CASCADE;
DROP TABLE IF EXISTS twitter_seen_tweets CASCADE;
DROP TABLE IF EXISTS twitter_queries CASCADE;
DROP TABLE IF EXISTS twitter_relevant_accounts CASCADE;
DROP TABLE IF EXISTS twitter_tokens CASCADE;
DROP TABLE IF EXISTS twitter_profiles CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- =============================================================================
-- USERS TABLE (with UUID)
-- =============================================================================
CREATE TABLE users (
    uid UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    account_type TEXT DEFAULT 'trial' CHECK (account_type IN ('trial', 'poster', 'premium')),
    models TEXT[] DEFAULT '{}',
    knowledge_base JSONB,
    intent TEXT DEFAULT ''
);

CREATE INDEX idx_users_uid ON users(uid);

-- =============================================================================
-- TWITTER PROFILES TABLE
-- =============================================================================
CREATE TABLE twitter_profiles (
    handle TEXT PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(uid) ON DELETE CASCADE,
    username TEXT,
    profile_pic_url TEXT,
    follower_count INTEGER DEFAULT 0,
    twitter_user_id TEXT,
    ideal_num_posts INTEGER DEFAULT 30,
    number_of_generations INTEGER DEFAULT 2,
    min_impressions_filter INTEGER DEFAULT 2000,
    manual_minimum_impressions INTEGER,
    intent_filter_examples JSONB DEFAULT '[]',
    intent_filter_last_updated TIMESTAMPTZ,
    use_rag_retrieval BOOLEAN DEFAULT FALSE,
    lifetime_new_follows INTEGER DEFAULT 0,
    lifetime_posts INTEGER DEFAULT 0,
    scrolling_time_saved INTEGER DEFAULT 0,
    scrapes_left INTEGER,
    posts_left INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_twitter_profiles_user_id ON twitter_profiles(user_id);

-- =============================================================================
-- FILES TABLE
-- =============================================================================
CREATE TABLE files (
    file_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(uid) ON DELETE CASCADE,
    file_type TEXT NOT NULL CHECK (file_type IN ('blog', 'notion', 'gdoc', 'pdf', 'youtube', 'podcast', 'other')),
    title TEXT,
    url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_files_user_id ON files(user_id);
CREATE INDEX idx_files_type ON files(user_id, file_type);

-- =============================================================================
-- MEMORIES TABLE
-- =============================================================================
CREATE TABLE memories (
    memory_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(uid) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding vector(1536) NOT NULL,
    source_type TEXT NOT NULL CHECK (source_type IN ('tweet', 'blog', 'podcast', 'file', 'manual')),
    source_id TEXT,
    file_id UUID REFERENCES files(file_id) ON DELETE CASCADE,
    visibility TEXT DEFAULT 'private' CHECK (visibility IN ('public', 'private', 'internal')),
    audience TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_memories_user_id ON memories(user_id);
CREATE INDEX idx_memories_source ON memories(user_id, source_type, source_id);
CREATE INDEX idx_memories_visibility ON memories(user_id, visibility);
CREATE INDEX idx_memories_embedding ON memories USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- =============================================================================
-- FEEDBACK TABLE
-- =============================================================================
CREATE TABLE feedback (
    feedback_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(uid) ON DELETE CASCADE,
    feedback_type TEXT NOT NULL CHECK (feedback_type IN ('edit', 'skip', 'choose_reply')),
    dothis TEXT,
    notthat TEXT,
    trigger_context TEXT,
    trigger_embedding vector(1536),
    extracted_rules JSONB DEFAULT '{}',
    source_action TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_feedback_user_id ON feedback(user_id);
CREATE INDEX idx_feedback_type ON feedback(user_id, feedback_type);
CREATE INDEX idx_feedback_created ON feedback(user_id, created_at DESC);
CREATE INDEX idx_feedback_embedding ON feedback USING hnsw (trigger_embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- =============================================================================
-- ROW LEVEL SECURITY
-- =============================================================================
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE twitter_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE files ENABLE ROW LEVEL SECURITY;
ALTER TABLE memories ENABLE ROW LEVEL SECURITY;
ALTER TABLE feedback ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can access own data" ON users FOR ALL USING (auth.uid() = uid);
CREATE POLICY "Users can access own twitter profiles" ON twitter_profiles FOR ALL USING (user_id = auth.uid());
CREATE POLICY "Users can access own files" ON files FOR ALL USING (user_id = auth.uid());
CREATE POLICY "Users can access own memories" ON memories FOR ALL USING (user_id = auth.uid());
CREATE POLICY "Users can access own feedback" ON feedback FOR ALL USING (user_id = auth.uid());

-- =============================================================================
-- RPC FUNCTIONS
-- =============================================================================
CREATE OR REPLACE FUNCTION search_memories(
    p_user_id UUID,
    p_embedding vector(1536),
    p_limit INTEGER DEFAULT 10,
    p_visibility TEXT DEFAULT NULL,
    p_audience TEXT DEFAULT NULL
)
RETURNS TABLE (
    memory_id UUID,
    content TEXT,
    source_type TEXT,
    source_id TEXT,
    visibility TEXT,
    audience TEXT,
    created_at TIMESTAMPTZ,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        m.memory_id, m.content, m.source_type, m.source_id,
        m.visibility, m.audience, m.created_at,
        1 - (m.embedding <=> p_embedding) AS similarity
    FROM memories m
    WHERE m.user_id = p_user_id
        AND (p_visibility IS NULL OR m.visibility = p_visibility)
        AND (p_audience IS NULL OR m.audience = p_audience)
    ORDER BY m.embedding <=> p_embedding
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION search_feedback(
    p_user_id UUID,
    p_embedding vector(1536),
    p_limit INTEGER DEFAULT 10
)
RETURNS TABLE (
    feedback_id UUID,
    feedback_type TEXT,
    dothis TEXT,
    notthat TEXT,
    trigger_context TEXT,
    extracted_rules JSONB,
    created_at TIMESTAMPTZ,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        f.feedback_id, f.feedback_type, f.dothis, f.notthat,
        f.trigger_context, f.extracted_rules, f.created_at,
        1 - (f.trigger_embedding <=> p_embedding) AS similarity
    FROM feedback f
    WHERE f.user_id = p_user_id
        AND f.trigger_embedding IS NOT NULL
    ORDER BY f.trigger_embedding <=> p_embedding
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;
