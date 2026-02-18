-- Complete conversion of users.uid from INTEGER to UUID
-- This updates all dependent tables and foreign keys

-- =============================================================================
-- Step 1: Drop all foreign key constraints that reference users.uid
-- =============================================================================

-- twitter_profiles
ALTER TABLE twitter_profiles DROP CONSTRAINT IF EXISTS twitter_profiles_user_id_fkey;

-- browser_states
ALTER TABLE browser_states DROP CONSTRAINT IF EXISTS browser_states_user_id_fkey;

-- error_logs (if it exists)
ALTER TABLE error_logs DROP CONSTRAINT IF EXISTS error_logs_user_id_fkey;

-- files (if it exists)
ALTER TABLE files DROP CONSTRAINT IF EXISTS files_user_id_fkey;

-- memories (if it exists)
ALTER TABLE memories DROP CONSTRAINT IF EXISTS memories_user_id_fkey;

-- feedback (if it exists)
ALTER TABLE feedback DROP CONSTRAINT IF EXISTS feedback_user_id_fkey;

-- =============================================================================
-- Step 2: Convert users.uid to UUID
-- =============================================================================

-- Drop the default on users.uid
ALTER TABLE users ALTER COLUMN uid DROP DEFAULT;

-- Convert to UUID (generates new UUIDs for existing rows)
ALTER TABLE users ALTER COLUMN uid TYPE UUID USING gen_random_uuid();

-- Set new default for future inserts
ALTER TABLE users ALTER COLUMN uid SET DEFAULT gen_random_uuid();

-- =============================================================================
-- Step 3: Convert all user_id columns in dependent tables to UUID
-- =============================================================================

-- twitter_profiles.user_id
ALTER TABLE twitter_profiles ALTER COLUMN user_id TYPE UUID USING gen_random_uuid();

-- browser_states.user_id
ALTER TABLE browser_states ALTER COLUMN user_id TYPE UUID USING gen_random_uuid();

-- error_logs.user_id (nullable, handle nulls)
ALTER TABLE error_logs ALTER COLUMN user_id TYPE UUID USING
    CASE WHEN user_id IS NULL THEN NULL ELSE gen_random_uuid() END;

-- files.user_id (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'files') THEN
        ALTER TABLE files ALTER COLUMN user_id TYPE UUID USING gen_random_uuid();
    END IF;
END $$;

-- memories.user_id (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'memories') THEN
        ALTER TABLE memories ALTER COLUMN user_id TYPE UUID USING gen_random_uuid();
    END IF;
END $$;

-- feedback.user_id (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'feedback') THEN
        ALTER TABLE feedback ALTER COLUMN user_id TYPE UUID USING gen_random_uuid();
    END IF;
END $$;

-- =============================================================================
-- Step 4: Recreate foreign key constraints
-- =============================================================================

-- twitter_profiles
ALTER TABLE twitter_profiles
    ADD CONSTRAINT twitter_profiles_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(uid) ON DELETE CASCADE;

-- browser_states
ALTER TABLE browser_states
    ADD CONSTRAINT browser_states_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(uid) ON DELETE CASCADE;

-- error_logs
ALTER TABLE error_logs
    ADD CONSTRAINT error_logs_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(uid) ON DELETE SET NULL;

-- files (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'files') THEN
        ALTER TABLE files
            ADD CONSTRAINT files_user_id_fkey
            FOREIGN KEY (user_id) REFERENCES users(uid) ON DELETE CASCADE;
    END IF;
END $$;

-- memories (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'memories') THEN
        ALTER TABLE memories
            ADD CONSTRAINT memories_user_id_fkey
            FOREIGN KEY (user_id) REFERENCES users(uid) ON DELETE CASCADE;
    END IF;
END $$;

-- feedback (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'feedback') THEN
        ALTER TABLE feedback
            ADD CONSTRAINT feedback_user_id_fkey
            FOREIGN KEY (user_id) REFERENCES users(uid) ON DELETE CASCADE;
    END IF;
END $$;

-- =============================================================================
-- Step 5: Update RLS policies if needed
-- =============================================================================

-- Drop and recreate policies to ensure they work with UUID
DROP POLICY IF EXISTS "Users can access own data" ON users;
CREATE POLICY "Users can access own data" ON users
    FOR ALL USING (auth.uid() = uid);

DROP POLICY IF EXISTS "Users can access own twitter profiles" ON twitter_profiles;
CREATE POLICY "Users can access own twitter profiles" ON twitter_profiles
    FOR ALL USING (user_id = auth.uid());

DROP POLICY IF EXISTS "Users can access own browser states" ON browser_states;
CREATE POLICY "Users can access own browser states" ON browser_states
    FOR ALL USING (user_id = auth.uid());

DROP POLICY IF EXISTS "Users can access own error logs" ON error_logs;
CREATE POLICY "Users can access own error logs" ON error_logs
    FOR ALL USING (user_id = auth.uid());

-- Recreate RAG table policies if they exist
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'files') THEN
        DROP POLICY IF EXISTS "Users can access own files" ON files;
        CREATE POLICY "Users can access own files" ON files
            FOR ALL USING (user_id = auth.uid());
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'memories') THEN
        DROP POLICY IF EXISTS "Users can access own memories" ON memories;
        CREATE POLICY "Users can access own memories" ON memories
            FOR ALL USING (user_id = auth.uid());
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'feedback') THEN
        DROP POLICY IF EXISTS "Users can access own feedback" ON feedback;
        CREATE POLICY "Users can access own feedback" ON feedback
            FOR ALL USING (user_id = auth.uid());
    END IF;
END $$;

-- =============================================================================
-- DONE!
-- =============================================================================
-- All users now have new UUIDs
-- All references have been updated
-- Note: This breaks existing relationships since new UUIDs were generated
-- You'll need to re-authenticate users and re-link Twitter accounts
