"""
Comprehensive unit tests for CostControlService.

Tests cover:
- Happy path scenarios
- Edge cases
- Error conditions
- Boundary value analysis
- Redis integration
- In-memory fallback
- Budget enforcement
- Cost tracking
"""

from unittest.mock import Mock, patch

from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError

from app.models.schemas import CostMetrics
from app.services.infrastructure.cost_control_service import CostControlService


class TestCostControlServiceInitialization:
    """Test CostControlService initialization."""

    def test_init_with_cost_control_disabled(self, mock_settings_cost_control_disabled):
        """
        Test: Initialize service with cost control disabled.

        Happy path - service initializes but cost control is disabled.
        """
        with patch(
            "app.services.infrastructure.cost_control_service.settings",
            mock_settings_cost_control_disabled,
        ):
            service = CostControlService()

            assert service._use_redis is False
            assert service._redis_client is None

    def test_init_with_redis_enabled(self, mock_settings_cost_control_enabled):
        """
        Test: Initialize service with Redis enabled.

        Happy path - connects to Redis successfully.
        """
        with patch(
            "app.services.infrastructure.cost_control_service.settings",
            mock_settings_cost_control_enabled,
        ):
            with patch("app.services.infrastructure.cost_control_service.redis") as mock_redis:
                with patch("redis.connection.ConnectionPool") as mock_pool_class:
                    mock_pool = Mock()
                    mock_pool_class.return_value = mock_pool

                    mock_client = Mock()
                    mock_client.ping = Mock(return_value=True)
                    mock_redis.Redis.return_value = mock_client

                    service = CostControlService()

                    assert service._use_redis is True
                    assert service._redis_client == mock_client
                    mock_client.ping.assert_called_once()

    def test_init_with_redis_connection_error(self, mock_settings_cost_control_enabled):
        """
        Test: Initialize service when Redis connection fails.

        Error condition - should fallback to in-memory tracking.
        """
        with patch(
            "app.services.infrastructure.cost_control_service.settings",
            mock_settings_cost_control_enabled,
        ):
            with patch("app.services.infrastructure.cost_control_service.redis") as mock_redis:
                with patch("redis.connection.ConnectionPool") as mock_pool_class:
                    mock_pool = Mock()
                    mock_pool_class.return_value = mock_pool

                    mock_client = Mock()
                    mock_client.ping = Mock(side_effect=RedisConnectionError("Connection failed"))
                    mock_redis.Redis.return_value = mock_client

                    service = CostControlService()

                    assert service._use_redis is False
                    assert service._redis_client is None

    def test_init_with_redis_error(self, mock_settings_cost_control_enabled):
        """
        Test: Initialize service when Redis raises generic error.

        Error condition - should fallback to in-memory tracking.
        """
        with patch(
            "app.services.infrastructure.cost_control_service.settings",
            mock_settings_cost_control_enabled,
        ):
            with patch("app.services.infrastructure.cost_control_service.redis") as mock_redis:
                with patch("redis.connection.ConnectionPool") as mock_pool_class:
                    mock_pool = Mock()
                    mock_pool_class.return_value = mock_pool

                    mock_redis.Redis.side_effect = RedisError("Redis error")

                    service = CostControlService()

                    assert service._use_redis is False

    def test_init_with_redis_disabled(self, mock_settings_cost_control_enabled):
        """
        Test: Initialize service when Redis is disabled in settings.

        Edge case - Redis disabled but cost control enabled.
        """
        mock_settings_cost_control_enabled.redis_enabled = False

        with patch(
            "app.services.infrastructure.cost_control_service.settings",
            mock_settings_cost_control_enabled,
        ):
            service = CostControlService()

            assert service._use_redis is False
            assert len(service._in_memory_costs) == 0

    def test_init_with_redis_password(self, mock_settings_cost_control_enabled):
        """
        Test: Initialize service with Redis password.

        Edge case - Redis connection with password authentication.
        """
        mock_settings_cost_control_enabled.redis_password = "test-password"

        with patch(
            "app.services.infrastructure.cost_control_service.settings",
            mock_settings_cost_control_enabled,
        ):
            with patch("app.services.infrastructure.cost_control_service.redis") as mock_redis:
                with patch("redis.connection.ConnectionPool") as mock_pool_class:
                    mock_pool = Mock()
                    mock_pool_class.return_value = mock_pool

                    mock_client = Mock()
                    mock_client.ping = Mock(return_value=True)
                    mock_redis.Redis.return_value = mock_client

                    _ = CostControlService()

                    # Verify password was passed to connection pool
                    call_kwargs = mock_pool_class.call_args[1]
                    assert call_kwargs["password"] == "test-password"

    def test_init_with_empty_redis_password(self, mock_settings_cost_control_enabled):
        """
        Test: Initialize service with empty Redis password.

        Edge case - empty password should be treated as None.
        """
        mock_settings_cost_control_enabled.redis_password = "   "  # Whitespace

        with patch(
            "app.services.infrastructure.cost_control_service.settings",
            mock_settings_cost_control_enabled,
        ):
            with patch("app.services.infrastructure.cost_control_service.redis") as mock_redis:
                with patch("redis.connection.ConnectionPool") as mock_pool_class:
                    mock_pool = Mock()
                    mock_pool_class.return_value = mock_pool

                    mock_client = Mock()
                    mock_client.ping = Mock(return_value=True)
                    mock_redis.Redis.return_value = mock_client

                    _ = CostControlService()

                    # Verify password was stripped and set to None
                    call_kwargs = mock_pool_class.call_args[1]
                    assert call_kwargs["password"] is None


class TestCostControlServiceTrackJobCost:
    """Test track_job_cost functionality."""

    def test_track_job_cost_when_disabled(self, mock_settings_cost_control_disabled):
        """
        Test: Track job cost when cost control is disabled.

        Edge case - should return early without tracking.
        """
        with patch(
            "app.services.infrastructure.cost_control_service.settings",
            mock_settings_cost_control_disabled,
        ):
            service = CostControlService()
            service.track_job_cost("job-123", 0.5)

            assert len(service._in_memory_costs) == 0

    def test_track_job_cost_with_redis(self, mock_settings_cost_control_enabled):
        """
        Test: Track job cost with Redis storage.

        Happy path - stores cost in Redis.
        """
        with patch(
            "app.services.infrastructure.cost_control_service.settings",
            mock_settings_cost_control_enabled,
        ):
            with patch("app.services.infrastructure.cost_control_service.redis") as mock_redis:
                with patch("redis.connection.ConnectionPool"):
                    mock_client = Mock()
                    mock_client.ping = Mock(return_value=True)
                    mock_redis.Redis.return_value = mock_client

                    service = CostControlService()
                    service.track_job_cost("job-123", 0.5)

                    # Verify Redis operations
                    mock_client.setex.assert_called()
                    mock_client.incrbyfloat.assert_called()
                    mock_client.expire.assert_called()

    def test_track_job_cost_calculation(self, mock_settings_cost_control_enabled):
        """
        Test: Verify cost calculation is correct.

        Happy path - cost = gpu_hours * gpu_cost_per_hour.
        """
        mock_settings_cost_control_enabled.gpu_cost_per_hour = 0.50

        with patch(
            "app.services.infrastructure.cost_control_service.settings",
            mock_settings_cost_control_enabled,
        ):
            with patch("app.services.infrastructure.cost_control_service.redis") as mock_redis:
                with patch("redis.connection.ConnectionPool"):
                    mock_client = Mock()
                    mock_client.ping = Mock(return_value=True)
                    mock_redis.Redis.return_value = mock_client

                    service = CostControlService()
                    service.track_job_cost("job-123", 2.0)  # 2 GPU hours

                    # Verify cost calculation: 2.0 * 0.50 = 1.0
                    # incrbyfloat is called twice: once for total_cost, once for total_hours
                    calls = mock_client.incrbyfloat.call_args_list
                    # Find the call for total_cost (first argument contains "total" but not "total_hours")
                    total_cost_call = next(
                        (
                            call
                            for call in calls
                            if "total" in call[0][0] and "total_hours" not in call[0][0]
                        ),
                        None,
                    )
                    assert total_cost_call is not None
                    assert total_cost_call[0][1] == 1.0  # Total cost increment

    def test_track_job_cost_with_redis_error(self, mock_settings_cost_control_enabled):
        """
        Test: Track job cost when Redis operation fails.

        Error condition - should fallback to in-memory storage.
        """
        with patch(
            "app.services.infrastructure.cost_control_service.settings",
            mock_settings_cost_control_enabled,
        ):
            with patch("app.services.infrastructure.cost_control_service.redis") as mock_redis:
                with patch("redis.connection.ConnectionPool"):
                    mock_client = Mock()
                    mock_client.ping = Mock(return_value=True)
                    mock_client.setex = Mock(side_effect=RedisError("Redis error"))
                    mock_redis.Redis.return_value = mock_client

                    service = CostControlService()
                    service.track_job_cost("job-123", 0.5)

                    # Should fallback to in-memory
                    assert len(service._in_memory_costs) == 1
                    assert service._in_memory_costs[0]["job_id"] == "job-123"

    def test_track_job_cost_in_memory(self, mock_settings_cost_control_enabled):
        """
        Test: Track job cost in-memory when Redis is unavailable.

        Happy path - stores cost in-memory.
        """
        mock_settings_cost_control_enabled.redis_enabled = False

        with patch(
            "app.services.infrastructure.cost_control_service.settings",
            mock_settings_cost_control_enabled,
        ):
            service = CostControlService()
            service.track_job_cost("job-123", 0.5)

            assert len(service._in_memory_costs) == 1
            cost_entry = service._in_memory_costs[0]
            assert cost_entry["job_id"] == "job-123"
            assert cost_entry["gpu_hours"] == 0.5
            assert cost_entry["cost"] == 0.25  # 0.5 * 0.50
            assert "timestamp" in cost_entry

    def test_track_job_cost_boundary_values(self, mock_settings_cost_control_enabled):
        """
        Test: Track job cost with boundary values.

        Boundary analysis - test zero, negative, and very large values.
        """
        mock_settings_cost_control_enabled.redis_enabled = False

        with patch(
            "app.services.infrastructure.cost_control_service.settings",
            mock_settings_cost_control_enabled,
        ):
            service = CostControlService()

            # Test zero
            service.track_job_cost("job-0", 0.0)
            assert service._in_memory_costs[0]["cost"] == 0.0

            # Test negative (should still work, though unusual)
            service.track_job_cost("job-neg", -1.0)
            assert service._in_memory_costs[1]["cost"] == -0.50

            # Test very large
            service.track_job_cost("job-large", 1000.0)
            assert service._in_memory_costs[2]["cost"] == 500.0

    def test_track_job_cost_multiple_jobs(self, mock_settings_cost_control_enabled):
        """
        Test: Track multiple job costs.

        Edge case - track multiple jobs and verify accumulation.
        """
        mock_settings_cost_control_enabled.redis_enabled = False

        with patch(
            "app.services.infrastructure.cost_control_service.settings",
            mock_settings_cost_control_enabled,
        ):
            service = CostControlService()

            jobs = [
                ("job-1", 0.5),
                ("job-2", 1.0),
                ("job-3", 0.25),
            ]

            for job_id, gpu_hours in jobs:
                service.track_job_cost(job_id, gpu_hours)

            assert len(service._in_memory_costs) == 3
            total_cost = sum(entry["cost"] for entry in service._in_memory_costs)
            assert total_cost == 0.875  # 0.25 + 0.50 + 0.125


class TestCostControlServiceCheckBudget:
    """Test check_budget functionality."""

    def test_check_budget_when_disabled(self, mock_settings_cost_control_disabled):
        """
        Test: Check budget when cost control is disabled.

        Edge case - should always return True (no budget limit).
        """
        with patch(
            "app.services.infrastructure.cost_control_service.settings",
            mock_settings_cost_control_disabled,
        ):
            service = CostControlService()
            assert service.check_budget() is True

    def test_check_budget_under_limit(self, mock_settings_cost_control_enabled):
        """
        Test: Check budget when under limit.

        Happy path - budget is OK.
        """
        mock_settings_cost_control_enabled.max_budget_usd = 100.0
        mock_settings_cost_control_enabled.redis_enabled = False

        with patch(
            "app.services.infrastructure.cost_control_service.settings",
            mock_settings_cost_control_enabled,
        ):
            service = CostControlService()
            service.track_job_cost("job-1", 1.0)  # Cost: 0.50

            assert service.check_budget() is True

    def test_check_budget_at_limit(self, mock_settings_cost_control_enabled):
        """
        Test: Check budget when at limit.

        Boundary case - exactly at budget limit.
        """
        mock_settings_cost_control_enabled.max_budget_usd = 0.50
        mock_settings_cost_control_enabled.redis_enabled = False

        with patch(
            "app.services.infrastructure.cost_control_service.settings",
            mock_settings_cost_control_enabled,
        ):
            service = CostControlService()
            service.track_job_cost("job-1", 1.0)  # Cost: 0.50

            # Should return False (budget exceeded or at limit)
            assert service.check_budget() is False

    def test_check_budget_over_limit(self, mock_settings_cost_control_enabled):
        """
        Test: Check budget when over limit.

        Error condition - budget exceeded.
        """
        mock_settings_cost_control_enabled.max_budget_usd = 0.25
        mock_settings_cost_control_enabled.redis_enabled = False

        with patch(
            "app.services.infrastructure.cost_control_service.settings",
            mock_settings_cost_control_enabled,
        ):
            service = CostControlService()
            service.track_job_cost("job-1", 1.0)  # Cost: 0.50

            assert service.check_budget() is False

    def test_check_budget_with_redis(self, mock_settings_cost_control_enabled):
        """
        Test: Check budget using Redis total cost.

        Happy path - reads total cost from Redis.
        """
        mock_settings_cost_control_enabled.max_budget_usd = 100.0

        with patch(
            "app.services.infrastructure.cost_control_service.settings",
            mock_settings_cost_control_enabled,
        ):
            with patch("app.services.infrastructure.cost_control_service.redis") as mock_redis:
                with patch("redis.connection.ConnectionPool"):
                    mock_client = Mock()
                    mock_client.ping = Mock(return_value=True)
                    mock_client.get = Mock(return_value="50.0")  # Total cost from Redis
                    mock_redis.Redis.return_value = mock_client

                    service = CostControlService()
                    result = service.check_budget()

                    assert result is True  # 50.0 < 100.0

    def test_check_budget_with_redis_error(self, mock_settings_cost_control_enabled):
        """
        Test: Check budget when Redis read fails.

        Error condition - should fallback to in-memory calculation.
        """
        mock_settings_cost_control_enabled.max_budget_usd = 100.0

        with patch(
            "app.services.infrastructure.cost_control_service.settings",
            mock_settings_cost_control_enabled,
        ):
            with patch("app.services.infrastructure.cost_control_service.redis") as mock_redis:
                with patch("redis.connection.ConnectionPool"):
                    mock_client = Mock()
                    mock_client.ping = Mock(return_value=True)
                    mock_client.get = Mock(side_effect=RedisError("Redis error"))
                    mock_redis.Redis.return_value = mock_client

                    service = CostControlService()
                    service._in_memory_costs = [{"cost": 50.0}]  # Set in-memory cost

                    result = service.check_budget()

                    # Should use in-memory fallback
                    assert result is True


class TestCostControlServiceGetCostMetrics:
    """Test get_cost_metrics functionality."""

    def test_get_cost_metrics_when_disabled(self, mock_settings_cost_control_disabled):
        """
        Test: Get cost metrics when cost control is disabled.

        Edge case - returns zero metrics.
        """
        with patch(
            "app.services.infrastructure.cost_control_service.settings",
            mock_settings_cost_control_disabled,
        ):
            service = CostControlService()
            metrics = service.get_cost_metrics(active_workers=3)

            assert isinstance(metrics, CostMetrics)
            assert metrics.total_cost == 0.0
            assert metrics.total_gpu_hours == 0.0
            assert metrics.jobs_processed == 0
            assert metrics.active_workers == 3
            assert metrics.budget_remaining == mock_settings_cost_control_disabled.max_budget_usd

    def test_get_cost_metrics_with_data(self, mock_settings_cost_control_enabled):
        """
        Test: Get cost metrics with tracked costs.

        Happy path - returns calculated metrics.
        """
        mock_settings_cost_control_enabled.max_budget_usd = 100.0
        mock_settings_cost_control_enabled.redis_enabled = False

        with patch(
            "app.services.infrastructure.cost_control_service.settings",
            mock_settings_cost_control_enabled,
        ):
            service = CostControlService()

            # Track some jobs
            service.track_job_cost("job-1", 1.0)  # Cost: 0.50
            service.track_job_cost("job-2", 1.0)  # Cost: 0.50
            service.track_job_cost("job-3", 1.0)  # Cost: 0.50

            metrics = service.get_cost_metrics(active_workers=2)

            assert metrics.total_cost == 1.50
            assert metrics.total_gpu_hours == 3.0
            assert metrics.jobs_processed == 3
            assert metrics.cost_per_job == 0.50  # 1.50 / 3
            assert metrics.budget_remaining == 98.50  # 100.0 - 1.50
            assert metrics.active_workers == 2

    def test_get_cost_metrics_zero_jobs(self, mock_settings_cost_control_enabled):
        """
        Test: Get cost metrics with no jobs processed.

        Edge case - division by zero protection.
        """
        mock_settings_cost_control_enabled.max_budget_usd = 100.0
        mock_settings_cost_control_enabled.redis_enabled = False

        with patch(
            "app.services.infrastructure.cost_control_service.settings",
            mock_settings_cost_control_enabled,
        ):
            service = CostControlService()
            metrics = service.get_cost_metrics(active_workers=0)

            assert metrics.cost_per_job == 0.0  # Should not raise division by zero
            assert metrics.jobs_processed == 0

    def test_get_cost_metrics_budget_alert(self, mock_settings_cost_control_enabled):
        """
        Test: Get cost metrics triggers budget alert.

        Edge case - when budget reaches alert threshold.
        """
        mock_settings_cost_control_enabled.max_budget_usd = 100.0
        mock_settings_cost_control_enabled.budget_alert_threshold = 0.8
        mock_settings_cost_control_enabled.redis_enabled = False

        with patch(
            "app.services.infrastructure.cost_control_service.settings",
            mock_settings_cost_control_enabled,
        ):
            with patch("app.services.infrastructure.cost_control_service.logger") as mock_logger:
                service = CostControlService()

                # Track costs to reach 80% of budget (80.0)
                # Each job costs 0.50, so need 160 jobs
                for i in range(160):
                    service.track_job_cost(f"job-{i}", 1.0)

                metrics = service.get_cost_metrics()

                # Should trigger alert
                mock_logger.warning.assert_called()
                assert metrics.total_cost >= 80.0

    def test_get_cost_metrics_with_redis(self, mock_settings_cost_control_enabled):
        """
        Test: Get cost metrics using Redis data.

        Happy path - reads from Redis.
        """
        mock_settings_cost_control_enabled.max_budget_usd = 100.0

        with patch(
            "app.services.infrastructure.cost_control_service.settings",
            mock_settings_cost_control_enabled,
        ):
            with patch("app.services.infrastructure.cost_control_service.redis") as mock_redis:
                with patch("redis.connection.ConnectionPool"):
                    mock_client = Mock()
                    mock_client.ping = Mock(return_value=True)
                    mock_client.get = Mock(side_effect=["50.0", "100.0"])  # total_cost, total_hours
                    mock_client.keys = Mock(return_value=["cost:job:1", "cost:job:2"])  # 2 jobs
                    mock_redis.Redis.return_value = mock_client

                    service = CostControlService()
                    metrics = service.get_cost_metrics(active_workers=1)

                    assert metrics.total_cost == 50.0
                    assert metrics.total_gpu_hours == 100.0
                    assert metrics.jobs_processed == 2


class TestCostControlServiceEnforceIdleTimeout:
    """Test enforce_idle_timeout functionality."""

    def test_enforce_idle_timeout_when_disabled(self, mock_settings_cost_control_disabled):
        """
        Test: Enforce idle timeout when cost control is disabled.

        Edge case - should always return False.
        """
        with patch(
            "app.services.infrastructure.cost_control_service.settings",
            mock_settings_cost_control_disabled,
        ):
            service = CostControlService()
            assert service.enforce_idle_timeout("worker-1", 1000) is False

    def test_enforce_idle_timeout_under_threshold(self, mock_settings_cost_control_enabled):
        """
        Test: Enforce idle timeout when under threshold.

        Happy path - worker should not be terminated.
        """
        mock_settings_cost_control_enabled.worker_idle_timeout_seconds = 600

        with patch(
            "app.services.infrastructure.cost_control_service.settings",
            mock_settings_cost_control_enabled,
        ):
            service = CostControlService()
            assert service.enforce_idle_timeout("worker-1", 300) is False  # 300 < 600

    def test_enforce_idle_timeout_at_threshold(self, mock_settings_cost_control_enabled):
        """
        Test: Enforce idle timeout exactly at threshold.

        Boundary case - exactly at timeout threshold.
        """
        mock_settings_cost_control_enabled.worker_idle_timeout_seconds = 600

        with patch(
            "app.services.infrastructure.cost_control_service.settings",
            mock_settings_cost_control_enabled,
        ):
            service = CostControlService()
            assert service.enforce_idle_timeout("worker-1", 600) is False  # 600 is not > 600

    def test_enforce_idle_timeout_over_threshold(self, mock_settings_cost_control_enabled):
        """
        Test: Enforce idle timeout when over threshold.

        Happy path - worker should be terminated.
        """
        mock_settings_cost_control_enabled.worker_idle_timeout_seconds = 600

        with patch(
            "app.services.infrastructure.cost_control_service.settings",
            mock_settings_cost_control_enabled,
        ):
            service = CostControlService()
            assert service.enforce_idle_timeout("worker-1", 601) is True  # 601 > 600

    def test_enforce_idle_timeout_boundary_values(self, mock_settings_cost_control_enabled):
        """
        Test: Enforce idle timeout with boundary values.

        Boundary analysis - test various timeout values.
        """
        mock_settings_cost_control_enabled.worker_idle_timeout_seconds = 600

        with patch(
            "app.services.infrastructure.cost_control_service.settings",
            mock_settings_cost_control_enabled,
        ):
            service = CostControlService()

            # Test boundary values
            assert service.enforce_idle_timeout("worker-1", 0) is False
            assert service.enforce_idle_timeout("worker-1", 599) is False
            assert service.enforce_idle_timeout("worker-1", 600) is False
            assert service.enforce_idle_timeout("worker-1", 601) is True
            assert service.enforce_idle_timeout("worker-1", 999999) is True


class TestCostControlServiceResetCostTracking:
    """Test reset_cost_tracking functionality."""

    def test_reset_cost_tracking_with_redis(self, mock_settings_cost_control_enabled):
        """
        Test: Reset cost tracking with Redis.

        Happy path - clears Redis keys and in-memory costs.
        """
        with patch(
            "app.services.infrastructure.cost_control_service.settings",
            mock_settings_cost_control_enabled,
        ):
            with patch("app.services.infrastructure.cost_control_service.redis") as mock_redis:
                with patch("redis.connection.ConnectionPool"):
                    mock_client = Mock()
                    mock_client.ping = Mock(return_value=True)
                    mock_client.keys = Mock(return_value=["cost:total", "cost:job:1"])
                    mock_client.delete = Mock(return_value=2)
                    mock_redis.Redis.return_value = mock_client

                    service = CostControlService()
                    service._in_memory_costs = [{"cost": 10.0}]

                    service.reset_cost_tracking()

                    # Verify Redis keys were deleted
                    mock_client.delete.assert_called()
                    # Verify in-memory costs were cleared
                    assert len(service._in_memory_costs) == 0

    def test_reset_cost_tracking_in_memory_only(self, mock_settings_cost_control_enabled):
        """
        Test: Reset cost tracking in-memory only.

        Happy path - clears in-memory costs when Redis is disabled.
        """
        mock_settings_cost_control_enabled.redis_enabled = False

        with patch(
            "app.services.infrastructure.cost_control_service.settings",
            mock_settings_cost_control_enabled,
        ):
            service = CostControlService()
            service._in_memory_costs = [{"cost": 10.0}, {"cost": 20.0}]

            service.reset_cost_tracking()

            assert len(service._in_memory_costs) == 0

    def test_reset_cost_tracking_with_redis_error(self, mock_settings_cost_control_enabled):
        """
        Test: Reset cost tracking when Redis operation fails.

        Error condition - should still clear in-memory costs.
        """
        with patch(
            "app.services.infrastructure.cost_control_service.settings",
            mock_settings_cost_control_enabled,
        ):
            with patch("app.services.infrastructure.cost_control_service.redis") as mock_redis:
                with patch("redis.connection.ConnectionPool"):
                    mock_client = Mock()
                    mock_client.ping = Mock(return_value=True)
                    mock_client.keys = Mock(side_effect=RedisError("Redis error"))
                    mock_redis.Redis.return_value = mock_client

                    service = CostControlService()
                    service._in_memory_costs = [{"cost": 10.0}]

                    service.reset_cost_tracking()

                    # Should still clear in-memory
                    assert len(service._in_memory_costs) == 0
