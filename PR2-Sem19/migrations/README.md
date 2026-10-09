# Database migrations

Plain SQL files applied against the Postgres database (Neon in production) in
numbered order. They are idempotent — safe to run more than once.

```bash
psql "$DATABASE_URL" -f migrations/001_transcription_jobs_source_check.sql
```

| File | What it guarantees |
| --- | --- |
| `001_transcription_jobs_source_check.sql` | `transcription_jobs.source` accepts every value the app writes (`youtube_captions`, `asr`, `tiktok_captions`). Prevents the "billed but no history" bug. |

When you add a new `source` value in the app, add it to **all three** places and
the guard test will stay green:

1. `app/services/credits/credits_service.py` → `ALLOWED_TRANSCRIPTION_SOURCES`
2. `migrations/001_transcription_jobs_source_check.sql`
3. (nothing to change in) `tests/test_transcription_sources.py` — it reads the other two
