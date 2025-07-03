-- Drop obsolete prompts table as we've migrated to JSON-based prompts
-- The role_prompts table is kept for A/B testing and overrides but not actively used

-- First, check if the table exists before dropping
DO $$
BEGIN
    -- Drop the obsolete prompts table if it exists
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'prompts' AND table_schema = 'public') THEN
        DROP TABLE prompts;
        RAISE NOTICE 'Dropped obsolete prompts table';
    ELSE
        RAISE NOTICE 'prompts table does not exist, nothing to drop';
    END IF;
END
$$;

-- Add a comment to the role_prompts table to clarify its purpose
COMMENT ON TABLE role_prompts IS 'Used for A/B testing and prompt overrides. Primary prompts are now stored as JSON files in the repository.'; 