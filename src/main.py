"""
Main entry point for archive.org to YouTube uploader.

Orchestrates the entire workflow: scraping, downloading, video creation, and uploading.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

# Handle imports for both direct execution and module import
try:
    from archive_scraper import ArchiveScraper
    from audio_downloader import AudioDownloader
    from metadata_formatter import MetadataFormatter
    from video_creator import VideoCreator
    from youtube_uploader import YouTubeUploader
except ImportError:
    # If running as module from project root
    from src.archive_scraper import ArchiveScraper
    from src.audio_downloader import AudioDownloader
    from src.metadata_formatter import MetadataFormatter
    from src.video_creator import VideoCreator
    from src.youtube_uploader import YouTubeUploader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class ArchiveToYouTube:
    """Main orchestrator for archive.org to YouTube workflow."""

    def __init__(
        self,
        temp_dir: str = "temp",
        credentials_path: str = "config/client_secrets.json"
    ):
        """
        Initialize the uploader.

        Args:
            temp_dir: Directory for temporary files
            credentials_path: Path to YouTube API credentials
        """
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(exist_ok=True)

        self.audio_downloader = AudioDownloader(str(self.temp_dir))
        self.video_creator = VideoCreator(str(self.temp_dir))
        self.metadata_formatter = MetadataFormatter()
        self.youtube_uploader = YouTubeUploader(credentials_path)

        logger.info("Archive to YouTube uploader initialized")

    def process_archive_url(self, url: str) -> None:
        """
        Process an archive.org URL and upload to YouTube.

        Args:
            url: Archive.org detail page URL
        """
        logger.info(f"Processing archive.org URL: {url}")

        try:
            # Step 1: Scrape metadata
            logger.info("Step 1: Extracting metadata from archive.org...")
            scraper = ArchiveScraper(url)
            metadata = scraper.extract_metadata()
            tracks = metadata.get('tracks', [])

            if not tracks:
                raise ValueError("No tracks found on archive.org page")

            logger.info(f"Found {len(tracks)} tracks")

            # Step 2: Get audio file URLs
            logger.info("Step 2: Finding audio file URLs...")
            track_audio = scraper.get_audio_file_urls()

            if not track_audio:
                raise ValueError("No audio files found for tracks")

            logger.info(f"Found {len(track_audio)} audio files")

            # Step 3: Download background image
            logger.info("Step 3: Downloading background image...")
            background_image_url = metadata.get('background_image_url')
            if not background_image_url:
                raise ValueError("No background image found")

            image_path = self.audio_downloader.download(
                background_image_url,
                "background_image.jpg"
            )
            logger.info(f"Downloaded background image: {image_path}")

            # Step 4: Process each track
            uploaded_video_ids = []
            downloaded_audio_files = []
            created_video_files = []

            try:
                for i, track_info in enumerate(track_audio, 1):
                    track_num = track_info['number']
                    track_name = track_info['name']
                    audio_url = track_info['url']

                    logger.info(f"\n{'='*60}")
                    logger.info(f"Processing track {i}/{len(track_audio)}: {track_num}. {track_name}")
                    logger.info(f"{'='*60}")

                    try:
                        # Download audio
                        logger.info(f"Downloading audio file...")
                        audio_path = self.audio_downloader.download(
                            audio_url,
                            f"track_{track_num}_{track_info.get('filename', 'audio')}"
                        )
                        downloaded_audio_files.append(audio_path)

                        # Create video
                        logger.info(f"Creating video...")
                        video_path = self.temp_dir / f"video_{track_num}.mp4"
                        self.video_creator.create_video(
                            audio_path,
                            image_path,
                            video_path
                        )
                        created_video_files.append(video_path)

                        # Format metadata
                        video_title = self.metadata_formatter.format_video_title(
                            track_info,
                            metadata
                        )
                        video_description = self.metadata_formatter.format_track_description(
                            track_info,
                            metadata
                        )

                        # Upload to YouTube
                        logger.info(f"Uploading to YouTube...")
                        video_id = self.youtube_uploader.upload_video(
                            video_path,
                            video_title,
                            video_description
                        )
                        uploaded_video_ids.append(video_id)

                        logger.info(f"✓ Successfully processed track {i}")

                        # Clean up audio and video files immediately after upload
                        logger.debug("Cleaning up temporary files for this track...")
                        self.audio_downloader.cleanup(audio_path)
                        self.video_creator.cleanup(video_path)

                    except Exception as e:
                        logger.error(f"Failed to process track {i}: {e}")
                        logger.error("Continuing with next track...")
                        continue

                # Step 5: Create playlist
                if uploaded_video_ids:
                    logger.info(f"\n{'='*60}")
                    logger.info("Creating YouTube playlist...")
                    logger.info(f"{'='*60}")

                    playlist_title = self.metadata_formatter.format_playlist_title(metadata)
                    playlist_description = self.metadata_formatter.format_playlist_description(
                        metadata,
                        tracks
                    )

                    playlist_id = self.youtube_uploader.create_playlist(
                        playlist_title,
                        playlist_description,
                        uploaded_video_ids
                    )

                    logger.info(f"\n{'='*60}")
                    logger.info("SUCCESS!")
                    logger.info(f"{'='*60}")
                    logger.info(f"Uploaded {len(uploaded_video_ids)} videos")
                    logger.info(f"Playlist: https://www.youtube.com/playlist?list={playlist_id}")
                    logger.info(f"Videos are set to PRIVATE - you can change this in YouTube Studio")
                else:
                    logger.error("No videos were successfully uploaded")

            finally:
                # Final cleanup
                logger.info("Performing final cleanup...")
                self.audio_downloader.cleanup(image_path)
                # Audio and video files should already be cleaned up, but ensure cleanup
                for audio_file in downloaded_audio_files:
                    if audio_file.exists():
                        self.audio_downloader.cleanup(audio_file)
                for video_file in created_video_files:
                    if video_file.exists():
                        self.video_creator.cleanup(video_file)

        except Exception as e:
            logger.error(f"Error processing archive.org URL: {e}")
            raise


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Upload archive.org audio tracks to YouTube as videos'
    )
    parser.add_argument(
        'url',
        help='Archive.org detail page URL (e.g., https://archive.org/details/lf2007-11-21.a)'
    )
    parser.add_argument(
        '--temp-dir',
        default='temp',
        help='Directory for temporary files (default: temp)'
    )
    parser.add_argument(
        '--credentials',
        default='config/client_secrets.json',
        help='Path to YouTube API credentials (default: config/client_secrets.json)'
    )

    args = parser.parse_args()

    try:
        uploader = ArchiveToYouTube(
            temp_dir=args.temp_dir,
            credentials_path=args.credentials
        )
        uploader.process_archive_url(args.url)
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

