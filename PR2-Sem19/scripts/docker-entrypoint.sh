#!/bin/bash
set -e

# Docker entrypoint script that ensures Whisper model is downloaded before starting the app

echo "=========================================="
echo "YouTube Transcription API - Entrypoint"
echo "=========================================="

# Ensure temp_audio directory exists and has proper permissions
TEMP_AUDIO_DIR="/app/temp_audio"
echo "Checking temp_audio directory: $TEMP_AUDIO_DIR"
if [ ! -d "$TEMP_AUDIO_DIR" ]; then
    echo "  Creating temp_audio directory..."
    mkdir -p "$TEMP_AUDIO_DIR"
fi
# Ensure directory is writable (fix permissions if needed)
if [ -d "$TEMP_AUDIO_DIR" ]; then
    chmod 777 "$TEMP_AUDIO_DIR" 2>/dev/null || echo "  Warning: Could not set permissions on temp_audio directory"
    # Test write access
    if touch "$TEMP_AUDIO_DIR/.write_test" 2>/dev/null; then
        rm -f "$TEMP_AUDIO_DIR/.write_test"
        echo "✓ temp_audio directory is writable"
    else
        echo "⚠ Warning: temp_audio directory may not be writable (check volume permissions)"
    fi
fi

# Get model path from environment or use default
MODEL_PATH="${WHISPER_MODEL_PATH:-/app/models/whisper}"
MODEL_ID="${WHISPER_MODEL:-openai/whisper-base}"

echo "Model path: $MODEL_PATH"
echo "Model ID: $MODEL_ID"

# Check if model directory exists and contains config.json
if [ -d "$MODEL_PATH" ] && [ -f "$MODEL_PATH/config.json" ]; then
    echo "✓ Whisper model found at $MODEL_PATH"
    echo "  Using pre-downloaded model (fast startup)"
else
    echo "⚠ Whisper model not found at $MODEL_PATH"
    
    # Check if the path is writable (not read-only mount)
    WRITABLE_PATH="$MODEL_PATH"
    if [ -d "$MODEL_PATH" ]; then
        # Test if directory is writable
        if ! touch "$MODEL_PATH/.write_test" 2>/dev/null; then
            echo "  Directory is read-only (volume mount)"
            echo "  Using internal writable location: /app/.models/whisper"
            WRITABLE_PATH="/app/.models/whisper"
            mkdir -p "$WRITABLE_PATH"
            # Update MODEL_PATH and export for child processes
            MODEL_PATH="$WRITABLE_PATH"
            export WHISPER_MODEL_PATH="$WRITABLE_PATH"
        else
            # Remove test file
            rm -f "$MODEL_PATH/.write_test"
            echo "  Directory is writable, downloading model..."
        fi
    else
        # Try to create directory
        if mkdir -p "$MODEL_PATH" 2>/dev/null && touch "$MODEL_PATH/.write_test" 2>/dev/null; then
            rm -f "$MODEL_PATH/.write_test"
            echo "  Created writable directory, downloading model..."
        else
            echo "  Cannot create directory (read-only), using internal location: /app/.models/whisper"
            WRITABLE_PATH="/app/.models/whisper"
            mkdir -p "$WRITABLE_PATH"
            MODEL_PATH="$WRITABLE_PATH"
            export WHISPER_MODEL_PATH="$WRITABLE_PATH"
        fi
    fi
    
    echo "  Downloading model from Hugging Face..."
    echo "  This may take a few minutes on first run..."
    echo ""
    
    # Download model using Python script to writable path
    # Don't fail if download fails - let the app handle it on first request
    if python3 /app/scripts/download_whisper_model.py "$MODEL_ID" "$WRITABLE_PATH"; then
        echo ""
        echo "✓ Model downloaded successfully to $WRITABLE_PATH!"
        if [ "$WRITABLE_PATH" != "$MODEL_PATH" ]; then
            echo "  Note: Model saved to internal location due to read-only volume mount"
        fi
    else
        echo ""
        echo "⚠ Failed to download model automatically"
        echo "  The app will attempt to download on first request"
        echo "  This is normal if running without internet"
    fi
fi

echo ""
echo "=========================================="
echo "Starting application..."
echo "=========================================="
echo ""

# Execute the main command (from CMD or passed arguments)
exec "$@"

