"""
Metadata formatter for YouTube descriptions.

Formats track-specific and playlist descriptions from archive.org metadata.
"""

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class MetadataFormatter:
    """Formats metadata for YouTube uploads."""

    @staticmethod
    def format_track_description(track: Dict, metadata: Dict) -> str:
        """
        Format description for a single track video.

        Args:
            track: Track information (number, name, url)
            metadata: Full metadata from archive.org

        Returns:
            Formatted description string
        """
        parts = []

        # Track name
        track_name = track.get('name', 'Unknown Track')
        parts.append(track_name)

        # Artist/Band
        artist = metadata.get('artist', '')
        if artist:
            parts.append(f"performed by {artist}")

        # Venue and location
        venue = metadata.get('venue', '')
        location = metadata.get('location', '')
        if venue or location:
            venue_info = venue
            if location and location not in venue:
                if venue_info:
                    venue_info += f", {location}"
                else:
                    venue_info = location
            if venue_info:
                parts.append(f"at {venue_info}")

        # Date
        date = metadata.get('date', '')
        if date:
            # Format date nicely (YYYY-MM-DD -> MM/DD/YYYY)
            try:
                year, month, day = date.split('-')
                formatted_date = f"{month}/{day}/{year}"
                parts.append(f"on {formatted_date}")
            except ValueError:
                parts.append(f"on {date}")

        # Credits
        taped_by = metadata.get('taped_by', '')
        transferred_by = metadata.get('transferred_by', '')

        credits = []
        if taped_by:
            credits.append(f"Taped by {taped_by}")
        if transferred_by:
            credits.append(f"Transferred by {transferred_by}")

        if credits:
            parts.append(". ".join(credits) + ".")

        # Lineage
        lineage = metadata.get('lineage', '')
        if lineage:
            parts.append(f"Lineage: {lineage}")

        # Link back to original
        original_url = metadata.get('url', '')
        if original_url:
            parts.append(f"\nOriginal source: {original_url}")

        description = ". ".join(parts)
        # Clean up any double periods or spacing issues
        description = description.replace("..", ".").replace(" .", ".")
        return description

    @staticmethod
    def format_playlist_title(metadata: Dict) -> str:
        """
        Format title for YouTube playlist.

        Args:
            metadata: Full metadata from archive.org

        Returns:
            Playlist title
        """
        title = metadata.get('title', '')
        artist = metadata.get('artist', '')
        date = metadata.get('date', '')

        parts = []
        if title:
            parts.append(title)
        if artist and artist not in title:
            parts.append(f"by {artist}")
        if date:
            try:
                year, month, day = date.split('-')
                formatted_date = f"{month}/{day}/{year}"
                parts.append(f"({formatted_date})")
            except ValueError:
                parts.append(f"({date})")

        return " - ".join(parts) if parts else "Archive.org Playlist"

    @staticmethod
    def format_playlist_description(metadata: Dict, tracks: List[Dict]) -> str:
        """
        Format description for YouTube playlist.

        Args:
            metadata: Full metadata from archive.org
            tracks: List of all tracks

        Returns:
            Formatted playlist description
        """
        parts = []

        # Title
        title = metadata.get('title', '')
        if title:
            parts.append(f"Title: {title}")

        # Artist
        artist = metadata.get('artist', '')
        if artist:
            parts.append(f"Artist/Band: {artist}")

        # Venue
        venue = metadata.get('venue', '')
        if venue:
            parts.append(f"Venue: {venue}")

        # Location
        location = metadata.get('location', '')
        if location:
            parts.append(f"Location: {location}")

        # Date
        date = metadata.get('date', '')
        if date:
            parts.append(f"Date: {date}")

        # Year
        year = metadata.get('year', '')
        if year and year not in date:
            parts.append(f"Year: {year}")

        # Credits
        taped_by = metadata.get('taped_by', '')
        transferred_by = metadata.get('transferred_by', '')
        if taped_by:
            parts.append(f"Taped by: {taped_by}")
        if transferred_by:
            parts.append(f"Transferred by: {transferred_by}")

        # Lineage
        lineage = metadata.get('lineage', '')
        if lineage:
            parts.append(f"Lineage: {lineage}")

        # Topics
        topics = metadata.get('topics', [])
        if topics:
            parts.append(f"Topics: {', '.join(topics)}")

        # Collection
        collection = metadata.get('collection', '')
        if collection:
            parts.append(f"Collection: {collection}")

        # Track list
        if tracks:
            parts.append("\nTrack List:")
            for track in tracks:
                track_num = track.get('number', '')
                track_name = track.get('name', 'Unknown')
                parts.append(f"{track_num}. {track_name}")

        # Full description from archive.org
        full_description = metadata.get('description', '')
        if full_description:
            parts.append(f"\nFull Description:\n{full_description}")

        # Original URL
        original_url = metadata.get('url', '')
        if original_url:
            parts.append(f"\nOriginal source: {original_url}")

        return "\n".join(parts)

    @staticmethod
    def _sanitize_title(text: str) -> str:
        """
        Sanitize title text by removing HTML tags and entities.
        
        Args:
            text: Text to sanitize
            
        Returns:
            Cleaned text without HTML
        """
        import re
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Decode common HTML entities
        text = text.replace('&gt;', '>').replace('&lt;', '<').replace('&amp;', '&')
        text = text.replace('&nbsp;', ' ').replace('&quot;', '"').replace('&#39;', "'")
        # Clean up extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        # YouTube title limit is 100 characters
        if len(text) > 100:
            text = text[:97] + '...'
        return text

    @staticmethod
    def format_video_title(track: Dict, metadata: Dict) -> str:
        """
        Format title for a single track video.

        Args:
            track: Track information
            metadata: Full metadata

        Returns:
            Video title (sanitized, no HTML)
        """
        track_name = track.get('name', 'Unknown Track')
        # Sanitize track name to remove HTML tags
        track_name = MetadataFormatter._sanitize_title(track_name)
        
        # Ensure track name is not empty after sanitization
        if not track_name or len(track_name.strip()) == 0:
            track_num = track.get('number', '01')
            track_name = f"Track {track_num}"
        
        artist = metadata.get('artist', '')
        date = metadata.get('date', '')

        parts = [track_name]
        if artist:
            parts.append(f"by {artist}")
        if date:
            try:
                year, month, day = date.split('-')
                formatted_date = f"{month}/{day}/{year}"
                parts.append(f"({formatted_date})")
            except ValueError:
                parts.append(f"({date})")

        title = " - ".join(parts)
        # Final sanitization of the complete title
        title = MetadataFormatter._sanitize_title(title)
        
        # Final safety check - ensure title is not empty
        if not title or len(title.strip()) == 0:
            track_num = track.get('number', '01')
            title = f"Track {track_num}"
        
        return title

