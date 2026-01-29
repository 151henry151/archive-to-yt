"""
Audio file downloader from archive.org.

Handles downloading audio files for processing.
"""

import logging
import os
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)


class AudioDownloader:
    """Downloads audio files from archive.org."""

    def __init__(self, temp_dir: str = "temp"):
        """
        Initialize downloader.

        Args:
            temp_dir: Directory to store downloaded files
        """
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(exist_ok=True)
        logger.info(f"Audio downloader initialized with temp directory: {self.temp_dir}")

    def download(self, url: str, filename: Optional[str] = None) -> Path:
        """
        Download an audio file from URL.

        Args:
            url: URL of the audio file to download
            filename: Optional filename to save as (defaults to URL filename)

        Returns:
            Path to the downloaded file
        """
        if not filename:
            # Extract filename from URL
            parsed = urlparse(url)
            filename = os.path.basename(parsed.path)
            if not filename:
                filename = "audio_file"

        filepath = self.temp_dir / filename

        logger.info(f"Downloading audio file: {url}")
        logger.info(f"Saving to: {filepath}")

        try:
            response = requests.get(url, stream=True, timeout=60)
            response.raise_for_status()

            # Get file size for progress logging
            total_size = int(response.headers.get('content-length', 0))
            if total_size:
                logger.info(f"File size: {total_size / (1024 * 1024):.2f} MB")

            # Download with progress
            downloaded = 0
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size:
                            percent = (downloaded / total_size) * 100
                            if downloaded % (1024 * 1024) == 0:  # Log every MB
                                logger.info(f"Downloaded: {downloaded / (1024 * 1024):.2f} MB ({percent:.1f}%)")

            logger.info(f"Successfully downloaded: {filepath}")
            return filepath

        except requests.RequestException as e:
            logger.error(f"Failed to download audio file: {e}")
            # Clean up partial download
            if filepath.exists():
                filepath.unlink()
            raise

    def cleanup(self, filepath: Path) -> None:
        """
        Delete a downloaded file.

        Args:
            filepath: Path to file to delete
        """
        try:
            if filepath.exists():
                filepath.unlink()
                logger.debug(f"Cleaned up audio file: {filepath}")
        except Exception as e:
            logger.warning(f"Failed to cleanup audio file {filepath}: {e}")

    def cleanup_all(self) -> None:
        """Clean up all files in temp directory."""
        try:
            for filepath in self.temp_dir.glob("*"):
                if filepath.is_file():
                    filepath.unlink()
                    logger.debug(f"Cleaned up: {filepath}")
            logger.info("Cleaned up all temporary audio files")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp directory: {e}")

