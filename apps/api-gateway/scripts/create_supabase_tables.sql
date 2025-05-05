-- Create tables for workbook persistence in Supabase

-- Spreadsheet workbooks table
create table if not exists spreadsheet_workbooks (
    id uuid primary key default gen_random_uuid(),
    wid text unique not null,
    created_at timestamptz default now()
);

-- Spreadsheet sheets table
create table if not exists spreadsheet_sheets (
    id uuid primary key default gen_random_uuid(),
    workbook_wid text references spreadsheet_workbooks(wid) on delete cascade,
    name text not null,
    n_rows int,
    n_cols int,
    cells jsonb,
    updated_at timestamptz default now(),
    unique (workbook_wid, name)
);

-- Add indexes for faster queries
create index if not exists idx_spreadsheet_workbooks_wid on spreadsheet_workbooks(wid);
create index if not exists idx_spreadsheet_sheets_workbook_wid on spreadsheet_sheets(workbook_wid); 