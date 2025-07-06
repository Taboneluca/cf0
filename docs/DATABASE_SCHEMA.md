# Database Schema Documentation

This document describes the Supabase PostgreSQL database schema used by CF0.

## Overview

CF0 uses Supabase for:
- User authentication and management
- Workbook and sheet data persistence
- Chat history storage
- System configuration (prompts)
- Row-level security (RLS) for data isolation

## Core Tables

### workbooks
Stores workbook metadata and configuration.

```sql
CREATE TABLE workbooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL DEFAULT 'Untitled Workbook',
    sheets TEXT[] NOT NULL DEFAULT ARRAY['Sheet1'],
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Indexes
CREATE INDEX idx_workbooks_user_id ON workbooks(user_id);
CREATE INDEX idx_workbooks_updated_at ON workbooks(updated_at DESC);

-- RLS Policies
ALTER TABLE workbooks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own workbooks" ON workbooks
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can create own workbooks" ON workbooks
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own workbooks" ON workbooks
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own workbooks" ON workbooks
    FOR DELETE USING (auth.uid() = user_id);
```

### sheets
Stores individual sheet data within workbooks.

```sql
CREATE TABLE sheets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workbook_id UUID REFERENCES workbooks(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    data JSONB NOT NULL DEFAULT '{"cells": [], "n_rows": 100, "n_cols": 26}'::jsonb,
    formulas JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    position INTEGER NOT NULL DEFAULT 0,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Indexes
CREATE INDEX idx_sheets_workbook_id ON sheets(workbook_id);
CREATE UNIQUE INDEX idx_sheets_workbook_name ON sheets(workbook_id, name);

-- RLS Policies (inherit from workbook)
ALTER TABLE sheets ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view sheets in own workbooks" ON sheets
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM workbooks 
            WHERE workbooks.id = sheets.workbook_id 
            AND workbooks.user_id = auth.uid()
        )
    );

-- Similar policies for INSERT, UPDATE, DELETE
```

### chat_history
Stores conversation history for each workbook.

```sql
CREATE TABLE chat_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workbook_id UUID REFERENCES workbooks(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    response TEXT,
    mode TEXT CHECK (mode IN ('ask', 'analyst')) DEFAULT 'ask',
    model TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_chat_history_workbook_id ON chat_history(workbook_id);
CREATE INDEX idx_chat_history_created_at ON chat_history(created_at DESC);

-- RLS Policies
ALTER TABLE chat_history ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own chat history" ON chat_history
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can create own chat history" ON chat_history
    FOR INSERT WITH CHECK (auth.uid() = user_id);
```

### prompts
System prompts for AI agents.

```sql
CREATE TABLE prompts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role TEXT NOT NULL CHECK (role IN ('ask', 'analyst', 'system')),
    version TEXT NOT NULL DEFAULT '1.0',
    content TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE UNIQUE INDEX idx_prompts_role_version ON prompts(role, version);
CREATE INDEX idx_prompts_active ON prompts(is_active) WHERE is_active = TRUE;

-- No RLS - prompts are system-wide
```

## Authentication Schema

Supabase Auth provides these tables in the `auth` schema:

### auth.users
Core user accounts.

```sql
-- Provided by Supabase
CREATE TABLE auth.users (
    id UUID PRIMARY KEY,
    email TEXT UNIQUE,
    encrypted_password TEXT,
    email_confirmed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    -- ... other Supabase fields
);
```

### auth.sessions
Active user sessions.

```sql
-- Provided by Supabase
CREATE TABLE auth.sessions (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id),
    access_token TEXT,
    refresh_token TEXT,
    expires_at TIMESTAMPTZ,
    -- ... other Supabase fields
);
```

## Data Types and Formats

### Sheet Data Format (JSONB)
```json
{
  "cells": [
    [{"value": "A1"}, {"value": "B1"}],
    [{"value": "A2"}, {"value": "B2"}]
  ],
  "n_rows": 100,
  "n_cols": 26,
  "styles": {
    "A1": {"bold": true, "color": "#000000"}
  }
}
```

### Formula Storage (JSONB)
```json
{
  "B1": "=SUM(A1:A10)",
  "C1": "=B1*0.2",
  "D5": "=VLOOKUP(A5,Sheet2!A:B,2,FALSE)"
}
```

### Metadata Format (JSONB)
Flexible storage for additional properties:
```json
{
  "tags": ["finance", "q4-2024"],
  "description": "Q4 Financial Model",
  "last_accessed": "2024-01-15T10:30:00Z",
  "custom_fields": {}
}
```

## Migrations

Migration files are stored in `supabase/migrations/`:

```sql
-- Example: 20240509_add_prompts_table.sql
CREATE TABLE IF NOT EXISTS prompts (...);

-- Example: 20240611_role_prompts.sql
ALTER TABLE prompts ADD COLUMN IF NOT EXISTS role TEXT;

-- Example: 20250127_drop_obsolete_prompts_table.sql
DROP TABLE IF EXISTS obsolete_prompts;
```

## Row-Level Security (RLS)

### Key Principles
1. Users can only access their own data
2. Workbook ownership determines sheet access
3. System tables (prompts) have no RLS
4. Service role bypasses RLS for admin operations

### RLS Helper Functions
```sql
-- Check if user owns workbook
CREATE FUNCTION user_owns_workbook(workbook_id UUID)
RETURNS BOOLEAN AS $$
    SELECT EXISTS (
        SELECT 1 FROM workbooks 
        WHERE id = workbook_id 
        AND user_id = auth.uid()
    );
$$ LANGUAGE SQL SECURITY DEFINER;
```

## Indexes and Performance

### Query Patterns and Indexes
1. **Workbook listing**: `idx_workbooks_user_id`
2. **Recent workbooks**: `idx_workbooks_updated_at`
3. **Sheet lookup**: `idx_sheets_workbook_name`
4. **Chat history**: `idx_chat_history_created_at`

### Performance Tips
- Use JSONB operators for efficient queries
- Partial indexes for active records
- Consider table partitioning for chat_history
- Regular VACUUM for deleted records

## Backup and Recovery

### Backup Strategy
1. Supabase automatic daily backups
2. Point-in-time recovery (PITR) available
3. Export critical data via pg_dump

### Recovery Procedures
```bash
# Restore from backup
supabase db restore --backup-id <backup-id>

# Export specific tables
pg_dump --table=workbooks --table=sheets > backup.sql
```

## Best Practices

1. **Always use RLS** for user data tables
2. **Validate JSONB** structure at application level
3. **Use transactions** for multi-table updates
4. **Index foreign keys** for CASCADE operations
5. **Monitor query performance** with EXPLAIN
6. **Version migrations** with timestamps
7. **Test RLS policies** thoroughly

## Common Queries

### Get user's workbooks
```sql
SELECT * FROM workbooks 
WHERE user_id = auth.uid() 
ORDER BY updated_at DESC;
```

### Get sheets for workbook
```sql
SELECT * FROM sheets 
WHERE workbook_id = $1 
ORDER BY position;
```

### Get recent chat history
```sql
SELECT * FROM chat_history 
WHERE workbook_id = $1 
ORDER BY created_at DESC 
LIMIT 50;
```

### Get active prompts
```sql
SELECT * FROM prompts 
WHERE is_active = TRUE 
AND role = $1 
ORDER BY version DESC 
LIMIT 1;
``` 