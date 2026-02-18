-- Convert users.uid from INTEGER to UUID
-- Run this BEFORE creating RAG tables

-- Step 1: Drop the default value on uid
ALTER TABLE users ALTER COLUMN uid DROP DEFAULT;

-- Step 2: Convert uid to UUID type
-- This assumes you don't have existing data, or existing uid values can be cast to UUID
-- If you have existing integer IDs, this will fail - see alternative below
ALTER TABLE users ALTER COLUMN uid TYPE UUID USING gen_random_uuid();

-- Step 3: Keep the UUID default for new users
ALTER TABLE users ALTER COLUMN uid SET DEFAULT gen_random_uuid();

-- Alternative if you have existing users:
-- If the above fails because you have existing data that can't be converted,
-- you'll need to either:
-- 1. Clear the users table (if safe to do so):
--    TRUNCATE TABLE users CASCADE;
--    Then run the above ALTER statements
--
-- 2. Or map existing integer IDs to UUIDs (more complex):
--    -- Create a temporary mapping table
--    CREATE TEMP TABLE user_id_mapping AS
--    SELECT uid as old_uid, gen_random_uuid() as new_uid FROM users;
--
--    -- Update all foreign key references in other tables
--    -- (repeat for each table that references users.uid)
--    -- Example:
--    -- UPDATE twitter_profiles tp
--    -- SET user_id = m.new_uid::text
--    -- FROM user_id_mapping m
--    -- WHERE tp.user_id::text = m.old_uid::text;
--
--    -- Then proceed with the ALTER statements above
