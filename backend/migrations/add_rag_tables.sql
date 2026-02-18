-- Add RAG tables (files, memories, feedback) to existing UUID-based schema
-- Run this after your schema has been converted to UUID

-- =============================================================================
-- ENABLE VECTOR EXTENSION
-- =============================================================================
CREATE EXTENSION IF NOT EXISTS vector;

-- =============================================================================
-- FILES TABLE
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.files (
    file_id uuid NOT NULL DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    file_type text NOT NULL CHECK (file_type = ANY (ARRAY['blog'::text, 'notion'::text, 'gdoc'::text, 'pdf'::text, 'youtube'::text, 'podcast'::text, 'other'::text])),
    title text,
    url text,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT files_pkey PRIMARY KEY (file_id),
    CONSTRAINT files_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(uid) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_files_user_id ON public.files(user_id);
CREATE INDEX IF NOT EXISTS idx_files_type ON public.files(user_id, file_type);

-- =============================================================================
-- MEMORIES TABLE
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.memories (
    memory_id uuid NOT NULL DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    content text NOT NULL,
    embedding vector(1536) NOT NULL,
    source_type text NOT NULL CHECK (source_type = ANY (ARRAY['tweet'::text, 'blog'::text, 'podcast'::text, 'file'::text, 'manual'::text])),
    source_id text,
    file_id uuid,
    visibility text DEFAULT 'private'::text CHECK (visibility = ANY (ARRAY['public'::text, 'private'::text, 'internal'::text])),
    audience text,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT memories_pkey PRIMARY KEY (memory_id),
    CONSTRAINT memories_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(uid) ON DELETE CASCADE,
    CONSTRAINT memories_file_id_fkey FOREIGN KEY (file_id) REFERENCES public.files(file_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_memories_user_id ON public.memories(user_id);
CREATE INDEX IF NOT EXISTS idx_memories_source ON public.memories(user_id, source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_memories_visibility ON public.memories(user_id, visibility);

-- HNSW index for fast vector similarity search
CREATE INDEX IF NOT EXISTS idx_memories_embedding ON public.memories
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- =============================================================================
-- FEEDBACK TABLE
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.feedback (
    feedback_id uuid NOT NULL DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    feedback_type text NOT NULL CHECK (feedback_type = ANY (ARRAY['edit'::text, 'skip'::text, 'choose_reply'::text])),
    dothis text,
    notthat text,
    trigger_context text,
    trigger_embedding vector(1536),
    extracted_rules jsonb DEFAULT '{}'::jsonb,
    source_action text,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT feedback_pkey PRIMARY KEY (feedback_id),
    CONSTRAINT feedback_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(uid) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_feedback_user_id ON public.feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_feedback_type ON public.feedback(user_id, feedback_type);
CREATE INDEX IF NOT EXISTS idx_feedback_created ON public.feedback(user_id, created_at DESC);

-- HNSW index for fast vector similarity search
CREATE INDEX IF NOT EXISTS idx_feedback_embedding ON public.feedback
USING hnsw (trigger_embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- =============================================================================
-- ROW LEVEL SECURITY
-- =============================================================================
ALTER TABLE public.files ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.memories ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.feedback ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist
DROP POLICY IF EXISTS "Users can access own files" ON public.files;
DROP POLICY IF EXISTS "Users can access own memories" ON public.memories;
DROP POLICY IF EXISTS "Users can access own feedback" ON public.feedback;

-- Create RLS policies
CREATE POLICY "Users can access own files" ON public.files
    FOR ALL USING (user_id = auth.uid());

CREATE POLICY "Users can access own memories" ON public.memories
    FOR ALL USING (user_id = auth.uid());

CREATE POLICY "Users can access own feedback" ON public.feedback
    FOR ALL USING (user_id = auth.uid());

-- =============================================================================
-- RPC FUNCTIONS FOR VECTOR SEARCH
-- =============================================================================

-- Search memories by vector similarity
CREATE OR REPLACE FUNCTION public.search_memories(
    p_user_id uuid,
    p_embedding vector(1536),
    p_limit integer DEFAULT 10,
    p_visibility text DEFAULT NULL,
    p_audience text DEFAULT NULL
)
RETURNS TABLE (
    memory_id uuid,
    content text,
    source_type text,
    source_id text,
    visibility text,
    audience text,
    created_at timestamp with time zone,
    similarity double precision
)
LANGUAGE plpgsql
AS $$
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
        (1 - (m.embedding <=> p_embedding))::double precision AS similarity
    FROM public.memories m
    WHERE m.user_id = p_user_id
        AND (p_visibility IS NULL OR m.visibility = p_visibility)
        AND (p_audience IS NULL OR m.audience = p_audience)
    ORDER BY m.embedding <=> p_embedding
    LIMIT p_limit;
END;
$$;

-- Search feedback by vector similarity
CREATE OR REPLACE FUNCTION public.search_feedback(
    p_user_id uuid,
    p_embedding vector(1536),
    p_limit integer DEFAULT 10
)
RETURNS TABLE (
    feedback_id uuid,
    feedback_type text,
    dothis text,
    notthat text,
    trigger_context text,
    extracted_rules jsonb,
    created_at timestamp with time zone,
    similarity double precision
)
LANGUAGE plpgsql
AS $$
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
        (1 - (f.trigger_embedding <=> p_embedding))::double precision AS similarity
    FROM public.feedback f
    WHERE f.user_id = p_user_id
        AND f.trigger_embedding IS NOT NULL
    ORDER BY f.trigger_embedding <=> p_embedding
    LIMIT p_limit;
END;
$$;

-- =============================================================================
-- DONE! RAG tables are now set up and ready to use
-- =============================================================================
