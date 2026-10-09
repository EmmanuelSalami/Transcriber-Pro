"""Guard: the app's transcription `source` values and the DB CHECK constraint must agree.

This is the regression test for the "billed but no history" bug. ASR usage is billed
on its own path, so if the app writes a `source` the database constraint rejects, the
user is charged but the History INSERT silently fails. This test fails CI the moment
``ALLOWED_TRANSCRIPTION_SOURCES`` and migration 001 drift apart, forcing both to be
updated together instead of discovering the mismatch in production.
"""

import re
from pathlib import Path

from app.services.credits.credits_service import ALLOWED_TRANSCRIPTION_SOURCES

MIGRATION = (
    Path(__file__).resolve().parent.parent
    / "migrations"
    / "001_transcription_jobs_source_check.sql"
)


def _constraint_sources_from_sql() -> set[str]:
    """Pull the string literals out of the CHECK (... ARRAY[...]) in the migration."""
    sql = MIGRATION.read_text(encoding="utf-8")
    match = re.search(r"ARRAY\s*\[(.*?)\]", sql, re.IGNORECASE | re.DOTALL)
    assert match, f"Could not find ARRAY[...] in {MIGRATION.name}"
    return set(re.findall(r"'([^']+)'", match.group(1)))


def test_app_sources_match_db_constraint():
    app_sources = set(ALLOWED_TRANSCRIPTION_SOURCES)
    db_sources = _constraint_sources_from_sql()
    assert app_sources == db_sources, (
        "transcription `source` values are out of sync.\n"
        f"  app  (ALLOWED_TRANSCRIPTION_SOURCES): {sorted(app_sources)}\n"
        f"  db   (migration 001 CHECK):           {sorted(db_sources)}\n"
        "Update app/services/credits/credits_service.py AND "
        "migrations/001_transcription_jobs_source_check.sql together."
    )


def test_known_sources_present():
    # The three sources the app has historically written must never silently disappear.
    for required in ("youtube_captions", "asr", "tiktok_captions"):
        assert required in ALLOWED_TRANSCRIPTION_SOURCES
