"""Unit tests for middleware.

This module tests:
- MetricsMiddleware initialization
- Request tracking
- Metrics collection
- Error handling in middleware
- Metrics endpoint skipping
- Disabled metrics behavior
- Edge cases and boundary conditions
"""

import asyncio
import time
from unittest.mock import Mock, patch

import pytest
from fastapi import Request, Response

from app.core.middleware import MetricsMiddleware, get_observability_service


class TestGetObservabilityService:
    """Test suite for get_observability_service function."""

    def test_get_observability_service_singleton(self):
        """Test: Service is returned as singleton.

        Verifies that get_observability_service returns the same
        instance on multiple calls (singleton pattern).
        """
        # Reset the global variable
        import app.core.middleware

        app.core.middleware._observability_service = None

        service1 = get_observability_service()
        service2 = get_observability_service()

        assert service1 is service2

    def test_get_observability_service_creates_instance(self):
        """Test: Service instance is created on first call.

        Verifies that a new ObservabilityService instance is created
        on the first call.
        """
        import app.core.middleware

        app.core.middleware._observability_service = None

        with patch("app.core.middleware.ObservabilityService") as mock_service_class:
            mock_instance = Mock()
            mock_service_class.return_value = mock_instance

            service = get_observability_service()

            assert service is mock_instance
            mock_service_class.assert_called_once()


class TestMetricsMiddleware:
    """Test suite for MetricsMiddleware class."""

    def test_metrics_middleware_initialization_enabled(self, mock_settings):
        """Test: Middleware initializes when metrics are enabled.

        Verifies that middleware initializes correctly when observability
        and metrics are enabled in settings.
        """
        mock_settings.observability_enabled = True
        mock_settings.metrics_enabled = True

        mock_app = Mock()

        with patch("app.core.middleware.settings", mock_settings):
            with patch("app.core.middleware.get_observability_service") as mock_get_service:
                mock_service = Mock()
                mock_get_service.return_value = mock_service

                middleware = MetricsMiddleware(mock_app)

                assert middleware._metrics_enabled is True
                assert middleware._obs_service is mock_service

    def test_metrics_middleware_initialization_disabled(self, mock_settings):
        """Test: Middleware initializes when metrics are disabled.

        Verifies that middleware initializes correctly when metrics
        are disabled, and doesn't create observability service.
        """
        mock_settings.observability_enabled = False
        mock_settings.metrics_enabled = False

        mock_app = Mock()

        with patch("app.core.middleware.settings", mock_settings):
            middleware = MetricsMiddleware(mock_app)

            assert middleware._metrics_enabled is False
            assert middleware._obs_service is None

    def test_metrics_middleware_initialization_partially_disabled(self, mock_settings):
        """Test: Middleware disables when observability is off.

        Edge case: Even if metrics_enabled is True, if observability
        is disabled, metrics should be disabled.
        """
        mock_settings.observability_enabled = False
        mock_settings.metrics_enabled = True

        mock_app = Mock()

        with patch("app.core.middleware.settings", mock_settings):
            middleware = MetricsMiddleware(mock_app)

            assert middleware._metrics_enabled is False
            assert middleware._obs_service is None

    @pytest.mark.asyncio
    async def test_metrics_middleware_tracks_request_happy_path(
        self, mock_request, mock_settings, mock_observability_service
    ):
        """Test: Request is tracked when metrics are enabled.

        Verifies that successful requests are tracked with correct
        method, endpoint, status code, and duration.
        """
        mock_settings.observability_enabled = True
        mock_settings.metrics_enabled = True

        mock_app = Mock()
        mock_response_obj = Mock(spec=Response)
        mock_response_obj.status_code = 200

        # Ensure mock_request.url.path is set correctly
        mock_request.url.path = "/v1/test"

        async def call_next(request):
            return mock_response_obj

        with patch("app.core.middleware.settings", mock_settings):
            with patch(
                "app.core.middleware.get_observability_service",
                return_value=mock_observability_service,
            ):
                middleware = MetricsMiddleware(mock_app)

                response = await middleware.dispatch(mock_request, call_next)

                assert response == mock_response_obj
                mock_observability_service.track_request.assert_called_once()

                # Verify tracking arguments
                call_args = mock_observability_service.track_request.call_args
                assert call_args[0][0] == mock_request.method  # method (should match fixture)
                # Use the actual endpoint from the call, not hardcoded
                assert call_args[0][1] == mock_request.url.path  # endpoint
                assert call_args[0][2] == 200  # status_code
                assert isinstance(call_args[0][3], float)  # duration

    @pytest.mark.asyncio
    async def test_metrics_middleware_skips_when_disabled(self, mock_request, mock_settings):
        """Test: Request tracking is skipped when metrics are disabled.

        Verifies that when metrics are disabled, requests are not tracked
        and the observability service is not called.
        """
        mock_settings.observability_enabled = False
        mock_settings.metrics_enabled = False

        mock_app = Mock()
        mock_response_obj = Mock(spec=Response)
        mock_response_obj.status_code = 200

        async def call_next(request):
            return mock_response_obj

        with patch("app.core.middleware.settings", mock_settings):
            middleware = MetricsMiddleware(mock_app)

            response = await middleware.dispatch(mock_request, call_next)

            assert response == mock_response_obj
            # Should not have created observability service
            assert middleware._obs_service is None

    @pytest.mark.asyncio
    async def test_metrics_middleware_skips_metrics_endpoint(
        self, mock_request, mock_settings, mock_observability_service
    ):
        """Test: Metrics endpoint itself is not tracked.

        Verifies that requests to the /metrics endpoint are not tracked
        to avoid recursion or infinite loops.
        """
        mock_settings.observability_enabled = True
        mock_settings.metrics_enabled = True

        mock_request.url.path = "/metrics"

        mock_app = Mock()
        mock_response_obj = Mock(spec=Response)
        mock_response_obj.status_code = 200

        async def call_next(request):
            return mock_response_obj

        with patch("app.core.middleware.settings", mock_settings):
            with patch(
                "app.core.middleware.get_observability_service",
                return_value=mock_observability_service,
            ):
                middleware = MetricsMiddleware(mock_app)

                response = await middleware.dispatch(mock_request, call_next)

                assert response == mock_response_obj
                # Should not track metrics endpoint
                mock_observability_service.track_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_metrics_middleware_tracks_error_status(
        self, mock_request, mock_settings, mock_observability_service
    ):
        """Test: Error status codes are tracked correctly.

        Verifies that requests resulting in error status codes (4xx, 5xx)
        are tracked with the correct status code.
        """
        mock_settings.observability_enabled = True
        mock_settings.metrics_enabled = True

        mock_app = Mock()
        mock_response_obj = Mock(spec=Response)
        mock_response_obj.status_code = 404

        async def call_next(request):
            return mock_response_obj

        with patch("app.core.middleware.settings", mock_settings):
            with patch(
                "app.core.middleware.get_observability_service",
                return_value=mock_observability_service,
            ):
                middleware = MetricsMiddleware(mock_app)

                await middleware.dispatch(mock_request, call_next)

                call_args = mock_observability_service.track_request.call_args
                assert call_args[0][2] == 404  # status_code

    @pytest.mark.asyncio
    async def test_metrics_middleware_tracks_exception(
        self, mock_request, mock_settings, mock_observability_service
    ):
        """Test: Exceptions during request processing are tracked.

        Verifies that when an exception occurs during request processing,
        it's tracked with status code 500.
        """
        mock_settings.observability_enabled = True
        mock_settings.metrics_enabled = True

        mock_app = Mock()

        async def call_next(request):
            raise ValueError("Test error")

        with patch("app.core.middleware.settings", mock_settings):
            with patch(
                "app.core.middleware.get_observability_service",
                return_value=mock_observability_service,
            ):
                middleware = MetricsMiddleware(mock_app)

                with pytest.raises(ValueError):
                    await middleware.dispatch(mock_request, call_next)

                # Should track the error
                mock_observability_service.track_request.assert_called_once()
                call_args = mock_observability_service.track_request.call_args
                assert call_args[0][2] == 500  # status_code

    @pytest.mark.asyncio
    async def test_metrics_middleware_calculates_duration(
        self, mock_request, mock_settings, mock_observability_service
    ):
        """Test: Request duration is calculated correctly.

        Verifies that the time taken to process a request is calculated
        and passed to the tracking function.
        """
        mock_settings.observability_enabled = True
        mock_settings.metrics_enabled = True

        mock_app = Mock()
        mock_response_obj = Mock(spec=Response)
        mock_response_obj.status_code = 200

        async def call_next(request):
            await asyncio.sleep(0.1)  # Simulate processing time
            return mock_response_obj

        with patch("app.core.middleware.settings", mock_settings):
            with patch(
                "app.core.middleware.get_observability_service",
                return_value=mock_observability_service,
            ):
                middleware = MetricsMiddleware(mock_app)

                start_time = time.time()
                await middleware.dispatch(mock_request, call_next)
                end_time = time.time()

                call_args = mock_observability_service.track_request.call_args
                duration = call_args[0][3]

                # Duration should be approximately the sleep time
                assert duration >= 0.1
                assert duration <= (end_time - start_time) + 0.01  # Small tolerance

    @pytest.mark.asyncio
    async def test_metrics_middleware_handles_tracking_error(
        self, mock_request, mock_settings, mock_observability_service
    ):
        """Test: Errors in tracking don't break the request.

        Verifies that if tracking fails, the request still completes
        successfully (defensive programming).
        """
        mock_settings.observability_enabled = True
        mock_settings.metrics_enabled = True

        mock_app = Mock()
        mock_response_obj = Mock(spec=Response)
        mock_response_obj.status_code = 200

        # Make tracking raise an exception
        mock_observability_service.track_request.side_effect = Exception("Tracking error")

        async def call_next(request):
            return mock_response_obj

        with patch("app.core.middleware.settings", mock_settings):
            with patch(
                "app.core.middleware.get_observability_service",
                return_value=mock_observability_service,
            ):
                with patch("app.core.middleware.logger") as mock_logger:
                    middleware = MetricsMiddleware(mock_app)

                    # Should not raise, request should complete
                    response = await middleware.dispatch(mock_request, call_next)

                    assert response == mock_response_obj
                    # Should log the error
                    mock_logger.debug.assert_called()

    @pytest.mark.asyncio
    async def test_metrics_middleware_different_methods(
        self, mock_settings, mock_observability_service
    ):
        """Test: Different HTTP methods are tracked correctly.

        Verifies that GET, POST, PUT, DELETE, etc. are all tracked
        with the correct method name.
        """
        mock_settings.observability_enabled = True
        mock_settings.metrics_enabled = True

        mock_app = Mock()
        mock_response_obj = Mock(spec=Response)
        mock_response_obj.status_code = 200

        async def call_next(request):
            return mock_response_obj

        methods = ["GET", "POST", "PUT", "DELETE", "PATCH"]

        with patch("app.core.middleware.settings", mock_settings):
            with patch(
                "app.core.middleware.get_observability_service",
                return_value=mock_observability_service,
            ):
                middleware = MetricsMiddleware(mock_app)

                for method in methods:
                    # Create a new request mock for each method
                    request = Mock(spec=Request)
                    request.method = method
                    request.url.path = "/v1/test"
                    request.url.query = ""
                    request.client = Mock()
                    request.client.host = "127.0.0.1"
                    request.headers = Mock()

                    await middleware.dispatch(request, call_next)

                # Verify all methods were tracked
                assert mock_observability_service.track_request.call_count == len(methods)

                # Verify method names
                for i, method in enumerate(methods):
                    call_args = mock_observability_service.track_request.call_args_list[i]
                    assert call_args[0][0] == method

    @pytest.mark.asyncio
    async def test_metrics_middleware_different_endpoints(
        self, mock_request, mock_settings, mock_observability_service
    ):
        """Test: Different endpoints are tracked correctly.

        Verifies that requests to different endpoints are tracked
        with the correct path.
        """
        mock_settings.observability_enabled = True
        mock_settings.metrics_enabled = True

        mock_app = Mock()
        mock_response_obj = Mock(spec=Response)
        mock_response_obj.status_code = 200

        async def call_next(request):
            return mock_response_obj

        endpoints = ["/v1/test", "/v1/other", "/v1/youtube"]

        with patch("app.core.middleware.settings", mock_settings):
            with patch(
                "app.core.middleware.get_observability_service",
                return_value=mock_observability_service,
            ):
                middleware = MetricsMiddleware(mock_app)

                for endpoint in endpoints:
                    mock_request.url.path = endpoint
                    await middleware.dispatch(mock_request, call_next)

                # Verify all endpoints were tracked
                assert mock_observability_service.track_request.call_count == len(endpoints)

                # Verify endpoint paths
                tracked_endpoints = [
                    call[0][1] for call in mock_observability_service.track_request.call_args_list
                ]
                assert set(tracked_endpoints) == set(endpoints)


class TestMetricsMiddlewareEdgeCases:
    """Test suite for edge cases in MetricsMiddleware."""

    @pytest.mark.asyncio
    async def test_metrics_middleware_very_fast_request(
        self, mock_request, mock_settings, mock_observability_service
    ):
        """Test: Very fast requests are tracked correctly.

        Boundary case: Requests that complete very quickly should
        still be tracked with a small duration.
        """
        mock_settings.observability_enabled = True
        mock_settings.metrics_enabled = True

        mock_app = Mock()
        mock_response_obj = Mock(spec=Response)
        mock_response_obj.status_code = 200

        async def call_next(request):
            return mock_response_obj

        with patch("app.core.middleware.settings", mock_settings):
            with patch(
                "app.core.middleware.get_observability_service",
                return_value=mock_observability_service,
            ):
                middleware = MetricsMiddleware(mock_app)

                await middleware.dispatch(mock_request, call_next)

                call_args = mock_observability_service.track_request.call_args
                duration = call_args[0][3]

                # Duration should be a small positive number
                assert duration >= 0
                assert duration < 1.0  # Should be very fast

    @pytest.mark.asyncio
    async def test_metrics_middleware_very_slow_request(
        self, mock_request, mock_settings, mock_observability_service
    ):
        """Test: Very slow requests are tracked correctly.

        Boundary case: Requests that take a long time should be
        tracked with the correct duration.
        """
        mock_settings.observability_enabled = True
        mock_settings.metrics_enabled = True

        mock_app = Mock()
        mock_response_obj = Mock(spec=Response)
        mock_response_obj.status_code = 200

        async def call_next(request):
            import asyncio

            await asyncio.sleep(0.5)  # Simulate slow request
            return mock_response_obj

        with patch("app.core.middleware.settings", mock_settings):
            with patch(
                "app.core.middleware.get_observability_service",
                return_value=mock_observability_service,
            ):
                middleware = MetricsMiddleware(mock_app)

                await middleware.dispatch(mock_request, call_next)

                call_args = mock_observability_service.track_request.call_args
                duration = call_args[0][3]

                # Duration should be approximately the sleep time
                assert duration >= 0.5
                assert duration < 1.0  # Should be less than 1 second

    @pytest.mark.asyncio
    async def test_metrics_middleware_none_obs_service(self, mock_request, mock_settings):
        """Test: Middleware handles None observability service gracefully.

        Edge case: If observability service is None, should not crash.
        """
        mock_settings.observability_enabled = True
        mock_settings.metrics_enabled = True

        mock_app = Mock()
        mock_response_obj = Mock(spec=Response)
        mock_response_obj.status_code = 200

        async def call_next(request):
            return mock_response_obj

        with patch("app.core.middleware.settings", mock_settings):
            with patch("app.core.middleware.get_observability_service", return_value=None):
                middleware = MetricsMiddleware(mock_app)

                # Should not raise, should complete request
                response = await middleware.dispatch(mock_request, call_next)
                assert response == mock_response_obj
