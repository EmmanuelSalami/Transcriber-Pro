"""
Services package for transcription application.

This package contains service classes that handle core business logic:
- TranscriptionService: Main orchestration service for YouTube and media transcription
- YouTubeCaptionsService: Service for fetching YouTube captions
- WhisperService: ASR transcription service using Hugging Face Whisper
- JobManager: Manages async transcription jobs with Redis persistence
- FileStorageService: Handles uploaded file persistence and cleanup
- MediaDownloadService: Downloads remote media files from HTTP/HTTPS URLs
- MediaValidationService: Validates media files and remote URLs
- AudioDownloadService: Downloads audio from YouTube videos
- WebhookService: Sends webhook callbacks on job completion
"""

# Re-export all services for backward compatibility
from app.services.infrastructure import (CostControlService,
                                         ObservabilityService, WebhookService)
from app.services.jobs import JobManager, QueueService, WorkerManager
from app.services.media import (AudioDownloadService, FileStorageService,
                                MediaDownloadService, MediaValidationService,
                                S3StorageService)
from app.services.transcription import (TranscriptionService, WhisperService,
                                        YouTubeCaptionsService)

__all__ = [
    # Transcription services
    "TranscriptionService",
    "WhisperService",
    "YouTubeCaptionsService",
    # Media services
    "AudioDownloadService",
    "FileStorageService",
    "MediaDownloadService",
    "MediaValidationService",
    "S3StorageService",
    # Job services
    "JobManager",
    "QueueService",
    "WorkerManager",
    # Infrastructure services
    "CostControlService",
    "ObservabilityService",
    "WebhookService",
]
