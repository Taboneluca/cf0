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

-- Create RLS policies for spreadsheet_workbooks table
-- Allow authenticated users to INSERT their own workbooks
CREATE POLICY "Users can insert their own workbooks" 
ON spreadsheet_workbooks FOR INSERT 
WITH CHECK (auth.uid() = user_id OR user_id IS NULL);

-- Allow authenticated users to SELECT their own workbooks
CREATE POLICY "Users can view their own workbooks" 
ON spreadsheet_workbooks FOR SELECT 
USING (auth.uid() = user_id OR user_id IS NULL);

-- Allow authenticated users to UPDATE their own workbooks
CREATE POLICY "Users can update their own workbooks" 
ON spreadsheet_workbooks FOR UPDATE 
USING (auth.uid() = user_id OR user_id IS NULL);

-- Allow authenticated users to DELETE their own workbooks
CREATE POLICY "Users can delete their own workbooks" 
ON spreadsheet_workbooks FOR DELETE 
USING (auth.uid() = user_id OR user_id IS NULL);

-- Create RLS policies for spreadsheet_sheets table
-- Allow authenticated users to INSERT their own sheets
CREATE POLICY "Users can insert their own sheets" 
ON spreadsheet_sheets FOR INSERT 
WITH CHECK (auth.uid() = user_id OR user_id IS NULL);

-- Allow authenticated users to SELECT their own sheets
CREATE POLICY "Users can view their own sheets" 
ON spreadsheet_sheets FOR SELECT 
USING (auth.uid() = user_id OR user_id IS NULL);

-- Allow authenticated users to UPDATE their own sheets
CREATE POLICY "Users can update their own sheets" 
ON spreadsheet_sheets FOR UPDATE 
USING (auth.uid() = user_id OR user_id IS NULL);

-- Allow authenticated users to DELETE their own sheets
CREATE POLICY "Users can delete their own sheets" 
ON spreadsheet_sheets FOR DELETE 
USING (auth.uid() = user_id OR user_id IS NULL);

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