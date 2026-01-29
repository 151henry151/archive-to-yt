"""
Archive.org metadata scraper.

Extracts track information, metadata, and background images from archive.org detail pages.
"""

import re
import logging
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class ArchiveScraper:
    """Scraper for archive.org detail pages."""

    def __init__(self, url: str):
        """
        Initialize scraper with archive.org URL.

        Args:
            url: Archive.org detail page URL (e.g., https://archive.org/details/lf2007-11-21.a)
        """
        self.url = url
        self.identifier = self._extract_identifier(url)
        self.soup = None
        self.metadata = {}

    @staticmethod
    def _extract_identifier(url: str) -> str:
        """Extract identifier from archive.org URL."""
        # URL format: https://archive.org/details/IDENTIFIER
        match = re.search(r'/details/([^/?#]+)', url)
        if not match:
            raise ValueError(f"Invalid archive.org URL format: {url}")
        return match.group(1)

    def fetch_page(self) -> None:
        """Fetch and parse the archive.org detail page."""
        logger.info(f"Fetching archive.org page: {self.url}")
        try:
            response = requests.get(self.url, timeout=30)
            response.raise_for_status()
            self.soup = BeautifulSoup(response.content, 'html.parser')
            logger.info("Successfully fetched archive.org page")
        except requests.RequestException as e:
            logger.error(f"Failed to fetch archive.org page: {e}")
            raise

    def extract_metadata(self) -> Dict:
        """
        Extract all metadata from the page.

        Returns:
            Dictionary containing all extracted metadata
        """
        if not self.soup:
            self.fetch_page()

        logger.info("Extracting metadata from archive.org page")

        metadata = {
            'identifier': self.identifier,
            'url': self.url,
            'title': self._extract_title(),
            'artist': self._extract_artist(),
            'venue': self._extract_venue(),
            'location': self._extract_location(),
            'date': self._extract_date(),
            'year': self._extract_year(),
            'taped_by': self._extract_taped_by(),
            'transferred_by': self._extract_transferred_by(),
            'lineage': self._extract_lineage(),
            'topics': self._extract_topics(),
            'collection': self._extract_collection(),
            'description': self._extract_full_description(),
            'tracks': self._extract_tracks(),
            'background_image_url': self._extract_background_image(),
        }

        self.metadata = metadata
        logger.info(f"Extracted metadata: {len(metadata.get('tracks', []))} tracks found")
        return metadata

    def _extract_title(self) -> str:
        """Extract title from page."""
        # Try multiple selectors for title
        title_elem = (
            self.soup.select_one('h1.item-title') or
            self.soup.select_one('meta[property="og:title"]') or
            self.soup.select_one('title')
        )
        if title_elem:
            title = title_elem.get('content') if title_elem.name == 'meta' else title_elem.get_text(strip=True)
            # Remove "by Artist" suffix if present
            title = re.sub(r'\s+by\s+.*$', '', title, flags=re.IGNORECASE)
            return title.strip()
        return ""

    def _extract_artist(self) -> str:
        """Extract artist/band name."""
        # Look for "by Artist" in title or metadata
        title_elem = self.soup.select_one('h1.item-title')
        if title_elem:
            match = re.search(r'by\s+(.+?)(?:\s*$|\s*Publication)', title_elem.get_text(), re.IGNORECASE)
            if match:
                return match.group(1).strip()

        # Try metadata field
        metadata = self.soup.find('div', class_='item-details')
        if metadata:
            for row in metadata.find_all('div', class_='metadata-row'):
                label = row.find('div', class_='metadata-label')
                if label and 'band' in label.get_text().lower() or 'artist' in label.get_text().lower():
                    value = row.find('div', class_='metadata-value')
                    if value:
                        return value.get_text(strip=True)
        return ""

    def _extract_venue(self) -> str:
        """Extract venue information."""
        metadata = self.soup.find('div', class_='item-details')
        if metadata:
            for row in metadata.find_all('div', class_='metadata-row'):
                label = row.find('div', class_='metadata-label')
                if label and 'venue' in label.get_text().lower():
                    value = row.find('div', class_='metadata-value')
                    if value:
                        return value.get_text(strip=True)
        return ""

    def _extract_location(self) -> str:
        """Extract location information."""
        metadata = self.soup.find('div', class_='item-details')
        if metadata:
            for row in metadata.find_all('div', class_='metadata-row'):
                label = row.find('div', class_='metadata-label')
                if label and 'location' in label.get_text().lower():
                    value = row.find('div', class_='metadata-value')
                    if value:
                        return value.get_text(strip=True)
        return ""

    def _extract_date(self) -> str:
        """Extract publication/recording date."""
        metadata = self.soup.find('div', class_='item-details')
        if metadata:
            for row in metadata.find_all('div', class_='metadata-row'):
                label = row.find('div', class_='metadata-label')
                if label and 'publication date' in label.get_text().lower():
                    value = row.find('div', class_='metadata-value')
                    if value:
                        date_text = value.get_text(strip=True)
                        # Extract just the date part (YYYY-MM-DD)
                        match = re.search(r'(\d{4}-\d{2}-\d{2})', date_text)
                        if match:
                            return match.group(1)
        return ""

    def _extract_year(self) -> str:
        """Extract year."""
        date = self._extract_date()
        if date:
            match = re.search(r'(\d{4})', date)
            if match:
                return match.group(1)

        metadata = self.soup.find('div', class_='item-details')
        if metadata:
            for row in metadata.find_all('div', class_='metadata-row'):
                label = row.find('div', class_='metadata-label')
                if label and 'year' in label.get_text().lower():
                    value = row.find('div', class_='metadata-value')
                    if value:
                        return value.get_text(strip=True)
        return ""

    def _extract_taped_by(self) -> str:
        """Extract 'Taped by' credit."""
        metadata = self.soup.find('div', class_='item-details')
        if metadata:
            for row in metadata.find_all('div', class_='metadata-row'):
                label = row.find('div', class_='metadata-label')
                if label and 'taped by' in label.get_text().lower():
                    value = row.find('div', class_='metadata-value')
                    if value:
                        return value.get_text(strip=True)
        return ""

    def _extract_transferred_by(self) -> str:
        """Extract 'Transferred by' credit."""
        metadata = self.soup.find('div', class_='item-details')
        if metadata:
            for row in metadata.find_all('div', class_='metadata-row'):
                label = row.find('div', class_='metadata-label')
                if label and 'transferred by' in label.get_text().lower():
                    value = row.find('div', class_='metadata-value')
                    if value:
                        return value.get_text(strip=True)
        return ""

    def _extract_lineage(self) -> str:
        """Extract lineage information."""
        metadata = self.soup.find('div', class_='item-details')
        if metadata:
            for row in metadata.find_all('div', class_='metadata-row'):
                label = row.find('div', class_='metadata-label')
                if label and 'lineage' in label.get_text().lower():
                    value = row.find('div', class_='metadata-value')
                    if value:
                        return value.get_text(strip=True)
        return ""

    def _extract_topics(self) -> List[str]:
        """Extract topics."""
        topics = []
        metadata = self.soup.find('div', class_='item-details')
        if metadata:
            for row in metadata.find_all('div', class_='metadata-row'):
                label = row.find('div', class_='metadata-label')
                if label and 'topics' in label.get_text().lower():
                    value = row.find('div', class_='metadata-value')
                    if value:
                        links = value.find_all('a')
                        topics = [link.get_text(strip=True) for link in links]
        return topics

    def _extract_collection(self) -> str:
        """Extract collection name."""
        metadata = self.soup.find('div', class_='item-details')
        if metadata:
            for row in metadata.find_all('div', class_='metadata-row'):
                label = row.find('div', class_='metadata-label')
                if label and 'collection' in label.get_text().lower():
                    value = row.find('div', class_='metadata-value')
                    if value:
                        return value.get_text(strip=True)
        return ""

    def _extract_full_description(self) -> str:
        """Extract full description text from the page."""
        # Try to find description in various places
        desc_elem = (
            self.soup.select_one('div.item-description') or
            self.soup.select_one('div#descript') or
            self.soup.select_one('meta[name="description"]')
        )
        if desc_elem:
            if desc_elem.name == 'meta':
                return desc_elem.get('content', '')
            return desc_elem.get_text(strip=True)
        return ""

    def _extract_tracks(self) -> List[Dict[str, str]]:
        """
        Extract track list from the page.

        Returns:
            List of dictionaries with 'number' and 'name' keys
        """
        tracks = []

        # Look for track list in various formats
        # Format 1: Numbered list in description or metadata
        description = self._extract_full_description()
        track_pattern = r'(\d{2})\.\s*(.+?)(?:\n|$)'
        matches = re.findall(track_pattern, description, re.MULTILINE)
        if matches:
            for number, name in matches:
                tracks.append({
                    'number': number,
                    'name': name.strip()
                })

        # Format 2: Look in item-description or other text areas
        if not tracks:
            desc_elem = self.soup.select_one('div.item-description')
            if desc_elem:
                text = desc_elem.get_text()
                matches = re.findall(track_pattern, text, re.MULTILINE)
                for number, name in matches:
                    tracks.append({
                        'number': number,
                        'name': name.strip()
                    })

        # Format 3: Look for audio file names that might indicate tracks
        if not tracks:
            # Try to infer from file names
            audio_files = self._find_audio_files()
            for i, audio_file in enumerate(audio_files, 1):
                # Extract track name from filename if possible
                filename = audio_file.get('filename', '')
                track_name = re.sub(r'\.(flac|mp3|wav|m4a)$', '', filename, flags=re.IGNORECASE)
                tracks.append({
                    'number': f"{i:02d}",
                    'name': track_name
                })

        return tracks

    def _extract_background_image(self) -> Optional[str]:
        """
        Extract background image URL from the page.

        Returns:
            URL of the background image, or None if not found
        """
        # Look for background image in various places
        # Common pattern: https://ia800801.us.archive.org/14/items/IDENTIFIER/.../img.jpg

        # Try to find in page metadata
        img_elem = (
            self.soup.select_one('img.item-img') or
            self.soup.select_one('div.item-img img') or
            self.soup.select_one('meta[property="og:image"]')
        )

        if img_elem:
            img_url = img_elem.get('src') or img_elem.get('content')
            if img_url:
                # Make absolute URL if relative
                if img_url.startswith('//'):
                    img_url = 'https:' + img_url
                elif img_url.startswith('/'):
                    img_url = urljoin('https://archive.org', img_url)
                return img_url

        # Try to construct URL based on common pattern
        # Pattern: https://ia*.us.archive.org/*/items/IDENTIFIER/*/img.jpg
        base_url = f"https://archive.org/download/{self.identifier}"
        # Try common image names
        for img_name in ['img.jpg', 'cover.jpg', 'image.jpg', 'artwork.jpg']:
            test_url = f"{base_url}/{img_name}"
            # We'll verify this exists when we try to download it
            return test_url

        return None

    def _find_audio_files(self) -> List[Dict[str, str]]:
        """
        Find all audio files available for download.

        Returns:
            List of dictionaries with file information
        """
        audio_files = []
        audio_extensions = ['.flac', '.mp3', '.wav', '.m4a', '.ogg']

        # Look for download links
        download_div = self.soup.find('div', {'id': 'download-box'})
        if download_div:
            for link in download_div.find_all('a', href=True):
                href = link.get('href', '')
                filename = link.get_text(strip=True)
                if any(filename.lower().endswith(ext) for ext in audio_extensions):
                    full_url = urljoin(self.url, href)
                    audio_files.append({
                        'filename': filename,
                        'url': full_url
                    })

        return audio_files

    def get_audio_file_urls(self) -> List[Dict[str, str]]:
        """
        Get URLs for all audio files, matched to tracks if possible.

        Returns:
            List of dictionaries with track number, name, and audio URL
        """
        tracks = self.metadata.get('tracks', [])
        audio_files = self._find_audio_files()

        # Try to match tracks to audio files
        track_audio = []
        for track in tracks:
            track_num = track['number']
            track_name = track['name']

            # Try to find matching audio file
            matched_file = None
            for audio_file in audio_files:
                filename = audio_file['filename'].lower()
                # Check if track number is in filename
                if track_num in filename or f"track{track_num}" in filename:
                    matched_file = audio_file
                    break

            if matched_file:
                track_audio.append({
                    'number': track_num,
                    'name': track_name,
                    'url': matched_file['url'],
                    'filename': matched_file['filename']
                })
            elif audio_files:
                # If we have audio files but couldn't match, use them in order
                if len(track_audio) < len(audio_files):
                    audio_file = audio_files[len(track_audio)]
                    track_audio.append({
                        'number': track_num,
                        'name': track_name,
                        'url': audio_file['url'],
                        'filename': audio_file['filename']
                    })

        return track_audio

