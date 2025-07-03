-- Role-specific prompt table for AI assistant agents
create table role_prompts (
  id bigint generated always as identity primary key,
  mode text not null check (mode in ('ask','analyst')),
  version text default 'v1.0',
  content text not null,
  active boolean default false,
  inserted_at timestamptz default now()
);

-- Create partial unique index to ensure only one active prompt per mode
create unique index idx_role_prompts_active_mode on role_prompts (mode) where active = true; 