"""
Comprehensive unit tests for Metrics endpoint.

This module tests the /metrics endpoint covering:
- Happy path scenarios (metrics enabled/disabled)
- Edge cases (observability service initialization)
- Error conditions (metrics generation errors)
"""

from unittest.mock import Mock, patch

import pytest
from fastapi import status
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST

from app.api.v1.endpoints.metrics import get_metrics


class TestGetMetrics:
    """Tests for get_metrics endpoint."""

    @pytest.mark.asyncio
    async def test_get_metrics_enabled_success(self):
        """Test: Happy path - Get metrics when metrics are enabled returns Prometheus format."""
        # Arrange
        mock_metrics_data = b'# HELP api_requests_total Total number of API requests\n# TYPE api_requests_total counter\napi_requests_total{endpoint="/v1/transcriptions/youtube",method="POST",status="200"} 42.0\n'

        with patch("app.api.v1.endpoints.metrics.settings") as mock_settings:
            with patch("app.api.v1.endpoints.metrics.generate_latest") as mock_generate:
                with patch(
                    "app.api.v1.endpoints.metrics.get_observability_service"
                ) as mock_get_obs:
                    mock_settings.metrics_enabled = True
                    mock_settings.observability_enabled = True
                    mock_generate.return_value = mock_metrics_data
                    mock_get_obs.return_value = Mock()

                    # Act
                    result = await get_metrics()

        # Assert
        assert isinstance(result, Response)
        assert result.status_code == status.HTTP_200_OK
        assert result.media_type == CONTENT_TYPE_LATEST
        assert result.body == mock_metrics_data
        mock_generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_metrics_disabled(self):
        """Test: Happy path - Get metrics when metrics are disabled returns disabled message."""
        # Arrange
        with patch("app.api.v1.endpoints.metrics.settings") as mock_settings:
            mock_settings.metrics_enabled = False

            # Act
            result = await get_metrics()

        # Assert
        assert isinstance(result, Response)
        assert result.status_code == status.HTTP_200_OK
        assert result.media_type == CONTENT_TYPE_LATEST
        assert b"Metrics are disabled" in result.body

    @pytest.mark.asyncio
    async def test_get_metrics_observability_enabled(self):
        """Test: Happy path - Observability service is initialized when enabled."""
        # Arrange
        mock_metrics_data = b"# Metrics data\n"
        mock_obs_service = Mock()

        with patch("app.api.v1.endpoints.metrics.settings") as mock_settings:
            with patch("app.api.v1.endpoints.metrics.generate_latest") as mock_generate:
                with patch(
                    "app.api.v1.endpoints.metrics.get_observability_service"
                ) as mock_get_obs:
                    mock_settings.metrics_enabled = True
                    mock_settings.observability_enabled = True
                    mock_generate.return_value = mock_metrics_data
                    mock_get_obs.return_value = mock_obs_service

                    # Act
                    result = await get_metrics()

        # Assert
        assert isinstance(result, Response)
        assert result.status_code == status.HTTP_200_OK
        mock_get_obs.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_metrics_observability_disabled(self):
        """Test: Edge case - Metrics work even when observability is disabled."""
        # Arrange
        mock_metrics_data = b"# Metrics data\n"

        with patch("app.api.v1.endpoints.metrics.settings") as mock_settings:
            with patch("app.api.v1.endpoints.metrics.generate_latest") as mock_generate:
                mock_settings.metrics_enabled = True
                mock_settings.observability_enabled = False
                mock_generate.return_value = mock_metrics_data

                # Act
                result = await get_metrics()

        # Assert
        assert isinstance(result, Response)
        assert result.status_code == status.HTTP_200_OK
        mock_generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_metrics_generation_error(self):
        """Test: Error condition - Error during metrics generation returns error response."""
        # Arrange
        error_message = "Failed to generate metrics"

        with patch("app.api.v1.endpoints.metrics.settings") as mock_settings:
            with patch("app.api.v1.endpoints.metrics.generate_latest") as mock_generate:
                with patch(
                    "app.api.v1.endpoints.metrics.get_observability_service"
                ) as mock_get_obs:
                    mock_settings.metrics_enabled = True
                    mock_settings.observability_enabled = True
                    mock_generate.side_effect = Exception(error_message)
                    mock_get_obs.return_value = Mock()

                    # Act
                    result = await get_metrics()

        # Assert
        assert isinstance(result, Response)
        assert result.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert result.media_type == CONTENT_TYPE_LATEST
        assert error_message.encode() in result.body

    @pytest.mark.asyncio
    async def test_get_metrics_observability_service_error(self):
        """Test: Error condition - Error initializing observability service is handled."""
        # Arrange
        mock_metrics_data = b"# Metrics data\n"

        with patch("app.api.v1.endpoints.metrics.settings") as mock_settings:
            with patch("app.api.v1.endpoints.metrics.generate_latest") as mock_generate:
                with patch(
                    "app.api.v1.endpoints.metrics.get_observability_service"
                ) as mock_get_obs:
                    mock_settings.metrics_enabled = True
                    mock_settings.observability_enabled = True
                    mock_generate.return_value = mock_metrics_data
                    mock_get_obs.side_effect = Exception("Observability service error")

                    # Act
                    result = await get_metrics()

        # Assert
        # Should still return metrics even if observability service fails
        assert isinstance(result, Response)
        # The exact behavior depends on implementation, but should not crash

    @pytest.mark.asyncio
    async def test_get_metrics_content_type(self):
        """Test: Response has correct Content-Type header for Prometheus."""
        # Arrange
        mock_metrics_data = b"# Metrics data\n"

        with patch("app.api.v1.endpoints.metrics.settings") as mock_settings:
            with patch("app.api.v1.endpoints.metrics.generate_latest") as mock_generate:
                with patch(
                    "app.api.v1.endpoints.metrics.get_observability_service"
                ) as mock_get_obs:
                    mock_settings.metrics_enabled = True
                    mock_settings.observability_enabled = True
                    mock_generate.return_value = mock_metrics_data
                    mock_get_obs.return_value = Mock()

                    # Act
                    result = await get_metrics()

        # Assert
        assert result.media_type == CONTENT_TYPE_LATEST

    @pytest.mark.asyncio
    async def test_get_metrics_empty_metrics(self):
        """Test: Edge case - Empty metrics data is handled."""
        # Arrange
        mock_metrics_data = b""

        with patch("app.api.v1.endpoints.metrics.settings") as mock_settings:
            with patch("app.api.v1.endpoints.metrics.generate_latest") as mock_generate:
                with patch(
                    "app.api.v1.endpoints.metrics.get_observability_service"
                ) as mock_get_obs:
                    mock_settings.metrics_enabled = True
                    mock_settings.observability_enabled = True
                    mock_generate.return_value = mock_metrics_data
                    mock_get_obs.return_value = Mock()

                    # Act
                    result = await get_metrics()

        # Assert
        assert isinstance(result, Response)
        assert result.status_code == status.HTTP_200_OK
        assert result.body == b""

    @pytest.mark.asyncio
    async def test_get_metrics_large_metrics_data(self):
        """Test: Edge case - Large metrics data is handled."""
        # Arrange
        mock_metrics_data = b"# " + b"x" * (10 * 1024 * 1024)  # 10MB of metrics

        with patch("app.api.v1.endpoints.metrics.settings") as mock_settings:
            with patch("app.api.v1.endpoints.metrics.generate_latest") as mock_generate:
                with patch(
                    "app.api.v1.endpoints.metrics.get_observability_service"
                ) as mock_get_obs:
                    mock_settings.metrics_enabled = True
                    mock_settings.observability_enabled = True
                    mock_generate.return_value = mock_metrics_data
                    mock_get_obs.return_value = Mock()

                    # Act
                    result = await get_metrics()

        # Assert
        assert isinstance(result, Response)
        assert result.status_code == status.HTTP_200_OK
        assert len(result.body) == len(mock_metrics_data)
