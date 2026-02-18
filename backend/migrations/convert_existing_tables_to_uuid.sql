-- Convert existing tables from INTEGER to UUID
-- Only handles tables that already exist (users, twitter_profiles, browser_states, error_logs)
-- Run this FIRST, then create RAG tables with UUID

-- =============================================================================
-- Step 1: Drop foreign key constraints
-- =============================================================================

ALTER TABLE twitter_profiles DROP CONSTRAINT IF EXISTS twitter_profiles_user_id_fkey;
ALTER TABLE browser_states DROP CONSTRAINT IF EXISTS browser_states_user_id_fkey;
ALTER TABLE error_logs DROP CONSTRAINT IF EXISTS error_logs_user_id_fkey;

-- =============================================================================
-- Step 2: Convert users.uid to UUID
-- =============================================================================

ALTER TABLE users ALTER COLUMN uid DROP DEFAULT;
ALTER TABLE users ALTER COLUMN uid TYPE UUID USING gen_random_uuid();
ALTER TABLE users ALTER COLUMN uid SET DEFAULT gen_random_uuid();

-- =============================================================================
-- Step 3: Convert dependent user_id columns to UUID
-- =============================================================================

ALTER TABLE twitter_profiles ALTER COLUMN user_id TYPE UUID USING gen_random_uuid();
ALTER TABLE browser_states ALTER COLUMN user_id TYPE UUID USING gen_random_uuid();

-- error_logs.user_id is nullable, handle NULLs
ALTER TABLE error_logs ALTER COLUMN user_id TYPE UUID USING
    CASE WHEN user_id IS NULL THEN NULL ELSE gen_random_uuid() END;

-- =============================================================================
-- Step 4: Recreate foreign key constraints
-- =============================================================================

ALTER TABLE twitter_profiles
    ADD CONSTRAINT twitter_profiles_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(uid) ON DELETE CASCADE;

ALTER TABLE browser_states
    ADD CONSTRAINT browser_states_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(uid) ON DELETE CASCADE;

ALTER TABLE error_logs
    ADD CONSTRAINT error_logs_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(uid) ON DELETE SET NULL;

-- =============================================================================
-- Step 5: Update RLS policies
-- =============================================================================

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

-- =============================================================================
-- DONE! Now you can run create_rag_tables_clean.sql to create RAG tables
-- =============================================================================
