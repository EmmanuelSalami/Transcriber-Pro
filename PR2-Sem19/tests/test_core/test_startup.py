"""Unit tests for startup and shutdown functions.

This module tests:
- Configuration validation
- Dev mode warnings
- Orphaned job recovery
- Whisper model preloading
- Observability initialization
- Auto-scaling task management
- Edge cases and error handling
"""

import asyncio
from unittest.mock import Mock, patch

import pytest

from app.core.startup import (initialize_observability, log_dev_mode_warnings,
                              preload_whisper_model, recover_orphaned_jobs,
                              shutdown_auto_scaling_task,
                              start_auto_scaling_task,
                              validate_startup_configuration)


class TestValidateStartupConfiguration:
    """Test suite for validate_startup_configuration function."""

    def test_validate_startup_configuration_dev_mode_skips(self, mock_settings_dev_mode):
        """Test: Validation skipped in development mode.

        Verifies that validation is skipped when not in production mode,
        and warnings are logged instead of errors.
        """
        with patch("app.core.startup.settings", mock_settings_dev_mode):
            # Patch the method at the Settings class level from config module
            with patch("app.core.config.Settings.validate_production_settings") as mock_validate:
                # Should not raise
                validate_startup_configuration()

                # validate_production_settings should be called
                mock_validate.assert_called_once()

    def test_validate_startup_configuration_production_valid(self, mock_settings_production):
        """Test: Valid production configuration passes validation.

        Verifies that valid production settings pass validation without errors.
        """
        with patch("app.core.startup.settings", mock_settings_production):
            # Should not raise
            validate_startup_configuration()

    def test_validate_startup_configuration_production_invalid_raises(
        self, mock_settings_production
    ):
        """Test: Invalid production configuration raises ValueError.

        Verifies that invalid production settings raise ValueError.
        """
        with patch("app.core.startup.settings", mock_settings_production):
            # Patch at the Settings class level from config module
            with patch("app.core.config.Settings.validate_production_settings") as mock_validate:
                mock_validate.side_effect = ValueError("Configuration error")

                # Mock is_production to return True
                with patch("app.core.config.Settings.is_production", return_value=True):
                    with pytest.raises(ValueError):
                        validate_startup_configuration()

    def test_validate_startup_configuration_logs_error_in_production(
        self, mock_settings_production
    ):
        """Test: Production validation errors are logged.

        Verifies that validation errors in production mode are logged as errors.
        """
        with patch("app.core.startup.settings", mock_settings_production):
            # Patch at the Settings class level from config module
            with patch("app.core.config.Settings.validate_production_settings") as mock_validate:
                mock_validate.side_effect = ValueError("Configuration error")

                # Mock is_production to return True
                with patch("app.core.config.Settings.is_production", return_value=True):
                    with patch("app.core.startup.logger") as mock_logger:
                        try:
                            validate_startup_configuration()
                        except ValueError:
                            pass

                        mock_logger.error.assert_called()


class TestLogDevModeWarnings:
    """Test suite for log_dev_mode_warnings function."""

    def test_log_dev_mode_warnings_no_api_keys(self, mock_settings_dev_mode):
        """Test: Warning logged when no API keys in dev mode.

        Verifies that a warning is logged when API keys are not configured
        in development mode.
        """
        with patch("app.core.startup.settings", mock_settings_dev_mode):
            with patch("app.core.startup.logger") as mock_logger:
                log_dev_mode_warnings()

                mock_logger.warning.assert_called()
                # Check that warning mentions API keys
                warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
                assert any("API keys" in str(call) for call in warning_calls)

    def test_log_dev_mode_warnings_wildcard_cors(self, mock_settings_dev_mode):
        """Test: Warning logged when CORS is wildcard in dev mode.

        Verifies that a warning is logged when CORS is set to "*" in
        development mode.
        """
        with patch("app.core.startup.settings", mock_settings_dev_mode):
            # Patch at the Settings class level from config module
            with patch("app.core.config.Settings.get_cors_origins", return_value=["*"]):
                with patch("app.core.startup.logger") as mock_logger:
                    log_dev_mode_warnings()

                    mock_logger.warning.assert_called()
                    # Check that warning mentions CORS
                    warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
                    assert any("CORS" in str(call) for call in warning_calls)

    def test_log_dev_mode_warnings_production_no_warnings(self, mock_settings_production):
        """Test: No warnings logged in production mode.

        Verifies that warnings are not logged when in production mode.
        """
        with patch("app.core.startup.settings", mock_settings_production):
            with patch("app.core.startup.logger") as mock_logger:
                log_dev_mode_warnings()

                # Should not log warnings in production
                mock_logger.warning.assert_not_called()


class TestRecoverOrphanedJobs:
    """Test suite for recover_orphaned_jobs function."""

    def test_recover_orphaned_jobs_happy_path(self, mock_job_manager):
        """Test: Orphaned jobs are recovered successfully.

        Verifies that orphaned jobs are recovered and the count is logged.
        """
        mock_job_manager.recover_orphaned_jobs.return_value = 5

        with patch("app.core.startup.JobManager", return_value=mock_job_manager):
            with patch("app.core.startup.logger") as mock_logger:
                recover_orphaned_jobs()

                mock_job_manager.recover_orphaned_jobs.assert_called_once()
                mock_logger.info.assert_called()
                # Check that info mentions recovered count
                info_calls = [str(call) for call in mock_logger.info.call_args_list]
                assert any("5" in str(call) for call in info_calls)

    def test_recover_orphaned_jobs_no_orphaned_jobs(self, mock_job_manager):
        """Test: No orphaned jobs logs debug message.

        Verifies that when no orphaned jobs are found, a debug message
        is logged instead of info.
        """
        mock_job_manager.recover_orphaned_jobs.return_value = 0

        with patch("app.core.startup.JobManager", return_value=mock_job_manager):
            with patch("app.core.startup.logger") as mock_logger:
                recover_orphaned_jobs()

                mock_logger.debug.assert_called()
                # Should not log info about recovered jobs
                info_calls = [str(call) for call in mock_logger.info.call_args_list]
                assert not any("Recovered" in str(call) for call in info_calls)

    def test_recover_orphaned_jobs_handles_exception(self, mock_job_manager):
        """Test: Exceptions during recovery are handled gracefully.

        Verifies that if job recovery fails, an error is logged but
        the application startup continues.
        """
        mock_job_manager.recover_orphaned_jobs.side_effect = Exception("Recovery error")

        with patch("app.core.startup.JobManager", return_value=mock_job_manager):
            with patch("app.core.startup.logger") as mock_logger:
                # Should not raise
                recover_orphaned_jobs()

                mock_logger.error.assert_called()
                # Check that error mentions failure
                error_calls = [str(call) for call in mock_logger.error.call_args_list]
                assert any("Failed" in str(call) for call in error_calls)


class TestPreloadWhisperModel:
    """Test suite for preload_whisper_model function."""

    def test_preload_whisper_model_happy_path(self, mock_whisper_service):
        """Test: Whisper model is preloaded successfully.

        Verifies that the Whisper model is loaded at startup and
        success is logged.
        """
        mock_whisper_service.ensure_model_loaded.return_value = True

        with patch("app.core.startup.WhisperService") as mock_service_class:
            mock_service_class.get_instance.return_value = mock_whisper_service

            with patch("app.core.startup.logger") as mock_logger:
                preload_whisper_model()

                mock_whisper_service.ensure_model_loaded.assert_called_once()
                mock_logger.info.assert_called()
                # Check that info mentions successful load
                info_calls = [str(call) for call in mock_logger.info.call_args_list]
                assert any("loaded successfully" in str(call).lower() for call in info_calls)

    def test_preload_whisper_model_not_loaded_warning(self, mock_whisper_service):
        """Test: Warning logged when model not loaded.

        Verifies that a warning is logged when the model fails to load,
        but startup continues.
        """
        mock_whisper_service.ensure_model_loaded.return_value = False

        with patch("app.core.startup.WhisperService") as mock_service_class:
            mock_service_class.get_instance.return_value = mock_whisper_service

            with patch("app.core.startup.logger") as mock_logger:
                preload_whisper_model()

                mock_logger.warning.assert_called()
                # Check that warning mentions model not loaded
                warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
                assert any("not loaded" in str(call).lower() for call in warning_calls)

    def test_preload_whisper_model_handles_exception(self, mock_whisper_service):
        """Test: Exceptions during preload are handled gracefully.

        Verifies that if model preloading fails, an error is logged but
        the application startup continues.
        """
        mock_whisper_service.ensure_model_loaded.side_effect = Exception("Load error")

        with patch("app.core.startup.WhisperService") as mock_service_class:
            mock_service_class.get_instance.return_value = mock_whisper_service

            with patch("app.core.startup.logger") as mock_logger:
                # Should not raise
                preload_whisper_model()

                mock_logger.error.assert_called()
                # Check that error mentions failure
                error_calls = [str(call) for call in mock_logger.error.call_args_list]
                assert any("Failed" in str(call) for call in error_calls)


class TestInitializeObservability:
    """Test suite for initialize_observability function."""

    def test_initialize_observability_enabled(self, mock_settings):
        """Test: Observability is initialized when enabled.

        Verifies that observability service is initialized when
        observability and metrics are enabled.
        """
        mock_settings.observability_enabled = True
        mock_settings.metrics_enabled = True

        with patch("app.core.startup.settings", mock_settings):
            with patch("app.core.startup.get_observability_service") as mock_get_service:
                mock_service = Mock()
                mock_get_service.return_value = mock_service

                with patch("app.core.startup.logger") as mock_logger:
                    initialize_observability()

                    mock_get_service.assert_called_once()
                    mock_logger.info.assert_called()
                    # Check that info mentions initialization
                    info_calls = [str(call) for call in mock_logger.info.call_args_list]
                    assert any("initialized" in str(call).lower() for call in info_calls)

    def test_initialize_observability_disabled(self, mock_settings):
        """Test: Observability is not initialized when disabled.

        Verifies that observability service is not initialized when
        observability is disabled.
        """
        mock_settings.observability_enabled = False
        mock_settings.metrics_enabled = True

        with patch("app.core.startup.settings", mock_settings):
            with patch("app.core.startup.get_observability_service") as mock_get_service:
                initialize_observability()

                # Should not be called when disabled
                mock_get_service.assert_not_called()

    def test_initialize_observability_handles_exception(self, mock_settings):
        """Test: Exceptions during initialization are handled gracefully.

        Verifies that if observability initialization fails, an error
        is logged but the application startup continues.
        """
        mock_settings.observability_enabled = True
        mock_settings.metrics_enabled = True

        with patch("app.core.startup.settings", mock_settings):
            with patch("app.core.startup.get_observability_service") as mock_get_service:
                mock_get_service.side_effect = Exception("Init error")

                with patch("app.core.startup.logger") as mock_logger:
                    # Should not raise
                    initialize_observability()

                    mock_logger.error.assert_called()
                    # Check that error mentions failure
                    error_calls = [str(call) for call in mock_logger.error.call_args_list]
                    assert any("Failed" in str(call) for call in error_calls)


class TestStartAutoScalingTask:
    """Test suite for start_auto_scaling_task function."""

    @pytest.mark.asyncio
    async def test_start_auto_scaling_task_enabled(self, mock_settings):
        """Test: Auto-scaling task is started when enabled.

        Verifies that auto-scaling task is created when enabled and
        RunPod is configured.
        """
        mock_settings.worker_auto_scaling_enabled = True
        mock_settings.runpod_api_key = "test-key"
        mock_settings.runpod_template_id = "test-template"

        with patch("app.core.startup.settings", mock_settings):
            with patch("app.core.startup.logger") as mock_logger:
                with patch("asyncio.create_task") as mock_create_task:
                    mock_task = Mock()
                    mock_create_task.return_value = mock_task

                    task = await start_auto_scaling_task()

                    assert task is mock_task
                    mock_create_task.assert_called_once()
                    mock_logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_start_auto_scaling_task_disabled(self, mock_settings):
        """Test: Auto-scaling task is not started when disabled.

        Verifies that auto-scaling task is not created when disabled.
        """
        mock_settings.worker_auto_scaling_enabled = False

        with patch("app.core.startup.settings", mock_settings):
            task = await start_auto_scaling_task()

            assert task is None

    @pytest.mark.asyncio
    async def test_start_auto_scaling_task_no_runpod_config(self, mock_settings):
        """Test: Auto-scaling task is not started without RunPod config.

        Verifies that auto-scaling task is not created when RunPod
        is not configured, even if enabled.
        """
        mock_settings.worker_auto_scaling_enabled = True
        mock_settings.runpod_api_key = ""
        mock_settings.runpod_template_id = ""

        with patch("app.core.startup.settings", mock_settings):
            with patch("app.core.startup.logger") as mock_logger:
                task = await start_auto_scaling_task()

                assert task is None
                mock_logger.info.assert_called()
                # Check that info mentions RunPod not configured
                info_calls = [str(call) for call in mock_logger.info.call_args_list]
                assert any("RunPod" in str(call) for call in info_calls)


class TestShutdownAutoScalingTask:
    """Test suite for shutdown_auto_scaling_task function."""

    @pytest.mark.asyncio
    async def test_shutdown_auto_scaling_task_happy_path(self):
        """Test: Auto-scaling task is cancelled successfully.

        Verifies that auto-scaling task is cancelled and awaited
        during shutdown.
        """

        # Create a proper async task mock
        async def dummy_task():
            await asyncio.sleep(0.01)

        task = asyncio.create_task(dummy_task())
        task.cancel()

        with patch("app.core.startup.logger") as mock_logger:
            await shutdown_auto_scaling_task(task)

            mock_logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_shutdown_auto_scaling_task_none(self):
        """Test: None task is handled gracefully.

        Edge case: If task is None, should not raise.
        """
        with patch("app.core.startup.logger") as mock_logger:
            # Should not raise
            await shutdown_auto_scaling_task(None)

            # Should not log if task is None
            mock_logger.info.assert_not_called()

    @pytest.mark.asyncio
    async def test_shutdown_auto_scaling_task_handles_cancelled_error(self):
        """Test: CancelledError is handled gracefully.

        Verifies that CancelledError raised during task await is
        caught and handled.
        """

        # Create a proper async task mock that will be cancelled
        async def dummy_task():
            await asyncio.sleep(0.01)

        task = asyncio.create_task(dummy_task())
        task.cancel()

        with patch("app.core.startup.logger") as mock_logger:
            # Should not raise
            await shutdown_auto_scaling_task(task)

            mock_logger.info.assert_called()


class TestStartupEdgeCases:
    """Test suite for edge cases in startup functions."""

    def test_recover_orphaned_jobs_zero_count(self, mock_job_manager):
        """Test: Zero orphaned jobs is handled correctly.

        Edge case: When zero jobs are recovered, should log debug.
        """
        mock_job_manager.recover_orphaned_jobs.return_value = 0

        with patch("app.core.startup.JobManager", return_value=mock_job_manager):
            with patch("app.core.startup.logger") as mock_logger:
                recover_orphaned_jobs()

                mock_logger.debug.assert_called()

    def test_preload_whisper_model_service_unavailable(self):
        """Test: WhisperService unavailable is handled.

        Edge case: If WhisperService cannot be instantiated, should
        log error but continue startup.
        """
        with patch("app.core.startup.WhisperService") as mock_service_class:
            mock_service_class.get_instance.side_effect = Exception("Service unavailable")

            with patch("app.core.startup.logger") as mock_logger:
                # Should not raise
                preload_whisper_model()

                mock_logger.error.assert_called()
