"""IP hashing utilities for abuse prevention. Must match lib/auth/signup-check.ts."""

from typing import Union

from fastapi import Request

from app.core.config import settings


def hash_ip(ip: str) -> str:
    """Hash an IP string using same algorithm as TypeScript signup-check.
    Salt from SIGNUP_IP_SALT env (default: transcriber-signup).
    Returns string like h_<hex>.
    """
    salt = getattr(settings, "signup_ip_salt", None) or "transcriber-signup"
    s = ip + salt
    h = 0
    for i in range(len(s)):
        h = ((h << 5) - h + ord(s[i])) & 0xFFFFFFFF
    # Match JS: h|=0 gives signed int; Math.abs(h).toString(16)
    if h >= 0x80000000:
        h = h - 0x100000000
    return f"h_{abs(h):x}"


def get_client_ip(request: Request) -> str:
    """Extract client IP from request (X-Forwarded-For or X-Real-IP)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    return "unknown"


def hash_client_ip(request: Request) -> str:
    """Get hashed client IP from request."""
    return hash_ip(get_client_ip(request))
