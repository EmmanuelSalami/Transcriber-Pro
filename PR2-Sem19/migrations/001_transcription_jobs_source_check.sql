-- Migration 001: transcription_jobs.source allowed values
--
-- WHY THIS EXISTS
-- The History page reads public.transcription_jobs. Each row carries a `source`
-- column guarded by the CHECK constraint below. ASR billing is recorded separately
-- (credit_usage), so if the app writes a `source` value this constraint does not
-- allow, Postgres silently rejects the history INSERT while the user is STILL billed
-- -- the "billed but no history" bug. When TikTok-captions transcription shipped it
-- wrote source='tiktok_captions', which the original constraint (youtube_captions, asr)
-- rejected. This migration makes the allowed set authoritative and reproducible, so a
-- freshly provisioned database matches production.
--
-- KEEP IN LOCKSTEP WITH:
--   app/services/credits/credits_service.py -> ALLOWED_TRANSCRIPTION_SOURCES
--   tests/test_transcription_sources.py (fails CI if the two drift)
--
-- HOW TO RUN (safe to run repeatedly; idempotent):
--   psql "$DATABASE_URL" -f migrations/001_transcription_jobs_source_check.sql

ALTER TABLE public.transcription_jobs
    DROP CONSTRAINT IF EXISTS transcription_jobs_source_check;

ALTER TABLE public.transcription_jobs
    ADD CONSTRAINT transcription_jobs_source_check
    CHECK (source = ANY (ARRAY['youtube_captions', 'asr', 'tiktok_captions']));
