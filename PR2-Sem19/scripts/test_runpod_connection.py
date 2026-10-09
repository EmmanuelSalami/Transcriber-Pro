#!/usr/bin/env python3
"""
Script to test RunPod API connection.

This script can be run standalone or in Docker to verify that RunPod
configuration is correct and the API connection is working.

Usage:
    python scripts/test_runpod_connection.py

Environment Variables:
    RUNPOD_API_KEY: RunPod API key (required)
    RUNPOD_TEMPLATE_ID: RunPod template ID (optional for connection test)
    RUNPOD_API_URL: RunPod API URL (default: https://api.runpod.io/graphql)
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.jobs.worker_manager import WorkerManager  # noqa: E402


async def main():
    """Test RunPod connection."""
    print("=" * 60)
    print("RunPod Connection Test")
    print("=" * 60)
    print()

    # Check environment variables
    api_key = os.getenv("RUNPOD_API_KEY", "")
    template_id = os.getenv("RUNPOD_TEMPLATE_ID", "")
    api_url = os.getenv("RUNPOD_API_URL", "https://api.runpod.io/graphql")

    print("Configuration:")
    print(f"  RUNPOD_API_KEY: {'***' + api_key[-4:] if api_key else 'NOT SET'}")
    print(f"  RUNPOD_TEMPLATE_ID: {template_id if template_id else 'NOT SET'}")
    print(f"  RUNPOD_API_URL: {api_url}")
    print()

    if not api_key:
        print("❌ ERROR: RUNPOD_API_KEY environment variable is not set")
        print()
        print("To set it:")
        print("  export RUNPOD_API_KEY='your-api-key'")
        print()
        print("Or in Docker:")
        print("  docker run -e RUNPOD_API_KEY='your-api-key' ...")
        sys.exit(1)

    # Test connection
    print("Testing connection to RunPod API...")
    print()

    manager = WorkerManager()
    try:
        result = await manager.test_connection()
        await manager.close()

        if result.get("connected"):
            print("✅ SUCCESS: Connected to RunPod API")
            print()
            details = result.get("details", {})
            if "username" in details:
                print(f"  User: {details.get('username')}")
            if "user_id" in details:
                print(f"  User ID: {details.get('user_id')}")
            print(f"  API URL: {details.get('api_url')}")
            print(f"  Template ID configured: {details.get('template_id_set')}")
            print()
            print("Connection test passed! RunPod is properly configured.")
            sys.exit(0)
        else:
            print("❌ FAILED: Could not connect to RunPod API")
            print()
            error = result.get("error", "Unknown error")
            print(f"  Error: {error}")
            print()
            details = result.get("details", {})
            print("  Details:")
            for key, value in details.items():
                print(f"    {key}: {value}")
            print()
            print("Please check:")
            print("  1. Your RUNPOD_API_KEY is correct")
            print("  2. You have internet connectivity")
            print("  3. RunPod API is accessible")
            sys.exit(1)

    except Exception as e:
        print(f"❌ ERROR: Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
