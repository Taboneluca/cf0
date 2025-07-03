create table "public"."profiles" (
    "id" uuid not null,
    "email" text not null,
    "full_name" text,
    "avatar_url" text,
    "is_waitlisted" boolean default true,
    "is_verified" boolean default false,
    "created_at" timestamp with time zone default CURRENT_TIMESTAMP,
    "updated_at" timestamp with time zone default CURRENT_TIMESTAMP,
    "is_admin" boolean default false
);


alter table "public"."profiles" enable row level security;

create table "public"."waitlist" (
    "id" bigint generated always as identity not null,
    "email" text not null,
    "status" text not null default 'pending'::text,
    "created_at" timestamp with time zone default now(),
    "invited_at" timestamp with time zone,
    "invite_code" uuid default gen_random_uuid()
);


alter table "public"."waitlist" enable row level security;

create table "public"."workbooks" (
    "id" uuid not null default gen_random_uuid(),
    "user_id" uuid not null,
    "title" text not null,
    "description" text,
    "data" jsonb not null default '{}'::jsonb,
    "is_public" boolean default false,
    "created_at" timestamp with time zone default CURRENT_TIMESTAMP,
    "updated_at" timestamp with time zone default CURRENT_TIMESTAMP,
    "sheets" jsonb default '["Sheet1"]'::jsonb
);


alter table "public"."workbooks" enable row level security;

CREATE UNIQUE INDEX profiles_email_key ON public.profiles USING btree (email);

CREATE UNIQUE INDEX profiles_pkey ON public.profiles USING btree (id);

CREATE UNIQUE INDEX waitlist_email_key ON public.waitlist USING btree (email);

CREATE UNIQUE INDEX waitlist_pkey ON public.waitlist USING btree (id);

CREATE UNIQUE INDEX workbooks_pkey ON public.workbooks USING btree (id);

alter table "public"."profiles" add constraint "profiles_pkey" PRIMARY KEY using index "profiles_pkey";

alter table "public"."waitlist" add constraint "waitlist_pkey" PRIMARY KEY using index "waitlist_pkey";

alter table "public"."workbooks" add constraint "workbooks_pkey" PRIMARY KEY using index "workbooks_pkey";

alter table "public"."profiles" add constraint "profiles_email_key" UNIQUE using index "profiles_email_key";

alter table "public"."profiles" add constraint "profiles_id_fkey" FOREIGN KEY (id) REFERENCES auth.users(id) not valid;

alter table "public"."profiles" validate constraint "profiles_id_fkey";

alter table "public"."waitlist" add constraint "waitlist_email_key" UNIQUE using index "waitlist_email_key";

alter table "public"."workbooks" add constraint "workbooks_user_id_fkey" FOREIGN KEY (user_id) REFERENCES profiles(id) not valid;

alter table "public"."workbooks" validate constraint "workbooks_user_id_fkey";

set check_function_bodies = off;

CREATE OR REPLACE FUNCTION public.handle_new_user()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
BEGIN
  INSERT INTO public.profiles (id, email, full_name, avatar_url)
  VALUES (new.id, new.email, new.raw_user_meta_data->>'full_name', new.raw_user_meta_data->>'avatar_url');
  
  -- Check if user was on waitlist and approved
  UPDATE public.waitlist
  SET status = 'converted'
  WHERE email = new.email AND status = 'approved';
  
  RETURN new;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.invite_waitlist_user(user_email text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
DECLARE updated_row jsonb;
BEGIN
  UPDATE public.waitlist
  SET
    status      = 'approved',
    invite_code = gen_random_uuid()
  WHERE email = user_email
  RETURNING to_jsonb(waitlist.*) INTO updated_row;

  UPDATE public.waitlist
  SET status     = 'invited',
      invited_at = NOW()
  WHERE email = user_email;

  RETURN updated_row;        -- contains invite_code for the API route
END;
$function$
;

CREATE OR REPLACE FUNCTION public.manual_invite(p_email text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'extensions', 'auth'
AS $function$
DECLARE
  resp jsonb;
BEGIN
  -- First, update status to approved
  UPDATE public.waitlist
    SET status = 'approved'
  WHERE email = p_email;

  -- Send mail + create auth.users entry
  SELECT auth.invite_user_by_email(p_email) INTO resp;  -- built-in Supabase function

  -- Update status to invited and set timestamp
  UPDATE public.waitlist
    SET status     = 'invited',
        invited_at = now()
  WHERE email = p_email;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.update_updated_at_column()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$function$
;

grant delete on table "public"."profiles" to "anon";

grant insert on table "public"."profiles" to "anon";

grant references on table "public"."profiles" to "anon";

grant select on table "public"."profiles" to "anon";

grant trigger on table "public"."profiles" to "anon";

grant truncate on table "public"."profiles" to "anon";

grant update on table "public"."profiles" to "anon";

grant delete on table "public"."profiles" to "authenticated";

grant insert on table "public"."profiles" to "authenticated";

grant references on table "public"."profiles" to "authenticated";

grant select on table "public"."profiles" to "authenticated";

grant trigger on table "public"."profiles" to "authenticated";

grant truncate on table "public"."profiles" to "authenticated";

grant update on table "public"."profiles" to "authenticated";

grant delete on table "public"."profiles" to "service_role";

grant insert on table "public"."profiles" to "service_role";

grant references on table "public"."profiles" to "service_role";

grant select on table "public"."profiles" to "service_role";

grant trigger on table "public"."profiles" to "service_role";

grant truncate on table "public"."profiles" to "service_role";

grant update on table "public"."profiles" to "service_role";

grant delete on table "public"."waitlist" to "anon";

grant insert on table "public"."waitlist" to "anon";

grant references on table "public"."waitlist" to "anon";

grant select on table "public"."waitlist" to "anon";

grant trigger on table "public"."waitlist" to "anon";

grant truncate on table "public"."waitlist" to "anon";

grant update on table "public"."waitlist" to "anon";

grant delete on table "public"."waitlist" to "authenticated";

grant insert on table "public"."waitlist" to "authenticated";

grant references on table "public"."waitlist" to "authenticated";

grant select on table "public"."waitlist" to "authenticated";

grant trigger on table "public"."waitlist" to "authenticated";

grant truncate on table "public"."waitlist" to "authenticated";

grant update on table "public"."waitlist" to "authenticated";

grant delete on table "public"."waitlist" to "service_role";

grant insert on table "public"."waitlist" to "service_role";

grant references on table "public"."waitlist" to "service_role";

grant select on table "public"."waitlist" to "service_role";

grant trigger on table "public"."waitlist" to "service_role";

grant truncate on table "public"."waitlist" to "service_role";

grant update on table "public"."waitlist" to "service_role";

grant delete on table "public"."workbooks" to "anon";

grant insert on table "public"."workbooks" to "anon";

grant references on table "public"."workbooks" to "anon";

grant select on table "public"."workbooks" to "anon";

grant trigger on table "public"."workbooks" to "anon";

grant truncate on table "public"."workbooks" to "anon";

grant update on table "public"."workbooks" to "anon";

grant delete on table "public"."workbooks" to "authenticated";

grant insert on table "public"."workbooks" to "authenticated";

grant references on table "public"."workbooks" to "authenticated";

grant select on table "public"."workbooks" to "authenticated";

grant trigger on table "public"."workbooks" to "authenticated";

grant truncate on table "public"."workbooks" to "authenticated";

grant update on table "public"."workbooks" to "authenticated";

grant delete on table "public"."workbooks" to "service_role";

grant insert on table "public"."workbooks" to "service_role";

grant references on table "public"."workbooks" to "service_role";

grant select on table "public"."workbooks" to "service_role";

grant trigger on table "public"."workbooks" to "service_role";

grant truncate on table "public"."workbooks" to "service_role";

grant update on table "public"."workbooks" to "service_role";

create policy "Users can update their own profile"
on "public"."profiles"
as permissive
for update
to public
using ((auth.uid() = id));


create policy "Users can view their own profile"
on "public"."profiles"
as permissive
for select
to public
using ((auth.uid() = id));


create policy "Admin can manage waitlist"
on "public"."waitlist"
as permissive
for all
to public
using (true)
with check (true);


create policy "Public can insert to waitlist"
on "public"."waitlist"
as permissive
for insert
to public
with check (true);


create policy "Users can update their own waitlist entries"
on "public"."waitlist"
as permissive
for update
to public
using ((email = (auth.jwt() ->> 'email'::text)))
with check (((email = (auth.jwt() ->> 'email'::text)) AND (status = 'converted'::text)));


create policy "Users can view their own waitlist entries"
on "public"."waitlist"
as permissive
for select
to public
using ((email = (auth.jwt() ->> 'email'::text)));


create policy "Users can delete their own workbooks"
on "public"."workbooks"
as permissive
for delete
to public
using ((auth.uid() = user_id));


create policy "Users can insert their own workbooks"
on "public"."workbooks"
as permissive
for insert
to public
with check ((auth.uid() = user_id));


create policy "Users can update their own workbooks"
on "public"."workbooks"
as permissive
for update
to public
using ((auth.uid() = user_id));


create policy "Users can view public workbooks"
on "public"."workbooks"
as permissive
for select
to public
using ((is_public = true));


create policy "Users can view their own workbooks"
on "public"."workbooks"
as permissive
for select
to public
using ((auth.uid() = user_id));


CREATE TRIGGER update_profiles_updated_at BEFORE UPDATE ON public.profiles FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_workbooks_updated_at BEFORE UPDATE ON public.workbooks FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


