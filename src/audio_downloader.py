"""
Audio file downloader from archive.org.

Handles downloading audio files for processing.
"""

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import List, Optional
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

    def download(self, url: str, filename: Optional[str] = None, skip_if_exists: bool = True, validate_audio: bool = True) -> Path:
        """
        Download a file from URL.

        Args:
            url: URL of the file to download
            filename: Optional filename to save as (defaults to URL filename)
            skip_if_exists: If True, skip download if file already exists (resume capability)
            validate_audio: If True, validate the downloaded file as an audio file (default: True)

        Returns:
            Path to the downloaded file
        """
        if not filename:
            # Extract filename from URL
            parsed = urlparse(url)
            filename = os.path.basename(parsed.path)
            if not filename:
                filename = "audio_file"
        else:
            # Sanitize filename - remove any directory components
            # Only use the basename to avoid creating subdirectories
            filename = os.path.basename(filename)
            if not filename:
                # Fallback: extract from URL if provided filename is invalid
                parsed = urlparse(url)
                filename = os.path.basename(parsed.path) or "audio_file"

        filepath = self.temp_dir / filename

        # Ensure parent directory exists (should already exist, but be safe)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # Check if file already exists (resume capability)
        if skip_if_exists and filepath.exists():
            file_size = filepath.stat().st_size
            logger.info(f"Audio file exists: {filepath} ({file_size / (1024 * 1024):.2f} MB)")
            
            # Validate the existing file if it should be an audio file
            if validate_audio:
                if self._validate_audio_file(filepath):
                    logger.info(f"Existing audio file is valid, skipping download: {filepath}")
                    return filepath
                else:
                    logger.warning(f"Existing audio file is corrupted or incomplete, will re-download: {filepath}")
                    # Delete corrupted file
                    try:
                        filepath.unlink()
                        logger.info(f"Deleted corrupted audio file: {filepath}")
                    except Exception as e:
                        logger.warning(f"Failed to delete corrupted audio file: {e}")
                    # Continue to download
            else:
                # For non-audio files (like images), just check if it exists
                logger.info(f"Existing file found, skipping download: {filepath}")
                return filepath

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

            # Validate the downloaded file if it should be an audio file
            if validate_audio:
                logger.info("Validating downloaded audio file...")
                if not self._validate_audio_file(filepath):
                    # Clean up invalid file
                    if filepath.exists():
                        filepath.unlink()
                    raise RuntimeError("Downloaded audio file failed validation - may be corrupted")
                logger.info(f"Successfully downloaded and validated: {filepath}")
            else:
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

    def _validate_audio_file(self, audio_path: Path) -> bool:
        """
        Validate that an audio file is complete and valid.
        
        Args:
            audio_path: Path to audio file to validate
            
        Returns:
            True if audio is valid, False otherwise
        """
        if not audio_path.exists():
            return False
        
        # Check file size - must be at least 1KB (very small files are likely corrupted)
        file_size = audio_path.stat().st_size
        if file_size < 1024:  # Less than 1KB is suspicious
            logger.warning(f"Audio file is suspiciously small ({file_size} bytes), likely corrupted")
            return False
        
        # Validate audio file using ffprobe
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration:stream=codec_type',
                '-of', 'json',
                str(audio_path)
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                logger.warning(f"ffprobe validation failed for {audio_path.name}: {result.stderr}")
                return False
            
            # Check if we got valid JSON output
            try:
                probe_data = json.loads(result.stdout)
                format_info = probe_data.get('format', {})
                
                # Check if format duration exists and is valid
                duration_str = format_info.get('duration', '0')
                if duration_str:
                    duration = float(duration_str)
                    if duration <= 0:
                        logger.warning(f"Audio has invalid duration ({duration} seconds)")
                        return False
                
                # Check if audio stream exists
                streams = probe_data.get('streams', [])
                has_audio = any(s.get('codec_type') == 'audio' for s in streams)
                
                if not has_audio:
                    logger.warning(f"Audio file has no audio stream")
                    return False
                
                logger.debug(f"Audio file validated successfully: duration={duration:.2f}s, size={file_size / (1024*1024):.2f}MB")
                return True
                
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.warning(f"Failed to parse ffprobe output for {audio_path.name}: {e}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.warning(f"ffprobe validation timed out for {audio_path.name}")
            return False
        except FileNotFoundError:
            # ffprobe not found - skip validation but warn
            logger.warning("ffprobe not found, skipping audio validation")
            return True  # Assume valid if we can't validate
        except Exception as e:
            logger.warning(f"Error validating audio file {audio_path.name}: {e}")
            return False

    def get_audio_duration_from_url(self, url: str) -> Optional[float]:
        """
        Get duration of audio file from URL using ffprobe (without downloading).
        
        Args:
            url: URL of audio file
            
        Returns:
            Duration in seconds, or None if unable to determine
        """
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                url
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                duration_str = result.stdout.strip()
                if duration_str:
                    return float(duration_str)
            logger.debug(f"Could not get duration from URL: {url}")
            return None
        except subprocess.TimeoutExpired:
            logger.debug(f"ffprobe timed out getting duration from URL: {url}")
            return None
        except FileNotFoundError:
            logger.debug("ffprobe not found, cannot get duration from URL")
            return None
        except Exception as e:
            logger.debug(f"Error getting duration from URL {url}: {e}")
            return None

    def find_existing_files(self, identifier: str) -> List[Path]:
        """
        Find existing audio files for a given identifier (resume capability).
        
        Args:
            identifier: Archive.org identifier to search for
            
        Returns:
            List of existing audio file paths
        """
        existing_files = []
        pattern = f"{identifier}_track_*"
        for filepath in self.temp_dir.glob(pattern):
            if filepath.is_file():
                existing_files.append(filepath)
        return sorted(existing_files)

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

