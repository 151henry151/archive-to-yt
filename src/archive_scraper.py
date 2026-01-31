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
        else:
            # Check if there are more audio files than tracks extracted from description
            # This handles cases like disc 2 where description doesn't list individual tracks
            audio_files = [
                f for f in files 
                if any(f.get('name', '').lower().endswith(ext) for ext in ['.flac', '.mp3', '.wav', '.m4a', '.ogg', '.oggvorbis'])
            ]
            # Count unique tracks (prefer FLAC, ignore MP3 duplicates)
            unique_tracks = set()
            for f in audio_files:
                filename = f.get('name', '').lower()
                # Extract disc and track pattern (e.g., d1t01, d2t01)
                disc_track_match = re.search(r'd(\d+)t(\d+)', filename)
                if disc_track_match:
                    disc_num = disc_track_match.group(1)
                    track_num = disc_track_match.group(2)
                    unique_tracks.add(f"d{disc_num}t{track_num}")
                else:
                    # Fallback: extract any track number pattern
                    track_match = re.search(r't(\d+)', filename)
                    if track_match:
                        unique_tracks.add(f"t{track_match.group(1)}")
            
            # If we have more unique tracks than extracted tracks, extract additional ones from filenames
            if len(unique_tracks) > len(tracks):
                logger.info(f"Found {len(unique_tracks)} unique audio tracks but only {len(tracks)} tracks in description")
                logger.info("Extracting additional tracks from filenames...")
                additional_tracks = self._extract_tracks_from_files_disc_aware(files, existing_track_count=len(tracks))
                if additional_tracks:
                    tracks.extend(additional_tracks)
                    logger.info(f"Added {len(additional_tracks)} additional tracks from filenames (total: {len(tracks)})")

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
        # Be more strict: track names should be reasonable length and not look like metadata
        
        # First, try to find a section that looks like a track list
        # Look for patterns like "Set I", "Set II", "Disc 1", or just a sequence of numbered items
        track_list_section = description_clean
        
        # Try to find the track list section (between common markers)
        # Look for a sequence of at least 5 consecutive numbered items (01. Track, 02. Track, etc.)
        consecutive_tracks_pattern = r'(\d{1,2}\.\s+[^\n]+(?:\n\d{1,2}\.\s+[^\n]+){4,})'
        consecutive_match = re.search(consecutive_tracks_pattern, description_clean, re.MULTILINE)
        if consecutive_match:
            track_list_section = consecutive_match.group(1)
            logger.debug(f"Found track list section: {len(track_list_section)} chars with consecutive numbered items")
        else:
            # Fallback: look for section markers
            section_patterns = [
                r'(?:Set\s+[IVX]+|Disc\s+\d+|Track\s+List|Tracks?)[:\s]*\n\n?(.*?)(?:\n\n|\n\*|Taper\s+notes|Transfer\s+notes|Recorded\s+by|$)',  # Track list section
            ]
            
            for section_pattern in section_patterns:
                section_match = re.search(section_pattern, description_clean, re.IGNORECASE | re.DOTALL)
                if section_match:
                    track_list_section = section_match.group(1) if section_match.groups() else section_match.group(0)
                    logger.debug(f"Found track list section using marker pattern")
                    break
        
        # Look for numbered track list patterns in the section
        # Be more strict: track numbers should be followed by track names, not dates or locations
        track_patterns = [
            r'(\d{2})\.\s+([^\n]+?)(?=\s*\d{2}\.\s*|\s*\d{1}\.\s*|$|\n\n|\n\*|\nTaper|\nTransfer|\nRecorded)',  # Two-digit format
            r'(\d{1,2})\.\s+([^\n]+?)(?=\s*\d{1,2}\.\s*|$|\n\n|\n\*|\nTaper|\nTransfer|\nRecorded)',  # One or two digit format
        ]

        seen_track_numbers = set()  # Track numbers we've already added to avoid duplicates
        
        for pattern in track_patterns:
            matches = re.findall(pattern, track_list_section, re.MULTILINE)
            if matches:
                for number, name in matches:
                    # Pad single digits to two digits
                    track_num = number.zfill(2)
                    
                    # Skip if we've already seen this track number (avoid duplicates)
                    if track_num in seen_track_numbers:
                        continue
                    
                    # Clean up track name: remove extra whitespace, HTML remnants
                    clean_name = re.sub(r'\s+', ' ', name.strip())
                    # Remove any remaining HTML entities
                    clean_name = clean_name.replace('&nbsp;', ' ').strip()
                    
                    # Filter out invalid track names:
                    # Check invalid patterns - some need case-sensitive matching
                    is_invalid = False
                    
                    # Case-insensitive patterns
                    case_insensitive_patterns = [
                        r'^[A-Z][a-z]+\s+[A-Z][a-z]+,\s+[A-Z]{2}',  # Location patterns (Cropseyville NY, Kansasville WI)
                        r'^[A-Z][a-z]+\s+[A-Z][a-z]+\'s',  # Possessive patterns (Martha Mary Lane's)
                        r'^[A-Z][a-z]+\s+by:',  # "Recorded by:", "Transfer by:"
                        r'^[A-Z][a-z]+\s+notes:',  # "Taper notes:", "Transfer notes:"
                        r'^[A-Z][a-z]+\s+[A-Z][a-z]+:',  # Other metadata patterns
                        r'^[A-Z][a-z]+\.flac\d+',  # Filename patterns (Romp2010-04-02.flac16)
                    ]
                    
                    for pattern in case_insensitive_patterns:
                        if re.match(pattern, clean_name, re.IGNORECASE):
                            is_invalid = True
                            logger.debug(f"Skipping invalid track name: '{clean_name}' (matches pattern: {pattern})")
                            break
                    
                    # Case-sensitive patterns (to avoid false matches)
                    if not is_invalid:
                        case_sensitive_patterns = [
                            r'^\d{4}[-/]\d',  # Date patterns (2010-04-02, 6/25/11)
                            r'^\d{1,2}[-/]\d',  # Date patterns (04/02, 6/25, May 01)
                            r'^[A-Z][a-z]+\s+\d{1,2},\s+\d{4}',  # "May 01, 2010"
                            r'^[()]+$',  # Just parentheses
                            r'^[A-Z]{2,}\s*$',  # Just uppercase letters ONLY (no lowercase) - case sensitive
                        ]
                        
                        for pattern in case_sensitive_patterns:
                            if re.match(pattern, clean_name):  # No IGNORECASE flag
                                is_invalid = True
                                logger.debug(f"Skipping invalid track name: '{clean_name}' (matches pattern: {pattern})")
                                break
                    
                    # Additional checks
                    if len(clean_name) < 2:
                        is_invalid = True
                    if len(clean_name) > 200:
                        is_invalid = True
                    
                    # Check if it looks like a filename pattern that should be handled differently
                    # Patterns like "Lane Family.2011-06-25.t01" or "Romp2010-04-02.T01" or "Lane Family.2011-06-"
                    if re.search(r'\.t\d+$', clean_name) or re.search(r'\.T\d+$', clean_name) or re.search(r'\.\d{4}-\d{2}-$', clean_name):
                        # This is a filename pattern - extract track number and use generic name
                        track_match = re.search(r'[tT](\d+)$', clean_name)
                        if track_match:
                            # Use a generic name since the actual track name isn't in the description
                            clean_name = f"Track {track_match.group(1)}"
                            # Also update track_num to match the filename's track number
                            track_num = track_match.group(1).zfill(2)
                        else:
                            # Pattern like "Lane Family.2011-06-" - extract from track_num we already have
                            clean_name = f"Track {track_num}"
                            is_invalid = False  # Override invalid flag since we're fixing it
                    
                    # Check if name contains a date pattern (like "May 01, 2010")
                    if re.search(r'[A-Z][a-z]+\s+\d{1,2}[,\s]+\d{4}', clean_name):
                        is_invalid = True
                    
                    if not is_invalid and clean_name:
                        tracks.append({
                            'number': track_num,
                            'name': clean_name
                        })
                        seen_track_numbers.add(track_num)
                
                # Only use matches if we got reasonable number of tracks (more than 1, less than 100)
                # And check for duplicates - if we have duplicate track numbers, something is wrong
                unique_track_nums = set(t['number'] for t in tracks)
                if len(tracks) > 1 and len(tracks) < 100 and len(unique_track_nums) == len(tracks):
                    logger.debug(f"Extracted {len(tracks)} tracks from description")
                    break  # Use first pattern that finds matches
                else:
                    if len(unique_track_nums) != len(tracks):
                        logger.warning(f"Found duplicate track numbers, resetting extraction")
                    tracks = []  # Reset if we didn't get good matches
                    seen_track_numbers = set()

        # Log first few tracks for debugging
        if tracks:
            logger.debug(f"Sample tracks extracted: {tracks[:3]}")
        
        return tracks

    def _extract_tracks_from_files_disc_aware(self, files: List[Dict], existing_track_count: int = 0) -> List[Dict[str, str]]:
        """
        Extract tracks from filenames, handling disc-based naming (d1t01, d2t01).
        Only extracts tracks that aren't already in the existing tracks list.
        
        Args:
            files: List of file dictionaries from API
            existing_track_count: Number of tracks already extracted (to continue numbering)
            
        Returns:
            List of dictionaries with 'number' and 'name' keys
        """
        tracks = []
        audio_extensions = ['.flac', '.mp3', '.wav', '.m4a', '.ogg', '.oggvorbis']
        
        # Filter audio files, prefer FLAC over MP3
        audio_files = []
        seen_tracks = set()
        
        for f in files:
            filename = f.get('name', '')
            if not any(filename.lower().endswith(ext) for ext in audio_extensions):
                continue
            
            # Extract disc and track pattern (e.g., d1t01, d2t01)
            disc_track_match = re.search(r'd(\d+)t(\d+)', filename.lower())
            if disc_track_match:
                disc_num = disc_track_match.group(1)
                track_num = disc_track_match.group(2)
                track_key = f"d{disc_num}t{track_num}"
                
                # Prefer FLAC over MP3
                if track_key not in seen_tracks or filename.lower().endswith('.flac'):
                    if track_key in seen_tracks:
                        # Replace MP3 with FLAC
                        for i, existing in enumerate(audio_files):
                            if existing.get('key') == track_key and not existing.get('filename', '').lower().endswith('.flac'):
                                audio_files[i] = {'filename': filename, 'key': track_key, 'disc': disc_num, 'track': track_num}
                                break
                    else:
                        audio_files.append({'filename': filename, 'key': track_key, 'disc': disc_num, 'track': track_num})
                        seen_tracks.add(track_key)
            else:
                # Fallback: extract any track number
                track_match = re.search(r't(\d+)', filename.lower())
                if track_match:
                    track_num = track_match.group(1)
                    track_key = f"t{track_num}"
                    if track_key not in seen_tracks or filename.lower().endswith('.flac'):
                        if track_key not in seen_tracks:
                            audio_files.append({'filename': filename, 'key': track_key, 'disc': '1', 'track': track_num})
                            seen_tracks.add(track_key)
        
        # Filter to only disc 2 tracks (or tracks not in disc 1)
        # We only want to add tracks that aren't already extracted from description
        disc2_files = [af for af in audio_files if af.get('disc', '1') != '1']
        disc1_files = [af for af in audio_files if af.get('disc', '1') == '1']
        
        # Only extract disc 2 tracks (or if no disc info, extract all that aren't disc 1)
        files_to_extract = disc2_files if disc2_files else [af for af in audio_files if af not in disc1_files]
        
        # Sort by disc number, then track number
        files_to_extract.sort(key=lambda x: (int(x.get('disc', 2)), int(x.get('track', 0))))
        
        # Extract tracks starting from existing_track_count + 1
        track_counter = existing_track_count + 1
        for audio_file in files_to_extract:
            filename = audio_file['filename']
            track_num_from_file = audio_file.get('track', '01')
            disc_num = audio_file.get('disc', '2')
            
            # Use sequential numbering across discs
            track_num = f"{track_counter:02d}"
            
            # Extract track name from filename (use basename only)
            track_name = os.path.basename(filename)
            track_name = re.sub(r'\.(flac|mp3|wav|m4a|ogg|oggvorbis)$', '', track_name, flags=re.IGNORECASE)
            # Remove disc/track patterns (d1t01, d2t01, etc.)
            track_name = re.sub(r'[dD]\d+[tT]\d+', '', track_name)
            track_name = re.sub(r'^(track[-_\s]*\d+[-_\s]*)', '', track_name, flags=re.IGNORECASE)
            # Remove common prefixes
            track_name = re.sub(r'^(studio[-_\s]*album[-_\s]*)', '', track_name, flags=re.IGNORECASE)
            track_name = re.sub(r'^romp[-_\s]*', '', track_name, flags=re.IGNORECASE)
            track_name = re.sub(r'[-_\s]+', ' ', track_name).strip()
            
            if not track_name or len(track_name) < 3:
                # Use generic name with disc info
                if disc_num != '1':
                    track_name = f"Disc {disc_num}, Track {track_num_from_file}"
                else:
                    track_name = f"Track {track_num_from_file}"
            
            tracks.append({
                'number': track_num,
                'name': track_name
            })
            track_counter += 1
        
        return tracks

    def _extract_tracks_from_files(self, files: List[Dict]) -> List[Dict[str, str]]:
        """
        Try to infer tracks from audio file names.
        Prefers FLAC over MP3 to avoid duplicates.

        Returns:
            List of dictionaries with 'number' and 'name' keys
        """
        tracks = []
        audio_extensions = ['.flac', '.mp3', '.wav', '.m4a', '.ogg', '.oggvorbis']
        
        # Filter audio files, prefer FLAC over MP3
        audio_files_dict = {}  # key: track identifier, value: file info
        file_priority = {'.flac': 1, '.wav': 2, '.m4a': 3, '.ogg': 4, '.oggvorbis': 4, '.mp3': 5}
        
        for f in files:
            filename = f.get('name', '')
            if not any(filename.lower().endswith(ext) for ext in audio_extensions):
                continue
            
            # Extract track identifier - look for patterns like T01, t01, d1t01, etc.
            track_key = None
            track_num_from_file = None
            
            # Try disc-based pattern first (d1t01, d2t01)
            disc_track_match = re.search(r'[dD](\d+)[tT](\d+)', filename)
            if disc_track_match:
                track_key = f"d{disc_track_match.group(1)}t{disc_track_match.group(2)}"
                track_num_from_file = disc_track_match.group(2)
            else:
                # Try T01, t01 pattern (uppercase or lowercase T)
                track_match = re.search(r'[tT](\d+)', filename)
                if track_match:
                    track_key = f"t{track_match.group(1)}"
                    track_num_from_file = track_match.group(1)
            
            if track_key:
                # Get file extension priority
                ext_priority = 999
                for ext, priority in file_priority.items():
                    if filename.lower().endswith(ext):
                        ext_priority = priority
                        break
                
                # Prefer higher quality (lower priority number)
                if track_key not in audio_files_dict or ext_priority < audio_files_dict[track_key]['priority']:
                    audio_files_dict[track_key] = {
                        'filename': filename,
                        'track_num': track_num_from_file,
                        'priority': ext_priority
                    }
        
        # Convert to list and sort by track number
        audio_files_list = []
        for track_key, file_info in audio_files_dict.items():
            audio_files_list.append({
                'filename': file_info['filename'],
                'track_num': file_info['track_num']
            })
        
        # Sort by track number (extract numeric part for sorting)
        def sort_key(x):
            track_num = x['track_num']
            if track_num:
                return int(track_num)
            return 999
        
        audio_files_list.sort(key=sort_key)
        
        for i, audio_file in enumerate(audio_files_list, 1):
            filename = audio_file['filename']
            track_num_from_file = audio_file['track_num']
            
            # Use track number from filename if available, otherwise use index
            if track_num_from_file:
                track_num = track_num_from_file.zfill(2)
            else:
                track_num = f"{i:02d}"
            
            # Extract track name from filename (use basename only)
            track_name = os.path.basename(filename)
            track_name = re.sub(r'\.(flac|mp3|wav|m4a|ogg|oggvorbis)$', '', track_name, flags=re.IGNORECASE)
            # Remove track number patterns
            track_name = re.sub(r'[dD]\d+[tT]\d+', '', track_name)
            track_name = re.sub(r'[tT]\d+', '', track_name)
            track_name = re.sub(r'^(track[-_\s]*\d+[-_\s]*)', '', track_name, flags=re.IGNORECASE)
            track_name = re.sub(r'[-_\s]+', ' ', track_name).strip()
            
            if not track_name or len(track_name) < 2:
                track_name = f"Track {track_num_from_file if track_num_from_file else i}"
            
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
        Prefers FLAC over MP3 to avoid duplicates.

        Returns:
            List of dictionaries with file information
        """
        if not self.api_data:
            self.fetch_api_data()

        files = self.api_data.get('files', [])
        audio_files = []
        audio_extensions = ['.flac', '.mp3', '.wav', '.m4a', '.ogg', '.oggvorbis']
        
        # Track unique tracks (by disc/track pattern) to prefer FLAC over MP3
        seen_tracks = {}
        file_priority = {'.flac': 1, '.wav': 2, '.m4a': 3, '.ogg': 4, '.oggvorbis': 4, '.mp3': 5}

        for file_info in files:
            filename = file_info.get('name', '')
            if not any(filename.lower().endswith(ext) for ext in audio_extensions):
                continue
            
            # Extract track identifier (disc+track pattern or just track)
            track_key = None
            disc_track_match = re.search(r'[dD](\d+)[tT](\d+)', filename)
            if disc_track_match:
                track_key = f"d{disc_track_match.group(1)}t{disc_track_match.group(2)}"
            else:
                track_match = re.search(r'[tT](\d+)', filename)
                if track_match:
                    track_key = f"t{track_match.group(1)}"
            
            # Construct download URL
            download_url = f"https://archive.org/download/{self.identifier}/{filename}"
            safe_filename = os.path.basename(filename)
            
            # Get file extension priority
            ext_priority = 999
            for ext, priority in file_priority.items():
                if filename.lower().endswith(ext):
                    ext_priority = priority
                    break
            
            # If we have a track key, prefer higher quality (lower priority number)
            if track_key:
                if track_key not in seen_tracks or ext_priority < seen_tracks[track_key]['priority']:
                    seen_tracks[track_key] = {
                        'filename': safe_filename,
                        'url': download_url,
                        'priority': ext_priority
                    }
            else:
                # No track key, just add it
                audio_files.append({
                    'filename': safe_filename,
                    'url': download_url
                })
        
        # Add unique tracks (preferring FLAC)
        for track_data in seen_tracks.values():
            audio_files.append({
                'filename': track_data['filename'],
                'url': track_data['url']
            })

        # Sort by filename to maintain consistent order
        audio_files.sort(key=lambda x: x['filename'].lower())
        
        logger.info(f"Found {len(audio_files)} unique audio files from API (preferring FLAC over MP3)")
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
            track_index = int(track_num) - 1  # 0-based index

            # Try to find matching audio file
            matched_file = None
            for i, audio_file in enumerate(audio_files):
                if i in used_audio_files:
                    continue
                    
                filename = audio_file['filename'].lower()
                # Check if track number is in filename (various formats)
                track_num_str = track_num.lstrip('0')  # Remove leading zeros
                track_num_padded = track_num.zfill(2)  # Ensure two digits
                
                # For disc-based files, calculate which sequential track this file corresponds to
                # Check if this is a disc-based file (d1t01, d2t01, etc.)
                disc_track_match = re.search(r'd(\d+)t(\d+)', filename)
                if disc_track_match:
                    file_disc = int(disc_track_match.group(1))
                    file_track = int(disc_track_match.group(2))
                    
                    # Calculate which sequential track number this disc/track corresponds to
                    # Count how many tracks are in disc 1 (tracks numbered 01-10 typically)
                    disc1_tracks = len([t for t in tracks if int(t['number']) <= 10])
                    
                    if file_disc == 1:
                        # Disc 1 tracks are numbered 01-10 (or however many disc 1 has)
                        file_sequential_track = file_track
                    else:
                        # Disc 2+ tracks continue the numbering after disc 1
                        file_sequential_track = disc1_tracks + file_track
                    
                    # Check if this file's sequential track number matches our current track
                    if file_sequential_track == int(track_num):
                        matched = True
                        logger.debug(f"Matched disc-based pattern: track {track_num} to file '{filename}' (disc {file_disc}, track {file_track})")
                        matched_file = audio_file
                        used_audio_files.add(i)
                        logger.info(f"✓ Matched track {track_num} '{track_name}' to audio file [{i}] {audio_file['filename']}")
                        logger.info(f"  Verified: disc {file_disc}, track {file_track} -> sequential track {file_sequential_track}")
                        break
                    else:
                        continue  # Skip this file, it's for a different sequential track number
                
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
                
                # First try specific patterns (t01, track01, d1t01, d2t01, etc.) - these are more reliable
                specific_patterns = [
                    f"d1t{track_num_padded}",  # d1t01, d1t02 (disc 1)
                    f"d1t{track_num_str}",    # d1t1, d1t2
                    f"d2t{track_num_padded}",  # d2t01, d2t02 (disc 2)
                    f"d2t{track_num_str}",    # d2t1, d2t2
                    rf"d\d+t{track_num_padded}",  # dXt01 (any disc)
                    rf"d\d+t{track_num_str}",     # dXt1 (any disc)
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
                    # For patterns with regex (like d\d+t), compile directly
                    if '\\d' in pattern:
                        pattern_re = re.compile(pattern, re.IGNORECASE)
                    else:
                        # For literal patterns, check they're not part of a larger number
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
                        f"d1t{track_num_padded}",  # d1t03
                        f"d1t{track_num_str}",     # d1t3
                        f"d2t{track_num_padded}",  # d2t03
                        f"d2t{track_num_str}",     # d2t3
                        rf"d\d+t{track_num_padded}",  # dXt03 (any disc)
                        rf"d\d+t{track_num_str}",     # dXt3 (any disc)
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
                        # Handle regex patterns (like d\d+t)
                        if '\\d' in pattern:
                            pattern_re = re.compile(pattern, re.IGNORECASE)
                        else:
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
