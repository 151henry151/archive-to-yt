"""
Archive.org metadata scraper using the Archive.org Metadata API.

Extracts track information, metadata, and background images from archive.org items.
"""

import os
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

    @staticmethod
    def _safe_get_string(api_metadata: Dict, key: str, default: str = '') -> str:
        """
        Safely extract a string value from API metadata.
        
        Archive.org API may return fields as strings or lists.
        This helper converts lists to strings and handles None values.
        
        Args:
            api_metadata: Metadata dictionary from API
            key: Key to extract
            default: Default value if key not found
            
        Returns:
            String value (empty string if not found or invalid)
        """
        value = api_metadata.get(key, default)
        if value is None:
            return default
        if isinstance(value, list):
            # Join list items into a single string
            return ' '.join(str(v) for v in value if v).strip()
        return str(value).strip()

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

        # Extract performer/band name (who performed, not who recorded)
        performer = self._extract_performer(api_metadata, description)
        
        # Extract recorder (who recorded/taped it)
        recorder = (
            self._safe_get_string(api_metadata, 'creator') or
            self._safe_get_string(api_metadata, 'taper') or
            self._safe_get_string(api_metadata, 'tapedby') or
            self._safe_get_string(api_metadata, 'taped_by') or
            ''
        )
        
        # Clean venue - remove [Romp] or similar prefixes
        venue_raw = self._safe_get_string(api_metadata, 'venue')
        venue = self._clean_venue(venue_raw)
        
        metadata = {
            'identifier': self.identifier,
            'url': self.url,
            'title': self._safe_get_string(api_metadata, 'title'),
            'performer': performer,  # Who performed (band/artist)
            'recorder': recorder,  # Who recorded it
            'artist': performer,  # Keep for backwards compatibility
            'venue': venue,
            'location': self._safe_get_string(api_metadata, 'location'),
            'date': self._safe_get_string(api_metadata, 'date'),
            'year': self._safe_get_string(api_metadata, 'year'),
            'taped_by': self._safe_get_string(api_metadata, 'taper') or self._safe_get_string(api_metadata, 'tapedby') or self._safe_get_string(api_metadata, 'taped_by'),
            'transferred_by': self._safe_get_string(api_metadata, 'transferer') or self._safe_get_string(api_metadata, 'transferredby') or self._safe_get_string(api_metadata, 'transferred_by'),
            'lineage': self._safe_get_string(api_metadata, 'lineage'),
            'topics': self._extract_topics(api_metadata),
            'collection': self._safe_get_string(api_metadata, 'collection'),
            'description': description,
            'tracks': tracks,
            'background_image_url': background_image_url,
        }

        self.metadata = metadata
        logger.info(f"Extracted metadata: {len(tracks)} tracks found")
        return metadata

    def _extract_performer(self, api_metadata: Dict, description: str = '') -> str:
        """
        Extract performer/band name (who performed, not who recorded).
        
        Tries to find the actual performer/band name, which may be:
        - In the description (first line often has the band name)
        - In the venue field (e.g., "[Romp] Fox Hollow Restaurant")
        - In a 'band' or 'artist' field
        """
        # Try 'band' field first (most specific)
        performer = self._safe_get_string(api_metadata, 'band')
        if performer:
            return performer
        
        # Try to extract from description (first line often has band name)
        if description:
            # Get first line of description (before first <br> or newline)
            first_line = re.split(r'<br\s*/?>|\n', description, 1)[0].strip()
            # Remove HTML tags
            first_line = re.sub(r'<[^>]+>', '', first_line).strip()
            if first_line and len(first_line) < 100:  # Reasonable band name length
                return first_line
        
        # Try to extract from venue field (e.g., "[Romp] Fox Hollow Restaurant")
        venue = self._safe_get_string(api_metadata, 'venue')
        if venue:
            # Look for [BandName] pattern
            match = re.search(r'\[([^\]]+)\]', venue)
            if match:
                return match.group(1).strip()
        
        # Try 'artist' field (but not 'creator' which is usually the recorder)
        performer = self._safe_get_string(api_metadata, 'artist')
        if performer:
            return performer
        
        # Last resort: try to extract from title
        title = self._safe_get_string(api_metadata, 'title')
        if title:
            # Look for patterns like "Band Live at..." or "...by Band"
            match = re.search(r'^([^L]+?)\s+Live\s+at', title, re.IGNORECASE)
            if match:
                return match.group(1).strip()
            match = re.search(r'by\s+(.+?)(?:\s*$|\s*Live|\s*Publication)', title, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return ''
    
    def _clean_venue(self, venue: str) -> str:
        """
        Clean venue name by removing band name prefixes like [Romp].
        
        Args:
            venue: Raw venue string (e.g., "[Romp] Fox Hollow Restaurant")
            
        Returns:
            Cleaned venue string (e.g., "Fox Hollow Restaurant")
        """
        if not venue:
            return ''
        
        # Remove [BandName] prefix
        venue = re.sub(r'^\[[^\]]+\]\s*', '', venue)
        
        return venue.strip()
    
    def _extract_artist(self, api_metadata: Dict) -> str:
        """Extract artist/band name from metadata (backwards compatibility)."""
        # This now just calls _extract_performer for consistency
        return self._extract_performer(api_metadata, '')

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

        # Clean HTML tags and entities from description
        # Replace HTML line breaks with newlines first
        description_clean = re.sub(r'<br\s*/?>', '\n', description, flags=re.IGNORECASE)
        # Remove other HTML tags
        description_clean = re.sub(r'<[^>]+>', ' ', description_clean)
        # Decode HTML entities
        description_clean = description_clean.replace('&gt;', '>').replace('&lt;', '<').replace('&amp;', '&')
        description_clean = description_clean.replace('&nbsp;', ' ')

        # Look for numbered track list patterns
        # Format: "01. Track Name" or "1. Track Name"
        # Match until end of line or next track number
        track_patterns = [
            r'(\d{2})\.\s*([^\n]+?)(?=\s*\d{2}\.\s*|\s*\d{1}\.\s*|$|\n\n)',  # Two-digit format: 01. Track (stop at next track or double newline)
            r'(\d{1,2})\.\s*([^\n]+?)(?=\s*\d{1,2}\.\s*|$|\n\n)',  # One or two digit format
        ]

        for pattern in track_patterns:
            matches = re.findall(pattern, description_clean, re.MULTILINE)
            if matches:
                for number, name in matches:
                    # Pad single digits to two digits
                    track_num = number.zfill(2)
                    # Clean up track name: remove extra whitespace, HTML remnants
                    clean_name = re.sub(r'\s+', ' ', name.strip())
                    # Remove any remaining HTML entities
                    clean_name = clean_name.replace('&nbsp;', ' ').strip()
                    
                    # Only add if we have a valid track name (not empty, not just whitespace)
                    # And make sure it's not capturing multiple tracks
                    if clean_name and len(clean_name) > 0 and len(clean_name) < 200:  # Reasonable length limit
                        tracks.append({
                            'number': track_num,
                            'name': clean_name
                        })
                
                # Only use matches if we got reasonable number of tracks (more than 1)
                if len(tracks) > 1:
                    logger.debug(f"Extracted {len(tracks)} tracks from description")
                    break  # Use first pattern that finds matches
                else:
                    tracks = []  # Reset if we didn't get good matches

        # Log first few tracks for debugging
        if tracks:
            logger.debug(f"Sample tracks extracted: {tracks[:3]}")
        
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
                # Note: filename may include directory path, but URL needs full path
                download_url = f"https://archive.org/download/{self.identifier}/{filename}"
                # Sanitize filename for local storage (use basename only)
                safe_filename = os.path.basename(filename)
                audio_files.append({
                    'filename': safe_filename,  # Use sanitized filename for local storage
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
        
        # Log all audio files for debugging
        logger.info("Audio files found:")
        for i, af in enumerate(audio_files):
            logger.info(f"  [{i}] {af['filename']}")
        
        # Log all tracks for debugging
        logger.info("Tracks extracted:")
        for track in tracks:
            logger.info(f"  Track {track['number']}: '{track['name']}'")

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
                track_num_padded = track_num.zfill(2)  # Ensure two digits
                
                # Common patterns: t01, t02, track01, track-01, track_01, 01., etc.
                # Also check for patterns like "t01" (common in archive.org: Romp2007-11-21t01.flac)
                patterns = [
                    f"t{track_num_padded}",  # t01, t02 (most common in archive.org)
                    f"t{track_num_str}",     # t1, t2
                    f"t{track_num}",         # t01, t02 (if already padded)
                    track_num_padded,        # 01, 02
                    track_num_str,           # 1, 2
                    track_num,               # 01, 02 (original)
                    f"track{track_num_padded}",
                    f"track{track_num_str}",
                    f"track {track_num_padded}",
                    f"track {track_num_str}",
                    f"track-{track_num_padded}",
                    f"track-{track_num_str}",
                    f"track_{track_num_padded}",
                    f"track_{track_num_str}",
                    f"{track_num_padded}.",  # 01. at start or after separator
                    f"{track_num_str}.",
                ]
                
                # Check if any pattern matches in the filename
                # Prioritize more specific patterns (t01, t02) over generic numeric patterns
                matched = False
                import re
                
                # First try specific patterns (t01, track01, etc.) - these are more reliable
                specific_patterns = [
                    f"t{track_num_padded}",  # t01, t02 (most common in archive.org)
                    f"t{track_num_str}",     # t1, t2
                    f"track{track_num_padded}",
                    f"track{track_num_str}",
                    f"track-{track_num_padded}",
                    f"track-{track_num_str}",
                    f"track_{track_num_padded}",
                    f"track_{track_num_str}",
                ]
                
                for pattern in specific_patterns:
                    # For specific patterns, check they're not part of a larger number
                    pattern_re = re.compile(r'(^|[^0-9])' + re.escape(pattern) + r'([^0-9]|\.|$)', re.IGNORECASE)
                    if pattern_re.search(filename.lower()):
                        matched = True
                        logger.debug(f"Matched specific pattern '{pattern}' in '{filename}' for track {track_num} '{track_name}'")
                        break
                
                # If no specific pattern matched, try generic numeric patterns (but be more careful)
                if not matched:
                    generic_patterns = [
                        f"{track_num_padded}.",  # 01. at start or after separator
                        f"{track_num_str}.",
                        track_num_padded,        # 01, 02 (check boundaries carefully)
                        track_num_str,           # 1, 2
                    ]
                    
                    for pattern in generic_patterns:
                        # For generic patterns, be very strict about word boundaries
                        pattern_re = re.compile(r'(^|[^0-9])' + re.escape(pattern) + r'([^0-9]|\.|$)', re.IGNORECASE)
                        if pattern_re.search(filename.lower()):
                            # Double-check it's not matching part of a date (e.g., 2007-11-21)
                            # If pattern is just digits, make sure it's not in the middle of a date string
                            if pattern.isdigit():
                                # Check that it's not part of a date pattern like 2007-11-21
                                date_pattern = re.compile(r'\d{4}[-\/]\d{1,2}[-\/]' + re.escape(pattern))
                                if not date_pattern.search(filename.lower()):
                                    matched = True
                                    logger.debug(f"Matched generic pattern '{pattern}' in '{filename}' for track {track_num} '{track_name}'")
                                    break
                            else:
                                matched = True
                                logger.debug(f"Matched generic pattern '{pattern}' in '{filename}' for track {track_num}")
                                break
                
                if matched:
                    # Double-check: verify the matched file actually contains the track number
                    # This prevents false matches (e.g., track 3 matching to track 1's file)
                    filename_lower = filename.lower()
                    track_num_str = track_num.lstrip('0') or '0'  # Handle '00' case
                    track_num_padded = track_num.zfill(2)
                    
                    # Verify the match is correct by checking for track number patterns
                    verification_patterns = [
                        f"t{track_num_padded}",  # t03
                        f"t{track_num_str}",     # t3
                        f"track{track_num_padded}",
                        f"track{track_num_str}",
                        f"track-{track_num_padded}",
                        f"track-{track_num_str}",
                        f"track_{track_num_padded}",
                        f"track_{track_num_str}",
                        f"{track_num_padded}.",  # 03.
                        f"{track_num_str}.",      # 3.
                    ]
                    
                    verified = False
                    for pattern in verification_patterns:
                        pattern_re = re.compile(r'(^|[^0-9])' + re.escape(pattern) + r'([^0-9]|\.|$)', re.IGNORECASE)
                        if pattern_re.search(filename_lower):
                            verified = True
                            break
                    
                    if verified:
                        matched_file = audio_file
                        used_audio_files.add(i)
                        logger.info(f"✓ Matched track {track_num} '{track_name}' to audio file [{i}] {audio_file['filename']}")
                        logger.info(f"  Verified: audio file contains track number {track_num}")
                        break
                    else:
                        logger.warning(f"  Match found but failed verification for track {track_num}")
                        logger.warning(f"  Audio file '{audio_file['filename']}' doesn't clearly contain track number {track_num}")
                        # Continue searching for a better match

            if matched_file:
                track_audio.append({
                    'number': track_num,
                    'name': track_name,
                    'url': matched_file['url'],
                    'filename': matched_file['filename']
                })
            else:
                logger.warning(f"✗ Could not match track {track_num} '{track_name}' to any audio file")
                logger.warning(f"  Tried patterns: t{track_num_padded}, t{track_num_str}, {track_num_padded}, {track_num_str}")

        # If we have unmatched tracks but have audio files, try sequential matching
        if len(track_audio) < len(tracks) and len(audio_files) > len(track_audio):
            logger.warning(f"Some tracks couldn't be matched by pattern, trying sequential matching")
            # Sort unused audio files by filename to maintain order
            unused_files = [(i, f) for i, f in enumerate(audio_files) if i not in used_audio_files]
            unused_files.sort(key=lambda x: x[1]['filename'].lower())
            
            for track in tracks[len(track_audio):]:
                if unused_files:
                    i, audio_file = unused_files.pop(0)
                    track_audio.append({
                        'number': track['number'],
                        'name': track['name'],
                        'url': audio_file['url'],
                        'filename': audio_file['filename']
                    })
                    used_audio_files.add(i)
                    logger.warning(f"Sequentially assigned track {track['number']} '{track['name']}' to {audio_file['filename']} (may be incorrect!)")

        # Validate that we have the right number of matches
        if len(track_audio) != len(tracks):
            logger.error(f"Mismatch: {len(track_audio)} track-audio matches for {len(tracks)} tracks")
            logger.error("This may cause incorrect track-to-audio matching!")
        
        # Log the final matches for verification
        logger.info(f"Final track-to-audio matches:")
        for ta in track_audio:
            logger.info(f"  Track {ta['number']}: '{ta['name']}' -> {ta['filename']}")
        
        logger.info(f"Matched {len(track_audio)} tracks to audio files")
        return track_audio
