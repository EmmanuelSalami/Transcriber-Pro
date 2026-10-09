"""Observability service for structured logging, metrics, and tracing."""

import logging
import time
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Dict, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# Lazy imports for optional dependencies
try:
    import structlog

    STRUCTLOG_AVAILABLE = True
except ImportError:
    STRUCTLOG_AVAILABLE = False
    structlog = None  # type: ignore

if TYPE_CHECKING:
    from prometheus_client import Counter, Gauge, Histogram

    PROMETHEUS_AVAILABLE = True
else:
    try:
        from prometheus_client import Counter, Gauge, Histogram

        PROMETHEUS_AVAILABLE = True
    except ImportError:
        PROMETHEUS_AVAILABLE = False
        Counter = None  # type: ignore
        Histogram = None  # type: ignore
        Gauge = None  # type: ignore


class ObservabilityService:
    """
    Observability service for structured logging, metrics, and tracing.

    Provides unified interface for logging, metrics collection, and distributed
    tracing. Supports JSON structured logging, Prometheus metrics, and OpenTelemetry tracing.

    Attributes:
        _logger: Structured logger instance
        _metrics_enabled (bool): Whether metrics collection is enabled
        _tracing_enabled (bool): Whether distributed tracing is enabled
        _request_counter: Prometheus counter for API requests
        _request_duration: Prometheus histogram for request duration
        _job_counter: Prometheus counter for job operations
        _queue_depth: Prometheus gauge for queue depth

    Example:
        >>> obs = ObservabilityService()
        >>> obs.log_structured("INFO", "job_started", {"job_id": "job-123"})
        >>> obs.track_metric("job_duration", 120.5, {"status": "completed"})
        >>> with obs.start_trace("transcribe_audio"):
        ...     # Do work
        ...     pass
    """

    def __init__(self) -> None:
        """
        Initialize the observability service.

        Sets up structured logging, Prometheus metrics, and optional tracing
        based on configuration. Automatically detects available dependencies
        (structlog, prometheus_client) and falls back gracefully if not available.

        Returns:
            None: Initializes the service instance

        Note:
            - If structlog is not available, falls back to standard logging
            - If prometheus_client is not available, metrics are disabled
            - Tracing (OpenTelemetry) is not yet implemented
        """
        self._metrics_enabled = settings.observability_enabled and settings.metrics_enabled
        self._tracing_enabled = settings.observability_enabled and settings.tracing_enabled

        self._request_counter: Optional["Counter"] = None
        self._request_duration: Optional["Histogram"] = None
        self._job_counter: Optional["Counter"] = None
        self._job_duration: Optional["Histogram"] = None
        self._queue_depth: Optional["Gauge"] = None
        self._worker_count: Optional["Gauge"] = None

        if settings.observability_enabled and settings.log_format == "json" and STRUCTLOG_AVAILABLE:
            structlog.configure(
                processors=[
                    structlog.processors.TimeStamper(fmt="iso"),
                    structlog.processors.add_log_level,
                    structlog.processors.JSONRenderer(),
                ],
                wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
                context_class=dict,
                logger_factory=structlog.PrintLoggerFactory(),
                cache_logger_on_first_use=True,
            )
            self._logger = structlog.get_logger()
        else:
            self._logger = logger

        if self._metrics_enabled and PROMETHEUS_AVAILABLE:
            self._request_counter = Counter(
                "api_requests_total",
                "Total number of API requests",
                ["method", "endpoint", "status"],
            )
            self._request_duration = Histogram(
                "api_request_duration_seconds",
                "API request duration in seconds",
                ["method", "endpoint"],
            )
            self._job_counter = Counter(
                "jobs_total",
                "Total number of jobs",
                ["status", "source"],
            )
            self._job_duration = Histogram(
                "job_duration_seconds",
                "Job processing duration in seconds",
                ["source"],
            )
            self._queue_depth = Gauge(
                "queue_depth",
                "Current depth of the job queue",
            )
            self._worker_count = Gauge(
                "workers_total",
                "Total number of workers",
                ["status"],
            )
            logger.info("ObservabilityService initialized with Prometheus metrics")
        if self._metrics_enabled and not PROMETHEUS_AVAILABLE:
            logger.warning(
                "Prometheus metrics enabled but prometheus_client not installed. "
                "Install with: pip install prometheus-client"
            )

        if self._tracing_enabled:
            logger.info("Tracing enabled but OpenTelemetry not yet implemented")
            self._tracer = None
        else:
            self._tracer = None

        logger.info(
            f"ObservabilityService initialized "
            f"(metrics: {self._metrics_enabled}, tracing: {self._tracing_enabled})"
        )

    def log_structured(
        self, level: str, event: str, context: Dict[str, Any], **kwargs: Any
    ) -> None:
        """
        Log a structured event with context.

        Logs an event with structured context data. Uses JSON format if
        structured logging is enabled (structlog), otherwise uses standard logging.
        Merges context dictionary and kwargs into a single context.

        Args:
            level (str): Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            event (str): Event name/identifier
            context (Dict[str, Any]): Context data dictionary
            **kwargs: Additional context fields (merged with context)

        Returns:
            None: Logs the event in-place

        Example:
            >>> obs = ObservabilityService()
            >>> obs.log_structured("INFO", "job_started", {"job_id": "job-123", "source": "youtube"})
        """
        full_context = {**context, **kwargs}
        full_context["event"] = event

        if isinstance(self._logger, structlog.BoundLogger):
            log_method = getattr(self._logger, level.lower(), self._logger.info)
            log_method(event, **full_context)
        else:
            log_method = getattr(logger, level.lower(), logger.info)
            context_str = ", ".join(f"{k}={v}" for k, v in full_context.items())
            log_method(f"{event}: {context_str}")

    def track_metric(
        self, metric_name: str, value: float, tags: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Track a custom metric.

        Records a metric value with optional tags. Currently logs the metric
        as debug information. Full Prometheus support for custom metrics would
        require dynamic metric creation.

        Args:
            metric_name (str): Name of the metric
            value (float): Metric value to record
            tags (Optional[Dict[str, str]]): Optional tags/labels for the metric

        Returns:
            None: Logs the metric if metrics are enabled

        Note:
            This is a placeholder for future custom metric support. Currently
            only predefined metrics (request_counter, job_counter, etc.) are
            fully supported.

        Example:
            >>> obs = ObservabilityService()
            >>> obs.track_metric("custom_metric", 42.0, {"tag1": "value1"})
        """
        if not self._metrics_enabled:
            return

        logger.debug(f"Metric: {metric_name}={value}, tags={tags}")

    def update_queue_depth(self, depth: int) -> None:
        """
        Update queue depth metric.

        Updates the Prometheus gauge for queue depth. This metric tracks
        the current number of jobs waiting in the queue.

        Args:
            depth (int): Current queue depth (number of pending jobs)

        Returns:
            None: Updates the metric in-place

        Example:
            >>> obs = ObservabilityService()
            >>> obs.update_queue_depth(10)
        """
        if self._queue_depth is not None:
            self._queue_depth.set(depth)

    def update_worker_count(self, status: str, count: int) -> None:
        """
        Update worker count metric.

        Updates the Prometheus gauge for worker count by status. This metric
        tracks the number of workers in each state (idle, busy, warming_up, unhealthy).

        Args:
            status (str): Worker status (idle, busy, warming_up, unhealthy)
            count (int): Number of workers with this status

        Returns:
            None: Updates the metric in-place

        Example:
            >>> obs = ObservabilityService()
            >>> obs.update_worker_count("idle", 3)
        """
        if self._worker_count is not None:
            self._worker_count.labels(status=status).set(count)

    def track_request(
        self, method: str, endpoint: str, status_code: int, duration_seconds: float
    ) -> None:
        """
        Track an API request.

        Records request metrics including count and duration. Updates both
        the request counter (with method, endpoint, status labels) and the
        request duration histogram (with method, endpoint labels).

        Args:
            method (str): HTTP method (GET, POST, PUT, DELETE, etc.)
            endpoint (str): API endpoint path (e.g., "/v1/transcriptions/youtube")
            status_code (int): HTTP status code (200, 400, 500, etc.)
            duration_seconds (float): Request processing duration in seconds

        Returns:
            None: Updates metrics in-place

        Example:
            >>> obs = ObservabilityService()
            >>> obs.track_request("POST", "/v1/transcriptions/youtube", 200, 1.5)
        """
        if self._request_counter is not None:
            self._request_counter.labels(
                method=method, endpoint=endpoint, status=str(status_code)
            ).inc()

        if self._request_duration is not None:
            self._request_duration.labels(method=method, endpoint=endpoint).observe(
                duration_seconds
            )

    def track_job(self, status: str, source: str, duration_seconds: Optional[float] = None) -> None:
        """
        Track a job operation.

        Records job metrics including count and duration. Updates both the
        job counter (with status and source labels) and optionally the job
        duration histogram (with source label) if duration is provided.

        Args:
            status (str): Job status (queued, processing, completed, failed)
            source (str): Job source (youtube_captions, asr, media)
            duration_seconds (Optional[float]): Job duration in seconds.
                Only recorded if provided and job is completed. Default: None

        Returns:
            None: Updates metrics in-place

        Example:
            >>> obs = ObservabilityService()
            >>> obs.track_job("completed", "asr", duration_seconds=120.5)
        """
        if self._job_counter is not None:
            self._job_counter.labels(status=status, source=source).inc()

        if duration_seconds is not None and self._job_duration is not None:
            self._job_duration.labels(source=source).observe(duration_seconds)

    @contextmanager
    def start_trace(self, operation: str, **context: Any):
        """
        Start a distributed trace for an operation.

        Context manager that starts a trace and automatically ends it when
        the context exits. Logs trace start, end, and any errors that occur.
        Currently implements basic trace logging; full OpenTelemetry support
        is planned for the future.

        Args:
            operation (str): Operation name (e.g., "transcribe_audio", "download_media")
            **context: Additional context fields for the trace (e.g., job_id, source)

        Yields:
            None: Currently yields None as a placeholder for future TraceContext object

        Raises:
            Exception: Re-raises any exception that occurs during the traced operation
                after logging it

        Example:
            >>> obs = ObservabilityService()
            >>> with obs.start_trace("transcribe_audio", job_id="job-123"):
            ...     # Do work
            ...     result = transcribe(audio_file)
            ...     return result
        """
        start_time = time.time()
        trace_id = f"trace_{int(time.time() * 1000000)}"

        self.log_structured(
            "DEBUG", "trace_start", {"operation": operation, "trace_id": trace_id, **context}
        )

        try:
            yield None  # Placeholder for future TraceContext object
        except Exception as e:
            duration = time.time() - start_time
            self.log_structured(
                "ERROR",
                "trace_error",
                {
                    "operation": operation,
                    "trace_id": trace_id,
                    "error": str(e),
                    "duration_seconds": duration,
                    **context,
                },
            )
            raise
        else:
            duration = time.time() - start_time
            self.log_structured(
                "DEBUG",
                "trace_end",
                {
                    "operation": operation,
                    "trace_id": trace_id,
                    "duration_seconds": duration,
                    **context,
                },
            )

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current metrics snapshot.

        Returns a dictionary with current metric values for monitoring.
        Currently returns a placeholder with service configuration status.
        Future implementation will return actual Prometheus metrics in text format.

        Returns:
            Dict[str, Any]: Dictionary containing:
                - metrics_enabled (bool): Whether metrics collection is enabled
                - tracing_enabled (bool): Whether distributed tracing is enabled

        Note:
            This is a placeholder method. Full Prometheus metrics export should
            use the Prometheus client library's text format directly.

        Example:
            >>> obs = ObservabilityService()
            >>> metrics = obs.get_metrics()
            >>> print(metrics["metrics_enabled"])
            True
        """
        return {
            "metrics_enabled": self._metrics_enabled,
            "tracing_enabled": self._tracing_enabled,
        }
