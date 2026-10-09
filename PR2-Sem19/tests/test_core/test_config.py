"""Unit tests for configuration settings.

This module tests:
- Settings initialization and defaults
- API key parsing and validation
- CORS origin parsing and validation
- Production/development mode detection
- Configuration validation
- Format parsing (audio, video, languages)
- Boundary values and edge cases
"""

from unittest.mock import patch

import pytest

from app.core.config import Settings


class TestSettingsInitialization:
    """Test suite for Settings class initialization."""

    def test_settings_default_values(self):
        """Test: Settings should have correct default values.

        Verifies that all default values are set correctly when no
        environment variables are provided.
        """
        settings = Settings()
        assert settings.api_title == "YouTube Transcription API"
        assert settings.api_version == "v1"
        assert settings.api_prefix == "/v1"
        assert settings.rate_limit_per_minute == 60
        assert settings.whisper_model == "openai/whisper-base"
        assert settings.whisper_device == "cpu"
        assert settings.async_threshold_seconds == 300
        assert settings.max_video_duration_seconds == 3600

    def test_settings_from_env_vars(self, env_vars):
        """Test: Settings should load from environment variables.

        Verifies that settings can be overridden via environment variables.
        """
        env_vars(
            API_TITLE="Custom API",
            API_VERSION="v2",
            API_KEYS="key1,key2",
            RATE_LIMIT_PER_MINUTE="120",
        )
        settings = Settings()
        assert settings.api_title == "Custom API"
        assert settings.api_version == "v2"
        assert settings.api_keys == "key1,key2"
        assert settings.rate_limit_per_minute == 120

    def test_settings_case_insensitive_env_vars(self, env_vars):
        """Test: Environment variable names are case-insensitive.

        Verifies that environment variables can be provided in any case.
        """
        env_vars(api_keys="key1,key2", dev_mode="true")
        settings = Settings()
        assert settings.api_keys == "key1,key2"
        assert settings.dev_mode is True


class TestGetApiKeys:
    """Test suite for get_api_keys method."""

    def test_get_api_keys_happy_path(self):
        """Test: Parse comma-separated API keys correctly.

        Verifies that comma-separated API keys are parsed into a list
        with whitespace stripped.
        """
        settings = Settings(api_keys="key1,key2,key3")
        keys = settings.get_api_keys()
        assert keys == ["key1", "key2", "key3"]

    def test_get_api_keys_with_whitespace(self):
        """Test: Strip whitespace from API keys.

        Edge case: API keys with leading/trailing whitespace should be
        stripped during parsing.
        """
        settings = Settings(api_keys="  key1  ,  key2  ,  key3  ")
        keys = settings.get_api_keys()
        assert keys == ["key1", "key2", "key3"]

    def test_get_api_keys_empty_string(self):
        """Test: Empty API keys string returns empty list.

        Edge case: Empty string should return an empty list.
        """
        settings = Settings(api_keys="")
        keys = settings.get_api_keys()
        assert keys == []

    def test_get_api_keys_single_key(self):
        """Test: Single API key is parsed correctly.

        Boundary case: Single key without commas should work.
        """
        settings = Settings(api_keys="single-key")
        keys = settings.get_api_keys()
        assert keys == ["single-key"]

    def test_get_api_keys_empty_entries_filtered(self):
        """Test: Empty entries in comma-separated list are filtered out.

        Edge case: Multiple commas or empty entries should be ignored.
        """
        settings = Settings(api_keys="key1,,key2,  ,key3")
        keys = settings.get_api_keys()
        assert keys == ["key1", "key2", "key3"]

    def test_get_api_keys_only_commas(self):
        """Test: String with only commas returns empty list.

        Edge case: String containing only commas and whitespace.
        """
        settings = Settings(api_keys=",,  ,,")
        keys = settings.get_api_keys()
        assert keys == []


class TestGetCorsOrigins:
    """Test suite for get_cors_origins method."""

    def test_get_cors_origins_happy_path(self):
        """Test: Parse comma-separated CORS origins correctly.

        Verifies that comma-separated origins are parsed into a list.
        """
        settings = Settings(cors_origins="https://example.com,https://app.example.com")
        origins = settings.get_cors_origins()
        assert origins == ["https://example.com", "https://app.example.com"]

    def test_get_cors_origins_wildcard(self):
        """Test: Wildcard (*) is preserved as single-item list.

        Verifies that "*" is returned as ["*"] for allow-all origins.
        """
        settings = Settings(cors_origins="*")
        origins = settings.get_cors_origins()
        assert origins == ["*"]

    def test_get_cors_origins_empty_string(self):
        """Test: Empty string defaults to wildcard.

        Edge case: Empty string should default to ["*"].
        """
        settings = Settings(cors_origins="")
        origins = settings.get_cors_origins()
        assert origins == ["*"]

    def test_get_cors_origins_invalid_origins_filtered(self):
        """Test: Invalid origin formats are filtered out.

        Edge case: Origins that don't start with http:// or https://
        should be filtered out, defaulting to ["*"] if none valid.
        """
        settings = Settings(cors_origins="invalid-origin,https://valid.com")
        origins = settings.get_cors_origins()
        assert origins == ["https://valid.com"]

    def test_get_cors_origins_all_invalid_defaults_to_wildcard(self):
        """Test: All invalid origins default to wildcard.

        Edge case: If all origins are invalid, should default to ["*"].
        """
        settings = Settings(cors_origins="invalid1,invalid2")
        origins = settings.get_cors_origins()
        assert origins == ["*"]

    def test_get_cors_origins_production_warning(self, env_vars):
        """Test: Production mode warns about wildcard CORS.

        Verifies that production mode logs a warning when CORS is "*".
        """
        env_vars(DEV_MODE="false")
        settings = Settings(api_keys="key1,key2", cors_origins="*", dev_mode=False)
        with patch("app.core.config.logger") as mock_logger:
            origins = settings.get_cors_origins()
            assert origins == ["*"]
            # Should log error in production
            mock_logger.error.assert_called()

    def test_get_cors_origins_strict_check_raises(self, env_vars):
        """Test: Strict CORS check raises ValueError in production.

        Verifies that when strict_cors_check is True and CORS is "*"
        in production, ValueError is raised.
        """
        env_vars(DEV_MODE="false", STRICT_CORS_CHECK="true")
        settings = Settings(
            api_keys="key1,key2", cors_origins="*", strict_cors_check=True, dev_mode=False
        )
        with pytest.raises(ValueError, match="CORS must be restricted"):
            settings.get_cors_origins()

    def test_get_cors_origins_with_whitespace(self):
        """Test: Strip whitespace from CORS origins.

        Edge case: Origins with leading/trailing whitespace should be
        stripped during parsing.
        """
        settings = Settings(cors_origins="  https://example.com  ,  https://app.com  ")
        origins = settings.get_cors_origins()
        assert origins == ["https://example.com", "https://app.com"]


class TestIsProduction:
    """Test suite for is_production method."""

    def test_is_production_with_api_keys(self):
        """Test: Production mode when API keys are configured.

        Verifies that production mode is True when API keys exist
        and DEV_MODE is not set.
        """
        settings = Settings(api_keys="key1,key2", dev_mode=False)
        with patch("app.core.config.os.getenv", return_value="false"):
            assert settings.is_production() is True

    def test_is_production_dev_mode_env_var(self, env_vars):
        """Test: DEV_MODE environment variable disables production.

        Verifies that DEV_MODE="true" environment variable overrides
        settings.dev_mode.
        """
        env_vars(DEV_MODE="true")
        settings = Settings(api_keys="key1,key2", dev_mode=False)
        assert settings.is_production() is False

    def test_is_production_dev_mode_setting(self):
        """Test: dev_mode setting disables production.

        Verifies that settings.dev_mode=True disables production mode.
        """
        settings = Settings(api_keys="key1,key2", dev_mode=True)
        with patch("app.core.config.os.getenv", return_value="false"):
            assert settings.is_production() is False

    def test_is_production_no_api_keys(self):
        """Test: No API keys means not production.

        Edge case: Without API keys, should not be production even
        if DEV_MODE is not set.
        """
        settings = Settings(api_keys="", dev_mode=False)
        with patch("app.core.config.os.getenv", return_value="false"):
            assert settings.is_production() is False

    def test_is_production_env_var_takes_precedence(self, env_vars):
        """Test: Environment variable takes precedence over setting.

        Verifies that DEV_MODE environment variable overrides
        settings.dev_mode value.
        """
        env_vars(DEV_MODE="true")
        settings = Settings(api_keys="key1,key2", dev_mode=False)
        assert settings.is_production() is False


class TestValidateProductionSettings:
    """Test suite for validate_production_settings method."""

    def test_validate_production_settings_dev_mode_skips(self):
        """Test: Validation skipped in development mode.

        Verifies that validation is skipped when not in production mode.
        """
        settings = Settings(api_keys="", dev_mode=True)
        # Should not raise
        settings.validate_production_settings()

    def test_validate_production_settings_valid(self):
        """Test: Valid production settings pass validation.

        Verifies that valid production settings (API keys and CORS)
        pass validation.
        """
        settings = Settings(
            api_keys="key1,key2",
            cors_origins="https://example.com",
            dev_mode=False,
            strict_cors_check=False,
        )
        with patch("app.core.config.os.getenv", return_value="false"):
            # Should not raise
            settings.validate_production_settings()

    def test_validate_production_settings_no_api_keys_raises(self):
        """Test: Missing API keys in production raises ValueError.

        Verifies that production mode without API keys raises ValueError.
        """
        settings = Settings(api_keys="", cors_origins="https://example.com", dev_mode=False)
        with patch("app.core.config.os.getenv", return_value="false"):
            # Mock is_production method at the class level
            with patch.object(Settings, "is_production", return_value=True):
                with pytest.raises(ValueError, match="API keys must be configured"):
                    settings.validate_production_settings()

    def test_validate_production_settings_wildcard_cors_strict_raises(self):
        """Test: Wildcard CORS with strict check raises ValueError.

        Verifies that production mode with wildcard CORS and strict
        check enabled raises ValueError.
        """
        settings = Settings(
            api_keys="key1,key2", cors_origins="*", dev_mode=False, strict_cors_check=True
        )
        with patch("app.core.config.os.getenv", return_value="false"):
            with pytest.raises(ValueError, match="CORS must be restricted"):
                settings.validate_production_settings()


class TestGetAllowedFormats:
    """Test suite for format parsing methods."""

    def test_get_allowed_audio_formats_happy_path(self):
        """Test: Parse allowed audio formats correctly.

        Verifies that comma-separated audio formats are parsed into a set.
        """
        settings = Settings(allowed_audio_formats="mp3,wav,m4a")
        formats = settings.get_allowed_audio_formats()
        assert formats == {"mp3", "wav", "m4a"}

    def test_get_allowed_audio_formats_default(self):
        """Test: Default audio formats when empty.

        Edge case: Empty string should return default formats.
        """
        settings = Settings(allowed_audio_formats="")
        formats = settings.get_allowed_audio_formats()
        assert formats == {"mp3", "wav", "m4a", "flac", "ogg"}

    def test_get_allowed_audio_formats_case_insensitive(self):
        """Test: Audio formats are converted to lowercase.

        Verifies that formats are normalized to lowercase.
        """
        settings = Settings(allowed_audio_formats="MP3,WAV,M4A")
        formats = settings.get_allowed_audio_formats()
        assert formats == {"mp3", "wav", "m4a"}

    def test_get_allowed_video_formats_happy_path(self):
        """Test: Parse allowed video formats correctly.

        Verifies that comma-separated video formats are parsed into a set.
        """
        settings = Settings(allowed_video_formats="mp4,mkv,avi")
        formats = settings.get_allowed_video_formats()
        assert formats == {"mp4", "mkv", "avi"}

    def test_get_allowed_video_formats_default(self):
        """Test: Default video formats when empty.

        Edge case: Empty string should return default formats.
        """
        settings = Settings(allowed_video_formats="")
        formats = settings.get_allowed_video_formats()
        assert formats == {"mp4", "mkv", "avi", "mov", "webm"}

    def test_get_allowed_video_formats_case_insensitive(self):
        """Test: Video formats are converted to lowercase.

        Verifies that formats are normalized to lowercase.
        """
        settings = Settings(allowed_video_formats="MP4,MKV,AVI")
        formats = settings.get_allowed_video_formats()
        assert formats == {"mp4", "mkv", "avi"}


class TestGetLanguages:
    """Test suite for language parsing methods."""

    def test_get_preferred_languages_happy_path(self):
        """Test: Parse preferred languages correctly.

        Verifies that comma-separated languages are parsed into a list.
        """
        settings = Settings(preferred_languages="en,es,fr")
        languages = settings.get_preferred_languages()
        assert languages == ["en", "es", "fr"]

    def test_get_preferred_languages_default(self):
        """Test: Default preferred languages when empty.

        Edge case: Empty string should return default languages.
        """
        settings = Settings(preferred_languages="")
        languages = settings.get_preferred_languages()
        assert languages == ["en", "es", "fr", "de", "it", "pt", "ru"]

    def test_get_common_languages_happy_path(self):
        """Test: Parse common languages correctly.

        Verifies that comma-separated common languages are parsed.
        """
        settings = Settings(common_languages="en,es,fr,de")
        languages = settings.get_common_languages()
        assert languages == ["en", "es", "fr", "de"]

    def test_get_common_languages_default(self):
        """Test: Default common languages when empty.

        Edge case: Empty string should return default languages.
        """
        settings = Settings(common_languages="")
        languages = settings.get_common_languages()
        expected = ["en", "es", "fr", "de", "it", "pt", "ru", "ja", "ko", "zh-Hans", "zh-Hant"]
        assert languages == expected

    def test_get_languages_with_whitespace(self):
        """Test: Strip whitespace from language codes.

        Edge case: Languages with whitespace should be stripped.
        """
        settings = Settings(preferred_languages="  en  ,  es  ,  fr  ")
        languages = settings.get_preferred_languages()
        assert languages == ["en", "es", "fr"]


class TestSettingsBoundaryValues:
    """Test suite for boundary value analysis."""

    def test_rate_limit_minimum_value(self):
        """Test: Minimum rate limit value (boundary).

        Boundary case: Very small rate limit value should be accepted.
        """
        settings = Settings(rate_limit_per_minute=1)
        assert settings.rate_limit_per_minute == 1

    def test_rate_limit_maximum_value(self):
        """Test: Maximum rate limit value (boundary).

        Boundary case: Very large rate limit value should be accepted.
        """
        settings = Settings(rate_limit_per_minute=1000000)
        assert settings.rate_limit_per_minute == 1000000

    def test_max_video_duration_zero(self):
        """Test: Zero max video duration (boundary).

        Boundary case: Zero duration should be accepted (though not practical).
        """
        settings = Settings(max_video_duration_seconds=0)
        assert settings.max_video_duration_seconds == 0

    def test_max_video_duration_very_large(self):
        """Test: Very large max video duration (boundary).

        Boundary case: Very large duration value should be accepted.
        """
        settings = Settings(max_video_duration_seconds=86400)  # 24 hours
        assert settings.max_video_duration_seconds == 86400

    def test_cache_max_size_zero(self):
        """Test: Zero cache max size (boundary).

        Boundary case: Zero cache size should be accepted.
        """
        settings = Settings(cache_max_size=0)
        assert settings.cache_max_size == 0

    def test_cache_max_size_very_large(self):
        """Test: Very large cache max size (boundary).

        Boundary case: Very large cache size should be accepted.
        """
        settings = Settings(cache_max_size=1000000)
        assert settings.cache_max_size == 1000000
