"""
Comprehensive unit tests for WebhookService.

Tests cover:
- Happy path scenarios
- Edge cases
- Error conditions
- Boundary value analysis
- SSRF protection
- Retry logic
- Timeout handling
- URL validation
"""

import socket
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from app.core.exceptions import TranscriptionError
from app.services.infrastructure.webhook_service import WebhookService


class TestWebhookServiceInitialization:
    """Test WebhookService initialization."""

    def test_init_with_default_settings(self, mock_settings_webhook):
        """
        Test: Initialize service with default settings.

        Happy path - uses settings from config.
        """
        with patch("app.services.infrastructure.webhook_service.settings", mock_settings_webhook):
            service = WebhookService()

            assert service.timeout_seconds == 10
            assert service.max_retries == 3
            assert service.retry_backoff_base == 1.0

    def test_init_with_custom_timeout(self, mock_settings_webhook):
        """
        Test: Initialize service with custom timeout.

        Edge case - override default timeout.
        """
        with patch("app.services.infrastructure.webhook_service.settings", mock_settings_webhook):
            service = WebhookService(timeout_seconds=30)

            assert service.timeout_seconds == 30
            assert service.max_retries == 3  # Still uses default

    def test_init_with_custom_retries(self, mock_settings_webhook):
        """
        Test: Initialize service with custom max retries.

        Edge case - override default max retries.
        """
        with patch("app.services.infrastructure.webhook_service.settings", mock_settings_webhook):
            service = WebhookService(max_retries=5)

            assert service.max_retries == 5
            assert service.timeout_seconds == 10  # Still uses default

    def test_init_with_all_custom(self, mock_settings_webhook):
        """
        Test: Initialize service with all custom parameters.

        Edge case - override all defaults.
        """
        with patch("app.services.infrastructure.webhook_service.settings", mock_settings_webhook):
            service = WebhookService(timeout_seconds=60, max_retries=10)

            assert service.timeout_seconds == 60
            assert service.max_retries == 10


class TestWebhookServiceIsPrivateIP:
    """Test _is_private_ip functionality."""

    def test_is_private_ip_localhost(self, mock_settings_webhook):
        """
        Test: Check if localhost is private IP.

        SSRF protection - localhost should be blocked.
        """
        with patch("app.services.infrastructure.webhook_service.settings", mock_settings_webhook):
            service = WebhookService()

            with patch("socket.gethostbyname", return_value="127.0.0.1"):
                assert service._is_private_ip("localhost") is True

    def test_is_private_ip_192_168(self, mock_settings_webhook):
        """
        Test: Check if 192.168.x.x is private IP.

        SSRF protection - private IP ranges should be blocked.
        """
        with patch("app.services.infrastructure.webhook_service.settings", mock_settings_webhook):
            service = WebhookService()

            with patch("socket.gethostbyname", return_value="192.168.1.1"):
                assert service._is_private_ip("internal.example.com") is True

    def test_is_private_ip_10_0_0_0(self, mock_settings_webhook):
        """
        Test: Check if 10.0.0.0/8 is private IP.

        SSRF protection - RFC 1918 private range.
        """
        with patch("app.services.infrastructure.webhook_service.settings", mock_settings_webhook):
            service = WebhookService()

            with patch("socket.gethostbyname", return_value="10.0.0.1"):
                assert service._is_private_ip("internal.example.com") is True

    def test_is_private_ip_172_16(self, mock_settings_webhook):
        """
        Test: Check if 172.16.0.0/12 is private IP.

        SSRF protection - RFC 1918 private range.
        """
        with patch("app.services.infrastructure.webhook_service.settings", mock_settings_webhook):
            service = WebhookService()

            with patch("socket.gethostbyname", return_value="172.16.0.1"):
                assert service._is_private_ip("internal.example.com") is True

    def test_is_private_ip_public_ip(self, mock_settings_webhook):
        """
        Test: Check if public IP is not private.

        Happy path - public IPs should pass.
        """
        with patch("app.services.infrastructure.webhook_service.settings", mock_settings_webhook):
            service = WebhookService()

            with patch("socket.gethostbyname", return_value="8.8.8.8"):
                assert service._is_private_ip("example.com") is False

    def test_is_private_ip_resolution_error(self, mock_settings_webhook):
        """
        Test: Check behavior when hostname resolution fails.

        Error condition - should block on resolution failure (fail-safe).
        """
        with patch("app.services.infrastructure.webhook_service.settings", mock_settings_webhook):
            service = WebhookService()

            with patch("socket.gethostbyname", side_effect=socket.gaierror("Resolution failed")):
                assert service._is_private_ip("invalid-hostname") is True  # Block on error

    def test_is_private_ip_link_local(self, mock_settings_webhook):
        """
        Test: Check if link-local address is blocked.

        SSRF protection - link-local addresses should be blocked.
        """
        with patch("app.services.infrastructure.webhook_service.settings", mock_settings_webhook):
            service = WebhookService()

            with patch("socket.gethostbyname", return_value="169.254.1.1"):
                assert service._is_private_ip("link-local.example.com") is True

    def test_is_private_ip_loopback(self, mock_settings_webhook):
        """
        Test: Check if loopback address is blocked.

        SSRF protection - loopback addresses should be blocked.
        """
        with patch("app.services.infrastructure.webhook_service.settings", mock_settings_webhook):
            service = WebhookService()

            with patch("socket.gethostbyname", return_value="127.0.0.1"):
                assert service._is_private_ip("loopback.example.com") is True


class TestWebhookServiceValidateWebhookURL:
    """Test _validate_webhook_url functionality."""

    def test_validate_webhook_url_valid(self, mock_settings_webhook):
        """
        Test: Validate valid webhook URL.

        Happy path - valid HTTPS URL should pass.
        """
        with patch("app.services.infrastructure.webhook_service.settings", mock_settings_webhook):
            with patch("app.services.infrastructure.webhook_service.validate_remote_url"):
                service = WebhookService()
                result = service._validate_webhook_url("https://example.com/webhook")

                assert result is True

    def test_validate_webhook_url_invalid_scheme(self, mock_settings_webhook):
        """
        Test: Validate URL with invalid scheme.

        SSRF protection - non-HTTP/HTTPS schemes should be blocked.
        """
        with patch("app.services.infrastructure.webhook_service.settings", mock_settings_webhook):
            with patch(
                "app.services.infrastructure.webhook_service.validate_remote_url",
                side_effect=TranscriptionError("Invalid scheme", code="INVALID_URL"),
            ):
                service = WebhookService()
                result = service._validate_webhook_url("file:///etc/passwd")

                assert result is False

    def test_validate_webhook_url_private_ip(self, mock_settings_webhook):
        """
        Test: Validate URL pointing to private IP.

        SSRF protection - private IPs should be blocked.
        """
        with patch("app.services.infrastructure.webhook_service.settings", mock_settings_webhook):
            with patch(
                "app.services.infrastructure.webhook_service.validate_remote_url",
                side_effect=TranscriptionError("SSRF blocked", code="SSRF_BLOCKED"),
            ):
                service = WebhookService()
                result = service._validate_webhook_url("http://192.168.1.1/webhook")

                assert result is False

    def test_validate_webhook_url_validation_error(self, mock_settings_webhook):
        """
        Test: Validate URL when validation raises exception.

        Error condition - should return False on any exception.
        """
        with patch("app.services.infrastructure.webhook_service.settings", mock_settings_webhook):
            with patch(
                "app.services.infrastructure.webhook_service.validate_remote_url",
                side_effect=Exception("Unexpected error"),
            ):
                service = WebhookService()
                result = service._validate_webhook_url("https://example.com/webhook")

                assert result is False


class TestWebhookServiceSendWebhook:
    """Test send_webhook functionality."""

    @pytest.mark.asyncio
    async def test_send_webhook_success(self, mock_settings_webhook, sample_webhook_result):
        """
        Test: Send webhook successfully.

        Happy path - webhook sent successfully on first attempt.
        """
        with patch("app.services.infrastructure.webhook_service.settings", mock_settings_webhook):
            with patch(
                "app.services.infrastructure.webhook_service.validate_remote_url", return_value=True
            ):
                with patch("httpx.AsyncClient") as mock_client_class:
                    mock_response = Mock()
                    mock_response.status_code = 200
                    mock_response.raise_for_status = Mock()

                    mock_client = AsyncMock()
                    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                    mock_client.__aexit__ = AsyncMock(return_value=None)
                    mock_client.post = AsyncMock(return_value=mock_response)
                    mock_client_class.return_value = mock_client

                    service = WebhookService()
                    result = await service.send_webhook(
                        "https://example.com/webhook", sample_webhook_result, job_id="job-123"
                    )

                    assert result is True
                    mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_webhook_invalid_url(self, mock_settings_webhook, sample_webhook_result):
        """
        Test: Send webhook with invalid URL.

        Error condition - should return False without attempting request.
        """
        with patch("app.services.infrastructure.webhook_service.settings", mock_settings_webhook):
            with patch(
                "app.services.infrastructure.webhook_service.validate_remote_url",
                return_value=False,
            ):
                service = WebhookService()
                result = await service.send_webhook(
                    "http://localhost/webhook", sample_webhook_result
                )

                assert result is False

    @pytest.mark.asyncio
    async def test_send_webhook_timeout_retry(self, mock_settings_webhook, sample_webhook_result):
        """
        Test: Send webhook with timeout, then success on retry.

        Error condition - timeout on first attempt, success on second.
        """
        with patch("app.services.infrastructure.webhook_service.settings", mock_settings_webhook):
            with patch(
                "app.services.infrastructure.webhook_service.validate_remote_url", return_value=True
            ):
                with patch("httpx.AsyncClient") as mock_client_class:
                    mock_response = Mock()
                    mock_response.status_code = 200
                    mock_response.raise_for_status = Mock()

                    mock_client = AsyncMock()
                    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                    mock_client.__aexit__ = AsyncMock(return_value=None)
                    # First call times out, second succeeds
                    mock_client.post = AsyncMock(
                        side_effect=[httpx.TimeoutException("Timeout"), mock_response]
                    )
                    mock_client_class.return_value = mock_client

                    service = WebhookService(max_retries=3)

                    with patch(
                        "asyncio.sleep", new_callable=AsyncMock
                    ):  # Mock sleep to speed up test
                        result = await service.send_webhook(
                            "https://example.com/webhook", sample_webhook_result
                        )

                    assert result is True
                    assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_send_webhook_all_retries_fail(
        self, mock_settings_webhook, sample_webhook_result
    ):
        """
        Test: Send webhook when all retries fail.

        Error condition - all retry attempts fail.
        """
        with patch("app.services.infrastructure.webhook_service.settings", mock_settings_webhook):
            with patch(
                "app.services.infrastructure.webhook_service.validate_remote_url", return_value=True
            ):
                with patch("httpx.AsyncClient") as mock_client_class:
                    mock_client = AsyncMock()
                    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                    mock_client.__aexit__ = AsyncMock(return_value=None)
                    mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
                    mock_client_class.return_value = mock_client

                    service = WebhookService(max_retries=3)

                    with patch("asyncio.sleep", new_callable=AsyncMock):
                        result = await service.send_webhook(
                            "https://example.com/webhook", sample_webhook_result
                        )

                    assert result is False
                    assert mock_client.post.call_count == 3  # All retries attempted

    @pytest.mark.asyncio
    async def test_send_webhook_connection_error(
        self, mock_settings_webhook, sample_webhook_result
    ):
        """
        Test: Send webhook with connection error.

        Error condition - connection error should retry.
        """
        with patch("app.services.infrastructure.webhook_service.settings", mock_settings_webhook):
            with patch(
                "app.services.infrastructure.webhook_service.validate_remote_url", return_value=True
            ):
                with patch("httpx.AsyncClient") as mock_client_class:
                    mock_client = AsyncMock()
                    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                    mock_client.__aexit__ = AsyncMock(return_value=None)
                    mock_client.post = AsyncMock(
                        side_effect=httpx.ConnectError("Connection failed")
                    )
                    mock_client_class.return_value = mock_client

                    service = WebhookService(max_retries=2)

                    with patch("asyncio.sleep", new_callable=AsyncMock):
                        result = await service.send_webhook(
                            "https://example.com/webhook", sample_webhook_result
                        )

                    assert result is False
                    assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_send_webhook_4xx_error_no_retry(
        self, mock_settings_webhook, sample_webhook_result
    ):
        """
        Test: Send webhook with 4xx error (no retry).

        Error condition - 4xx errors should not be retried.
        """
        with patch("app.services.infrastructure.webhook_service.settings", mock_settings_webhook):
            with patch(
                "app.services.infrastructure.webhook_service.validate_remote_url", return_value=True
            ):
                with patch("httpx.AsyncClient") as mock_client_class:
                    mock_response = Mock()
                    mock_response.status_code = 400

                    mock_client = AsyncMock()
                    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                    mock_client.__aexit__ = AsyncMock(return_value=None)
                    mock_client.post = AsyncMock(
                        side_effect=httpx.HTTPStatusError(
                            "Bad request", request=Mock(), response=mock_response
                        )
                    )
                    mock_client_class.return_value = mock_client

                    service = WebhookService(max_retries=3)

                    result = await service.send_webhook(
                        "https://example.com/webhook", sample_webhook_result
                    )

                    assert result is False
                    assert mock_client.post.call_count == 1  # No retry for 4xx

    @pytest.mark.asyncio
    async def test_send_webhook_5xx_error_retry(self, mock_settings_webhook, sample_webhook_result):
        """
        Test: Send webhook with 5xx error (should retry).

        Error condition - 5xx errors should be retried.
        """
        with patch("app.services.infrastructure.webhook_service.settings", mock_settings_webhook):
            with patch(
                "app.services.infrastructure.webhook_service.validate_remote_url", return_value=True
            ):
                with patch("httpx.AsyncClient") as mock_client_class:
                    mock_response = Mock()
                    mock_response.status_code = 500

                    mock_client = AsyncMock()
                    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                    mock_client.__aexit__ = AsyncMock(return_value=None)
                    mock_client.post = AsyncMock(
                        side_effect=httpx.HTTPStatusError(
                            "Server error", request=Mock(), response=mock_response
                        )
                    )
                    mock_client_class.return_value = mock_client

                    service = WebhookService(max_retries=2)

                    with patch("asyncio.sleep", new_callable=AsyncMock):
                        result = await service.send_webhook(
                            "https://example.com/webhook", sample_webhook_result
                        )

                    assert result is False
                    assert mock_client.post.call_count == 2  # Should retry 5xx

    @pytest.mark.asyncio
    async def test_send_webhook_exponential_backoff(
        self, mock_settings_webhook, sample_webhook_result
    ):
        """
        Test: Send webhook with exponential backoff.

        Edge case - verify backoff delays increase exponentially.
        """
        with patch("app.services.infrastructure.webhook_service.settings", mock_settings_webhook):
            with patch(
                "app.services.infrastructure.webhook_service.validate_remote_url", return_value=True
            ):
                with patch("httpx.AsyncClient") as mock_client_class:
                    mock_client = AsyncMock()
                    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                    mock_client.__aexit__ = AsyncMock(return_value=None)
                    mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
                    mock_client_class.return_value = mock_client

                    service = WebhookService(max_retries=3, timeout_seconds=10)
                    service.retry_backoff_base = 1.0

                    sleep_calls = []

                    async def mock_sleep(delay):
                        sleep_calls.append(delay)

                    with patch("asyncio.sleep", side_effect=mock_sleep):
                        await service.send_webhook(
                            "https://example.com/webhook", sample_webhook_result
                        )

                    # Verify exponential backoff: 1.0, 2.0 (base * 2^attempt)
                    assert len(sleep_calls) == 2  # 2 retries (attempts 0 and 1, before attempt 2)
                    assert sleep_calls[0] == 1.0  # First retry: 1.0 * 2^0
                    assert sleep_calls[1] == 2.0  # Second retry: 1.0 * 2^1

    @pytest.mark.asyncio
    async def test_send_webhook_large_payload(
        self, mock_settings_webhook, sample_webhook_result_large
    ):
        """
        Test: Send webhook with large payload.

        Boundary case - large result payload.
        """
        with patch("app.services.infrastructure.webhook_service.settings", mock_settings_webhook):
            with patch(
                "app.services.infrastructure.webhook_service.validate_remote_url", return_value=True
            ):
                with patch("httpx.AsyncClient") as mock_client_class:
                    mock_response = Mock()
                    mock_response.status_code = 200
                    mock_response.raise_for_status = Mock()

                    mock_client = AsyncMock()
                    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                    mock_client.__aexit__ = AsyncMock(return_value=None)
                    mock_client.post = AsyncMock(return_value=mock_response)
                    mock_client_class.return_value = mock_client

                    service = WebhookService()
                    result = await service.send_webhook(
                        "https://example.com/webhook", sample_webhook_result_large
                    )

                    assert result is True
                    # Verify large payload was sent
                    call_args = mock_client.post.call_args
                    assert call_args[1]["json"] == sample_webhook_result_large

    @pytest.mark.asyncio
    async def test_send_webhook_with_job_id(self, mock_settings_webhook, sample_webhook_result):
        """
        Test: Send webhook with job_id for logging.

        Edge case - verify job_id is included in logging.
        """
        with patch("app.services.infrastructure.webhook_service.settings", mock_settings_webhook):
            with patch(
                "app.services.infrastructure.webhook_service.validate_remote_url", return_value=True
            ):
                with patch("app.services.infrastructure.webhook_service.logger") as mock_logger:
                    with patch("httpx.AsyncClient") as mock_client_class:
                        mock_response = Mock()
                        mock_response.status_code = 200
                        mock_response.raise_for_status = Mock()

                        mock_client = AsyncMock()
                        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                        mock_client.__aexit__ = AsyncMock(return_value=None)
                        mock_client.post = AsyncMock(return_value=mock_response)
                        mock_client_class.return_value = mock_client

                        service = WebhookService()
                        result = await service.send_webhook(
                            "https://example.com/webhook", sample_webhook_result, job_id="job-123"
                        )

                        assert result is True
                        # Verify job_id was logged
                        log_calls = [str(call) for call in mock_logger.info.call_args_list]
                        assert any("job-123" in call for call in log_calls)

    @pytest.mark.asyncio
    async def test_send_webhook_request_error(self, mock_settings_webhook, sample_webhook_result):
        """
        Test: Send webhook with RequestError.

        Error condition - generic request error should retry.
        """
        with patch("app.services.infrastructure.webhook_service.settings", mock_settings_webhook):
            with patch(
                "app.services.infrastructure.webhook_service.validate_remote_url", return_value=True
            ):
                with patch("httpx.AsyncClient") as mock_client_class:
                    mock_client = AsyncMock()
                    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                    mock_client.__aexit__ = AsyncMock(return_value=None)
                    mock_client.post = AsyncMock(side_effect=httpx.RequestError("Request error"))
                    mock_client_class.return_value = mock_client

                    service = WebhookService(max_retries=2)

                    with patch("asyncio.sleep", new_callable=AsyncMock):
                        result = await service.send_webhook(
                            "https://example.com/webhook", sample_webhook_result
                        )

                    assert result is False
                    assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_send_webhook_unexpected_exception(
        self, mock_settings_webhook, sample_webhook_result
    ):
        """
        Test: Send webhook with unexpected exception.

        Error condition - unexpected exceptions should be caught and logged.
        """
        with patch("app.services.infrastructure.webhook_service.settings", mock_settings_webhook):
            with patch(
                "app.services.infrastructure.webhook_service.validate_remote_url", return_value=True
            ):
                with patch("httpx.AsyncClient") as mock_client_class:
                    mock_client = AsyncMock()
                    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                    mock_client.__aexit__ = AsyncMock(return_value=None)
                    mock_client.post = AsyncMock(side_effect=ValueError("Unexpected error"))
                    mock_client_class.return_value = mock_client

                    service = WebhookService(max_retries=2)

                    with patch("asyncio.sleep", new_callable=AsyncMock):
                        with patch(
                            "app.services.infrastructure.webhook_service.logger"
                        ) as mock_logger:
                            result = await service.send_webhook(
                                "https://example.com/webhook", sample_webhook_result
                            )

                    assert result is False
                    # Verify error was logged
                    mock_logger.error.assert_called()


class TestWebhookServiceRetryWebhook:
    """Test retry_webhook functionality."""

    @pytest.mark.asyncio
    async def test_retry_webhook_with_custom_retries(
        self, mock_settings_webhook, sample_webhook_result
    ):
        """
        Test: Retry webhook with custom max_retries.

        Happy path - override max_retries for specific call.
        """
        with patch("app.services.infrastructure.webhook_service.settings", mock_settings_webhook):
            with patch(
                "app.services.infrastructure.webhook_service.validate_remote_url", return_value=True
            ):
                with patch("httpx.AsyncClient") as mock_client_class:
                    mock_response = Mock()
                    mock_response.status_code = 200
                    mock_response.raise_for_status = Mock()

                    mock_client = AsyncMock()
                    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                    mock_client.__aexit__ = AsyncMock(return_value=None)
                    mock_client.post = AsyncMock(return_value=mock_response)
                    mock_client_class.return_value = mock_client

                    service = WebhookService(max_retries=3)

                    result = await service.retry_webhook(
                        "https://example.com/webhook", sample_webhook_result, max_retries=5
                    )

                    assert result is True
                    # Verify original max_retries was restored
                    assert service.max_retries == 3

    @pytest.mark.asyncio
    async def test_retry_webhook_restores_original_retries(
        self, mock_settings_webhook, sample_webhook_result
    ):
        """
        Test: Retry webhook restores original max_retries.

        Edge case - verify max_retries is restored even on exception.
        """
        with patch("app.services.infrastructure.webhook_service.settings", mock_settings_webhook):
            with patch(
                "app.services.infrastructure.webhook_service.validate_remote_url",
                return_value=False,
            ):
                service = WebhookService(max_retries=3)

                await service.retry_webhook(
                    "https://example.com/webhook", sample_webhook_result, max_retries=5
                )

                # Verify original max_retries was restored
                assert service.max_retries == 3

    @pytest.mark.asyncio
    async def test_retry_webhook_with_none_retries(
        self, mock_settings_webhook, sample_webhook_result
    ):
        """
        Test: Retry webhook with None max_retries (uses default).

        Edge case - None should use instance default.
        """
        with patch("app.services.infrastructure.webhook_service.settings", mock_settings_webhook):
            with patch(
                "app.services.infrastructure.webhook_service.validate_remote_url", return_value=True
            ):
                with patch("httpx.AsyncClient") as mock_client_class:
                    mock_response = Mock()
                    mock_response.status_code = 200
                    mock_response.raise_for_status = Mock()

                    mock_client = AsyncMock()
                    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                    mock_client.__aexit__ = AsyncMock(return_value=None)
                    mock_client.post = AsyncMock(return_value=mock_response)
                    mock_client_class.return_value = mock_client

                    service = WebhookService(max_retries=3)

                    result = await service.retry_webhook(
                        "https://example.com/webhook", sample_webhook_result, max_retries=None
                    )

                    assert result is True
                    assert service.max_retries == 3  # Unchanged
