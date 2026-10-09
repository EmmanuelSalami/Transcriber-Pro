"""Pytest configuration and shared fixtures."""

import shutil
from pathlib import Path

import pytest

# Import fixtures first (they need to be available)
from tests.fixtures import *  # noqa: F401, F403

# Global patches - will be started in pytest_configure
_patches = {}


def pytest_configure(config):
    """
    Configure pytest and set up global mocks BEFORE any tests run.

    This is called very early, before test collection, so we can patch
    expensive services before they're imported.
    """
    from unittest.mock import Mock, patch

    # Create shared mock WhisperService instance
    mock_whisper_instance = Mock()
    mock_whisper_instance.health_check.return_value = {
        "loaded": True,
        "device": "cpu",
        "ready": True,
    }
    mock_whisper_instance.ensure_model_loaded.return_value = True
    mock_whisper_instance.transcribe_async = Mock()
    mock_whisper_instance.transcribe_media = Mock()

    # Patch settings to disable Redis (only if module exists)
    try:
        _patches["settings"] = patch("app.services.jobs.job_manager.settings")
        mock_settings = _patches["settings"].start()
        mock_settings.redis_enabled = False
        mock_settings.temp_store_dir = "/tmp/test_temp_store"
        mock_settings.job_ttl_seconds = 3600
    except (AttributeError, ImportError):
        pass  # Module not imported yet, skip patching

    # Patch WhisperService in whisper_service module (only if module exists)
    try:
        _patches["whisper1"] = patch("app.services.transcription.whisper_service.WhisperService")
        mock_whisper_class1 = _patches["whisper1"].start()
        mock_whisper_class1.get_instance.return_value = mock_whisper_instance
        mock_whisper_class1.return_value = mock_whisper_instance
    except (AttributeError, ImportError):
        pass

    # Patch WhisperService where TranscriptionService imports it (CRITICAL!)
    try:
        _patches["whisper2"] = patch(
            "app.services.transcription.transcription_service.WhisperService"
        )
        mock_whisper_class2 = _patches["whisper2"].start()
        mock_whisper_class2.get_instance.return_value = mock_whisper_instance
        mock_whisper_class2.return_value = mock_whisper_instance
    except (AttributeError, ImportError):
        pass

    # Patch AudioDownloadService
    try:
        _patches["audio"] = patch(
            "app.services.transcription.transcription_service.AudioDownloadService"
        )
        _patches["audio"].start()
    except (AttributeError, ImportError):
        pass

    # Patch JobManager
    try:
        _patches["job_manager"] = patch(
            "app.services.transcription.transcription_service.JobManager"
        )
        _patches["job_manager"].start()
    except (AttributeError, ImportError):
        pass


def pytest_sessionfinish(session, exitstatus):
    """Cleanup patches after all tests."""
    for patch_obj in _patches.values():
        try:
            patch_obj.stop()
        except Exception:
            pass  # Ignore cleanup errors


@pytest.fixture(scope="session", autouse=True)
def cleanup_temp_directories():
    """
    Cleanup fixture that removes temp_uploads and temp_downloads directories after all tests.

    This fixture runs automatically after all tests to ensure temp directories are cleaned up.
    Changed to session scope for better performance.
    """
    # Yield control to tests
    yield

    # Cleanup after all tests complete
    project_root = Path(__file__).parent.parent
    temp_uploads_dir = project_root / "temp_uploads"
    temp_downloads_dir = project_root / "temp_downloads"

    # Remove temp_uploads directory and all its contents
    if temp_uploads_dir.exists():
        try:
            shutil.rmtree(temp_uploads_dir)
        except Exception:
            pass  # Ignore errors during cleanup

    # Remove temp_downloads directory and all its contents
    if temp_downloads_dir.exists():
        try:
            shutil.rmtree(temp_downloads_dir)
        except Exception:
            pass  # Ignore errors during cleanup


# DISABLED for performance - cleanup only at session end
# @pytest.fixture(autouse=True, scope="function")
# def cleanup_temp_files_after_test():
#     """
#     Cleanup fixture that removes files from temp_uploads and temp_downloads after each test.
#
#     DISABLED for performance - files are cleaned up at session end instead.
#     """
#     yield


# Performance optimization: Cache JobManager instances
@pytest.fixture(scope="function")
def job_manager_mock():
    """
    Provide a mocked JobManager instance.

    This prevents real JobManager initialization which may try to connect to Redis.
    """
    from unittest.mock import Mock, patch

    with patch("app.services.jobs.job_manager.JobManager") as mock_job_manager_class:
        mock_manager = Mock()
        mock_manager._use_redis = False
        mock_manager._jobs = {}
        mock_manager.create_job = Mock(return_value=("test-job-id", {"status": "queued"}))
        mock_manager.get_job = Mock(return_value={"status": "queued", "job_id": "test-job-id"})
        mock_manager.update_job_status = Mock()
        mock_manager.complete_job = Mock()
        mock_manager.fail_job = Mock()
        mock_manager.get_all_jobs = Mock(return_value={})
        mock_manager.recover_orphaned_jobs = Mock(return_value=0)
        mock_manager.get_redis_pool_stats = Mock(return_value={})
        mock_job_manager_class.return_value = mock_manager
        yield mock_manager
