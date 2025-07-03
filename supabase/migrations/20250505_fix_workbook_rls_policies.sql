-- Migration to fix RLS (Row Level Security) policies for workbooks table
-- This addresses workbook persistence failures due to RLS policy violations

-- Enable RLS on spreadsheet_workbooks table if not already enabled
ALTER TABLE IF EXISTS spreadsheet_workbooks ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS spreadsheet_sheets ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist (to avoid conflicts)
DROP POLICY IF EXISTS "Users can insert their own workbooks" ON spreadsheet_workbooks;
DROP POLICY IF EXISTS "Users can view their own workbooks" ON spreadsheet_workbooks;
DROP POLICY IF EXISTS "Users can update their own workbooks" ON spreadsheet_workbooks;
DROP POLICY IF EXISTS "Users can delete their own workbooks" ON spreadsheet_workbooks;

DROP POLICY IF EXISTS "Users can insert their own sheets" ON spreadsheet_sheets;
DROP POLICY IF EXISTS "Users can view their own sheets" ON spreadsheet_sheets;
DROP POLICY IF EXISTS "Users can update their own sheets" ON spreadsheet_sheets;
DROP POLICY IF EXISTS "Users can delete their own sheets" ON spreadsheet_sheets;

-- Add user_id column to workbooks table if it doesn't exist
-- This is needed to associate workbooks with users for RLS
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'spreadsheet_workbooks' AND column_name = 'user_id') THEN
        ALTER TABLE spreadsheet_workbooks ADD COLUMN user_id UUID REFERENCES auth.users(id);
    END IF;
END $$;

-- Add user_id column to sheets table if it doesn't exist
-- This is needed to associate sheets with users for RLS
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'spreadsheet_sheets' AND column_name = 'user_id') THEN
        ALTER TABLE spreadsheet_sheets ADD COLUMN user_id UUID REFERENCES auth.users(id);
    END IF;
END $$;

-- Create optimized RLS policies for spreadsheet_workbooks table
-- Using (select auth.uid()) for better performance as recommended by Supabase advisors
-- Consolidated policies for better performance (fewer permissive policies)

-- Allow authenticated users to manage their own workbooks (all operations)
CREATE POLICY "Users can manage their own workbooks" 
ON spreadsheet_workbooks FOR ALL 
USING ((select auth.uid()) = user_id OR user_id IS NULL)
WITH CHECK ((select auth.uid()) = user_id OR user_id IS NULL);

-- Create optimized RLS policies for spreadsheet_sheets table
-- Using (select auth.uid()) for better performance as recommended by Supabase advisors
-- Consolidated policies for better performance (fewer permissive policies)

-- Allow authenticated users to manage their own sheets (all operations)
CREATE POLICY "Users can manage their own sheets" 
ON spreadsheet_sheets FOR ALL 
USING ((select auth.uid()) = user_id OR user_id IS NULL)
WITH CHECK ((select auth.uid()) = user_id OR user_id IS NULL);

-- Create function to automatically set user_id on insert
CREATE OR REPLACE FUNCTION set_user_id()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.user_id IS NULL THEN
        NEW.user_id = auth.uid();
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create triggers to automatically set user_id
DROP TRIGGER IF EXISTS set_user_id_workbooks ON spreadsheet_workbooks;
CREATE TRIGGER set_user_id_workbooks
    BEFORE INSERT ON spreadsheet_workbooks
    FOR EACH ROW EXECUTE FUNCTION set_user_id();

DROP TRIGGER IF EXISTS set_user_id_sheets ON spreadsheet_sheets;
CREATE TRIGGER set_user_id_sheets
    BEFORE INSERT ON spreadsheet_sheets
    FOR EACH ROW EXECUTE FUNCTION set_user_id();

-- Update existing records to have a default user_id (for backwards compatibility)
-- This is safe for development/testing environments
UPDATE spreadsheet_workbooks SET user_id = (SELECT id FROM auth.users LIMIT 1) WHERE user_id IS NULL;
UPDATE spreadsheet_sheets SET user_id = (SELECT id FROM auth.users LIMIT 1) WHERE user_id IS NULL;

-- Add indexes for foreign keys to improve performance (recommended by Supabase advisors)
-- Only create if they don't already exist
CREATE INDEX IF NOT EXISTS idx_spreadsheet_workbooks_user_id ON spreadsheet_workbooks(user_id);
CREATE INDEX IF NOT EXISTS idx_spreadsheet_sheets_user_id ON spreadsheet_sheets(user_id);

-- Additional indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_spreadsheet_workbooks_wid_user_id ON spreadsheet_workbooks(wid, user_id);
CREATE INDEX IF NOT EXISTS idx_spreadsheet_sheets_workbook_wid_user_id ON spreadsheet_sheets(workbook_wid, user_id); 