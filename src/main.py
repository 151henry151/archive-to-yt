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

    def _format_duration(self, seconds: Optional[float]) -> str:
        """Format duration in seconds as MM:SS or HH:MM:SS."""
        if seconds is None:
            return "Unknown"
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"

    def _preview_upload(self, metadata: dict, track_audio: List[dict]) -> None:
        """
        Display a preview of what would be uploaded to YouTube.
        
        Args:
            metadata: Extracted metadata from archive.org
            track_audio: List of track information with audio URLs
        """
        logger.info(f"\n{'='*80}")
        logger.info("PREVIEW: What will be uploaded to YouTube")
        logger.info(f"{'='*80}\n")
        
        # Show collection info
        logger.info("Collection Information:")
        logger.info(f"  Title: {metadata.get('title', 'Unknown')}")
        logger.info(f"  Performer: {metadata.get('performer', 'Unknown')}")
        logger.info(f"  Venue: {metadata.get('venue', 'Unknown')}")
        logger.info(f"  Date: {metadata.get('date', 'Unknown')}")
        logger.info(f"  Archive.org URL: {metadata.get('url', 'Unknown')}")
        logger.info(f"  Identifier: {metadata.get('identifier', 'Unknown')}\n")
        
        # Show playlist info
        playlist_title = self.metadata_formatter.format_playlist_title(metadata)
        tracks = metadata.get('tracks', [])
        playlist_description = self.metadata_formatter.format_playlist_description(metadata, tracks)
        
        logger.info("Playlist Information:")
        logger.info(f"  Title: {playlist_title}")
        logger.info(f"  Description length: {len(playlist_description)} characters")
        logger.info(f"  Number of tracks: {len(track_audio)}\n")
        
        # Show each track
        logger.info("Tracks to be uploaded:")
        logger.info(f"{'='*80}")
        total_duration = 0.0
        
        for i, track_info in enumerate(track_audio, 1):
            track_num = track_info['number']
            track_name = track_info['name']
            audio_url = track_info['url']
            audio_filename = track_info.get('filename', 'Unknown')
            
            # Clean track name for title formatting
            track_info_clean = track_info.copy()
            import re
            track_name_clean = str(track_info.get('name', 'Unknown Track')).strip()
            track_name_clean = re.sub(r'<[^>]+>', '', track_name_clean)
            track_name_clean = track_name_clean.replace('&gt;', '>').replace('&lt;', '<').replace('&amp;', '&')
            track_name_clean = re.sub(r'\s+', ' ', track_name_clean).strip()
            if len(track_name_clean) > 100 or '\n' in track_name_clean:
                track_name_clean = track_name_clean.split('\n')[0].strip()
            if not track_name_clean or len(track_name_clean) == 0:
                track_name_clean = f"Track {track_num}"
            track_info_clean['name'] = track_name_clean
            
            # Format video title
            video_title = self.metadata_formatter.format_video_title(
                track_info_clean,
                metadata
            )
            if not video_title or not video_title.strip():
                video_title = f"Track {track_num} - {track_name_clean}"
            
            # Get audio duration
            logger.info(f"  Getting duration for track {i}/{len(track_audio)}...")
            duration = self.audio_downloader.get_audio_duration_from_url(audio_url)
            if duration:
                total_duration += duration
            
            # Format description preview
            video_description = self.metadata_formatter.format_track_description(
                track_info_clean,
                metadata
            )
            description_preview = video_description[:200] + "..." if len(video_description) > 200 else video_description
            description_lines = description_preview.split('\n')[:3]  # Show first 3 lines max
            
            logger.info(f"\n  Track {i}: {track_num}. {track_name}")
            logger.info(f"    Video Title: {video_title}")
            logger.info(f"    Audio File: {audio_filename}")
            logger.info(f"    Duration: {self._format_duration(duration)}")
            logger.info(f"    Description ({len(video_description)} chars):")
            for line in description_lines:
                logger.info(f"      {line}")
            if len(video_description) > 200:
                logger.info(f"      ... (truncated, {len(video_description) - 200} more characters)")
            logger.info("")
        
        logger.info(f"{'='*80}")
        logger.info(f"Summary:")
        logger.info(f"  Total tracks: {len(track_audio)}")
        logger.info(f"  Total duration: {self._format_duration(total_duration)}")
        logger.info(f"  Playlist: {playlist_title}")
        logger.info(f"{'='*80}\n")

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

            # Get identifier for unique filenames (resume capability)
            identifier = metadata.get('identifier', 'unknown')
            logger.info(f"Using identifier '{identifier}' for file naming (resume capability enabled)")
            
            # DRY-RUN PREVIEW: Show what will be uploaded (before any downloads)
            logger.info(f"\n{'='*80}")
            logger.info("DRY-RUN PREVIEW")
            logger.info(f"{'='*80}")
            self._preview_upload(metadata, track_audio)
            
            # Ask for user confirmation
            logger.info("Please review the preview above.")
            response = input("\nProceed with download, video creation, and upload? (yes/no): ").strip().lower()
            
            if response not in ['yes', 'y']:
                logger.info("Aborted by user. No files downloaded or uploaded.")
                return
            
            logger.info("\nProceeding with download and upload...\n")
            
            # Check for existing files (resume capability)
            existing_audio = self.audio_downloader.find_existing_files(identifier)
            existing_videos = self.video_creator.find_existing_videos(identifier)
            
            if existing_audio or existing_videos:
                logger.info(f"Found existing files for this identifier - will resume from existing downloads:")
                if existing_audio:
                    logger.info(f"  {len(existing_audio)} audio file(s):")
                    for existing_file in existing_audio:
                        file_size = existing_file.stat().st_size / (1024 * 1024)
                        logger.info(f"    - {existing_file.name} ({file_size:.2f} MB)")
                if existing_videos:
                    logger.info(f"  {len(existing_videos)} video file(s):")
                    for existing_file in existing_videos:
                        file_size = existing_file.stat().st_size / (1024 * 1024)
                        logger.info(f"    - {existing_file.name} ({file_size:.2f} MB)")

            # Step 3: Download background image
            logger.info("Step 3: Downloading background image...")
            background_image_url = metadata.get('background_image_url')
            if not background_image_url:
                raise ValueError("No background image found")

            image_path = self.audio_downloader.download(
                background_image_url,
                f"{identifier}_background_image.jpg",
                skip_if_exists=True,
                validate_audio=False  # Don't validate images as audio files
            )
            logger.info(f"Downloaded background image: {image_path}")

            # Step 4: Check for existing videos on YouTube
            logger.info(f"\n{'='*60}")
            logger.info("Step 4: Checking for existing videos on YouTube...")
            logger.info(f"{'='*60}")
            
            # Generate expected video titles for all tracks and track their order
            expected_titles = []
            track_to_title_map = {}  # Map track index to expected title
            for idx, track_info in enumerate(track_audio):
                track_info_clean = track_info.copy()
                track_name_clean = track_info_clean.get('name', 'Unknown Track')
                # Sanitize track name
                import re
                track_name_clean = re.sub(r'<[^>]+>', '', track_name_clean)
                track_name_clean = track_name_clean.replace('&gt;', '>').replace('&lt;', '<').replace('&amp;', '&')
                track_name_clean = re.sub(r'\s+', ' ', track_name_clean).strip()
                if len(track_name_clean) > 100 or '\n' in track_name_clean:
                    track_name_clean = track_name_clean.split('\n')[0].strip()
                if not track_name_clean or len(track_name_clean) == 0:
                    track_name_clean = f"Track {track_info['number']}"
                track_info_clean['name'] = track_name_clean
                
                video_title = self.metadata_formatter.format_video_title(
                    track_info_clean,
                    metadata
                )
                if not video_title or not video_title.strip():
                    video_title = f"Track {track_info['number']} - {track_name_clean}"
                expected_titles.append(video_title)
                track_to_title_map[idx] = video_title
            
            # Search for existing videos
            existing_videos = self.youtube_uploader.find_existing_videos(
                metadata.get('url', ''),
                expected_titles
            )
            
            if existing_videos:
                logger.info(f"Found {len(existing_videos)} existing videos on YouTube")
                for title, video_id in existing_videos.items():
                    logger.info(f"  - {title} -> {video_id}")
            else:
                logger.info("No existing videos found on YouTube")
            
            # Step 5: Process each track
            uploaded_video_ids = []
            track_to_video_id_map = {}  # Map track index to video ID (for correct ordering)
            downloaded_audio_files = []
            created_video_files = []
            successfully_uploaded_audio = []  # Track which audio files were successfully uploaded
            successfully_uploaded_videos = []  # Track which videos were successfully uploaded

            try:
                for i, track_info in enumerate(track_audio):
                    track_index = i  # 0-based index for mapping
                    track_num = track_info['number']
                    track_name = track_info['name']
                    audio_url = track_info['url']
                    audio_filename = track_info.get('filename', 'audio')

                    logger.info(f"\n{'='*60}")
                    logger.info(f"Processing track {i+1}/{len(track_audio)}: {track_num}. {track_name}")
                    logger.info(f"{'='*60}")
                    logger.info(f"Track index: {track_index} (0-based)")
                    logger.info(f"Expected audio file should contain track number: {track_num}")
                    logger.info(f"Audio URL from match: {audio_url}")
                    logger.info(f"Audio filename from match: {audio_filename}")

                    try:
                        # Format metadata first to get the video title for checking
                        # Sanitize track name before formatting (extra safety)
                        track_info_clean = track_info.copy()
                        track_name_clean = track_info_clean.get('name', 'Unknown Track')
                        # Remove HTML tags if present
                        import re
                        track_name_clean = re.sub(r'<[^>]+>', '', track_name_clean)
                        track_name_clean = track_name_clean.replace('&gt;', '>').replace('&lt;', '<').replace('&amp;', '&')
                        track_name_clean = re.sub(r'\s+', ' ', track_name_clean).strip()
                        # If track name is too long or contains multiple tracks, take first line only
                        if len(track_name_clean) > 100 or '\n' in track_name_clean:
                            track_name_clean = track_name_clean.split('\n')[0].strip()
                        # Ensure we have a valid track name
                        if not track_name_clean or len(track_name_clean) == 0:
                            track_name_clean = f"Track {track_num}"
                        track_info_clean['name'] = track_name_clean
                        
                        video_title = self.metadata_formatter.format_video_title(
                            track_info_clean,
                            metadata
                        )
                        
                        # Final validation of title
                        if not video_title or not video_title.strip():
                            logger.error(f"Generated empty title for track {track_num}, using fallback")
                            video_title = f"Track {track_num} - {track_name_clean}"
                        
                        logger.debug(f"Final video title: '{video_title}' (length: {len(video_title)})")
                        
                        # Check if this video already exists on YouTube
                        video_id = existing_videos.get(video_title)
                        
                        if video_id:
                            # Verify the video title matches what we expect
                            # Get the actual video title from YouTube to verify
                            try:
                                video_response = self.youtube_uploader.youtube.videos().list(
                                    part='snippet',
                                    id=video_id
                                ).execute()
                                
                                if video_response.get('items'):
                                    actual_title = video_response['items'][0]['snippet']['title']
                                    # Normalize for comparison
                                    normalized_expected = ' '.join(video_title.lower().split())
                                    normalized_actual = ' '.join(actual_title.lower().split())
                                    
                                    # Check if titles match
                                    if (normalized_expected == normalized_actual or 
                                        normalized_expected in normalized_actual or 
                                        normalized_actual in normalized_expected):
                                        logger.info(f"Video already exists on YouTube: {video_title}")
                                        logger.info(f"  Video ID: {video_id}")
                                        logger.info(f"  URL: https://www.youtube.com/watch?v={video_id}")
                                        logger.info("Skipping download, video creation, and upload for this track")
                                        track_to_video_id_map[track_index] = video_id
                                        logger.info(f"✓ Successfully processed track {i+1} (using existing video)")
                                        continue
                                    else:
                                        logger.warning(f"Existing video has incorrect title!")
                                        logger.warning(f"  Expected: '{video_title}'")
                                        logger.warning(f"  Actual: '{actual_title}'")
                                        logger.warning(f"  Video ID: {video_id}")
                                        logger.warning("Will delete incorrect video and re-upload with correct track")
                                        
                                        # Delete the incorrect video
                                        if self.youtube_uploader.delete_video(video_id):
                                            logger.info(f"Deleted incorrect video {video_id}, will re-upload")
                                            # Continue to upload process below
                                        else:
                                            logger.error(f"Failed to delete incorrect video {video_id}")
                                            logger.error("Skipping this track - please delete manually and re-run")
                                            continue
                                else:
                                    logger.warning(f"Video {video_id} not found, will upload new one")
                                    # Continue to upload process below
                            except Exception as e:
                                logger.warning(f"Could not verify existing video {video_id}: {e}")
                                logger.warning("Will proceed with upload (may create duplicate)")
                                # Continue to upload process below
                        
                        # Download audio (with resume capability)
                        logger.info(f"Downloading audio file...")
                        logger.info(f"  Track {track_num}: '{track_name_clean}'")
                        logger.info(f"  Audio URL: {audio_url}")
                        logger.info(f"  Audio filename from match: {audio_filename}")
                        # Use identifier in filename for unique identification
                        audio_path = self.audio_downloader.download(
                            audio_url,
                            f"{identifier}_track_{track_num}_{audio_filename}",
                            skip_if_exists=True
                        )
                        downloaded_audio_files.append(audio_path)
                        logger.info(f"  Downloaded to: {audio_path}")

                        # Create video (with resume capability)
                        logger.info(f"Creating video...")
                        video_path = self.temp_dir / f"{identifier}_video_{track_num}.mp4"
                        self.video_creator.create_video(
                            audio_path,
                            image_path,
                            video_path,
                            skip_if_exists=True
                        )
                        created_video_files.append(video_path)
                        
                        video_description = self.metadata_formatter.format_track_description(
                            track_info_clean,
                            metadata
                        )
                        
                        # Final validation of description
                        if not video_description or not video_description.strip():
                            logger.warning(f"Generated empty description for track {track_num}, using fallback")
                            video_description = f"Track {track_num}: {track_name_clean}"
                        
                        logger.debug(f"Final video description length: {len(video_description)}")
                        logger.debug(f"Final video description preview: {video_description[:200]}..." if len(video_description) > 200 else f"Final video description: '{video_description}'")

                        # Upload to YouTube
                        logger.info(f"Uploading to YouTube...")
                        video_id = self.youtube_uploader.upload_video(
                            video_path,
                            video_title,
                            video_description
                        )
                        track_to_video_id_map[track_index] = video_id
                        uploaded_video_ids.append(video_id)

                        logger.info(f"✓ Successfully processed track {i}")

                        # Only cleanup after successful YouTube upload
                        logger.debug("Cleaning up temporary files for this track...")
                        self.audio_downloader.cleanup(audio_path)
                        successfully_uploaded_audio.append(audio_path)  # Track for final cleanup
                        self.video_creator.cleanup(video_path)
                        successfully_uploaded_videos.append(video_path)  # Track for final cleanup

                    except Exception as e:
                        logger.error(f"Failed to process track {i}: {e}")
                        logger.error("Continuing with next track...")
                        logger.info("Audio and video files preserved for resume capability")
                        continue

                # Step 6: Check for existing playlist or create new one
                playlist_title = self.metadata_formatter.format_playlist_title(metadata)
                playlist_description = self.metadata_formatter.format_playlist_description(
                    metadata,
                    tracks
                )
                
                # Check if playlist already exists
                existing_playlist_id = self.youtube_uploader.find_existing_playlist(
                    playlist_title,
                    metadata.get('url', '')
                )
                
                if existing_playlist_id:
                    logger.info(f"Found existing playlist: {existing_playlist_id}")
                    playlist_id = existing_playlist_id
                    
                    # Get existing playlist items to detect gaps
                    existing_playlist_items = self.youtube_uploader.get_playlist_items(playlist_id)
                    logger.info(f"Playlist currently has {len(existing_playlist_items)} videos")
                    
                    # Build a map of expected titles to positions
                    expected_titles_to_positions = {}
                    for idx, track_info in enumerate(track_audio):
                        track_info_clean = track_info.copy()
                        track_name_clean = str(track_info.get('name', 'Unknown Track')).strip()
                        import re
                        track_name_clean = re.sub(r'<[^>]+>', '', track_name_clean)
                        track_name_clean = track_name_clean.replace('&gt;', '>').replace('&lt;', '<').replace('&amp;', '&')
                        track_name_clean = re.sub(r'\s+', ' ', track_name_clean).strip()
                        if len(track_name_clean) > 100 or '\n' in track_name_clean:
                            track_name_clean = track_name_clean.split('\n')[0].strip()
                        if not track_name_clean or len(track_name_clean) == 0:
                            track_name_clean = f"Track {track_info['number']}"
                        track_info_clean['name'] = track_name_clean
                        
                        video_title = self.metadata_formatter.format_video_title(
                            track_info_clean,
                            metadata
                        )
                        if not video_title or not video_title.strip():
                            video_title = f"Track {track_info['number']} - {track_name_clean}"
                        expected_titles_to_positions[video_title] = idx
                    
                    # Check for gaps - find which videos are missing
                    missing_positions = []
                    for expected_title, expected_pos in expected_titles_to_positions.items():
                        # Check if this video exists in playlist
                        found = False
                        for item in existing_playlist_items:
                            actual_title = item['title']
                            normalized_expected = ' '.join(expected_title.lower().split())
                            normalized_actual = ' '.join(actual_title.lower().split())
                            if (normalized_expected == normalized_actual or 
                                normalized_expected in normalized_actual or 
                                normalized_actual in normalized_expected):
                                found = True
                                break
                        if not found:
                            missing_positions.append((expected_pos, expected_title))
                    
                    if missing_positions:
                        logger.info(f"Found {len(missing_positions)} missing videos in playlist:")
                        for pos, title in missing_positions:
                            logger.info(f"  Position {pos}: '{title}'")
                    
                    # If all videos exist and playlist exists, we can skip straight to review
                    if len(uploaded_video_ids) == 0 and len(existing_videos) == len(track_audio) and not missing_positions:
                        logger.info(f"\n{'='*60}")
                        logger.info("All videos and playlist already exist!")
                        logger.info(f"{'='*60}")
                        logger.info(f"Found {len(existing_videos)} existing videos")
                        logger.info(f"Found existing playlist")
                        logger.info("Skipping to review and publish step...")
                    else:
                        logger.info("Using existing playlist, some videos may be new or missing")
                else:
                    # Create new playlist
                    if uploaded_video_ids:
                        logger.info(f"\n{'='*60}")
                        logger.info("Creating YouTube playlist...")
                        logger.info(f"{'='*60}")

                        playlist_id = self.youtube_uploader.create_playlist(
                            playlist_title,
                            playlist_description,
                            uploaded_video_ids
                        )
                        
                        # If we have an existing playlist and new videos, add them
                        if existing_playlist_id and uploaded_video_ids:
                            logger.info(f"Adding {len(uploaded_video_ids)} new videos to existing playlist...")
                            # Get current playlist items to find correct positions
                            existing_items = self.youtube_uploader.get_playlist_items(existing_playlist_id)
                            current_count = len(existing_items)
                            
                            for video_id in uploaded_video_ids:
                                # Add to end of playlist
                                self.youtube_uploader.insert_video_to_playlist(
                                    existing_playlist_id,
                                    video_id,
                                    current_count
                                )
                                current_count += 1
                            playlist_id = existing_playlist_id
                    else:
                        logger.error("No videos to add to playlist")
                        playlist_id = None

                # Step 7: Review and publish (if we have a playlist)
                if playlist_id:
                    playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
                    
                    # Collect all video IDs in correct track order (both newly uploaded and existing)
                    all_video_ids = []
                    for track_index in range(len(track_audio)):
                        if track_index in track_to_video_id_map:
                            # This track was processed (either uploaded or found existing)
                            all_video_ids.append(track_to_video_id_map[track_index])
                        else:
                            # This track wasn't processed - check if it exists in existing_videos
                            expected_title = track_to_title_map.get(track_index)
                            if expected_title and expected_title in existing_videos:
                                all_video_ids.append(existing_videos[expected_title])
                    
                    # Also handle case where we have existing playlist with gaps
                    if existing_playlist_id and missing_positions:
                        logger.info(f"\n{'='*60}")
                        logger.info("Detected gaps in playlist - inserting missing videos...")
                        logger.info(f"{'='*60}")
                        
                        # Get current playlist items
                        existing_items = self.youtube_uploader.get_playlist_items(existing_playlist_id)
                        
                        # For each missing position, insert the video
                        for expected_pos, expected_title in missing_positions:
                            # Find the video_id for this title
                            video_id = None
                            if expected_title in existing_videos:
                                video_id = existing_videos[expected_title]
                            elif expected_title in track_to_title_map.values():
                                # Find the track index for this title
                                for idx, title in track_to_title_map.items():
                                    if title == expected_title:
                                        video_id = track_to_video_id_map.get(idx)
                                        break
                            
                            if video_id:
                                logger.info(f"Inserting video at position {expected_pos}: '{expected_title}'")
                                self.youtube_uploader.insert_video_to_playlist(
                                    existing_playlist_id,
                                    video_id,
                                    expected_pos
                                )
                            else:
                                logger.warning(f"Could not find video_id for missing video: '{expected_title}'")
                    
                    logger.info(f"\n{'='*60}")
                    logger.info("SUCCESS!")
                    logger.info(f"{'='*60}")
                    if uploaded_video_ids:
                        logger.info(f"Uploaded {len(uploaded_video_ids)} new videos")
                    if existing_videos:
                        logger.info(f"Found {len(existing_videos)} existing videos")
                    logger.info(f"Total: {len(all_video_ids)} videos in playlist")
                    logger.info(f"Playlist: {playlist_url}")
                    logger.info(f"Videos and playlist are currently set to PRIVATE")
                    
                    # Offer to review and make public
                    logger.info(f"\n{'='*60}")
                    logger.info("Review and Publish")
                    logger.info(f"{'='*60}")
                    logger.info(f"Please review your playlist at: {playlist_url}")
                    logger.info("")
                    
                    while True:
                        try:
                            response = input("Would you like to make all videos and the playlist PUBLIC? (yes/no): ").strip().lower()
                            if response in ['yes', 'y']:
                                logger.info("Making videos and playlist public...")
                                
                                # Make all videos public (both new and existing)
                                success_count = self.youtube_uploader.make_videos_public(all_video_ids)
                                
                                # Make playlist public
                                if self.youtube_uploader.update_playlist_privacy(playlist_id, 'public'):
                                    logger.info(f"\n{'='*60}")
                                    logger.info("PUBLISHED!")
                                    logger.info(f"{'='*60}")
                                    logger.info(f"All {success_count} videos and the playlist are now PUBLIC")
                                    logger.info(f"Public playlist: {playlist_url}")
                                else:
                                    logger.warning("Videos were made public, but playlist update failed")
                                    logger.warning("You may need to make the playlist public manually in YouTube Studio")
                                break
                            elif response in ['no', 'n']:
                                logger.info("Keeping videos and playlist as PRIVATE")
                                logger.info("You can change privacy settings later in YouTube Studio")
                                break
                            else:
                                logger.info("Please enter 'yes' or 'no'")
                        except (EOFError, KeyboardInterrupt):
                            logger.info("\nKeeping videos and playlist as PRIVATE")
                            logger.info("You can change privacy settings later in YouTube Studio")
                            break
                else:
                    logger.error("No playlist available")

            finally:
                # Final cleanup - only clean up successfully uploaded files
                logger.info("Performing final cleanup...")
                
                # Clean up background image (always safe to remove)
                self.audio_downloader.cleanup(image_path)
                
                # Only cleanup files that were successfully uploaded
                # Leave others for resume capability
                for audio_file in successfully_uploaded_audio:
                    if audio_file.exists():
                        self.audio_downloader.cleanup(audio_file)
                
                for video_file in successfully_uploaded_videos:
                    if video_file.exists():
                        self.video_creator.cleanup(video_file)
                
                # Log which files were preserved for resume
                remaining_audio = [f for f in downloaded_audio_files if f not in successfully_uploaded_audio and f.exists()]
                remaining_videos = [f for f in created_video_files if f not in successfully_uploaded_videos and f.exists()]
                
                if remaining_audio or remaining_videos:
                    logger.info(f"Preserved files for resume capability:")
                    if remaining_audio:
                        logger.info(f"  {len(remaining_audio)} audio file(s):")
                        for audio_file in remaining_audio:
                            logger.info(f"    - {audio_file.name}")
                    if remaining_videos:
                        logger.info(f"  {len(remaining_videos)} video file(s):")
                        for video_file in remaining_videos:
                            logger.info(f"    - {video_file.name}")

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

