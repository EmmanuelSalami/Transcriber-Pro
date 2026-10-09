#!/bin/bash
# Worker startup script for Runpod pods
# This script runs when the pod starts to configure and start the worker

set -e

echo "Starting GPU Worker..."

# Set worker ID from pod metadata or generate one
if [ -z "$WORKER_ID" ]; then
    export WORKER_ID="worker-$(hostname)-$(date +%s)"
fi

# Set Runpod pod ID from environment or metadata
if [ -z "$RUNPOD_POD_ID" ]; then
    export RUNPOD_POD_ID="${RUNPOD_POD_ID:-unknown}"
fi

# Set API base URL (should be configured in Runpod template)
if [ -z "$API_BASE_URL" ]; then
    echo "ERROR: API_BASE_URL environment variable not set"
    exit 1
fi

# Set GPU type if available
if [ -z "$GPU_TYPE" ]; then
    # Try to detect GPU type
    if command -v nvidia-smi &> /dev/null; then
        export GPU_TYPE=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -n1)
    else
        export GPU_TYPE="Unknown"
    fi
fi

echo "Worker Configuration:"
echo "  WORKER_ID: $WORKER_ID"
echo "  RUNPOD_POD_ID: $RUNPOD_POD_ID"
echo "  API_BASE_URL: $API_BASE_URL"
echo "  GPU_TYPE: $GPU_TYPE"

# Start the worker
exec python3 /app/workers/worker.py
