-- Role-specific prompt table for AI assistant agents
create table role_prompts (
  id bigint generated always as identity primary key,
  mode text not null check (mode in ('ask','analyst')),
  version text default 'v1.0',
  content text not null,
  active boolean default false,
  inserted_at timestamptz default now(),
  unique (mode) where active  -- only one active per mode
); 