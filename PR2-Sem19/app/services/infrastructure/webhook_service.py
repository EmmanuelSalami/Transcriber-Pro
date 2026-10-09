"""Service for sending webhook callbacks on job completion."""

import asyncio
import ipaddress
import logging
import socket
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings
from app.core.exceptions import TranscriptionError
from app.utils.url_validation import validate_remote_url

logger = logging.getLogger(__name__)


class WebhookService:
    """
    Service for sending webhook callbacks to external URLs.

    This service handles POSTing transcription results to callback URLs
    when jobs complete. It includes:
    - Timeout limits to prevent hanging requests
    - Retry logic with exponential backoff
    - SSRF protection (validates URLs and blocks private/internal IPs)
    - Non-blocking async execution
    - Proper error handling and logging

    Attributes:
        timeout_seconds (int): Timeout for webhook requests in seconds
        max_retries (int): Maximum number of retry attempts for failed webhooks
        retry_backoff_base (float): Base delay for exponential backoff (seconds)

    Example:
        >>> service = WebhookService()
        >>> success = await service.send_webhook(
        ...     "https://example.com/callback",
        ...     {"transcript": "Hello world", "segments": [...]},
        ...     job_id="job-123"
        ... )
        >>> if success:
        ...     print("Webhook sent successfully")
    """

    def __init__(
        self,
        timeout_seconds: Optional[int] = None,
        max_retries: Optional[int] = None,
    ) -> None:
        """
        Initialize the webhook service.

        Loads configuration from settings and sets up timeout and retry parameters.
        Uses dependency injection pattern to allow custom configuration for testing.

        Args:
            timeout_seconds (Optional[int]): Timeout for webhook requests in seconds.
                If None, uses settings.webhook_timeout_seconds (default: 10)
            max_retries (Optional[int]): Maximum number of retry attempts.
                If None, uses settings.webhook_max_retries (default: 3)

        Returns:
            None: Initializes the service instance

        Example:
            >>> service = WebhookService()
            >>> service.timeout_seconds
            10
            >>> service.max_retries
            3
            >>> # Custom configuration
            >>> custom_service = WebhookService(timeout_seconds=30, max_retries=5)
        """
        self.timeout_seconds = timeout_seconds or settings.webhook_timeout_seconds
        self.max_retries = max_retries or settings.webhook_max_retries
        self.retry_backoff_base = settings.webhook_retry_backoff_base

        logger.info(
            f"[WEBHOOK] WebhookService initialized: "
            f"timeout={self.timeout_seconds}s, max_retries={self.max_retries}"
        )

    def _is_private_ip(self, hostname: str) -> bool:
        """
        Check if hostname resolves to a private/internal IP address.

        This method provides comprehensive SSRF protection by:
        - Resolving hostname to IP address using socket.gethostbyname()
        - Checking if IP is in private ranges (RFC 1918, RFC 4193, etc.)
        - Checking for link-local, loopback, and multicast addresses
        - Handling both IPv4 and IPv6 addresses

        Args:
            hostname (str): Hostname or IP address to check

        Returns:
            bool: True if hostname resolves to private/internal IP, False otherwise.
                Returns True (blocks) if hostname cannot be resolved (fail-safe)

        Raises:
            None: All exceptions are caught and logged, method returns True (block) on error

        Note:
            This is a private method used internally for SSRF protection.
            Returns True (block) on any error to err on the side of caution.

        Example:
            >>> service = WebhookService()
            >>> service._is_private_ip("192.168.1.1")
            True
            >>> service._is_private_ip("example.com")
            False
        """
        try:
            # Resolve hostname to IP address
            ip_addr = socket.gethostbyname(hostname)

            # Check if IP is in private ranges using ipaddress module
            ip_obj = ipaddress.ip_address(ip_addr)

            if ip_obj.is_private:
                return True

            if ip_obj.is_link_local:
                return True

            if ip_obj.is_loopback:
                return True

            if ip_obj.is_multicast:
                return True

            return False
        except (socket.gaierror, socket.herror, ValueError) as e:
            logger.warning(f"[WEBHOOK] Could not resolve hostname {hostname}: {e}")
            return True
        except Exception as e:
            logger.error(f"[WEBHOOK] Unexpected error checking IP for {hostname}: {e}")
            return True

    def _validate_webhook_url(self, url: str) -> bool:
        """
        Validate webhook URL to prevent SSRF attacks.

        Uses shared URL validation utility (validate_remote_url) for consistent
        SSRF protection across the application. Returns boolean for backward
        compatibility with existing code.

        Args:
            url (str): Webhook URL to validate

        Returns:
            bool: True if URL is valid and safe (public URL, not private/internal),
                False otherwise (invalid scheme, private IP, etc.)

        Raises:
            None: All exceptions are caught and logged, method returns False on error

        Note:
            This is a private method used internally for URL validation.
            Delegates to app.utils.url_validation.validate_remote_url().

        Example:
            >>> service = WebhookService()
            >>> service._validate_webhook_url("https://example.com/callback")
            True
            >>> service._validate_webhook_url("file:///etc/passwd")
            False
            >>> service._validate_webhook_url("http://localhost:8080/callback")
            False
        """
        try:
            validate_remote_url(url)
            return True
        except TranscriptionError as e:
            logger.warning(f"[WEBHOOK] Invalid or unsafe webhook URL: {url} - {e.message}")
            return False
        except Exception as e:
            logger.error(f"[WEBHOOK] Error validating webhook URL {url}: {e}")
            return False

    async def send_webhook(
        self,
        url: str,
        result: Dict[str, Any],
        job_id: Optional[str] = None,
    ) -> bool:
        """
        Send webhook callback with transcription result.

        Sends a POST request to the provided URL with the transcription result
        as JSON payload. Includes retry logic with exponential backoff for
        transient failures. Does not retry on 4xx client errors.

        Args:
            url (str): Webhook callback URL (must be a valid, public URL)
            result (Dict[str, Any]): Transcription result dictionary to send as JSON
            job_id (Optional[str]): Job identifier for logging (optional, used in log messages)

        Returns:
            bool: True if webhook was sent successfully (HTTP 2xx response),
                False otherwise (validation failed, all retries exhausted, or client error)

        Raises:
            None: All exceptions are caught and handled internally with retries

        Note:
            - Validates URL before sending (SSRF protection)
            - Uses exponential backoff: delay = base * (2^attempt)
            - Does not retry on 4xx errors (client errors)
            - Retries on 5xx errors and network errors
            - Uses httpx.AsyncClient with configurable timeouts

        Example:
            >>> service = WebhookService()
            >>> success = await service.send_webhook(
            ...     "https://example.com/callback",
            ...     {"transcript": "Hello world", "segments": [...]},
            ...     job_id="job-123"
            ... )
            >>> success
            True
        """
        if not self._validate_webhook_url(url):
            logger.error(
                f"[WEBHOOK] Invalid or unsafe webhook URL: {url}"
                + (f" (job_id: {job_id})" if job_id else "")
            )
            return False

        logger.info(
            f"[WEBHOOK] Sending webhook to {url}" + (f" (job_id: {job_id})" if job_id else "")
        )

        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                timeout = httpx.Timeout(
                    connect=settings.webhook_connect_timeout,
                    read=self.timeout_seconds,
                    write=settings.webhook_write_timeout,
                    pool=settings.webhook_pool_timeout,
                )

                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        url,
                        json=result,
                        headers={
                            "Content-Type": "application/json",
                            "User-Agent": settings.webhook_user_agent,
                        },
                    )
                    response.raise_for_status()

                    logger.info(
                        f"[WEBHOOK] Webhook sent successfully to {url}"
                        + (f" (job_id: {job_id})" if job_id else "")
                        + f" (attempt {attempt + 1}/{self.max_retries}, status: {response.status_code})"
                    )
                    return True

            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(
                    f"[WEBHOOK] Webhook timeout for {url}"
                    + (f" (job_id: {job_id})" if job_id else "")
                    + f" (attempt {attempt + 1}/{self.max_retries})"
                )
            except httpx.ConnectError as e:
                last_error = e
                logger.warning(
                    f"[WEBHOOK] Webhook connection error for {url}: {e}"
                    + (f" (job_id: {job_id})" if job_id else "")
                    + f" (attempt {attempt + 1}/{self.max_retries})"
                )
            except httpx.HTTPStatusError as e:
                last_error = e
                status_code = e.response.status_code
                logger.warning(
                    f"[WEBHOOK] Webhook HTTP error for {url}: {status_code}"
                    + (f" (job_id: {job_id})" if job_id else "")
                    + f" (attempt {attempt + 1}/{self.max_retries})"
                )
                if 400 <= status_code < 500:
                    logger.error(
                        f"[WEBHOOK] Client error ({status_code}), not retrying: {url}"
                        + (f" (job_id: {job_id})" if job_id else "")
                    )
                    return False
            except httpx.RequestError as e:
                last_error = e
                logger.warning(
                    f"[WEBHOOK] Webhook request error for {url}: {e}"
                    + (f" (job_id: {job_id})" if job_id else "")
                    + f" (attempt {attempt + 1}/{self.max_retries})"
                )
            except Exception as e:
                last_error = e
                logger.error(
                    f"[WEBHOOK] Unexpected webhook error for {url}: {type(e).__name__}: {e}"
                    + (f" (job_id: {job_id})" if job_id else "")
                    + f" (attempt {attempt + 1}/{self.max_retries})",
                    exc_info=True,
                )

            if attempt < self.max_retries - 1:
                delay = self.retry_backoff_base * (2**attempt)
                logger.info(
                    f"[WEBHOOK] Retrying webhook in {delay:.1f}s"
                    + (f" (job_id: {job_id})" if job_id else "")
                )
                await asyncio.sleep(delay)

        logger.error(
            f"[WEBHOOK] Failed to send webhook after {self.max_retries} attempts: {url}"
            + (f" (job_id: {job_id})" if job_id else "")
            + f" (last error: {last_error})"
        )
        return False

    async def retry_webhook(
        self,
        url: str,
        result: Dict[str, Any],
        max_retries: Optional[int] = None,
        job_id: Optional[str] = None,
    ) -> bool:
        """
        Retry sending webhook with custom retry count.

        Convenience method that allows overriding the max_retries setting
        for specific webhook calls. Temporarily modifies the instance's
        max_retries attribute, then restores it after the call.

        Args:
            url (str): Webhook callback URL
            result (Dict[str, Any]): Transcription result dictionary to send
            max_retries (Optional[int]): Maximum number of retry attempts.
                If None, uses instance default (self.max_retries)
            job_id (Optional[str]): Job identifier for logging (optional)

        Returns:
            bool: True if webhook was sent successfully, False otherwise

        Note:
            This method temporarily modifies self.max_retries and restores
            it after the call, even if an exception occurs.

        Example:
            >>> service = WebhookService()
            >>> success = await service.retry_webhook(
            ...     "https://example.com/callback",
            ...     {"transcript": "Hello world"},
            ...     max_retries=5,
            ...     job_id="job-123"
            ... )
        """
        original_max_retries = self.max_retries
        try:
            if max_retries is not None:
                self.max_retries = max_retries
            return await self.send_webhook(url, result, job_id)
        finally:
            self.max_retries = original_max_retries
