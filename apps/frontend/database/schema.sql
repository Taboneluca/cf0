-- Create profiles table (extends Supabase auth.users)
CREATE TABLE IF NOT EXISTS profiles (
id UUID REFERENCES auth.users(id) PRIMARY KEY,
email TEXT UNIQUE NOT NULL,
full_name TEXT,
avatar_url TEXT,
is_waitlisted BOOLEAN DEFAULT TRUE,
is_verified BOOLEAN DEFAULT FALSE,
created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create workbooks table
CREATE TABLE IF NOT EXISTS workbooks (
id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
user_id UUID REFERENCES profiles(id) NOT NULL,
title TEXT NOT NULL,
description TEXT,
data JSONB NOT NULL DEFAULT '{}'::jsonb,
sheets JSONB DEFAULT '["Sheet1"]'::jsonb,
is_public BOOLEAN DEFAULT FALSE,
created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Add sheets column to existing workbooks table if not exists
ALTER TABLE workbooks ADD COLUMN IF NOT EXISTS sheets JSONB DEFAULT '["Sheet1"]'::jsonb;

-- Create waitlist table
CREATE TABLE IF NOT EXISTS waitlist (
id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
email TEXT UNIQUE NOT NULL,
status TEXT NOT NULL DEFAULT 'pending', -- pending, approved, rejected
invite_code TEXT UNIQUE,
invited_at TIMESTAMP WITH TIME ZONE,
created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create RLS policies
-- Enable Row Level Security
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE workbooks ENABLE ROW LEVEL SECURITY;
ALTER TABLE waitlist ENABLE ROW LEVEL SECURITY;

-- Profiles policies
CREATE POLICY "Users can view their own profile"
ON profiles FOR SELECT
USING (auth.uid() = id);

CREATE POLICY "Users can update their own profile"
ON profiles FOR UPDATE
USING (auth.uid() = id);

-- Workbooks policies
CREATE POLICY "Users can view their own workbooks"
ON workbooks FOR SELECT
USING (auth.uid() = user_id);

CREATE POLICY "Users can view public workbooks"
ON workbooks FOR SELECT
USING (is_public = true);

CREATE POLICY "Users can insert their own workbooks"
ON workbooks FOR INSERT
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own workbooks"
ON workbooks FOR UPDATE
USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own workbooks"
ON workbooks FOR DELETE
USING (auth.uid() = user_id);

-- Waitlist policies (admin only through service role)
CREATE POLICY "Public can insert to waitlist"
ON waitlist FOR INSERT
WITH CHECK (true);

-- Create function to handle new user signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
INSERT INTO public.profiles (id, email, full_name, avatar_url)
VALUES (new.id, new.email, new.raw_user_meta_data->>'full_name', new.raw_user_meta_data->>'avatar_url');

-- Check if user was on waitlist and approved
UPDATE public.waitlist
SET status = 'converted'
WHERE email = new.email AND status = 'approved';

RETURN new;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger for new user signup
CREATE OR REPLACE TRIGGER on_auth_user_created
AFTER INSERT ON auth.users
FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Create function to update timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
NEW.updated_at = NOW();
RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers for updated_at columns
CREATE TRIGGER update_profiles_updated_at
BEFORE UPDATE ON profiles
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_workbooks_updated_at
BEFORE UPDATE ON workbooks
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create function to handle user invitations in a single transaction
CREATE OR REPLACE FUNCTION invite_waitlist_user(user_email TEXT)
RETURNS JSONB AS $$
DECLARE
  updated_row JSONB;
BEGIN
  -- 1) Mark waitlist row as approved and get updated row
  UPDATE public.waitlist
  SET status = 'approved'
  WHERE email = user_email
  RETURNING to_jsonb(waitlist.*) INTO updated_row;
  
  -- 2) Send invite email (this happens via Supabase auth.admin.inviteUserByEmail in API)
  
  -- 3) Update status to invited with timestamp
  UPDATE public.waitlist
  SET status = 'invited', invited_at = NOW()
  WHERE email = user_email;
  
  RETURN updated_row;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
