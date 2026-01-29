"""
Video creator using ffmpeg.

Combines audio tracks with static background images to create videos.
"""

import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class VideoCreator:
    """Creates videos from audio and images using ffmpeg."""

    def __init__(self, temp_dir: str = "temp"):
        """
        Initialize video creator.

        Args:
            temp_dir: Directory to store created video files
        """
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(exist_ok=True)
        self._check_ffmpeg()
        logger.info(f"Video creator initialized with temp directory: {self.temp_dir}")

    def _check_ffmpeg(self) -> None:
        """Check if ffmpeg is available."""
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                raise RuntimeError("ffmpeg is not working properly")
            logger.info("ffmpeg is available")
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            logger.error("ffmpeg is not installed or not in PATH")
            raise RuntimeError(
                "ffmpeg is required but not found. "
                "Please install ffmpeg: https://ffmpeg.org/download.html"
            ) from e

    def create_video(
        self,
        audio_path: Path,
        image_path: Path,
        output_path: Path,
        duration: Optional[float] = None
    ) -> Path:
        """
        Create a video from audio and image.

        Args:
            audio_path: Path to audio file
            image_path: Path to background image
            output_path: Path to save output video
            duration: Optional duration override (if None, uses audio duration)

        Returns:
            Path to created video file
        """
        logger.info(f"Creating video from audio: {audio_path}")
        logger.info(f"Using background image: {image_path}")
        logger.info(f"Output video: {output_path}")

        # Get audio duration if not provided
        if duration is None:
            duration = self._get_audio_duration(audio_path)
            logger.info(f"Audio duration: {duration:.2f} seconds")

        # Build ffmpeg command
        # High quality settings:
        # - Video: H.264 codec, high quality preset, 1920x1080 resolution
        # - Audio: AAC codec, 192kbps bitrate (high quality within YouTube limits)
        # - Loop image for full duration
        cmd = [
            'ffmpeg',
            '-loop', '1',  # Loop the image
            '-i', str(image_path),  # Input image
            '-i', str(audio_path),  # Input audio
            '-c:v', 'libx264',  # Video codec
            '-preset', 'slow',  # High quality encoding (slower but better)
            '-crf', '18',  # High quality (lower = better, 18 is visually lossless)
            '-c:a', 'aac',  # Audio codec
            '-b:a', '192k',  # Audio bitrate (high quality, within YouTube limits)
            '-shortest',  # End when shortest input ends
            '-pix_fmt', 'yuv420p',  # Pixel format for compatibility
            '-vf', 'scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2',  # Scale and pad to 1080p
            '-y',  # Overwrite output file
            str(output_path)
        ]

        try:
            logger.info("Running ffmpeg to create video...")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )

            if result.returncode != 0:
                logger.error(f"ffmpeg failed with return code {result.returncode}")
                logger.error(f"ffmpeg stderr: {result.stderr}")
                raise RuntimeError(f"Failed to create video: {result.stderr}")

            if not output_path.exists():
                raise RuntimeError("Video file was not created")

            file_size = output_path.stat().st_size / (1024 * 1024)
            logger.info(f"Successfully created video: {output_path} ({file_size:.2f} MB)")

            return output_path

        except subprocess.TimeoutExpired:
            logger.error("ffmpeg timed out while creating video")
            raise RuntimeError("Video creation timed out")
        except Exception as e:
            logger.error(f"Error creating video: {e}")
            # Clean up partial output
            if output_path.exists():
                output_path.unlink()
            raise

    def _get_audio_duration(self, audio_path: Path) -> float:
        """
        Get duration of audio file using ffprobe.

        Args:
            audio_path: Path to audio file

        Returns:
            Duration in seconds
        """
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                str(audio_path)
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                return float(result.stdout.strip())
            else:
                logger.warning(f"Could not get audio duration, using default")
                return 0.0
        except Exception as e:
            logger.warning(f"Error getting audio duration: {e}, using default")
            return 0.0

    def cleanup(self, filepath: Path) -> None:
        """
        Delete a video file.

        Args:
            filepath: Path to video file to delete
        """
        try:
            if filepath.exists():
                filepath.unlink()
                logger.debug(f"Cleaned up video file: {filepath}")
        except Exception as e:
            logger.warning(f"Failed to cleanup video file {filepath}: {e}")

