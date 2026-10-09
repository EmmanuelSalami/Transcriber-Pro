#!/usr/bin/env python3
"""
Script to download Whisper model for Docker volume mounting.

This script downloads a Whisper model from Hugging Face and saves it locally.
In Docker, models are stored in Docker volumes (whisper-models, whisper-models-dev, etc.)
which persist across container restarts. This script can be used to pre-download
models locally before populating a Docker volume.

Usage:
    python scripts/download_whisper_model.py [model_id] [output_dir]

Examples:
    # Download default model (whisper-base) to local directory
    python scripts/download_whisper_model.py

    # Download specific model to custom directory
    python scripts/download_whisper_model.py openai/whisper-small ./models/whisper-small

    # Download large model
    python scripts/download_whisper_model.py openai/whisper-large-v3 ./models/whisper-large

Note: In Docker, models are automatically downloaded to Docker volumes on first run.
This script is mainly useful for pre-downloading models locally.
"""

import argparse
import logging
import sys
from pathlib import Path

try:
    import torch
    from transformers import pipeline
except ImportError:
    print(
        "Error: transformers and torch are required. Install with: "
        "pip install transformers torch"
    )
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def download_model(model_id: str, output_dir: str) -> bool:
    """
    Download Whisper model from Hugging Face and save to local directory.

    Args:
        model_id (str): Hugging Face model ID (e.g., "openai/whisper-base")
        output_dir (str): Directory to save the model

    Returns:
        bool: True if successful, False otherwise
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    logger.info(f"Downloading Whisper model: {model_id}")
    logger.info(f"Output directory: {output_path.absolute()}")

    try:
        # Determine device (use CPU for downloading)
        device = "cpu"
        dtype = torch.float32

        logger.info("Initializing pipeline to download model...")
        # Create pipeline - this will download the model
        pipe = pipeline(
            "automatic-speech-recognition",
            model=model_id,
            device=device,
            dtype=dtype,  # Use dtype instead of deprecated torch_dtype
        )

        # Get the actual model from the pipeline
        if hasattr(pipe, "model"):
            model = pipe.model
            tokenizer = pipe.tokenizer
            feature_extractor = pipe.feature_extractor

            logger.info("Saving model to local directory...")

            # Save model components
            if hasattr(model, "save_pretrained"):
                model.save_pretrained(str(output_path))
                logger.info(f"✓ Model saved to {output_path / 'pytorch_model.bin'}")
            else:
                logger.warning("Model doesn't have save_pretrained method")

            if hasattr(tokenizer, "save_pretrained"):
                tokenizer.save_pretrained(str(output_path))
                logger.info(f"✓ Tokenizer saved to {output_path / 'tokenizer.json'}")
            else:
                logger.warning("Tokenizer doesn't have save_pretrained method")

            if hasattr(feature_extractor, "save_pretrained"):
                feature_extractor.save_pretrained(str(output_path))
                logger.info(
                    f"✓ Feature extractor saved to {output_path / 'preprocessor_config.json'}"
                )
            else:
                logger.warning("Feature extractor doesn't have save_pretrained method")

            # Verify model files
            config_file = output_path / "config.json"
            if config_file.exists():
                logger.info(f"✓ Model configuration saved: {config_file}")
            else:
                logger.warning(f"⚠ config.json not found in {output_path}")

            logger.info(f"\n✓ Model downloaded successfully to: {output_path.absolute()}")

            # Only show Docker instructions if not running inside Docker
            import os

            if not os.path.exists("/.dockerenv"):
                logger.info(
                    "\nTo use this model in Docker, mount it as a volume:\n"
                    f"  docker run -v {output_path.absolute()}:/app/models/whisper:ro ...\n"
                    "\nOr in docker-compose.yml:\n"
                    f"  volumes:\n"
                    f"    - {output_path.absolute()}:/app/models/whisper:ro\n"
                    "\nThen set environment variable:\n"
                    "  WHISPER_MODEL_PATH=/app/models/whisper\n"
                )

            return True

        else:
            logger.error("Pipeline doesn't have a model attribute")
            return False

    except Exception as e:
        logger.error(f"Failed to download model: {type(e).__name__} - {str(e)}", exc_info=True)
        return False


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Download Whisper model for Docker volume mounting",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "model_id",
        nargs="?",
        default="openai/whisper-base",
        help="Hugging Face model ID (default: openai/whisper-base)",
    )
    parser.add_argument(
        "output_dir",
        nargs="?",
        default="./models/whisper",
        help="Output directory for model (default: ./models/whisper)",
    )

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Whisper Model Downloader")
    logger.info("=" * 60)

    success = download_model(args.model_id, args.output_dir)

    if success:
        logger.info("\n✓ Download completed successfully!")
        sys.exit(0)
    else:
        logger.error("\n✗ Download failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
