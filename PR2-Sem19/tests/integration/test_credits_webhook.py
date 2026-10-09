"""
Integration test: POST real webhook payload with valid Stripe signature.

Requires STRIPE_WEBHOOK_SECRET in env (use the one from `stripe listen`).
Mocks apply_top_up to avoid DB dependency; verifies handler receives and processes event.
"""

import json
import time
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


def _make_signed_payload(payload: dict, secret: str) -> tuple[bytes, str]:
    """Create payload bytes and Stripe-Signature header."""
    import stripe

    payload_str = json.dumps(payload)
    payload_bytes = payload_str.encode("utf-8")
    timestamp = int(time.time())
    signed_payload = f"{timestamp}.{payload_str}"
    sig = stripe.WebhookSignature._compute_signature(signed_payload, secret)
    scheme = stripe.WebhookSignature.EXPECTED_SCHEME
    header = f"t={timestamp},{scheme}={sig}"
    return payload_bytes, header


@pytest.mark.integration
@pytest.mark.asyncio
async def test_webhook_checkout_session_completed_valid_signature():
    """
    POST checkout.session.completed with valid signature.
    Verifies handler returns 200 and processes the event.
    """
    import os

    secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()
    if not secret:
        pytest.skip("STRIPE_WEBHOOK_SECRET not set (run: stripe listen)")

    payload = {
        "id": "evt_test_webhook",
        "object": "event",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_123",
                "object": "checkout.session",
                "client_reference_id": "550e8400-e29b-41d4-a716-446655440000",
                "metadata": {"user_id": "550e8400-e29b-41d4-a716-446655440000"},
                "amount_total": 500,
                "amount_subtotal": 500,
                "payment_intent": "pi_test_123",
            }
        },
    }

    payload_bytes, sig_header = _make_signed_payload(payload, secret)

    with patch(
        "app.api.v1.endpoints.credits.credits_service"
    ) as mock_svc:
        mock_svc.apply_top_up = AsyncMock(return_value=True)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                "/v1/credits/webhook",
                content=payload_bytes,
                headers={
                    "Content-Type": "application/json",
                    "stripe-signature": sig_header,
                },
            )

    assert resp.status_code == 200
    assert resp.json().get("received") is True
    mock_svc.apply_top_up.assert_called_once()
    call_kw = mock_svc.apply_top_up.call_args[1]
    assert call_kw["user_id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert call_kw["amount_pence"] == 500
