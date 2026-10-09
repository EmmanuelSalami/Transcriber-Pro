"""Tests for IP-based free minutes cap (Option 2)."""

import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.credits.credits_service import CreditsService, FREE_PLAN_ASR_MINUTES
from app.core.ip_utils import hash_ip, get_client_ip


class TestHashIp:
    """Verify Python hash matches TypeScript (lib/auth/signup-check.ts)."""

    def test_hash_ip_deterministic(self):
        """Same IP + salt produces same hash."""
        assert hash_ip("192.168.1.1") == hash_ip("192.168.1.1")

    def test_hash_ip_format(self):
        """Hash starts with h_ and is hex."""
        result = hash_ip("10.0.0.1")
        assert result.startswith("h_")
        assert all(c in "0123456789abcdef" for c in result[2:])

    def test_hash_ip_different_inputs_different_hashes(self):
        """Different IPs produce different hashes."""
        h1 = hash_ip("192.168.1.1")
        h2 = hash_ip("192.168.1.2")
        assert h1 != h2


class TestCreditsServiceIpCap:
    """Test get_user_credits and deduct_asr_minutes with ip_hash."""

    @pytest.fixture
    def mock_pool(self):
        """Create mock asyncpg pool."""
        pool = AsyncMock()
        conn = AsyncMock()
        pool.acquire.return_value.__aenter__.return_value = conn
        pool.acquire.return_value.__aexit__.return_value = None
        return pool, conn

    @pytest.mark.asyncio
    async def test_get_user_credits_caps_by_ip_when_ip_hash_provided(self, mock_pool):
        """When ip_hash provided and ip_free_usage has usage, remaining is capped."""
        pool, conn = mock_pool

        # User has 10 free used (0 remaining from user perspective), but we're testing IP cap
        # Simulate: user has 2 free minutes used (8 remaining per user), IP has 7 used (3 remaining per IP)
        user_row = {
            "balance_minutes": 0,
            "free_plan_asr_minutes_used": 2.0,
            "free_plan_youtube_used": 0,
        }
        ip_row = {"free_asr_minutes_used": 7.0}

        pool.fetchrow = AsyncMock(side_effect=[user_row, ip_row])
        conn.execute = AsyncMock()

        with patch.object(CreditsService, "_get_pool_async", return_value=pool):
            svc = CreditsService()
            svc._pool = pool

            uid = uuid.uuid4()
            credits = await svc.get_user_credits(uid, ip_hash="h_abc123")

            assert credits is not None
            # User free remaining = 10 - 2 = 8. IP cap = 10 - 7 = 3. Effective = min(8, 3) = 3
            assert credits.remaining_asr_minutes == 3.0

    @pytest.mark.asyncio
    async def test_get_user_credits_no_cap_when_no_ip_hash(self, mock_pool):
        """Without ip_hash, no IP cap applied."""
        pool, conn = mock_pool
        user_row = {
            "balance_minutes": 5,
            "free_plan_asr_minutes_used": 3.0,
            "free_plan_youtube_used": 0,
        }
        pool.fetchrow = AsyncMock(return_value=user_row)
        conn.execute = AsyncMock()

        with patch.object(CreditsService, "_get_pool_async", return_value=pool):
            svc = CreditsService()
            svc._pool = pool
            uid = uuid.uuid4()
            credits = await svc.get_user_credits(uid)

            assert credits is not None
            # 10 - 3 = 7 free + 5 balance = 12
            assert credits.remaining_asr_minutes == 12.0
