"""Unit tests for CreditsService."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.credits.credits_service import (
    CreditsService,
    FREE_PLAN_ASR_MINUTES,
    UserCredits,
)


@pytest.fixture
def mock_pool():
    """Mock asyncpg connection pool."""
    pool = MagicMock()
    pool.execute = AsyncMock()
    pool.fetchrow = AsyncMock()
    pool.fetch = AsyncMock()
    pool.acquire = MagicMock()
    conn = MagicMock()
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=None)
    conn.execute = AsyncMock()
    pool.acquire.return_value = conn
    return pool


@pytest.fixture
def credits_service():
    """CreditsService instance."""
    return CreditsService()


class TestCheckCanStartAsrJob:
    """Tests for check_can_start_asr_job pre-check logic."""

    @pytest.mark.asyncio
    async def test_anonymous_user_allowed(self, credits_service):
        """Anonymous (no user_id) is always allowed."""
        ok, msg = await credits_service.check_can_start_asr_job(None, 5.0)
        assert ok is True
        assert msg is None

    @pytest.mark.asyncio
    async def test_invalid_user_id_allowed(self, credits_service):
        """Invalid user_id format is allowed (fallback to no tracking)."""
        ok, msg = await credits_service.check_can_start_asr_job("not-a-uuid", 5.0)
        assert ok is True
        assert msg is None

    @pytest.mark.asyncio
    async def test_known_duration_sufficient_credits(self, credits_service, mock_pool):
        """User with enough minutes is allowed."""
        credits_service._pool = mock_pool
        mock_pool.fetchrow.return_value = {
            "balance_minutes": 0,
            "free_plan_asr_minutes_used": 3.0,
            "free_plan_youtube_used": 0,
        }
        uid = str(uuid.uuid4())
        ok, msg = await credits_service.check_can_start_asr_job(uid, 5.0)
        assert ok is True
        assert msg is None

    @pytest.mark.asyncio
    async def test_known_duration_insufficient_credits(self, credits_service, mock_pool):
        """User with insufficient minutes is rejected."""
        credits_service._pool = mock_pool
        mock_pool.fetchrow.return_value = {
            "balance_minutes": 0,
            "free_plan_asr_minutes_used": 8.0,
            "free_plan_youtube_used": 0,
        }
        uid = str(uuid.uuid4())
        ok, msg = await credits_service.check_can_start_asr_job(uid, 2.5)
        assert ok is False
        assert "2.5 minutes" in msg
        assert "2.0 minutes remaining" in msg
        assert "Top up" in msg

    @pytest.mark.asyncio
    async def test_unknown_duration_insufficient_balance(self, credits_service, mock_pool):
        """Unknown duration requires min_balance_for_unknown_duration."""
        credits_service._pool = mock_pool
        mock_pool.fetchrow.return_value = {
            "balance_minutes": 0,
            "free_plan_asr_minutes_used": 9.0,
            "free_plan_youtube_used": 0,
        }
        uid = str(uuid.uuid4())
        with patch("app.services.credits.credits_service.settings") as mock_settings:
            mock_settings.min_balance_for_unknown_duration = 15.0
            ok, msg = await credits_service.check_can_start_asr_job(uid, None)
        assert ok is False
        assert "15" in msg
        assert "1.0 minutes" in msg

    @pytest.mark.asyncio
    async def test_unknown_duration_sufficient_balance(self, credits_service, mock_pool):
        """Unknown duration allowed when enough balance (>= min_balance_for_unknown_duration)."""
        credits_service._pool = mock_pool
        mock_pool.fetchrow.return_value = {
            "balance_minutes": 100,
            "free_plan_asr_minutes_used": 10.0,
            "free_plan_youtube_used": 0,
        }
        uid = str(uuid.uuid4())
        with patch("app.services.credits.credits_service.settings") as mock_settings:
            mock_settings.min_balance_for_unknown_duration = 15.0
            ok, msg = await credits_service.check_can_start_asr_job(uid, None)
        assert ok is True
        assert msg is None


class TestUserCredits:
    """Tests for UserCredits dataclass."""

    def test_remaining_asr_minutes_free_plan(self):
        """remaining_asr_minutes = free remaining + paid balance."""
        c = UserCredits(
            balance_minutes=0,
            free_plan_asr_minutes_used=3.0,
            free_plan_youtube_used=0,
            remaining_asr_minutes=7.0,
        )
        assert c.free_plan_asr_remaining == 7.0
        assert c.remaining_asr_minutes == 7.0

    def test_remaining_asr_minutes_with_paid(self):
        """Paid balance adds to remaining."""
        c = UserCredits(
            balance_minutes=100,
            free_plan_asr_minutes_used=10.0,
            free_plan_youtube_used=0,
            remaining_asr_minutes=100.0,
        )
        assert c.free_plan_asr_remaining == 0
        assert c.remaining_asr_minutes == 100.0
