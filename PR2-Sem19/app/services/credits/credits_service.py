"""Credits service for user balance, free plan, and transcription_jobs."""

import logging
from dataclasses import dataclass
from typing import Optional, Tuple

from app.core.config import settings

logger = logging.getLogger(__name__)


# Plan constants (from PRICING_CREDITS_PLAN_V2.md)
FREE_PLAN_ASR_MINUTES = 10.0
FREE_PLAN_YOUTUBE_COUNT = 5
MIN_TOP_UP_PENCE = 500
MINUTES_PER_TOP_UP = 250  # £5 / 2p per minute

# Every value the app may write into transcription_jobs.source. This MUST stay in
# lockstep with the CHECK constraint in migrations/001_transcription_jobs_source_check.sql.
# A mismatch is what caused "billed but no history": the DB silently rejected a new
# source the app had started writing. tests/test_transcription_sources.py guards the pair.
ALLOWED_TRANSCRIPTION_SOURCES = ("youtube_captions", "asr", "tiktok_captions")


@dataclass
class UserCredits:
    """User credits snapshot."""

    balance_minutes: int
    free_plan_asr_minutes_used: float
    free_plan_youtube_used: int
    remaining_asr_minutes: float  # Free plan remaining + paid balance
    # Effective free remaining (IP-capped when ip_hash provided). For UI display.
    effective_free_plan_asr_remaining: float = 0.0

    @property
    def free_plan_asr_remaining(self) -> float:
        return max(0, FREE_PLAN_ASR_MINUTES - self.free_plan_asr_minutes_used)

    @property
    def free_plan_youtube_remaining(self) -> int:
        return max(0, FREE_PLAN_YOUTUBE_COUNT - self.free_plan_youtube_used)

    @property
    def effective_free_plan_asr_used(self) -> float:
        """Free plan minutes used (effective, IP-capped). For UI: show X/10 used."""
        return max(0.0, FREE_PLAN_ASR_MINUTES - self.effective_free_plan_asr_remaining)


class CreditsService:
    """
    Manages user credits (Neon Postgres).
    Lazy-creates user_credits on first access.
    """

    def __init__(self):
        self._pool = None

    async def _get_pool_async(self):
        """Get or create async connection pool."""
        if self._pool is None and settings.database_url:
            try:
                import asyncpg

                self._pool = await asyncpg.create_pool(
                    settings.database_url,
                    min_size=1,
                    max_size=5,
                    command_timeout=10,
                    max_inactive_connection_lifetime=60,
                )
                logger.info("CreditsService: Neon pool initialized")
            except Exception as e:
                logger.warning(f"CreditsService: Could not connect to Neon: {e}")
        return self._pool

    async def get_user_email(self, user_id: str) -> Optional[str]:
        """Get user email from public.user (Better Auth) for Stripe Checkout pre-fill."""
        pool = await self._get_pool_async()
        if not pool:
            return None
        try:
            row = await pool.fetchrow(
                'SELECT email FROM public."user" WHERE id = $1',
                user_id,
            )
            return row["email"] if row and row["email"] else None
        except Exception as e:
            logger.warning(f"get_user_email failed: {e}")
            return None

    async def is_unlimited_account(self, user_id: str) -> bool:
        """True if the account should never be charged.

        When billing is disabled (the default), every account is unlimited: no
        credits are deducted and no Stripe setup is needed. Flip BILLING_ENABLED=true
        to charge users; owner emails stay unlimited either way.
        """
        if not getattr(settings, "billing_enabled", False):
            return True
        owner_emails = settings.get_owner_emails()
        if not owner_emails:
            return False
        email = await self.get_user_email(user_id)
        return email is not None and email.strip().lower() in owner_emails

    async def ensure_user_credits(self, user_id: str) -> bool:
        """
        Create user_credits row if not exists (lazy sign-up).
        Returns True if row exists or was created.
        """
        pool = await self._get_pool_async()
        if not pool:
            return False
        try:
            await pool.execute(
                """
                INSERT INTO public.user_credits (user_id)
                VALUES ($1)
                ON CONFLICT (user_id) DO NOTHING
                """,
                user_id,
            )
            return True
        except Exception as e:
            logger.error(f"ensure_user_credits failed: {e}")
            return False

    async def check_can_start_asr_job(
        self,
        user_id: Optional[str],
        duration_minutes: Optional[float],
        ip_hash: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Pre-check: can user start an ASR job with given duration?

        - Anonymous (user_id None): allow (no credits tracking)
        - Unknown duration: require min_balance_for_unknown_duration (Option C)
        - Known duration: require remaining_minutes >= duration_minutes

        Returns:
            (True, None) if allowed
            (False, error_message) if rejected
        """
        if not user_id:
            return True, None

        if await self.is_unlimited_account(user_id):
            return True, None

        credits = await self.get_user_credits(user_id, ip_hash=ip_hash)
        if not credits:
            return False, "Could not verify credits. Please try again."

        remaining = credits.remaining_asr_minutes

        if duration_minutes is None:
            min_required = getattr(
                settings, "min_balance_for_unknown_duration", 15.0
            )
            if remaining < min_required:
                return (
                    False,
                    f"This media duration could not be determined. "
                    f"You need at least {min_required:.0f} minutes remaining to start. "
                    f"You have {remaining:.1f} minutes. Top up to continue.",
                )
            return True, None

        if remaining < duration_minutes:
            return (
                False,
                f"This media is {duration_minutes:.1f} minutes. "
                f"You have {remaining:.1f} minutes remaining. Top up to continue.",
            )
        return True, None

    async def check_can_youtube(
        self,
        user_id: Optional[str],
        ip_hash: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Pre-check: can user do a YouTube caption transcription?
        - First 5: free (no minutes).
        - After 5: allowed if remaining_minutes > 0 (will deduct by duration).

        Returns (True, None) if allowed, (False, error_message) if rejected.
        """
        if not user_id:
            return True, None

        if await self.is_unlimited_account(user_id):
            return True, None

        credits = await self.get_user_credits(user_id, ip_hash=ip_hash)
        if not credits:
            return False, "Could not verify credits. Please try again."
        if credits.free_plan_youtube_used >= FREE_PLAN_YOUTUBE_COUNT:
            # Past free 5: allow if they have remaining minutes
            if credits.remaining_asr_minutes <= 0:
                return (
                    False,
                    f"You've used all {FREE_PLAN_YOUTUBE_COUNT} free YouTube transcriptions. "
                    "Top up to continue.",
                )
        return True, None

    async def get_user_credits(
        self, user_id: str, ip_hash: Optional[str] = None
    ) -> Optional[UserCredits]:
        """Get user credits. Ensures row exists first. If ip_hash provided, caps free
        remaining by ip_free_usage (10 min shared per IP)."""
        if not await self.ensure_user_credits(user_id):
            return None
        pool = await self._get_pool_async()
        if not pool:
            return None
        try:
            row = await pool.fetchrow(
                """
                SELECT balance_minutes, free_plan_asr_minutes_used, free_plan_youtube_used
                FROM public.user_credits
                WHERE user_id = $1
                """,
                user_id,
            )
            if not row:
                return None
            free_remaining = max(0, FREE_PLAN_ASR_MINUTES - float(row["free_plan_asr_minutes_used"]))
            if ip_hash:
                ip_row = await pool.fetchrow(
                    """
                    SELECT free_asr_minutes_used FROM public.ip_free_usage WHERE ip_hash = $1
                    """,
                    ip_hash,
                )
                ip_used = float(ip_row["free_asr_minutes_used"]) if ip_row and ip_row["free_asr_minutes_used"] else 0
                ip_free_cap = max(0, FREE_PLAN_ASR_MINUTES - ip_used)
                free_remaining = min(free_remaining, ip_free_cap)
            total_remaining = free_remaining + row["balance_minutes"]
            return UserCredits(
                balance_minutes=row["balance_minutes"],
                free_plan_asr_minutes_used=float(row["free_plan_asr_minutes_used"]),
                free_plan_youtube_used=row["free_plan_youtube_used"],
                remaining_asr_minutes=total_remaining,
                effective_free_plan_asr_remaining=free_remaining,
            )
        except Exception as e:
            logger.error(f"get_user_credits failed: {e}")
            return None

    async def insert_transcription_job(
        self,
        job_id: str,
        user_id: str,
        source: str,
        status: str = "queued",
        source_url: Optional[str] = None,
        transcript: Optional[str] = None,
    ) -> bool:
        """Insert job into transcription_jobs for History page."""
        pool = await self._get_pool_async()
        if not pool:
            return False
        # Catch a drifted source value before the DB silently rejects the row.
        # This is the "billed but no history" trap: ASR usage is recorded under its
        # own source, so the charge lands even when this history INSERT fails.
        if source not in ALLOWED_TRANSCRIPTION_SOURCES:
            logger.error(
                "insert_transcription_job: source %r is NOT in the allowed set %s — "
                "the transcription_jobs CHECK constraint will reject this row and the "
                "user will be billed with NO history entry. Add it to "
                "ALLOWED_TRANSCRIPTION_SOURCES and migrations/001_transcription_jobs_source_check.sql. "
                "(job_id=%s user_id=%s)",
                source, list(ALLOWED_TRANSCRIPTION_SOURCES), job_id, user_id,
            )
        try:
            await pool.execute(
                """
                INSERT INTO public.transcription_jobs (job_id, user_id, source, status, source_url, transcript)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (job_id) DO NOTHING
                """,
                job_id,
                user_id,
                source,
                status,
                source_url,
                transcript,
            )
            return True
        except Exception as e:
            # Loud on purpose: a failure here means the job may still be billed while
            # the History page shows nothing. Log the full payload so it is unmissable.
            logger.error(
                "insert_transcription_job FAILED (billed-but-no-history risk): %s "
                "(job_id=%s user_id=%s source=%r status=%s)",
                e, job_id, user_id, source, status,
            )
            return False

    async def deduct_asr_minutes(
        self,
        user_id: str,
        job_id: str,
        minutes_used: float,
        ip_hash: Optional[str] = None,
    ) -> bool:
        """
        Deduct ASR minutes on job completion.
        Uses paid balance first, then free plan (preserves free for when paid runs out).
        Inserts credit_usage and updates user_credits.
        If ip_hash provided and free_portion > 0, updates ip_free_usage.
        Owner accounts (OWNER_EMAILS): no deduction.
        """
        if await self.is_unlimited_account(user_id):
            return True

        pool = await self._get_pool_async()
        if not pool:
            return False
        try:
            row = await pool.fetchrow(
                """
                SELECT free_plan_asr_minutes_used, balance_minutes
                FROM public.user_credits
                WHERE user_id = $1
                """,
                user_id,
            )
            if not row:
                logger.warning(f"deduct_asr_minutes: no user_credits for {user_id}")
                return False

            balance = row["balance_minutes"]
            remaining_free = max(
                0, FREE_PLAN_ASR_MINUTES - float(row["free_plan_asr_minutes_used"])
            )
            if ip_hash:
                ip_row = await pool.fetchrow(
                    "SELECT free_asr_minutes_used FROM public.ip_free_usage WHERE ip_hash = $1",
                    ip_hash,
                )
                ip_used = float(ip_row["free_asr_minutes_used"]) if ip_row and ip_row["free_asr_minutes_used"] else 0
                ip_free_cap = max(0, FREE_PLAN_ASR_MINUTES - ip_used)
                remaining_free = min(remaining_free, ip_free_cap)
            paid_portion = min(minutes_used, balance)
            free_portion = max(0, minutes_used - paid_portion)
            if free_portion > remaining_free:
                logger.warning(
                    f"deduct_asr_minutes: insufficient total user={user_id} "
                    f"free_portion={free_portion} remaining_free={remaining_free}"
                )
                free_portion = remaining_free

            async with pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(
                        """
                        UPDATE public.user_credits
                        SET free_plan_asr_minutes_used = free_plan_asr_minutes_used + $2,
                            balance_minutes = balance_minutes - $3,
                            total_minutes_used = total_minutes_used + $4,
                            updated_at = now()
                        WHERE user_id = $1
                        """,
                        user_id,
                        free_portion,
                        paid_portion,
                        minutes_used,
                    )
                    await conn.execute(
                        """
                        INSERT INTO public.credit_usage (user_id, job_id, minutes_used, source)
                        VALUES ($1, $2, $3, 'asr')
                        """,
                        user_id,
                        job_id,
                        minutes_used,
                    )
                    if ip_hash and free_portion > 0:
                        await conn.execute(
                            """
                            INSERT INTO public.ip_free_usage (ip_hash, free_asr_minutes_used, updated_at)
                            VALUES ($1, $2, now())
                            ON CONFLICT (ip_hash) DO UPDATE SET
                                free_asr_minutes_used = ip_free_usage.free_asr_minutes_used + $2,
                                updated_at = now()
                            """,
                            ip_hash,
                            free_portion,
                        )
            return True
        except Exception as e:
            logger.error(f"deduct_asr_minutes failed: {e}")
            return False

    async def apply_top_up(
        self,
        user_id: str,
        amount_pence: int,
        stripe_payment_intent_id: Optional[str] = None,
        stripe_status: Optional[str] = None,
    ) -> bool:
        """
        Apply a Stripe top-up: add minutes to balance, insert top_ups row.
        amount_pence must be >= 500 (£5). Minutes = amount_pence / 2 .
        """
        if amount_pence < MIN_TOP_UP_PENCE:
            logger.warning(f"apply_top_up: amount {amount_pence} below minimum {MIN_TOP_UP_PENCE}")
            return False
        minutes = (amount_pence // 2)  # 2p per minute, integer minutes
        pool = await self._get_pool_async()
        if not pool:
            return False
        try:
            await self.ensure_user_credits(user_id)
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(
                        """
                        UPDATE public.user_credits
                        SET balance_minutes = balance_minutes + $2,
                            total_minutes_purchased = total_minutes_purchased + $2,
                            updated_at = now()
                        WHERE user_id = $1
                        """,
                        user_id,
                        minutes,
                    )
                    await conn.execute(
                        """
                        INSERT INTO public.top_ups (user_id, amount_pence, minutes_purchased, stripe_payment_intent_id, stripe_status)
                        VALUES ($1, $2, $3, $4, $5)
                        """,
                        user_id,
                        amount_pence,
                        minutes,
                        stripe_payment_intent_id,
                        stripe_status,
                    )
            logger.info(f"apply_top_up: user={user_id} +{minutes} min (£{amount_pence/100:.2f})")
            return True
        except Exception as e:
            logger.error(f"apply_top_up failed: {e}")
            return False

    async def list_history(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """List transcription jobs for History page. Most recent first.
        Returns (jobs, total_count)."""
        pool = await self._get_pool_async()
        if not pool:
            return [], 0
        try:
            total_row = await pool.fetchrow(
                "SELECT COUNT(*)::int AS cnt FROM public.transcription_jobs WHERE user_id = $1",
                user_id,
            )
            total = total_row["cnt"] if total_row else 0

            rows = await pool.fetch(
                """
                SELECT job_id, source, status, duration_minutes, minutes_charged,
                       error_message, created_at, completed_at, source_url, transcript
                FROM public.transcription_jobs
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
                """,
                user_id,
                limit,
                offset,
            )
            def _f(v):
                if v is None:
                    return None
                return float(v)

            jobs = [
                {
                    "jobId": r["job_id"],
                    "source": r["source"],
                    "status": r["status"],
                    "durationMinutes": _f(r["duration_minutes"]),
                    "minutesCharged": _f(r["minutes_charged"]) or 0,
                    "errorMessage": r["error_message"],
                    "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
                    "completedAt": r["completed_at"].isoformat() if r["completed_at"] else None,
                    "sourceUrl": r["source_url"],
                    "transcript": r["transcript"],
                }
                for r in rows
            ]
            return jobs, total
        except Exception as e:
            logger.error(f"list_history failed: {e}")
            return [], 0

    async def update_transcription_job(
        self,
        job_id: str,
        status: str,
        duration_minutes: Optional[float] = None,
        minutes_charged: float = 0,
        error_message: Optional[str] = None,
        result_ref: Optional[str] = None,
        source_url: Optional[str] = None,
        transcript: Optional[str] = None,
    ) -> bool:
        """Update transcription_jobs on completion/failure."""
        pool = await self._get_pool_async()
        if not pool:
            return False
        try:
            await pool.execute(
                """
                UPDATE public.transcription_jobs
                SET status = $2, completed_at = now(),
                    duration_minutes = COALESCE($3, duration_minutes),
                    minutes_charged = $4,
                    error_message = $5,
                    result_ref = $6,
                    source_url = COALESCE($7, source_url),
                    transcript = COALESCE($8, transcript)
                WHERE job_id = $1
                """,
                job_id,
                status,
                duration_minutes,
                minutes_charged,
                error_message,
                result_ref,
                source_url,
                transcript,
            )
            return True
        except Exception as e:
            logger.error(
                "update_transcription_job FAILED (history may be stale): %s "
                "(job_id=%s status=%s)",
                e, job_id, status,
            )
            return False

    async def increment_youtube_used(self, user_id: str) -> bool:
        """Increment free_plan_youtube_used for a user (max 5 on free plan). Owner accounts: no increment."""
        if await self.is_unlimited_account(user_id):
            return True

        pool = await self._get_pool_async()
        if not pool:
            return False
        try:
            await pool.execute(
                """
                UPDATE public.user_credits
                SET free_plan_youtube_used = LEAST(free_plan_youtube_used + 1, $2),
                    updated_at = now()
                WHERE user_id = $1
                """,
                user_id,
                FREE_PLAN_YOUTUBE_COUNT,
            )
            return True
        except Exception as e:
            logger.error(f"increment_youtube_used failed: {e}")
            return False
