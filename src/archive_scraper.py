"""
Archive.org metadata scraper using the Archive.org Metadata API.

Extracts track information, metadata, and background images from archive.org items.
"""

import re
import logging
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)


class ArchiveScraper:
    """Scraper for archive.org items using the Metadata API."""

    def __init__(self, url: str):
        """
        Initialize scraper with archive.org URL.

        Args:
            url: Archive.org detail page URL (e.g., https://archive.org/details/lf2007-11-21.a)
        """
        self.url = url
        self.identifier = self._extract_identifier(url)
        self.api_data = None
        self.metadata = {}

    @staticmethod
    def _extract_identifier(url: str) -> str:
        """Extract identifier from archive.org URL."""
        # URL format: https://archive.org/details/IDENTIFIER
        match = re.search(r'/details/([^/?#]+)', url)
        if not match:
            raise ValueError(f"Invalid archive.org URL format: {url}")
        return match.group(1)

    def fetch_api_data(self) -> None:
        """Fetch metadata from Archive.org Metadata API."""
        api_url = f"https://archive.org/metadata/{self.identifier}"
        logger.info(f"Fetching metadata from Archive.org API: {api_url}")
        try:
            response = requests.get(api_url, timeout=30)
            response.raise_for_status()
            self.api_data = response.json()
            logger.info("Successfully fetched metadata from Archive.org API")
        except requests.RequestException as e:
            logger.error(f"Failed to fetch metadata from Archive.org API: {e}")
            raise
        except ValueError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            raise

    def extract_metadata(self) -> Dict:
        """
        Extract all metadata from the API response.

        Returns:
            Dictionary containing all extracted metadata
        """
        if not self.api_data:
            self.fetch_api_data()

        logger.info("Extracting metadata from Archive.org API response")

        # Get metadata dictionary from API
        api_metadata = self.api_data.get('metadata', {})
        files = self.api_data.get('files', [])

        # Extract tracks from description
        # Archive.org API may have description as string or list
        description_raw = api_metadata.get('description', '')
        if isinstance(description_raw, list):
            description = ' '.join(str(d) for d in description_raw)
        else:
            description = str(description_raw) if description_raw else ''
        tracks = self._extract_tracks_from_description(description)

        # If no tracks found in description, try to infer from filenames
        if not tracks:
            tracks = self._extract_tracks_from_files(files)

        # Extract background image
        background_image_url = self._extract_background_image(files)

        metadata = {
            'identifier': self.identifier,
            'url': self.url,
            'title': api_metadata.get('title', '').strip(),
            'artist': self._extract_artist(api_metadata),
            'venue': api_metadata.get('venue', '').strip(),
            'location': api_metadata.get('location', '').strip(),
            'date': api_metadata.get('date', '').strip(),
            'year': api_metadata.get('year', '').strip(),
            'taped_by': api_metadata.get('tapedby', '').strip() or api_metadata.get('taped_by', '').strip(),
            'transferred_by': api_metadata.get('transferredby', '').strip() or api_metadata.get('transferred_by', '').strip(),
            'lineage': api_metadata.get('lineage', '').strip(),
            'topics': self._extract_topics(api_metadata),
            'collection': api_metadata.get('collection', '').strip(),
            'description': description,
            'tracks': tracks,
            'background_image_url': background_image_url,
        }

        self.metadata = metadata
        logger.info(f"Extracted metadata: {len(tracks)} tracks found")
        return metadata

    def _extract_artist(self, api_metadata: Dict) -> str:
        """Extract artist/band name from metadata."""
        # Try various field names
        artist = (
            api_metadata.get('band') or
            api_metadata.get('artist') or
            api_metadata.get('creator') or
            api_metadata.get('band/artist') or
            ''
        )
        
        # If artist is in title (format: "Title by Artist"), extract it
        if not artist:
            title = api_metadata.get('title', '')
            match = re.search(r'by\s+(.+?)(?:\s*$|\s*Publication)', title, re.IGNORECASE)
            if match:
                artist = match.group(1).strip()
        
        return artist.strip()

    def _extract_topics(self, api_metadata: Dict) -> List[str]:
        """Extract topics from metadata."""
        topics_str = api_metadata.get('subject', '') or api_metadata.get('topics', '')
        if topics_str:
            # Topics can be a string or semicolon-separated list
            if isinstance(topics_str, list):
                return [t.strip() for t in topics_str if t.strip()]
            else:
                # Split by semicolon or comma
                topics = re.split(r'[;,]', topics_str)
                return [t.strip() for t in topics if t.strip()]
        return []

    def _extract_tracks_from_description(self, description: str) -> List[Dict[str, str]]:
        """
        Extract track list from description text.

        Returns:
            List of dictionaries with 'number' and 'name' keys
        """
        tracks = []
        if not description:
            return tracks

        # Look for numbered track list patterns
        # Format: "01. Track Name" or "1. Track Name"
        track_patterns = [
            r'(\d{2})\.\s*(.+?)(?:\n|$)',  # Two-digit format: 01. Track
            r'(\d{1,2})\.\s*(.+?)(?:\n|$)',  # One or two digit: 1. Track or 01. Track
        ]

        for pattern in track_patterns:
            matches = re.findall(pattern, description, re.MULTILINE)
            if matches:
                for number, name in matches:
                    # Pad single digits to two digits
                    track_num = number.zfill(2)
                    tracks.append({
                        'number': track_num,
                        'name': name.strip()
                    })
                break  # Use first pattern that finds matches

        return tracks

    def _extract_tracks_from_files(self, files: List[Dict]) -> List[Dict[str, str]]:
        """
        Try to infer tracks from audio file names.

        Returns:
            List of dictionaries with 'number' and 'name' keys
        """
        tracks = []
        audio_extensions = ['.flac', '.mp3', '.wav', '.m4a', '.ogg', '.oggvorbis']
        
        # Filter audio files and sort them
        audio_files = [
            f for f in files 
            if any(f.get('name', '').lower().endswith(ext) for ext in audio_extensions)
        ]
        
        # Sort by filename to maintain order
        audio_files.sort(key=lambda x: x.get('name', '').lower())
        
        for i, audio_file in enumerate(audio_files, 1):
            filename = audio_file.get('name', '')
            # Try to extract track number from filename
            track_num_match = re.search(r'(\d{1,2})', filename)
            if track_num_match:
                track_num = track_num_match.group(1).zfill(2)
            else:
                track_num = f"{i:02d}"
            
            # Extract track name from filename (remove extension and common prefixes)
            track_name = re.sub(r'\.(flac|mp3|wav|m4a|ogg|oggvorbis)$', '', filename, flags=re.IGNORECASE)
            track_name = re.sub(r'^(track[-_\s]*\d+[-_\s]*)', '', track_name, flags=re.IGNORECASE)
            track_name = track_name.strip()
            
            if not track_name:
                track_name = f"Track {i}"
            
            tracks.append({
                'number': track_num,
                'name': track_name
            })
        
        return tracks

    def _extract_background_image(self, files: List[Dict]) -> Optional[str]:
        """
        Extract background image URL from files list.

        Returns:
            URL of the background image, or None if not found
        """
        # Look for common image filenames
        image_names = ['img.jpg', 'cover.jpg', 'image.jpg', 'artwork.jpg', 'folder.jpg', 
                      'img.png', 'cover.png', 'image.png', 'artwork.png']
        
        for file_info in files:
            filename = file_info.get('name', '').lower()
            # Check if it's a common image name
            if filename in [img.lower() for img in image_names]:
                # Construct download URL
                # Pattern: https://archive.org/download/IDENTIFIER/FILENAME
                download_url = f"https://archive.org/download/{self.identifier}/{file_info['name']}"
                logger.info(f"Found background image: {file_info['name']}")
                return download_url
        
        # Look for any image files
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        for file_info in files:
            filename = file_info.get('name', '').lower()
            if any(filename.endswith(ext) for ext in image_extensions):
                # Prefer jpg/jpeg over other formats
                if filename.endswith(('.jpg', '.jpeg')):
                    download_url = f"https://archive.org/download/{self.identifier}/{file_info['name']}"
                    logger.info(f"Found background image: {file_info['name']}")
                    return download_url
        
        # If no image found, try common patterns
        for img_name in image_names:
            test_url = f"https://archive.org/download/{self.identifier}/{img_name}"
            # We'll verify this exists when we try to download it
            logger.debug(f"Trying default image URL: {test_url}")
            return test_url

        return None

    def _find_audio_files(self) -> List[Dict[str, str]]:
        """
        Find all audio files from the API files list.

        Returns:
            List of dictionaries with file information
        """
        if not self.api_data:
            self.fetch_api_data()

        files = self.api_data.get('files', [])
        audio_files = []
        audio_extensions = ['.flac', '.mp3', '.wav', '.m4a', '.ogg', '.oggvorbis']

        for file_info in files:
            filename = file_info.get('name', '')
            if any(filename.lower().endswith(ext) for ext in audio_extensions):
                # Construct download URL
                # Pattern: https://archive.org/download/IDENTIFIER/FILENAME
                download_url = f"https://archive.org/download/{self.identifier}/{filename}"
                audio_files.append({
                    'filename': filename,
                    'url': download_url
                })

        # Sort by filename to maintain consistent order
        audio_files.sort(key=lambda x: x['filename'].lower())
        
        logger.info(f"Found {len(audio_files)} audio files from API")
        return audio_files

    def get_audio_file_urls(self) -> List[Dict[str, str]]:
        """
        Get URLs for all audio files, matched to tracks if possible.

        Returns:
            List of dictionaries with track number, name, and audio URL
        """
        tracks = self.metadata.get('tracks', [])
        audio_files = self._find_audio_files()

        if not audio_files:
            logger.warning("No audio files found in API response")
            return []

        logger.info(f"Found {len(audio_files)} audio files, trying to match with {len(tracks)} tracks")

        # Try to match tracks to audio files
        track_audio = []
        used_audio_files = set()  # Track which audio files we've used

        for track in tracks:
            track_num = track['number']
            track_name = track['name']

            # Try to find matching audio file
            matched_file = None
            for i, audio_file in enumerate(audio_files):
                if i in used_audio_files:
                    continue
                    
                filename = audio_file['filename'].lower()
                # Check if track number is in filename (various formats)
                track_num_str = track_num.lstrip('0')  # Remove leading zeros
                if (track_num in filename or 
                    track_num_str in filename or 
                    f"track{track_num}" in filename or
                    f"track{track_num_str}" in filename or
                    f"track {track_num}" in filename or
                    f"track {track_num_str}" in filename or
                    f"track-{track_num}" in filename or
                    f"track-{track_num_str}" in filename or
                    f"track_{track_num}" in filename or
                    f"track_{track_num_str}" in filename):
                    matched_file = audio_file
                    used_audio_files.add(i)
                    break

            if matched_file:
                track_audio.append({
                    'number': track_num,
                    'name': track_name,
                    'url': matched_file['url'],
                    'filename': matched_file['filename']
                })
                logger.debug(f"Matched track {track_num} to {matched_file['filename']}")

        # If we have unmatched tracks but have audio files, use them in order
        if len(track_audio) < len(tracks) and len(audio_files) > len(track_audio):
            logger.info(f"Some tracks couldn't be matched, using audio files in order")
            for track in tracks[len(track_audio):]:
                # Find next unused audio file
                for i, audio_file in enumerate(audio_files):
                    if i not in used_audio_files:
                        track_audio.append({
                            'number': track['number'],
                            'name': track['name'],
                            'url': audio_file['url'],
                            'filename': audio_file['filename']
                        })
                        used_audio_files.add(i)
                        logger.debug(f"Assigned track {track['number']} to {audio_file['filename']} (by order)")
                        break

        # If we have more audio files than tracks, that's okay - we'll use what we matched
        logger.info(f"Matched {len(track_audio)} tracks to audio files")
        return track_audio
