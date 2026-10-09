"""User-scoped API key service for programmatic access (e.g. Apple Shortcuts)."""

import hashlib
import logging
import secrets
import uuid
from typing import Optional, Tuple

from app.core.config import settings

logger = logging.getLogger(__name__)

KEY_PREFIX = "tk_"
KEY_BYTES = 32  # 43 chars base64url


def _hash_key(plain_key: str) -> str:
    """SHA-256 hash of the API key for storage."""
    return hashlib.sha256(plain_key.encode()).hexdigest()


def _make_prefix(plain_key: str) -> str:
    """First 8 + ... + last 4 chars for display."""
    if len(plain_key) <= 12:
        return plain_key[:4] + "****"
    return plain_key[:8] + "..." + plain_key[-4:]


class ApiKeyService:
    """Generate, store, and lookup user API keys."""

    def __init__(self):
        self._pool = None

    async def _get_pool_async(self) -> Optional[object]:
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
                logger.info("ApiKeyService: Neon pool initialized")
            except Exception as e:
                logger.warning(f"ApiKeyService: Could not connect to Neon: {e}")
        return self._pool

    async def lookup_user_id(self, bearer_token: str) -> Optional[str]:
        """
        If the Bearer token is a user API key, return the user_id.
        Otherwise return None.
        """
        if not bearer_token or not bearer_token.strip():
            return None
        token = bearer_token.strip()
        key_hash = _hash_key(token)
        pool = await self._get_pool_async()
        if not pool:
            return None
        try:
            row = await pool.fetchrow(
                """
                SELECT user_id FROM public.user_api_keys
                WHERE key_hash = $1
                """,
                key_hash,
            )
            return str(row["user_id"]) if row and row.get("user_id") else None
        except Exception as e:
            logger.warning(f"lookup_user_id failed: {e}")
            return None

    async def get_or_create_key(self, user_id: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Get existing key prefix, or create new key.
        Returns (plain_key_if_new, key_prefix).
        - If key exists: (None, "tk_xxxx...xxxx")
        - If key created: (full_plain_key, "tk_xxxx...xxxx") - caller must return plain_key once
        """
        pool = await self._get_pool_async()
        if not pool:
            return None, None
        try:
            row = await pool.fetchrow(
                """
                SELECT key_prefix FROM public.user_api_keys
                WHERE user_id = $1
                """,
                user_id,
            )
            if row:
                return None, row["key_prefix"]

            # Create new key
            plain_key = KEY_PREFIX + secrets.token_urlsafe(KEY_BYTES)
            key_hash = _hash_key(plain_key)
            key_prefix = _make_prefix(plain_key)
            await pool.execute(
                """
                INSERT INTO public.user_api_keys (user_id, key_hash, key_prefix)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id) DO NOTHING
                """,
                user_id,
                key_hash,
                key_prefix,
            )
            # Verify insert (in case of race)
            row = await pool.fetchrow(
                "SELECT key_hash FROM public.user_api_keys WHERE user_id = $1",
                user_id,
            )
            if row and row["key_hash"] == key_hash:
                return plain_key, key_prefix
            # Race: another request created it
            row = await pool.fetchrow(
                "SELECT key_prefix FROM public.user_api_keys WHERE user_id = $1",
                user_id,
            )
            return None, row["key_prefix"] if row else None
        except Exception as e:
            logger.error(f"get_or_create_key failed: {e}")
            return None, None

    async def regenerate_key(self, user_id: str) -> Optional[str]:
        """
        Delete existing key and create new one.
        Returns the new plain key (show once only), or None on error.
        """
        pool = await self._get_pool_async()
        if not pool:
            return None
        try:
            await pool.execute(
                "DELETE FROM public.user_api_keys WHERE user_id = $1",
                user_id,
            )
            plain_key, _ = await self.get_or_create_key(user_id)
            return plain_key
        except Exception as e:
            logger.error(f"regenerate_key failed: {e}")
            return None

    async def get_key_prefix(self, user_id: str) -> Optional[str]:
        """Get masked key prefix for display."""
        pool = await self._get_pool_async()
        if not pool:
            return None
        try:
            row = await pool.fetchrow(
                """
                SELECT key_prefix FROM public.user_api_keys
                WHERE user_id = $1
                """,
                user_id,
            )
            return row["key_prefix"] if row and row.get("key_prefix") else None
        except Exception as e:
            logger.warning(f"get_key_prefix failed: {e}")
            return None


api_key_service = ApiKeyService()
