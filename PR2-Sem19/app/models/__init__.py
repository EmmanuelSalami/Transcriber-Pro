"""
Models package for Pydantic schemas and type definitions.

This package contains:
- Pydantic models for request/response schemas for API endpoints
- Data validation and serialization
- Type-safe data structures for transcription, jobs, and errors
- TypedDict definitions for type guards and type narrowing
"""

from app.models.types import ErrorDict

__all__ = ["ErrorDict"]
