"""
Comprehensive unit tests for ObservabilityService.

Tests cover:
- Happy path scenarios
- Edge cases
- Error conditions
- Boundary value analysis
- Initialization with different configurations
- Logging functionality
- Metrics tracking
- Tracing functionality
"""

import logging
import time
from unittest.mock import Mock, patch

import pytest

from app.services.infrastructure.observability_service import \
    ObservabilityService


@pytest.fixture(autouse=True)
def clear_prometheus_registry():
    """Clear Prometheus registry before and after each test to avoid duplicate metrics."""
    # Metrics created by ObservabilityService
    observability_metrics = [
        "api_requests_total",
        "api_request_duration_seconds",
        "jobs_total",
        "job_duration_seconds",
        "queue_depth",
        "workers_total",
    ]

    def _clear_metrics():
        try:
            from prometheus_client import REGISTRY

            # Get all metric names
            all_names = list(REGISTRY._names_to_collectors.keys())
            for name in all_names:
                # Remove our observability metrics
                if any(obs_name in name for obs_name in observability_metrics):
                    try:
                        collector = REGISTRY._names_to_collectors[name]
                        REGISTRY.unregister(collector)
                    except (KeyError, ValueError, AttributeError):
                        pass
        except (ImportError, AttributeError):
            pass

    # Clear before test
    _clear_metrics()
    yield
    # Clear after test
    _clear_metrics()


class TestObservabilityServiceInitialization:
    """Test ObservabilityService initialization with different configurations."""

    def test_init_with_observability_enabled(self, mock_settings_observability_enabled):
        """
        Test: Initialize service with observability enabled.

        Checks that service initializes correctly when observability is enabled.
        """
        with patch(
            "app.services.infrastructure.observability_service.settings",
            mock_settings_observability_enabled,
        ):
            with patch(
                "app.services.infrastructure.observability_service.PROMETHEUS_AVAILABLE", True
            ):
                with patch(
                    "app.services.infrastructure.observability_service.Counter"
                ) as mock_counter:
                    with patch(
                        "app.services.infrastructure.observability_service.Histogram"
                    ) as mock_histogram:
                        with patch(
                            "app.services.infrastructure.observability_service.Gauge"
                        ) as mock_gauge:
                            service = ObservabilityService()

                            assert service._metrics_enabled is True
                            assert service._tracing_enabled is False
                            # Verify metrics were created
                            assert mock_counter.call_count >= 2  # request_counter, job_counter
                            assert mock_histogram.call_count >= 2  # request_duration, job_duration
                            assert mock_gauge.call_count >= 2  # queue_depth, worker_count

    def test_init_with_observability_disabled(self, mock_settings_observability_disabled):
        """
        Test: Initialize service with observability disabled.

        Checks that service initializes correctly when observability is disabled.
        """
        with patch(
            "app.services.infrastructure.observability_service.settings",
            mock_settings_observability_disabled,
        ):
            service = ObservabilityService()

            assert service._metrics_enabled is False
            assert service._tracing_enabled is False
            assert service._request_counter is None
            assert service._request_duration is None
            assert service._job_counter is None

    def test_init_with_prometheus_unavailable(self, mock_settings_observability_enabled):
        """
        Test: Initialize service when Prometheus is not available.

        Checks graceful fallback when prometheus_client is not installed.
        """
        with patch(
            "app.services.infrastructure.observability_service.settings",
            mock_settings_observability_enabled,
        ):
            with patch(
                "app.services.infrastructure.observability_service.PROMETHEUS_AVAILABLE", False
            ):
                service = ObservabilityService()

                assert service._metrics_enabled is True  # Still enabled in settings
                assert service._request_counter is None  # But metrics are None
                assert service._request_duration is None

    def test_init_with_structlog_available(self, mock_settings_observability_enabled):
        """
        Test: Initialize service with structlog available.

        Checks that structured logging is configured when structlog is available.
        """
        with patch(
            "app.services.infrastructure.observability_service.settings",
            mock_settings_observability_enabled,
        ):
            with patch(
                "app.services.infrastructure.observability_service.STRUCTLOG_AVAILABLE", True
            ):
                with patch(
                    "app.services.infrastructure.observability_service.structlog"
                ) as mock_structlog:
                    mock_logger = Mock()
                    mock_structlog.get_logger.return_value = mock_logger

                    service = ObservabilityService()

                    # Verify structlog was configured
                    mock_structlog.configure.assert_called_once()
                    assert service._logger == mock_logger

    def test_init_with_structlog_unavailable(self, mock_settings_observability_enabled):
        """
        Test: Initialize service when structlog is not available.

        Checks fallback to standard logging when structlog is not installed.
        """
        with patch(
            "app.services.infrastructure.observability_service.settings",
            mock_settings_observability_enabled,
        ):
            with patch(
                "app.services.infrastructure.observability_service.STRUCTLOG_AVAILABLE", False
            ):
                service = ObservabilityService()

                # Should use standard logger
                assert isinstance(service._logger, logging.Logger)

    def test_init_with_tracing_enabled(self, mock_settings_observability_enabled):
        """
        Test: Initialize service with tracing enabled.

        Checks that tracing is initialized when enabled (currently placeholder).
        """
        mock_settings_observability_enabled.tracing_enabled = True

        with patch(
            "app.services.infrastructure.observability_service.settings",
            mock_settings_observability_enabled,
        ):
            service = ObservabilityService()

            assert service._tracing_enabled is True
            assert service._tracer is None  # Not yet implemented


class TestObservabilityServiceLogging:
    """Test logging functionality."""

    def test_log_structured_with_structlog(self, mock_settings_observability_enabled):
        """
        Test: Log structured event with structlog logger.

        Happy path - logs event with context using structlog.
        """
        with patch(
            "app.services.infrastructure.observability_service.settings",
            mock_settings_observability_enabled,
        ):
            with patch(
                "app.services.infrastructure.observability_service.STRUCTLOG_AVAILABLE", True
            ):
                # Create a proper BoundLogger class that can be used with isinstance
                class MockBoundLogger:
                    def info(self, *args, **kwargs):
                        pass

                # Create an actual instance of MockBoundLogger
                mock_logger = MockBoundLogger()
                mock_logger.info = Mock()

                with patch(
                    "app.services.infrastructure.observability_service.structlog"
                ) as mock_structlog_module:
                    mock_structlog_module.BoundLogger = MockBoundLogger
                    mock_structlog_module.get_logger.return_value = mock_logger
                    mock_structlog_module.configure = Mock()
                    mock_structlog_module.make_filtering_bound_logger = Mock(
                        return_value=MockBoundLogger
                    )
                    mock_structlog_module.PrintLoggerFactory = Mock()
                    mock_structlog_module.processors = Mock()
                    mock_structlog_module.processors.TimeStamper = Mock()
                    mock_structlog_module.processors.add_log_level = Mock()
                    mock_structlog_module.processors.JSONRenderer = Mock()

                    service = ObservabilityService()
                    # Replace logger with our mock instance
                    service._logger = mock_logger
                    service.log_structured("INFO", "test_event", {"key": "value"}, extra="data")

                    # Verify structlog method was called
                    mock_logger.info.assert_called_once()
                    call_args = mock_logger.info.call_args
                    assert call_args[0][0] == "test_event"
                    assert "key" in call_args[1] or "key" in str(call_args)

    def test_log_structured_with_standard_logger(self, mock_settings_observability_enabled):
        """
        Test: Log structured event with standard logger.

        Happy path - logs event with context using standard logging.
        """
        with patch(
            "app.services.infrastructure.observability_service.settings",
            mock_settings_observability_enabled,
        ):
            with patch(
                "app.services.infrastructure.observability_service.STRUCTLOG_AVAILABLE", False
            ):
                with patch(
                    "app.services.infrastructure.observability_service.logger"
                ) as mock_logger:
                    service = ObservabilityService()
                    # Reset mock to ignore initialization calls
                    mock_logger.info.reset_mock()
                    service.log_structured("INFO", "test_event", {"key": "value"})

                    # Verify standard logger was called (only once for our call)
                    mock_logger.info.assert_called_once()
                    assert "test_event" in str(mock_logger.info.call_args)

    def test_log_structured_all_levels(self, mock_settings_observability_enabled):
        """
        Test: Log with all log levels.

        Edge case - test all supported log levels.
        """
        with patch(
            "app.services.infrastructure.observability_service.settings",
            mock_settings_observability_enabled,
        ):
            with patch(
                "app.services.infrastructure.observability_service.STRUCTLOG_AVAILABLE", False
            ):
                with patch(
                    "app.services.infrastructure.observability_service.logger"
                ) as mock_logger:
                    service = ObservabilityService()

                    levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
                    for level in levels:
                        service.log_structured(level, f"test_{level.lower()}", {})

                    # Verify all levels were called
                    assert mock_logger.debug.called
                    assert mock_logger.info.called
                    assert mock_logger.warning.called
                    assert mock_logger.error.called
                    assert mock_logger.critical.called

    def test_log_structured_invalid_level(self, mock_settings_observability_enabled):
        """
        Test: Log with invalid log level.

        Edge case - invalid level should fallback to INFO.
        """
        with patch(
            "app.services.infrastructure.observability_service.settings",
            mock_settings_observability_enabled,
        ):
            with patch(
                "app.services.infrastructure.observability_service.STRUCTLOG_AVAILABLE", False
            ):
                with patch(
                    "app.services.infrastructure.observability_service.logger"
                ) as mock_logger:
                    service = ObservabilityService()
                    service.log_structured("INVALID", "test_event", {})

                    # Should fallback to info
                    mock_logger.info.assert_called()

    def test_log_structured_empty_context(self, mock_settings_observability_enabled):
        """
        Test: Log with empty context.

        Edge case - empty context dictionary.
        """
        with patch(
            "app.services.infrastructure.observability_service.settings",
            mock_settings_observability_enabled,
        ):
            with patch(
                "app.services.infrastructure.observability_service.STRUCTLOG_AVAILABLE", False
            ):
                with patch(
                    "app.services.infrastructure.observability_service.logger"
                ) as mock_logger:
                    service = ObservabilityService()
                    # Reset mock to ignore initialization calls
                    mock_logger.info.reset_mock()
                    service.log_structured("INFO", "test_event", {})

                    # Should still log successfully
                    mock_logger.info.assert_called_once()

    def test_log_structured_large_context(self, mock_settings_observability_enabled):
        """
        Test: Log with large context dictionary.

        Boundary case - context with many keys.
        """
        with patch(
            "app.services.infrastructure.observability_service.settings",
            mock_settings_observability_enabled,
        ):
            with patch(
                "app.services.infrastructure.observability_service.STRUCTLOG_AVAILABLE", False
            ):
                with patch(
                    "app.services.infrastructure.observability_service.logger"
                ) as mock_logger:
                    service = ObservabilityService()
                    # Reset mock to ignore initialization calls
                    mock_logger.info.reset_mock()
                    large_context = {f"key_{i}": f"value_{i}" for i in range(100)}
                    service.log_structured("INFO", "test_event", large_context)

                    # Should handle large context
                    mock_logger.info.assert_called_once()


class TestObservabilityServiceMetrics:
    """Test metrics tracking functionality."""

    def test_track_metric_when_disabled(self, mock_settings_observability_disabled):
        """
        Test: Track metric when metrics are disabled.

        Edge case - should return early without error.
        """
        with patch(
            "app.services.infrastructure.observability_service.settings",
            mock_settings_observability_disabled,
        ):
            service = ObservabilityService()
            # Should not raise error
            service.track_metric("test_metric", 42.0, {"tag": "value"})

    def test_track_metric_when_enabled(self, mock_settings_observability_enabled):
        """
        Test: Track metric when metrics are enabled.

        Happy path - tracks custom metric (currently just logs).
        """
        with patch(
            "app.services.infrastructure.observability_service.settings",
            mock_settings_observability_enabled,
        ):
            with patch("app.services.infrastructure.observability_service.logger") as mock_logger:
                service = ObservabilityService()
                service._metrics_enabled = True
                service.track_metric("test_metric", 42.0, {"tag": "value"})

                # Should log the metric
                mock_logger.debug.assert_called()

    def test_update_queue_depth(self, mock_settings_observability_enabled):
        """
        Test: Update queue depth metric.

        Happy path - updates Prometheus gauge.
        """
        with patch(
            "app.services.infrastructure.observability_service.settings",
            mock_settings_observability_enabled,
        ):
            with patch(
                "app.services.infrastructure.observability_service.PROMETHEUS_AVAILABLE", True
            ):
                with patch(
                    "app.services.infrastructure.observability_service.Gauge"
                ) as mock_gauge_class:
                    mock_gauge = Mock()
                    mock_gauge.set = Mock()
                    mock_gauge_class.return_value = mock_gauge

                    service = ObservabilityService()
                    service.update_queue_depth(10)

                    # Verify gauge was set
                    mock_gauge.set.assert_called_once_with(10)

    def test_update_queue_depth_when_none(self, mock_settings_observability_disabled):
        """
        Test: Update queue depth when gauge is None.

        Edge case - should not raise error.
        """
        with patch(
            "app.services.infrastructure.observability_service.settings",
            mock_settings_observability_disabled,
        ):
            service = ObservabilityService()
            # Should not raise error
            service.update_queue_depth(10)

    def test_update_queue_depth_boundary_values(self, mock_settings_observability_enabled):
        """
        Test: Update queue depth with boundary values.

        Boundary analysis - test zero, negative, and large values.
        """
        with patch(
            "app.services.infrastructure.observability_service.settings",
            mock_settings_observability_enabled,
        ):
            with patch(
                "app.services.infrastructure.observability_service.PROMETHEUS_AVAILABLE", True
            ):
                with patch(
                    "app.services.infrastructure.observability_service.Gauge"
                ) as mock_gauge_class:
                    mock_gauge = Mock()
                    mock_gauge.set = Mock()
                    mock_gauge_class.return_value = mock_gauge

                    service = ObservabilityService()

                    # Test boundary values
                    service.update_queue_depth(0)
                    service.update_queue_depth(-1)  # Should still work
                    service.update_queue_depth(999999)

                    assert mock_gauge.set.call_count == 3

    def test_update_worker_count(self, mock_settings_observability_enabled):
        """
        Test: Update worker count metric.

        Happy path - updates Prometheus gauge with labels.
        """
        with patch(
            "app.services.infrastructure.observability_service.settings",
            mock_settings_observability_enabled,
        ):
            with patch(
                "app.services.infrastructure.observability_service.PROMETHEUS_AVAILABLE", True
            ):
                with patch(
                    "app.services.infrastructure.observability_service.Gauge"
                ) as mock_gauge_class:
                    mock_gauge = Mock()
                    mock_labeled = Mock()
                    mock_labeled.set = Mock()
                    mock_gauge.labels.return_value = mock_labeled
                    mock_gauge_class.return_value = mock_gauge

                    service = ObservabilityService()
                    service.update_worker_count("idle", 5)

                    # Verify labels and set were called
                    mock_gauge.labels.assert_called_once_with(status="idle")
                    mock_labeled.set.assert_called_once_with(5)

    def test_update_worker_count_all_statuses(self, mock_settings_observability_enabled):
        """
        Test: Update worker count for all statuses.

        Edge case - test all worker status values.
        """
        with patch(
            "app.services.infrastructure.observability_service.settings",
            mock_settings_observability_enabled,
        ):
            with patch(
                "app.services.infrastructure.observability_service.PROMETHEUS_AVAILABLE", True
            ):
                with patch(
                    "app.services.infrastructure.observability_service.Gauge"
                ) as mock_gauge_class:
                    mock_gauge = Mock()
                    mock_labeled = Mock()
                    mock_labeled.set = Mock()
                    mock_gauge.labels.return_value = mock_labeled
                    mock_gauge_class.return_value = mock_gauge

                    service = ObservabilityService()

                    statuses = ["idle", "busy", "warming_up", "unhealthy"]
                    for status in statuses:
                        service.update_worker_count(status, 1)

                    assert mock_gauge.labels.call_count == len(statuses)

    def test_track_request(self, mock_settings_observability_enabled):
        """
        Test: Track API request.

        Happy path - tracks request counter and duration.
        """
        with patch(
            "app.services.infrastructure.observability_service.settings",
            mock_settings_observability_enabled,
        ):
            with patch(
                "app.services.infrastructure.observability_service.PROMETHEUS_AVAILABLE", True
            ):
                with patch(
                    "app.services.infrastructure.observability_service.Counter"
                ) as mock_counter_class:
                    with patch(
                        "app.services.infrastructure.observability_service.Histogram"
                    ) as mock_histogram_class:
                        mock_counter = Mock()
                        mock_labeled_counter = Mock()
                        mock_labeled_counter.inc = Mock()
                        mock_counter.labels.return_value = mock_labeled_counter
                        mock_counter_class.return_value = mock_counter

                        mock_histogram = Mock()
                        mock_labeled_histogram = Mock()
                        mock_labeled_histogram.observe = Mock()
                        mock_histogram.labels.return_value = mock_labeled_histogram
                        mock_histogram_class.return_value = mock_histogram

                        service = ObservabilityService()
                        service.track_request("POST", "/v1/test", 200, 1.5)

                        # Verify counter was incremented
                        mock_labeled_counter.inc.assert_called_once()
                        # Verify duration was observed
                        mock_labeled_histogram.observe.assert_called_once_with(1.5)

    def test_track_request_all_status_codes(self, mock_settings_observability_enabled):
        """
        Test: Track request with various status codes.

        Edge case - test different HTTP status codes.
        """
        with patch(
            "app.services.infrastructure.observability_service.settings",
            mock_settings_observability_enabled,
        ):
            with patch(
                "app.services.infrastructure.observability_service.PROMETHEUS_AVAILABLE", True
            ):
                with patch(
                    "app.services.infrastructure.observability_service.Counter"
                ) as mock_counter_class:
                    with patch("app.services.infrastructure.observability_service.Histogram"):
                        mock_counter = Mock()
                        mock_labeled_counter = Mock()
                        mock_labeled_counter.inc = Mock()
                        mock_counter.labels.return_value = mock_labeled_counter
                        mock_counter_class.return_value = mock_counter

                        service = ObservabilityService()

                        status_codes = [200, 201, 400, 401, 404, 500, 503]
                        for status in status_codes:
                            service.track_request("GET", "/v1/test", status, 0.5)

                        assert mock_labeled_counter.inc.call_count == len(status_codes)

    def test_track_job(self, mock_settings_observability_enabled):
        """
        Test: Track job operation.

        Happy path - tracks job counter and duration.
        """
        with patch(
            "app.services.infrastructure.observability_service.settings",
            mock_settings_observability_enabled,
        ):
            with patch(
                "app.services.infrastructure.observability_service.PROMETHEUS_AVAILABLE", True
            ):
                with patch(
                    "app.services.infrastructure.observability_service.Counter"
                ) as mock_counter_class:
                    with patch(
                        "app.services.infrastructure.observability_service.Histogram"
                    ) as mock_histogram_class:
                        mock_counter = Mock()
                        mock_labeled_counter = Mock()
                        mock_labeled_counter.inc = Mock()
                        mock_counter.labels.return_value = mock_labeled_counter
                        mock_counter_class.return_value = mock_counter

                        mock_histogram = Mock()
                        mock_labeled_histogram = Mock()
                        mock_labeled_histogram.observe = Mock()
                        mock_histogram.labels.return_value = mock_labeled_histogram
                        mock_histogram_class.return_value = mock_histogram

                        service = ObservabilityService()
                        service.track_job("completed", "asr", duration_seconds=120.5)

                        # Verify counter was incremented
                        mock_labeled_counter.inc.assert_called_once()
                        # Verify duration was observed
                        mock_labeled_histogram.observe.assert_called_once_with(120.5)

    def test_track_job_without_duration(self, mock_settings_observability_enabled):
        """
        Test: Track job without duration.

        Edge case - job tracking without duration (e.g., queued status).
        """
        with patch(
            "app.services.infrastructure.observability_service.settings",
            mock_settings_observability_enabled,
        ):
            with patch(
                "app.services.infrastructure.observability_service.PROMETHEUS_AVAILABLE", True
            ):
                with patch(
                    "app.services.infrastructure.observability_service.Counter"
                ) as mock_counter_class:
                    with patch(
                        "app.services.infrastructure.observability_service.Histogram"
                    ) as mock_histogram_class:
                        mock_counter = Mock()
                        mock_labeled_counter = Mock()
                        mock_labeled_counter.inc = Mock()
                        mock_counter.labels.return_value = mock_labeled_counter
                        mock_counter_class.return_value = mock_counter

                        mock_histogram = Mock()
                        mock_labeled_histogram = Mock()
                        mock_labeled_histogram.observe = Mock()
                        mock_histogram.labels.return_value = mock_labeled_histogram
                        mock_histogram_class.return_value = mock_histogram

                        service = ObservabilityService()
                        service.track_job("queued", "youtube_captions", duration_seconds=None)

                        # Counter should be incremented
                        mock_labeled_counter.inc.assert_called_once()
                        # Duration should NOT be observed
                        mock_labeled_histogram.observe.assert_not_called()

    def test_track_job_all_statuses(self, mock_settings_observability_enabled):
        """
        Test: Track job with all status values.

        Edge case - test all job status values.
        """
        with patch(
            "app.services.infrastructure.observability_service.settings",
            mock_settings_observability_enabled,
        ):
            with patch(
                "app.services.infrastructure.observability_service.PROMETHEUS_AVAILABLE", True
            ):
                with patch(
                    "app.services.infrastructure.observability_service.Counter"
                ) as mock_counter_class:
                    mock_counter = Mock()
                    mock_labeled_counter = Mock()
                    mock_labeled_counter.inc = Mock()
                    mock_counter.labels.return_value = mock_labeled_counter
                    mock_counter_class.return_value = mock_counter

                    service = ObservabilityService()

                    statuses = ["queued", "processing", "completed", "failed"]
                    for status in statuses:
                        service.track_job(status, "asr")

                    assert mock_labeled_counter.inc.call_count == len(statuses)


class TestObservabilityServiceTracing:
    """Test tracing functionality."""

    def test_start_trace_success(self, mock_settings_observability_enabled):
        """
        Test: Start trace context manager - success path.

        Happy path - trace starts and ends successfully.
        """
        with patch(
            "app.services.infrastructure.observability_service.settings",
            mock_settings_observability_enabled,
        ):
            with patch("app.services.infrastructure.observability_service.logger") as mock_logger:
                service = ObservabilityService()

                with service.start_trace("test_operation", job_id="job-123") as trace_context:
                    assert trace_context is None  # Placeholder
                    # Do some work
                    time.sleep(0.01)

                # Verify trace start and end were logged
                assert mock_logger.debug.call_count >= 2

    def test_start_trace_with_exception(self, mock_settings_observability_enabled):
        """
        Test: Start trace context manager - exception path.

        Error condition - trace should log error and re-raise exception.
        """
        with patch(
            "app.services.infrastructure.observability_service.settings",
            mock_settings_observability_enabled,
        ):
            with patch("app.services.infrastructure.observability_service.logger") as mock_logger:
                service = ObservabilityService()

                with pytest.raises(ValueError):
                    with service.start_trace("test_operation", job_id="job-123"):
                        raise ValueError("Test error")

                # Verify error was logged
                mock_logger.error.assert_called()

    def test_start_trace_with_context(self, mock_settings_observability_enabled):
        """
        Test: Start trace with additional context.

        Edge case - trace with extra context parameters.
        """
        with patch(
            "app.services.infrastructure.observability_service.settings",
            mock_settings_observability_enabled,
        ):
            with patch("app.services.infrastructure.observability_service.logger") as mock_logger:
                service = ObservabilityService()

                with service.start_trace(
                    "test_operation", job_id="job-123", user_id="user-456", source="api"
                ):
                    pass

                # Verify context was included in logs
                log_calls = [str(call) for call in mock_logger.debug.call_args_list]
                assert any("job-123" in str(call) for call in log_calls)
                assert any("user-456" in str(call) for call in log_calls)


class TestObservabilityServiceGetMetrics:
    """Test get_metrics functionality."""

    def test_get_metrics(self, mock_settings_observability_enabled):
        """
        Test: Get current metrics snapshot.

        Happy path - returns metrics dictionary.
        """
        with patch(
            "app.services.infrastructure.observability_service.settings",
            mock_settings_observability_enabled,
        ):
            service = ObservabilityService()
            metrics = service.get_metrics()

            assert isinstance(metrics, dict)
            assert "metrics_enabled" in metrics
            assert "tracing_enabled" in metrics
            assert metrics["metrics_enabled"] is True

    def test_get_metrics_when_disabled(self, mock_settings_observability_disabled):
        """
        Test: Get metrics when observability is disabled.

        Edge case - returns metrics with disabled flags.
        """
        with patch(
            "app.services.infrastructure.observability_service.settings",
            mock_settings_observability_disabled,
        ):
            service = ObservabilityService()
            metrics = service.get_metrics()

            assert metrics["metrics_enabled"] is False
            assert metrics["tracing_enabled"] is False
