"""API tests for credits endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def valid_user_id():
    """Valid UUID for X-User-Id header."""
    return "550e8400-e29b-41d4-a716-446655440000"


@pytest.mark.asyncio
async def test_get_credits_requires_x_user_id():
    """GET /v1/credits returns 401 without X-User-Id."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/v1/credits")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert "X-User-Id" in resp.json().get("detail", "")


@pytest.mark.asyncio
async def test_get_credits_accepts_better_auth_string_id():
    """GET /v1/credits accepts Better Auth-style string IDs (not just UUID)."""
    better_auth_id = "rOVnB5HISCRkc1162so8x7dMlPqlTwPb"
    mock_credits = {
        "balance_minutes": 5,
        "free_plan_asr_minutes_used": 2.0,
        "free_plan_youtube_used": 1,
        "remaining_asr_minutes": 13.0,
    }
    with patch(
        "app.api.v1.endpoints.credits.credits_service"
    ) as mock_svc:
        from app.services.credits.credits_service import UserCredits

        mock_svc.get_user_credits = AsyncMock(
            return_value=UserCredits(
                balance_minutes=mock_credits["balance_minutes"],
                free_plan_asr_minutes_used=mock_credits["free_plan_asr_minutes_used"],
                free_plan_youtube_used=mock_credits["free_plan_youtube_used"],
                remaining_asr_minutes=mock_credits["remaining_asr_minutes"],
                effective_free_plan_asr_remaining=8.0,
            )
        )
        mock_svc.is_unlimited_account = AsyncMock(return_value=False)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                "/v1/credits",
                headers={"X-User-Id": better_auth_id},
            )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["balanceMinutes"] == 5
    assert data["remainingAsrMinutes"] == 13.0


@pytest.mark.asyncio
async def test_get_credits_success(valid_user_id):
    """GET /v1/credits returns credits when X-User-Id valid."""
    mock_credits = {
        "balance_minutes": 0,
        "free_plan_asr_minutes_used": 3.0,
        "free_plan_youtube_used": 0,
        "remaining_asr_minutes": 7.0,
    }

    with patch(
        "app.api.v1.endpoints.credits.credits_service"
    ) as mock_svc:
        from app.services.credits.credits_service import UserCredits

        mock_svc.get_user_credits = AsyncMock(
            return_value=UserCredits(
                balance_minutes=mock_credits["balance_minutes"],
                free_plan_asr_minutes_used=mock_credits["free_plan_asr_minutes_used"],
                free_plan_youtube_used=mock_credits["free_plan_youtube_used"],
                remaining_asr_minutes=mock_credits["remaining_asr_minutes"],
                effective_free_plan_asr_remaining=7.0,
            )
        )
        mock_svc.is_unlimited_account = AsyncMock(return_value=False)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                "/v1/credits",
                headers={"X-User-Id": valid_user_id},
            )

    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["balanceMinutes"] == 0
    assert data["remainingAsrMinutes"] == 7.0


@pytest.mark.asyncio
async def test_get_history_requires_x_user_id():
    """GET /v1/credits/history returns 401 without X-User-Id."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/v1/credits/history")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_get_history_success(valid_user_id):
    """GET /v1/credits/history returns jobs when X-User-Id valid."""
    mock_jobs = [
        {
            "jobId": "abc123",
            "source": "asr",
            "status": "completed",
            "durationMinutes": 2.5,
            "minutesCharged": 2.5,
            "errorMessage": None,
            "createdAt": "2024-01-01T12:00:00",
            "completedAt": "2024-01-01T12:05:00",
        }
    ]

    with patch(
        "app.api.v1.endpoints.credits.credits_service"
    ) as mock_svc:
        mock_svc.list_history = AsyncMock(return_value=(mock_jobs, 1))
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                "/v1/credits/history",
                headers={"X-User-Id": valid_user_id},
            )

    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert "jobs" in data
    assert len(data["jobs"]) == 1
    assert data["jobs"][0]["jobId"] == "abc123"
    assert data["jobs"][0]["status"] == "completed"
    assert data["total"] == 1
    assert data["page"] == 1


@pytest.mark.asyncio
async def test_checkout_requires_x_user_id():
    """POST /v1/credits/checkout returns 401 without X-User-Id."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post(
            "/v1/credits/checkout",
            json={},
        )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_webhook_requires_secret():
    """POST /v1/credits/webhook returns 503 when webhook secret not configured."""
    with patch("app.api.v1.endpoints.credits.settings") as mock_settings:
        mock_settings.stripe_webhook_secret = ""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                "/v1/credits/webhook",
                content=b"{}",
                headers={"Content-Type": "application/json"},
            )
    assert resp.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


@pytest.mark.asyncio
async def test_webhook_invalid_signature():
    """POST /v1/credits/webhook returns 400 for invalid signature."""
    with patch("app.api.v1.endpoints.credits.settings") as mock_settings:
        mock_settings.stripe_webhook_secret = "whsec_test123"
        mock_settings.stripe_secret_key = "sk_test_123"
        with patch("stripe.Webhook.construct_event", side_effect=ValueError("Invalid")):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                resp = await client.post(
                    "/v1/credits/webhook",
                    content=b'{"type":"checkout.session.completed"}',
                    headers={
                        "Content-Type": "application/json",
                        "stripe-signature": "invalid",
                    },
                )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
