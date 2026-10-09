-- Cap free minutes per IP instead of blocking sign-up (Option 2)
-- Run this in Neon SQL Editor before deploying the code changes.

CREATE TABLE IF NOT EXISTS public.ip_free_usage (
  ip_hash TEXT PRIMARY KEY,
  free_asr_minutes_used NUMERIC(10,2) NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ip_free_usage_updated
  ON public.ip_free_usage(updated_at);
