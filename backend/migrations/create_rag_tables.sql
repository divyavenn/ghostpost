-- Create RAG tables (memories and feedback) for GhostPoster
-- Run this in Supabase SQL Editor if you don't have these tables yet

-- =============================================================================
-- ENABLE VECTOR EXTENSION
-- =============================================================================
CREATE EXTENSION IF NOT EXISTS vector;

-- =============================================================================
-- FILES TABLE (for RAG: blogs, notion docs, gdocs, etc.)
-- =============================================================================
CREATE TABLE IF NOT EXISTS files (
    file_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(uid) ON DELETE CASCADE,
    file_type TEXT NOT NULL CHECK (file_type IN ('blog', 'notion', 'gdoc', 'pdf', 'youtube', 'podcast', 'other')),
    title TEXT,
    url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for files
CREATE INDEX IF NOT EXISTS idx_files_user_id ON files(user_id);
CREATE INDEX IF NOT EXISTS idx_files_type ON files(user_id, file_type);

-- =============================================================================
-- MEMORIES TABLE (RAG knowledge base)
-- =============================================================================
CREATE TABLE IF NOT EXISTS memories (
    memory_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(uid) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding vector(1536) NOT NULL,

    -- Source tracking
    source_type TEXT NOT NULL CHECK (source_type IN ('tweet', 'blog', 'podcast', 'file', 'manual')),
    source_id TEXT, -- tweet_id, blog_url, etc.
    file_id UUID REFERENCES files(file_id) ON DELETE CASCADE,

    -- Visibility and audience
    visibility TEXT DEFAULT 'private' CHECK (visibility IN ('public', 'private', 'internal')),
    audience TEXT, -- e.g., 'technical', 'casual', 'professional'

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for memories
CREATE INDEX IF NOT EXISTS idx_memories_user_id ON memories(user_id);
CREATE INDEX IF NOT EXISTS idx_memories_source ON memories(user_id, source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_memories_visibility ON memories(user_id, visibility);

-- HNSW index for vector similarity search (O(log n) performance)
CREATE INDEX IF NOT EXISTS idx_memories_embedding ON memories
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- =============================================================================
-- FEEDBACK TABLE (learned preferences from user edits)
-- =============================================================================
CREATE TABLE IF NOT EXISTS feedback (
    feedback_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(uid) ON DELETE CASCADE,
    feedback_type TEXT NOT NULL CHECK (feedback_type IN ('edit', 'skip', 'choose_reply')),

    -- Contrastive learning: what to do vs what not to do
    dothis TEXT, -- positive example (what the user changed it to)
    notthat TEXT, -- negative example (what it was before)

    -- Context that triggered this feedback
    trigger_context TEXT, -- the original tweet being replied to
    trigger_embedding vector(1536),

    -- Extracted rules and patterns
    extracted_rules JSONB DEFAULT '{}', -- {tone_shift, confidence_shift, constraints, etc.}

    -- Metadata
    source_action TEXT, -- 'edited', 'skipped', 'selected_reply_N'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for feedback
CREATE INDEX IF NOT EXISTS idx_feedback_user_id ON feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_feedback_type ON feedback(user_id, feedback_type);
CREATE INDEX IF NOT EXISTS idx_feedback_created ON feedback(user_id, created_at DESC);

-- HNSW index for vector similarity search
CREATE INDEX IF NOT EXISTS idx_feedback_embedding ON feedback
USING hnsw (trigger_embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- =============================================================================
-- ROW LEVEL SECURITY
-- =============================================================================
ALTER TABLE files ENABLE ROW LEVEL SECURITY;
ALTER TABLE memories ENABLE ROW LEVEL SECURITY;
ALTER TABLE feedback ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist
DROP POLICY IF EXISTS "Users can access own files" ON files;
DROP POLICY IF EXISTS "Users can access own memories" ON memories;
DROP POLICY IF EXISTS "Users can access own feedback" ON feedback;

-- Create policies
CREATE POLICY "Users can access own files" ON files
    FOR ALL USING (user_id = auth.uid());

CREATE POLICY "Users can access own memories" ON memories
    FOR ALL USING (user_id = auth.uid());

CREATE POLICY "Users can access own feedback" ON feedback
    FOR ALL USING (user_id = auth.uid());

-- =============================================================================
-- RPC FUNCTIONS FOR VECTOR SEARCH
-- =============================================================================

-- Search memories by vector similarity
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
        m.memory_id,
        m.content,
        m.source_type,
        m.source_id,
        m.visibility,
        m.audience,
        m.created_at,
        1 - (m.embedding <=> p_embedding) AS similarity
    FROM memories m
    WHERE m.user_id = p_user_id
        AND (p_visibility IS NULL OR m.visibility = p_visibility)
        AND (p_audience IS NULL OR m.audience = p_audience)
    ORDER BY m.embedding <=> p_embedding
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Search feedback by vector similarity
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
        f.feedback_id,
        f.feedback_type,
        f.dothis,
        f.notthat,
        f.trigger_context,
        f.extracted_rules,
        f.created_at,
        1 - (f.trigger_embedding <=> p_embedding) AS similarity
    FROM feedback f
    WHERE f.user_id = p_user_id
        AND f.trigger_embedding IS NOT NULL
    ORDER BY f.trigger_embedding <=> p_embedding
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;
