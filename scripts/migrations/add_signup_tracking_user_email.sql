-- Add user_email and user_id to signup_tracking so we can show which account is linked to an IP.
-- Run this in Neon SQL Editor or via psql before deploying the code changes.

ALTER TABLE public.signup_tracking
  ADD COLUMN IF NOT EXISTS user_email TEXT,
  ADD COLUMN IF NOT EXISTS user_id TEXT;
