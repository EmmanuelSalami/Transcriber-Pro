# Test Suite Documentation

## Table of Contents

1. [Overview](#overview)
2. [Installation Instructions](#installation-instructions)
3. [Configuration Options](#configuration-options)
4. [API Reference](#api-reference)
5. [Usage Examples](#usage-examples)
6. [Troubleshooting Guide](#troubleshooting-guide)
7. [FAQ Section](#faq-section)
8. [Test Coverage](#test-coverage)

---

## Overview

### Target Audience

This documentation is designed for:
- **Developers** working on the transcription service codebase
- **QA Engineers** responsible for test execution and maintenance
- **DevOps Engineers** setting up CI/CD pipelines
- **Contributors** adding new features or fixing bugs

### Test Infrastructure

The test suite is built on **pytest**, a powerful Python testing framework that provides:

- **Comprehensive test coverage** across all application layers (API, services, models, utilities)
- **Fixture-based architecture** for reusable test data and mocks
- **Async test support** via `pytest-asyncio` for testing asynchronous operations
- **Parallel execution** capabilities using `pytest-xdist` for faster test runs
- **Mock-based isolation** to prevent external dependencies (Redis, S3, ML models) from affecting tests
- **Automatic cleanup** of temporary files and directories

### Test Organization

The test suite follows a modular structure mirroring the application architecture:

```
tests/
├── conftest.py              # Global pytest configuration and fixtures
├── fixtures/                # Reusable test fixtures organized by domain
│   ├── api.py              # API endpoint fixtures
│   ├── core.py             # Core module fixtures (auth, config, etc.)
│   ├── jobs.py             # Job management fixtures
│   ├── media.py            # Media handling fixtures
│   ├── models.py           # Data model fixtures
│   ├── transcription.py    # Transcription service fixtures
│   ├── infrastructure.py   # Infrastructure service fixtures
│   └── utils.py            # Utility function fixtures
├── test_api/               # API endpoint tests
├── test_core/              # Core functionality tests
├── test_models/            # Data model tests
├── test_services/           # Service layer tests
└── test_utils/             # Utility function tests
```

### Key Features

1. **Global Mocking**: Expensive services (WhisperService, Redis, S3) are automatically mocked at the pytest configuration level to prevent initialization overhead
2. **Session-scoped Cleanup**: Temporary directories are cleaned up after all tests complete (not after each test) for better performance
3. **Type Safety**: Tests leverage Python's type system and TypedDict for better code quality
4. **Comprehensive Coverage**: Tests cover happy paths, edge cases, error conditions, and boundary values

### Prerequisites

- Python 3.11 or higher (up to 3.14)
- Poetry for dependency management
- Understanding of pytest framework
- Basic knowledge of FastAPI and async Python

---

## Installation Instructions

### Step 1: Install Dependencies

The test suite uses Poetry for dependency management. Install all dependencies including dev dependencies:

```bash
# Install all dependencies (including dev dependencies)
poetry install
```

This will install:
- `pytest` - Core testing framework
- `pytest-cov` - Coverage reporting
- `pytest-asyncio` - Async test support
- `pytest-xdist` - Parallel test execution
- `httpx` - HTTP client for testing
- `black`, `ruff`, `mypy` - Code quality tools

### Step 2: Verify Installation

Run a simple test to verify everything is set up correctly:

```bash
# Run a single test file
poetry run pytest tests/test_models/test_types.py -v
```

Expected output should show passing tests without errors.

### Step 3: (Optional) Install Pre-commit Hooks

For code quality enforcement:

```bash
# Install pre-commit hooks (if configured)
pre-commit install
```

### Common Installation Issues

**Issue**: `poetry install` fails with dependency conflicts
- **Solution**: Update Poetry: `pip install --upgrade poetry`
- **Solution**: Clear Poetry cache: `poetry cache clear pypi --all`

**Issue**: Tests fail with import errors
- **Solution**: Ensure you're in the project root directory
- **Solution**: Verify `pythonpath` is set correctly in `pyproject.toml` (should include `.`)

**Issue**: Async tests fail with "Event loop is closed" errors
- **Solution**: Ensure `pytest-asyncio` is installed and `asyncio_mode = "auto"` is set in `pyproject.toml`

---

## Configuration Options

### Pytest Configuration

The pytest configuration is defined in `pyproject.toml` under `[tool.pytest.ini_options]`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]                    # Directory containing tests
pythonpath = ["."]                        # Add project root to Python path
asyncio_mode = "auto"                    # Automatic async test detection
addopts = [
    "--strict-markers",                   # Require marker registration
    "--disable-warnings",                 # Suppress warnings in output
    "-ra",                                # Show short test summary
    "--tb=short",                         # Short traceback format
]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: marks tests as integration tests",
]
```

### Environment Variables

Tests use mocked services by default, but you can configure behavior via environment variables:

```bash
# Disable Redis in tests (default behavior)
REDIS_ENABLED=false

# Set temporary storage directory
TEMP_STORE_DIR=/tmp/test_temp_store

# Enable verbose logging
LOG_LEVEL=DEBUG
```

### Test Markers

Use markers to categorize and selectively run tests:

```python
@pytest.mark.slow
def test_expensive_operation():
    """This test will be skipped with -m 'not slow'"""
    pass

@pytest.mark.integration
def test_external_service():
    """This test requires external services"""
    pass
```

**Usage**:
```bash
# Skip slow tests
pytest -m "not slow"

# Run only integration tests
pytest -m "integration"

# Run tests excluding both slow and integration
pytest -m "not slow and not integration"
```

### Coverage Configuration

Coverage reporting is configured via `pytest-cov`:

```bash
# Generate coverage report
pytest --cov=app --cov-report=html --cov-report=term

# Generate coverage report with minimum threshold
pytest --cov=app --cov-fail-under=80
```

### Parallel Execution

Run tests in parallel for faster execution:

```bash
# Auto-detect CPU count and run in parallel
pytest -n auto

# Run with specific number of workers
pytest -n 4
```

**Note**: Some tests may not be suitable for parallel execution if they modify shared state. Use test isolation best practices.

---

## API Reference

### Core Fixtures

#### `conftest.py` Fixtures

**`cleanup_temp_directories`** (session-scoped, autouse)
- Automatically cleans up `temp_uploads` and `temp_downloads` directories after all tests
- No parameters required
- Usage: Automatic (autouse fixture)

**`job_manager_mock`** (function-scoped)
- Provides a mocked JobManager instance
- Prevents real Redis connections during tests
- Usage: Inject as parameter in test functions

```python
def test_something(job_manager_mock):
    # job_manager_mock is available
    assert job_manager_mock.create_job is not None
```

### Fixture Modules

#### `fixtures/core.py`

**`mock_settings`**
- Mock Settings instance with default test values
- Includes API keys, Whisper model settings, processing thresholds
- Usage: Inject in tests that need configuration

**`mock_settings_dev_mode`**
- Settings with dev mode enabled (no API key required)
- Usage: Tests for development mode behavior

**`mock_settings_production`**
- Settings for production mode testing
- Usage: Tests for production-specific behavior

**`mock_request`**
- Mock FastAPI Request object
- Usage: API endpoint tests

**`mock_http_credentials`**
- Mock HTTPAuthorizationCredentials
- Usage: Authentication tests

#### `fixtures/api.py`

**`mock_request`** / **`mock_request_no_auth`**
- FastAPI Request objects with/without Authorization header
- Usage: API endpoint authentication tests

**`mock_upload_file`** / **`mock_upload_file_large`** / **`mock_upload_file_invalid_type`**
- Mock UploadFile objects for different scenarios
- Usage: File upload endpoint tests

**`sample_transcription_result_sync`** / **`sample_transcription_result_async`**
- Sample transcription results for synchronous/asynchronous processing
- Usage: Testing transcription response handling

**`valid_youtube_urls`** / **`invalid_youtube_urls`**
- Lists of valid/invalid YouTube URLs
- Usage: URL validation tests

#### `fixtures/jobs.py`

**`mock_redis_client`**
- Mock Redis client with common methods stubbed
- Usage: Tests that interact with Redis

**`mock_settings_redis_disabled`** / **`mock_settings_redis_enabled`**
- Settings with Redis disabled/enabled
- Usage: Testing Redis fallback behavior

**`sample_job_data`** / **`sample_job_data_completed`** / **`sample_job_data_failed`**
- Sample job data in different states
- Usage: Job management tests

**`temp_store_dir`**
- Temporary directory for job storage (uses pytest's tmp_path)
- Usage: Tests that need file system operations

### Pytest Hooks

**`pytest_configure(config)`**
- Called before test collection
- Sets up global mocks for WhisperService, Redis, and other expensive services
- Prevents expensive initialization during test imports

**`pytest_sessionfinish(session, exitstatus)`**
- Called after all tests complete
- Cleans up global patches

### Test Utilities

#### Creating Custom Fixtures

```python
import pytest
from unittest.mock import Mock

@pytest.fixture
def my_custom_fixture():
    """Create a custom fixture for your tests."""
    mock_service = Mock()
    mock_service.method.return_value = "result"
    return mock_service
```

#### Using Fixtures in Tests

```python
def test_example(mock_settings, mock_request):
    """Example test using multiple fixtures."""
    # Fixtures are automatically injected
    assert mock_settings.api_keys is not None
    assert mock_request.method == "GET"
```

#### Async Test Fixtures

```python
@pytest.fixture
async def async_fixture():
    """Async fixture example."""
    async_service = AsyncMock()
    await async_service.initialize()
    yield async_service
    await async_service.cleanup()
```

---

## Usage Examples

### Running Tests

#### Basic Test Execution

```bash
# Run all tests
poetry run pytest

# Run with verbose output
poetry run pytest -v

# Run specific test file
poetry run pytest tests/test_models/test_types.py

# Run specific test class
poetry run pytest tests/test_models/test_types.py::TestErrorDict

# Run specific test method
poetry run pytest tests/test_models/test_types.py::TestErrorDict::test_error_dict_valid
```

#### Advanced Test Execution

```bash
# Run tests in parallel (faster)
poetry run pytest -n auto

# Run only fast tests (exclude slow markers)
poetry run pytest -m "not slow"

# Run with coverage report
poetry run pytest --cov=app --cov-report=term-missing

# Run tests matching a pattern
poetry run pytest -k "youtube"

# Stop on first failure
poetry run pytest -x

# Show local variables in traceback
poetry run pytest -l
```

### Writing Tests

#### Basic Unit Test

```python
"""Example unit test for a utility function."""

def test_format_duration():
    """Test: Format duration correctly."""
    from app.utils.formatters import format_duration
    
    result = format_duration(125.5)
    assert result == "2:05"
```

#### Test with Fixtures

```python
"""Example test using fixtures."""

def test_api_endpoint(mock_request, mock_settings):
    """Test: API endpoint handles request correctly."""
    from app.api.v1.endpoints.youtube import transcribe_youtube
    
    # Use fixtures in test
    assert mock_request.method == "POST"
    assert len(mock_settings.get_api_keys()) > 0
```

#### Async Test

```python
"""Example async test."""

import pytest

@pytest.mark.asyncio
async def test_async_transcription(mock_whisper_service):
    """Test: Async transcription completes successfully."""
    from app.services.transcription.whisper_service import WhisperService
    
    result = await mock_whisper_service.transcribe_async("/path/to/audio.wav")
    assert result is not None
```

#### Test with Mocking

```python
"""Example test with mocking."""

from unittest.mock import Mock, patch

def test_service_with_mock():
    """Test: Service uses mocked dependency."""
    with patch("app.services.transcription.whisper_service.WhisperService") as mock_whisper:
        mock_instance = Mock()
        mock_instance.transcribe.return_value = {"text": "Hello"}
        mock_whisper.get_instance.return_value = mock_instance
        
        # Test code that uses WhisperService
        service = TranscriptionService()
        result = service.transcribe("audio.wav")
        
        assert result["text"] == "Hello"
```

#### Test Class Structure

```python
"""Example test class following project conventions."""

class TestMyFeature:
    """Test suite for MyFeature.
    
    Tests cover:
    1. Happy path scenarios
    2. Edge cases
    3. Error conditions
    4. Boundary value analysis
    """
    
    def test_happy_path(self, fixture1, fixture2):
        """Test: Happy path - feature works correctly."""
        # Arrange
        input_data = {"key": "value"}
        
        # Act
        result = my_function(input_data)
        
        # Assert
        assert result["status"] == "success"
    
    def test_edge_case_empty_input(self):
        """Test: Edge case - empty input handled gracefully."""
        result = my_function({})
        assert result["status"] == "error"
    
    def test_error_condition_invalid_input(self):
        """Test: Error condition - invalid input raises exception."""
        with pytest.raises(ValueError):
            my_function(None)
```

#### Integration Test Example

```python
"""Example integration test."""

import pytest
from fastapi.testclient import TestClient

@pytest.mark.integration
def test_api_integration():
    """Test: Full API integration."""
    from app.main import app
    
    client = TestClient(app)
    response = client.post(
        "/v1/transcriptions/youtube",
        json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        headers={"Authorization": "Bearer test-key"}
    )
    
    assert response.status_code == 200
    assert "jobId" in response.json()
```

### Test Patterns

#### Testing Async Functions

```python
@pytest.mark.asyncio
async def test_async_function():
    """Always use @pytest.mark.asyncio for async tests."""
    result = await async_function()
    assert result is not None
```

#### Testing Exceptions

```python
def test_exception_handling():
    """Test that exceptions are raised correctly."""
    with pytest.raises(ValueError, match="Invalid input"):
        function_that_raises("invalid")
```

#### Testing with Temporary Files

```python
def test_file_operations(tmp_path):
    """Use tmp_path fixture for temporary files."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")
    
    result = process_file(test_file)
    assert result == "content"
```

#### Parametrized Tests

```python
@pytest.mark.parametrize("input,expected", [
    ("hello", "HELLO"),
    ("world", "WORLD"),
    ("", ""),
])
def test_uppercase(input, expected):
    """Test multiple inputs at once."""
    assert input.upper() == expected
```

---

## Troubleshooting Guide

### Common Issues and Solutions

#### Issue: Tests Fail with Import Errors

**Symptoms**:
```
ImportError: cannot import name 'X' from 'app.module'
```

**Solutions**:
1. Verify you're running tests from the project root directory
2. Check that `pythonpath = ["."]` is set in `pyproject.toml`
3. Ensure all dependencies are installed: `poetry install`
4. Check for circular imports in the codebase

#### Issue: Async Tests Hang or Fail

**Symptoms**:
```
RuntimeError: Event loop is closed
asyncio.exceptions.CancelledError
```

**Solutions**:
1. Ensure `asyncio_mode = "auto"` in `pyproject.toml`
2. Use `@pytest.mark.asyncio` decorator on async test functions
3. Don't create event loops manually - let pytest-asyncio handle it
4. Ensure async fixtures use `yield` instead of `return` if cleanup is needed

**Example Fix**:
```python
# ❌ Wrong
@pytest.mark.asyncio
async def test_bad():
    loop = asyncio.get_event_loop()  # Don't do this
    result = await function()

# ✅ Correct
@pytest.mark.asyncio
async def test_good():
    result = await function()  # Let pytest handle the loop
```

#### Issue: Mocks Not Working as Expected

**Symptoms**:
- Mocks return `MagicMock` objects instead of expected values
- Patches don't seem to apply

**Solutions**:
1. Ensure patches are applied before imports:
   ```python
   with patch("module.Class") as mock:
       from module import Class  # Import after patch
   ```

2. Use `spec` parameter for better mock behavior:
   ```python
   mock = Mock(spec=RealClass)
   ```

3. Check patch target path - it must match where the object is used, not where it's defined:
   ```python
   # If MyClass is used in app.service, patch there:
   patch("app.service.MyClass")  # ✅ Correct
   # Not:
   patch("app.models.MyClass")  # ❌ Wrong
   ```

#### Issue: Fixtures Not Available

**Symptoms**:
```
fixture 'my_fixture' not found
```

**Solutions**:
1. Ensure fixture is defined in `conftest.py` or imported in `fixtures/__init__.py`
2. Check fixture scope - session-scoped fixtures may not be available in function-scoped tests
3. Verify fixture name matches exactly (case-sensitive)
4. Ensure fixture file is imported in `tests/fixtures/__init__.py`

#### Issue: Tests Pass Individually but Fail in Suite

**Symptoms**:
- Test passes when run alone: `pytest tests/test_file.py::test_name`
- Test fails when run with others: `pytest tests/`

**Solutions**:
1. Check for shared state between tests - use function-scoped fixtures
2. Ensure proper cleanup in fixtures:
   ```python
   @pytest.fixture
   def my_fixture():
       # Setup
       resource = create_resource()
       yield resource
       # Cleanup
       cleanup_resource(resource)
   ```

3. Check for global variables or singletons that retain state
4. Use `pytest --forked` to run tests in separate processes (requires pytest-forked)

#### Issue: Coverage Report Shows 0% Coverage

**Symptoms**:
- Coverage report shows no files covered
- Coverage HTML shows empty report

**Solutions**:
1. Ensure you're running coverage on the correct package:
   ```bash
   pytest --cov=app  # Not --cov=tests
   ```

2. Check that source files are in the coverage path
3. Verify `__init__.py` files exist in package directories
4. Use `--cov-report=term-missing` to see which lines are missing

#### Issue: Parallel Tests Fail Randomly

**Symptoms**:
- Tests fail intermittently when run with `-n auto`
- Different tests fail on each run

**Solutions**:
1. Identify tests that modify shared state (files, databases, etc.)
2. Use function-scoped fixtures instead of session-scoped for mutable data
3. Ensure tests are properly isolated - no shared global state
4. Mark problematic tests to run serially:
   ```python
   @pytest.mark.no_parallel
   def test_that_modifies_shared_state():
       pass
   ```
   Then run: `pytest -n auto -m "not no_parallel"`

#### Issue: Temporary Files Not Cleaned Up

**Symptoms**:
- `temp_uploads` or `temp_downloads` directories accumulate files
- Disk space issues after running tests

**Solutions**:
1. The `cleanup_temp_directories` fixture should handle this automatically
2. If issues persist, manually clean:
   ```bash
   rm -rf temp_uploads temp_downloads
   ```

3. Check that the cleanup fixture is not disabled
4. Use `tmp_path` fixture for test-specific temporary files

#### Issue: Redis Connection Errors in Tests

**Symptoms**:
```
redis.exceptions.ConnectionError: Error connecting to Redis
```

**Solutions**:
1. Redis is automatically disabled in tests via `conftest.py`
2. If errors persist, ensure `mock_settings_redis_disabled` fixture is used
3. Check that patches in `pytest_configure` are applied correctly
4. Verify no real Redis connection attempts are made:
   ```python
   with patch("app.services.jobs.job_manager.redis.Redis"):
       # Test code
   ```

### Debugging Tips

#### Enable Verbose Output

```bash
# Maximum verbosity
pytest -vv

# Show print statements
pytest -s

# Show local variables in tracebacks
pytest -l
```

#### Run Tests with Debugger

```python
import pytest

def test_with_debugger():
    """Set breakpoint to debug."""
    import pdb; pdb.set_trace()
    # Your test code
```

#### Isolate Failing Test

```bash
# Run only the failing test
pytest tests/path/to/test.py::TestClass::test_method -vv

# Run with maximum output
pytest tests/path/to/test.py::TestClass::test_method -vv -s --tb=long
```

#### Check Fixture Values

```python
def test_debug_fixture(mock_settings):
    """Debug fixture values."""
    print(f"API Keys: {mock_settings.get_api_keys()}")
    print(f"Dev Mode: {mock_settings.dev_mode}")
    # Your test
```

---

## FAQ Section

### General Questions

**Q: Why are some services mocked globally in `conftest.py`?**  
A: Services like WhisperService and Redis are expensive to initialize (loading ML models, connecting to databases). Global mocking in `pytest_configure` prevents these initializations during test imports, making tests faster and more reliable.

**Q: Can I run tests without Poetry?**  
A: While possible, it's not recommended. Poetry ensures consistent dependency versions. If you must, install dependencies manually:
```bash
pip install pytest pytest-cov pytest-asyncio pytest-xdist httpx
```

**Q: How do I add a new test file?**  
A: Create a new file following the naming convention `test_*.py` in the appropriate directory. The file will be automatically discovered by pytest.

**Q: What's the difference between unit tests and integration tests?**  
A: Unit tests test individual components in isolation (mocked dependencies). Integration tests test multiple components working together. Use the `@pytest.mark.integration` marker for integration tests.

**Q: How do I test code that uses environment variables?**  
A: Use the `env_vars` fixture from `fixtures/core.py`:
```python
def test_with_env(env_vars):
    env_vars(API_KEY="test-key", DEBUG="true")
    # Your test code
```

### Fixture Questions

**Q: What's the difference between function-scoped and session-scoped fixtures?**  
A: Function-scoped fixtures are created fresh for each test (default). Session-scoped fixtures are created once for the entire test session. Use session scope for expensive setup that can be shared.

**Q: Can I use a fixture in another fixture?**  
A: Yes! Just inject it as a parameter:
```python
@pytest.fixture
def base_fixture():
    return {"key": "value"}

@pytest.fixture
def extended_fixture(base_fixture):
    base_fixture["extra"] = "data"
    return base_fixture
```

**Q: How do I create a fixture that needs cleanup?**  
A: Use `yield` instead of `return`:
```python
@pytest.fixture
def resource_with_cleanup():
    resource = create_resource()
    yield resource
    cleanup_resource(resource)  # Runs after test
```

**Q: Why do some fixtures use `SimpleNamespace` instead of `Mock`?**  
A: `SimpleNamespace` creates a real object with real attributes, avoiding issues where `Mock` objects auto-create attributes. Use it when you need real attribute access without method tracking.

### Async Testing Questions

**Q: Do I always need `@pytest.mark.asyncio` for async tests?**  
A: With `asyncio_mode = "auto"`, pytest should detect async functions automatically. However, it's good practice to include the marker for clarity and compatibility.

**Q: How do I test async context managers?**  
A: Use `async with` in your test:
```python
@pytest.mark.asyncio
async def test_async_context():
    async with async_context_manager() as resource:
        result = await resource.do_something()
        assert result is not None
```

**Q: Can I use async fixtures with sync tests?**  
A: No, async fixtures can only be used in async tests. Use sync fixtures or convert your test to async.

### Mocking Questions

**Q: Where should I patch - in the test or in a fixture?**  
A: For reusable mocks, use fixtures. For test-specific mocks, use patches in the test. Global mocks (like WhisperService) go in `conftest.py`.

**Q: How do I verify a mock was called with specific arguments?**  
A: Use `assert_called_with`:
```python
mock_service.method.assert_called_with(arg1="value", arg2=123)
```

**Q: What's the difference between `Mock`, `MagicMock`, and `AsyncMock`?**  
A: `Mock` is the base class. `MagicMock` auto-creates attributes/methods. `AsyncMock` is for async functions. Use `Mock(spec=RealClass)` for type safety.

**Q: How do I mock a method that's called multiple times with different returns?**  
A: Use `side_effect`:
```python
mock.method.side_effect = [return1, return2, return3]
# Or with a function:
mock.method.side_effect = lambda x: x * 2
```

### Performance Questions

**Q: How can I make tests run faster?**  
A: 
1. Use `pytest -n auto` for parallel execution
2. Mark slow tests and skip them: `pytest -m "not slow"`
3. Use session-scoped fixtures for expensive setup
4. Ensure proper mocking to avoid real I/O operations

**Q: Why are my tests slow?**  
A: Common causes:
- Real network calls (should be mocked)
- Real file I/O (use `tmp_path` or mocks)
- Loading ML models (should be mocked)
- Database connections (should be mocked)
- Not using parallel execution

**Q: Should I use `pytest-xdist` for all tests?**  
A: Most tests benefit from parallel execution. However, tests that modify shared state or use session-scoped fixtures with mutable data may need to run serially.

### Coverage Questions

**Q: What's a good coverage target?**  
A: Aim for 80%+ coverage, but focus on critical paths. 100% coverage doesn't guarantee bug-free code.

**Q: How do I exclude files from coverage?**  
A: Add to `.coveragerc` or use `# pragma: no cover` comments:
```python
def function_not_tested():  # pragma: no cover
    pass
```

**Q: Why does my coverage report show uncovered lines I know are tested?**  
A: 
1. Check that you're running coverage on the source package (`--cov=app`)
2. Ensure tests actually execute those lines (use `--cov-report=term-missing`)
3. Verify imports and initialization code is executed

### Best Practices

**Q: What makes a good test?**  
A: A good test is:
- **Fast**: Completes in milliseconds
- **Isolated**: Doesn't depend on other tests
- **Repeatable**: Same result every time
- **Clear**: Easy to understand what's being tested
- **Focused**: Tests one thing

**Q: How should I name my tests?**  
A: Use descriptive names following the pattern:
```python
def test_feature_scenario_expected_result():
    """Test: Brief description of what's being tested."""
    pass
```

**Q: Should I test private methods?**  
A: Generally, no. Test public interfaces. However, if a private method has complex logic, consider extracting it to a separate function or testing it indirectly through public methods.

**Q: How do I test error handling?**  
A: Use `pytest.raises`:
```python
def test_error_handling():
    with pytest.raises(ValueError, match="error message"):
        function_that_raises_error()
```

**Q: When should I use parametrized tests?**  
A: When testing the same logic with multiple inputs:
```python
@pytest.mark.parametrize("input,expected", [
    (1, 2),
    (2, 4),
    (3, 6),
])
def test_double(input, expected):
    assert input * 2 == expected
```

---

## Test Coverage

### Current Coverage Status

**Overall Coverage: 77%** (as of latest test run)


### Coverage by Module

#### High Coverage Modules (90%+)
- `app/models/schemas.py` - **100%** (197 statements)
- `app/models/types.py` - **100%** (5 statements)
- `app/core/auth.py` - **100%** (28 statements)
- `app/core/error_handlers.py` - **100%** (61 statements)
- `app/core/exceptions.py` - **100%** (34 statements)
- `app/api/v1/endpoints/metrics.py` - **100%** (7 statements)
- `app/api/v1/endpoints/workers.py` - **100%** (80 statements)
- `app/services/media/audio_download_service.py` - **99%** (81 statements, 1 missed)
- `app/core/config.py` - **99%** (204 statements, 2 missed)
- `app/api/v1/endpoints/youtube.py` - **97%** (65 statements, 2 missed)
- `app/services/infrastructure/cost_control_service.py` - **97%** (117 statements, 4 missed)
- `app/services/transcription/whisper_service.py` - **90%** (489 statements, 48 missed)
- `app/services/infrastructure/observability_service.py` - **91%** (93 statements, 8 missed)
- `app/services/infrastructure/webhook_service.py` - **91%** (91 statements, 8 missed)

#### Medium Coverage Modules (70-89%)
- `app/services/media/media_validation.py` - **88%** (153 statements, 18 missed)
- `app/services/jobs/queue_service.py` - **88%** (164 statements, 20 missed)
- `app/api/v1/endpoints/jobs.py` - **88%** (51 statements, 6 missed)
- `app/api/v1/endpoints/media.py` - **91%** (68 statements, 6 missed)
- `app/utils/formatters.py` - **86%** (71 statements, 10 missed)
- `app/utils/url_validation.py` - **98%** (61 statements, 1 missed)
- `app/utils/youtube.py` - **96%** (52 statements, 2 missed)
- `app/core/middleware.py` - **98%** (50 statements, 1 missed)
- `app/services/transcription/transcription_service.py` - **74%** (205 statements, 54 missed)
- `app/services/jobs/worker_manager.py` - **75%** (237 statements, 60 missed)
- `app/services/media/file_storage.py` - **74%** (121 statements, 32 missed)

#### Low Coverage Modules (<70%)
- `app/services/jobs/job_manager.py` - **58%** (420 statements, 176 missed)
- `app/services/media/media_download_service.py` - **63%** (235 statements, 86 missed)
- `app/services/media/media_endpoint_service.py` - **43%** (291 statements, 166 missed)
- `app/services/media/s3_storage_service.py` - **59%** (244 statements, 99 missed)
- `app/services/transcription/youtube_captions.py` - **55%** (316 statements, 142 missed)
- `app/core/startup.py` - **73%** (92 statements, 25 missed)
- `app/utils/config_utils.py` - **32%** (38 statements, 26 missed)
- `app/main.py` - **0%** (66 statements, 66 missed) - *Not tested (application entry point)*

### Generating Coverage Reports

```bash
# Generate terminal coverage report
poetry run pytest --cov=app --cov-report=term-missing

# Generate HTML coverage report (opens in browser)
poetry run pytest --cov=app --cov-report=html
# Then open: htmlcov/index.html

# Generate both terminal and HTML reports
poetry run pytest --cov=app --cov-report=term-missing --cov-report=html

# Generate coverage with minimum threshold (fails if below threshold)
poetry run pytest --cov=app --cov-fail-under=77
```

#### Coverage Best Practices

1. **Focus on Critical Paths**: Prioritize testing business logic over utility functions
2. **Test Edge Cases**: Coverage numbers don't tell the whole story - test error conditions
3. **Avoid False Coverage**: Don't write tests just to increase numbers - ensure they test meaningful behavior
4. **Use Branch Coverage**: Enable branch coverage to catch untested code paths:
   ```bash
   pytest --cov=app --cov-branch
   ```
5. **Exclude Appropriate Code**: Some code shouldn't be tested (e.g., `main.py`, debug code):
   ```python
   # pragma: no cover
   def debug_function():
       pass
   ```

### Coverage Exclusions

Some files/modules are intentionally excluded from coverage:

- `app/main.py` - Application entry point (integration tested separately)
- Debug/development-only code marked with `# pragma: no cover`
- Type stubs and `__init__.py` files with only imports

### Monitoring Coverage Trends

Track coverage over time to ensure it doesn't regress:

```bash
# Generate coverage report and save to file
poetry run pytest --cov=app --cov-report=term > coverage_report.txt

# Compare with previous runs
diff coverage_report.txt previous_coverage_report.txt
```

---

## Additional Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
- [Python unittest.mock Documentation](https://docs.python.org/3/library/unittest.mock.html)
- [FastAPI Testing Guide](https://fastapi.tiangolo.com/tutorial/testing/)

---

## Contributing

When adding new tests:

1. Follow the existing test structure and naming conventions
2. Add appropriate fixtures if reusable test data is needed
3. Include docstrings explaining what's being tested
4. Cover happy paths, edge cases, and error conditions
5. Ensure tests are fast and isolated
6. Update this documentation if adding new patterns or fixtures

