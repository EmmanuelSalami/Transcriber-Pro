"""Credits and Stripe top-up endpoints."""

import logging
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.config import settings
from app.core.ip_utils import get_client_ip, hash_ip
from app.services.credits.api_key_service import api_key_service
from app.services.credits.credits_service import CreditsService

logger = logging.getLogger(__name__)

router = APIRouter()
credits_service = CreditsService()


class CreateCheckoutRequest(BaseModel):
    """Request body for creating a Checkout session."""

    success_url: Optional[str] = None
    cancel_url: Optional[str] = None
    amount_pence: Optional[int] = 500  # £5 minimum; default £5


class CheckoutSessionResponse(BaseModel):
    """Response with Checkout session URL."""

    url: str
    session_id: str


@router.get(
    "/credits",
    response_model=None,
    status_code=status.HTTP_200_OK,
    summary="Get user credits",
)
async def get_credits(
    request: Request,
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
) -> JSONResponse:
    """Get user credits (balance, free plan usage). Requires X-User-Id header."""
    if not x_user_id or not x_user_id.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-User-Id header required",
        )
    uid = x_user_id.strip()
    ip_hash = hash_ip(get_client_ip(request))
    credits = await credits_service.get_user_credits(uid, ip_hash=ip_hash)
    if not credits:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load credits",
        )
    is_unlimited = await credits_service.is_unlimited_account(str(uid))
    content = {
        "balanceMinutes": credits.balance_minutes,
        "freePlanAsrMinutesUsed": credits.free_plan_asr_minutes_used,
        "freePlanAsrMinutesEffectiveUsed": round(credits.effective_free_plan_asr_used, 1),
        "freePlanYoutubeUsed": credits.free_plan_youtube_used,
        "remainingAsrMinutes": credits.remaining_asr_minutes,
        "isUnlimited": is_unlimited,
    }
    return JSONResponse(status_code=status.HTTP_200_OK, content=content)


@router.get(
    "/credits/api-key",
    response_model=None,
    status_code=status.HTTP_200_OK,
    summary="Get or create user API key",
)
async def get_api_key(
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
) -> JSONResponse:
    """Get API key prefix. Creates key if none exists. Returns plainKey only on first create."""
    if not x_user_id or not x_user_id.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-User-Id header required",
        )
    uid = x_user_id.strip()
    plain_key, key_prefix = await api_key_service.get_or_create_key(uid)
    content: dict = {"keyPrefix": key_prefix}
    if plain_key:
        content["plainKey"] = plain_key
    return JSONResponse(status_code=status.HTTP_200_OK, content=content)


@router.post(
    "/credits/api-key/regenerate",
    response_model=None,
    status_code=status.HTTP_200_OK,
    summary="Regenerate user API key",
)
async def regenerate_api_key(
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
) -> JSONResponse:
    """Regenerate API key. Returns new plain key once. Old key is invalidated."""
    if not x_user_id or not x_user_id.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-User-Id header required",
        )
    uid = x_user_id.strip()
    plain_key = await api_key_service.regenerate_key(uid)
    if not plain_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to regenerate API key",
        )
    key_prefix = await api_key_service.get_key_prefix(uid)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"plainKey": plain_key, "keyPrefix": key_prefix or "tk_****"},
    )


@router.get(
    "/credits/history",
    response_model=None,
    status_code=status.HTTP_200_OK,
    summary="Get transcription history",
)
async def get_history(
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    limit: int = 5,
    page: int = 1,
) -> JSONResponse:
    """Get user's transcription job history (paginated). Requires X-User-Id header."""
    if not x_user_id or not x_user_id.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-User-Id header required",
        )
    uid = x_user_id.strip()
    limit = min(max(1, limit), 100)
    page = max(1, page)
    offset = (page - 1) * limit
    jobs, total = await credits_service.list_history(
        user_id=uid, limit=limit, offset=offset
    )
    total_pages = (total + limit - 1) // limit if total > 0 else 1
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "jobs": jobs,
            "total": total,
            "page": page,
            "limit": limit,
            "totalPages": total_pages,
        },
    )


@router.post(
    "/credits/checkout",
    response_model=None,
    status_code=status.HTTP_200_OK,
    summary="Create Stripe Checkout session for top-up",
)
async def create_checkout_session(
    request: Request,
    body: Optional[CreateCheckoutRequest] = None,
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
) -> JSONResponse:
    """Create a Stripe Checkout session. £5 minimum. Returns checkout URL."""
    if not x_user_id or not x_user_id.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-User-Id header required",
        )
    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe not configured",
        )
    amount_pence = (body.amount_pence if body and body.amount_pence is not None else 500)
    if amount_pence < 500:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Minimum top-up is £5 (500 pence)",
        )
    try:
        import stripe

        stripe.api_key = settings.stripe_secret_key
        base = str(request.base_url).rstrip("/")
        success_url = (
            (body.success_url if body else None)
            or settings.stripe_success_url
            or f"{base}/usage?topup=success"
        )
        cancel_url = (
            (body.cancel_url if body else None)
            or settings.stripe_cancel_url
            or f"{base}/usage"
        )
        user_email = await credits_service.get_user_email(x_user_id.strip())
        minutes = amount_pence // 2  # 2p per minute
        session_params: dict = {
            "mode": "payment",
            "line_items": [
                {
                    "price_data": {
                        "currency": "gbp",
                        "unit_amount": amount_pence,
                        "product_data": {
                            "name": "Transcription Credits",
                            "description": f"{minutes} minutes",
                        },
                    },
                    "quantity": 1,
                }
            ],
            "client_reference_id": x_user_id.strip(),
            "metadata": {"user_id": x_user_id.strip()},
            "success_url": success_url,
            "cancel_url": cancel_url,
            "allow_promotion_codes": True,
        }
        if user_email:
            session_params["customer_email"] = user_email
        session = stripe.checkout.Session.create(**session_params)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"url": session.url, "sessionId": session.id},
        )
    except Exception as e:
        logger.error(f"Failed to create Checkout session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create checkout session",
        )


@router.post(
    "/credits/webhook",
    response_model=None,
    status_code=status.HTTP_200_OK,
    summary="Stripe webhook",
)
async def stripe_webhook(request: Request) -> JSONResponse:
    """Handle Stripe webhook events. Verifies signature."""
    if not settings.stripe_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook secret not configured",
        )
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    try:
        import stripe

        stripe.api_key = settings.stripe_secret_key
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except ValueError as e:
        logger.warning(f"Webhook invalid payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except Exception as e:
        logger.warning(f"Webhook signature verification failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session.get("client_reference_id") or session.get("metadata", {}).get("user_id")
        # Use amount_total, or amount_subtotal if 100% coupon (amount_total=0)
        amount_total = session.get("amount_total") or 0
        amount_subtotal = session.get("amount_subtotal") or 0
        amount_pence = amount_total if amount_total >= 500 else amount_subtotal
        payment_intent = session.get("payment_intent")
        if user_id and amount_pence >= 500:
            ok = await credits_service.apply_top_up(
                user_id=user_id,
                amount_pence=amount_pence,
                stripe_payment_intent_id=payment_intent,
                stripe_status="succeeded",
            )
            if not ok:
                logger.error(f"Webhook: apply_top_up failed for user={user_id}")

    return JSONResponse(content={"received": True})
