"""Fixtures for testing media services."""

import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi import UploadFile

from app.services.media.media_validation import MediaMetadata


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_audio_dir(temp_dir):
    """Create a temporary audio directory."""
    audio_dir = temp_dir / "temp_audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    return audio_dir


@pytest.fixture
def temp_uploads_dir(temp_dir):
    """Create a temporary uploads directory."""
    uploads_dir = temp_dir / "temp_uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    return uploads_dir


@pytest.fixture
def temp_downloads_dir(temp_dir):
    """Create a temporary downloads directory."""
    downloads_dir = temp_dir / "temp_downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)
    return downloads_dir


@pytest.fixture
def sample_audio_file(temp_dir):
    """Create a sample audio file for testing."""
    audio_file = temp_dir / "test_audio.mp3"
    # Create a minimal valid MP3 file (just header bytes)
    with open(audio_file, "wb") as f:
        # MP3 header bytes
        f.write(b"\xff\xfb\x90\x00")
        f.write(b"test audio content" * 100)
    return audio_file


@pytest.fixture
def sample_video_file(temp_dir):
    """Create a sample video file for testing."""
    video_file = temp_dir / "test_video.mp4"
    # Create a minimal file
    with open(video_file, "wb") as f:
        f.write(b"test video content" * 1000)
    return video_file


@pytest.fixture
def sample_wav_file(temp_dir):
    """Create a sample WAV file for testing."""
    wav_file = temp_dir / "test_audio.wav"
    # Create a minimal WAV file header
    with open(wav_file, "wb") as f:
        # WAV header
        f.write(b"RIFF")
        f.write((36).to_bytes(4, "little"))  # File size
        f.write(b"WAVE")
        f.write(b"fmt ")
        f.write((16).to_bytes(4, "little"))  # Format chunk size
        f.write(b"test audio content" * 100)
    return wav_file


@pytest.fixture
def mock_upload_file_mp3():
    """Create a mock UploadFile for MP3."""

    async def async_read():
        return b"test audio content" * 1000

    file = Mock(spec=UploadFile)
    file.filename = "test_audio.mp3"
    file.content_type = "audio/mpeg"
    file.size = 1024 * 1024  # 1MB
    file.read = async_read
    return file


@pytest.fixture
def mock_upload_file_wav():
    """Create a mock UploadFile for WAV."""

    async def async_read():
        return b"test wav content" * 1000

    file = Mock(spec=UploadFile)
    file.filename = "test_audio.wav"
    file.content_type = "audio/wav"
    file.size = 2 * 1024 * 1024  # 2MB
    file.read = async_read
    return file


@pytest.fixture
def mock_upload_file_mp4():
    """Create a mock UploadFile for MP4."""

    async def async_read():
        return b"test video content" * 5000

    file = Mock(spec=UploadFile)
    file.filename = "test_video.mp4"
    file.content_type = "video/mp4"
    file.size = 10 * 1024 * 1024  # 10MB
    file.read = async_read
    return file


@pytest.fixture
def mock_upload_file_large():
    """Create a mock UploadFile that exceeds size limit."""

    async def async_read():
        return b"x" * (600 * 1024 * 1024)

    file = Mock(spec=UploadFile)
    file.filename = "large_file.mp3"
    file.content_type = "audio/mpeg"
    file.size = 600 * 1024 * 1024  # 600MB (exceeds typical 500MB limit)
    file.read = async_read
    return file


@pytest.fixture
def mock_upload_file_no_extension():
    """Create a mock UploadFile without extension."""

    async def async_read():
        return b"test content"

    file = Mock(spec=UploadFile)
    file.filename = "test_file"
    file.content_type = "audio/mpeg"
    file.size = 1024 * 1024
    file.read = async_read
    return file


@pytest.fixture
def mock_upload_file_invalid_type():
    """Create a mock UploadFile with invalid file type."""

    async def async_read():
        return b"test content"

    file = Mock(spec=UploadFile)
    file.filename = "test_file.exe"
    file.content_type = "application/x-msdownload"
    file.size = 1024 * 1024
    file.read = async_read
    return file


@pytest.fixture
def sample_media_metadata_audio():
    """Create sample MediaMetadata for audio."""
    return MediaMetadata(
        media_type="audio",
        media_format="mp3",
        file_size=1024 * 1024,
        mime_type="audio/mpeg",
        original_filename="test_audio.mp3",
        is_valid=True,
    )


@pytest.fixture
def sample_media_metadata_video():
    """Create sample MediaMetadata for video."""
    return MediaMetadata(
        media_type="video",
        media_format="mp4",
        file_size=10 * 1024 * 1024,
        mime_type="video/mp4",
        original_filename="test_video.mp4",
        is_valid=True,
    )


@pytest.fixture
def sample_job_id():
    """Sample job ID for testing."""
    return "test-job-123"


@pytest.fixture
def sample_video_url():
    """Sample YouTube video URL."""
    return "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


@pytest.fixture
def sample_media_url():
    """Sample media URL."""
    return "https://cdn.example.com/audio.mp3"


@pytest.fixture
def sample_media_url_mp4():
    """Sample media URL for MP4."""
    return "https://cdn.example.com/video.mp4"


@pytest.fixture
def sample_s3_uri():
    """Sample S3 URI."""
    return "s3://bucket/media/2024-01-15/job-123.mp3"


@pytest.fixture
def mock_s3_client():
    """Create a mock S3 client."""
    client = Mock()
    client.head_bucket = Mock()
    client.upload_fileobj = Mock()
    client.put_object = Mock()
    client.download_file = Mock()
    client.get_object = Mock()
    client.delete_object = Mock()
    client.create_multipart_upload = Mock()
    client.upload_part = Mock()
    client.complete_multipart_upload = Mock()
    client.abort_multipart_upload = Mock()
    return client


@pytest.fixture
def mock_httpx_response():
    """Create a mock httpx.Response."""
    response = Mock()
    response.status_code = 200
    response.headers = {
        "content-type": "audio/mpeg",
        "content-length": "1048576",  # 1MB
    }
    response.text = ""
    response.iter_bytes = Mock(return_value=iter([b"chunk1", b"chunk2", b"chunk3"]))
    return response


@pytest.fixture
def mock_httpx_client(mock_httpx_response):
    """Create a mock httpx.Client."""
    # Make mock_httpx_response a context manager
    mock_httpx_response.__enter__ = Mock(return_value=mock_httpx_response)
    mock_httpx_response.__exit__ = Mock(return_value=None)

    client = Mock()
    client.head = Mock(return_value=mock_httpx_response)
    client.stream = Mock(return_value=mock_httpx_response)
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=None)
    return client


@pytest.fixture
def mock_yt_dlp():
    """Create a mock yt-dlp YoutubeDL instance."""
    ydl = Mock()
    ydl.extract_info = Mock(
        return_value={
            "duration": 180.0,  # 3 minutes
            "id": "dQw4w9WgXcQ",
            "title": "Test Video",
        }
    )
    ydl.__enter__ = Mock(return_value=ydl)
    ydl.__exit__ = Mock(return_value=None)
    return ydl


@pytest.fixture
def boundary_file_sizes():
    """Boundary file sizes for testing."""
    return {
        "zero": 0,
        "one_byte": 1,
        "one_kb": 1024,
        "one_mb": 1024 * 1024,
        "max_allowed": 500 * 1024 * 1024,  # 500MB
        "max_plus_one": 500 * 1024 * 1024 + 1,  # Exceeds limit
        "very_large": 1024 * 1024 * 1024,  # 1GB
    }


@pytest.fixture
def sample_audio_formats():
    """List of valid audio formats."""
    return ["mp3", "wav", "m4a", "flac", "ogg"]


@pytest.fixture
def sample_video_formats():
    """List of valid video formats."""
    return ["mp4", "mkv", "avi", "mov", "webm"]


@pytest.fixture
def invalid_formats():
    """List of invalid file formats."""
    return ["exe", "zip", "pdf", "doc", "txt", "bin"]


@pytest.fixture
def sample_mime_types():
    """Dictionary of valid MIME types."""
    return {
        "audio/mpeg": "mp3",
        "audio/wav": "wav",
        "audio/mp4": "m4a",
        "video/mp4": "mp4",
        "video/webm": "webm",
    }


@pytest.fixture
def mock_media_endpoint_service():
    """Create a MediaEndpointService with all dependencies mocked for fast tests."""
    from unittest.mock import Mock

    from app.services.media.media_endpoint_service import MediaEndpointService

    return MediaEndpointService(
        validation_service=Mock(),
        file_storage_service=Mock(),
        media_download_service=Mock(),
        transcription_service=Mock(),
        job_manager=Mock(),
    )
