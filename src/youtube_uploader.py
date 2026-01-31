"""
YouTube API integration for uploading videos and creating playlists.
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

logger = logging.getLogger(__name__)

# YouTube API scopes
# youtube.upload: Required for uploading videos
# youtube: Required for creating playlists and managing playlist items
SCOPES = [
    'https://www.googleapis.com/auth/youtube.upload',
    'https://www.googleapis.com/auth/youtube'
]


class YouTubeUploader:
    """Handles YouTube video uploads and playlist creation."""

    def __init__(self, credentials_path: str = "config/client_secrets.json"):
        """
        Initialize YouTube uploader.

        Args:
            credentials_path: Path to OAuth2 credentials JSON file
        """
        self.credentials_path = Path(credentials_path)
        self.token_path = self.credentials_path.parent / "client_token.json"
        self.youtube = None
        self._authenticate()

    def _authenticate(self) -> None:
        """Authenticate with YouTube API using OAuth2."""
        creds = None

        # Load existing token if available
        if self.token_path.exists():
            logger.info("Loading existing YouTube API credentials...")
            try:
                creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
                # Check if token has all required scopes
                if creds.scopes and set(creds.scopes) != set(SCOPES):
                    logger.warning(
                        "Existing token has different scopes. Re-authentication required for playlist creation."
                    )
                    logger.warning(f"Current scopes: {creds.scopes}")
                    logger.warning(f"Required scopes: {SCOPES}")
                    logger.warning("Deleting old token file to force re-authentication...")
                    self.token_path.unlink()
                    creds = None
            except Exception as e:
                logger.warning(f"Could not load existing credentials: {e}")

        # If there are no (valid) credentials available, let the user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refreshing expired YouTube API credentials...")
                try:
                    creds.refresh(Request())
                except Exception as e:
                    logger.warning(f"Could not refresh credentials: {e}")
                    creds = None

            if not creds:
                if not self.credentials_path.exists():
                    raise FileNotFoundError(
                        f"YouTube API credentials not found at {self.credentials_path}. "
                        "Please follow the setup instructions in README.md to obtain credentials."
                    )

                logger.info("Starting OAuth2 flow for YouTube API...")
                logger.info("A browser window will open for authentication.")
                logger.info("Note: You'll need to grant permissions for both video uploads AND playlist management.")
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_path), SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Save credentials for next run
            logger.info(f"Saving credentials to {self.token_path}")
            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())

        # Build YouTube API service
        try:
            self.youtube = build('youtube', 'v3', credentials=creds)
            logger.info("Successfully authenticated with YouTube API")
        except Exception as e:
            logger.error(f"Failed to build YouTube API service: {e}")
            raise

    def upload_video(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: Optional[List[str]] = None,
        category_id: str = "10"  # Music category
    ) -> str:
        """
        Upload a video to YouTube.

        Args:
            video_path: Path to video file
            title: Video title
            description: Video description
            tags: Optional list of tags
            category_id: YouTube category ID (10 = Music)

        Returns:
            YouTube video ID
        """
        # Validate and sanitize title
        if not title or not title.strip():
            raise ValueError("Video title cannot be empty")
        
        # Ensure title is a string and strip whitespace
        title = str(title).strip()
        
        # YouTube title requirements:
        # - Must be between 1 and 100 characters
        # - Cannot be empty
        if len(title) == 0:
            raise ValueError("Video title cannot be empty after sanitization")
        if len(title) > 100:
            title = title[:97] + '...'
            logger.warning(f"Title truncated to 100 characters: {title}")
        
        logger.info(f"Uploading video: {title}")
        logger.info(f"Video file: {video_path}")
        logger.debug(f"Title length: {len(title)} characters")

        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        # Validate and sanitize description
        if description is None:
            description = ''
        
        # Ensure it's a string and handle encoding issues
        try:
            description = str(description)
        except (UnicodeError, TypeError):
            description = ''
        
        # Remove any null bytes or control characters that might cause issues
        import unicodedata
        description = ''.join(char for char in description if unicodedata.category(char)[0] != 'C' or char in '\n\t\r')
        
        description = description.strip()
        
        # Try to encode as ASCII with error handling - if it fails, use ASCII-safe version
        try:
            # Try encoding to ASCII to ensure compatibility
            description_ascii = description.encode('ascii', errors='ignore').decode('ascii')
            # Only use ASCII version if it's not too different (preserve original if possible)
            if len(description_ascii) >= len(description) * 0.8:  # If we keep at least 80% of characters
                description = description_ascii
            else:
                # Keep original but ensure it's valid UTF-8
                description.encode('utf-8')
        except (UnicodeEncodeError, UnicodeDecodeError):
            # If encoding fails, use ASCII-safe version
            logger.warning("Description contains problematic characters, using ASCII-safe version")
            description = description.encode('ascii', errors='ignore').decode('ascii')
            if not description or len(description.strip()) == 0:
                description = "Music track from archive.org"
        
        # YouTube description requirements:
        # - Must be a string (can be empty)
        # - Maximum 5000 characters
        # - Must be valid UTF-8
        if len(description) > 5000:
            description = description[:4997] + '...'
            logger.warning(f"Description truncated to 5000 characters")
        
        # Final validation: ensure it's valid UTF-8
        try:
            description.encode('utf-8')
        except UnicodeEncodeError:
            logger.error("Description contains invalid UTF-8 characters, using fallback")
            description = "Music track from archive.org"
        
        # Ensure description is not empty (YouTube requires at least something, even if minimal)
        if not description or len(description.strip()) == 0:
            logger.warning("Description is empty, using fallback")
            description = "Music track from archive.org"
        
        # Final safety: ensure it's a plain string (not bytes, not None)
        description = str(description) if description else "Music track from archive.org"
        
        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': tags or [],
                'categoryId': category_id
            },
            'status': {
                'privacyStatus': 'private'  # Start as private, user can change later
            }
        }
        
        # Log the actual body being sent (INFO level for debugging)
        logger.info(f"Request body title: '{body['snippet']['title']}'")
        logger.info(f"Request body title type: {type(body['snippet']['title'])}")
        logger.info(f"Request body title length: {len(body['snippet']['title']) if body['snippet']['title'] else 0}")
        logger.info(f"Request body description length: {len(body['snippet']['description'])}")
        logger.info(f"Request body description type: {type(body['snippet']['description'])}")
        logger.info(f"Request body description (first 200 chars): {body['snippet']['description'][:200]}..." if len(body['snippet']['description']) > 200 else f"Request body description: '{body['snippet']['description']}'")
        
        # Additional validation: check if description is actually a string in the body
        if not isinstance(body['snippet']['description'], str):
            logger.error(f"Description is not a string! Type: {type(body['snippet']['description'])}, Value: {body['snippet']['description']}")
            body['snippet']['description'] = str(body['snippet']['description']) if body['snippet']['description'] else "Music track from archive.org"
        
        # Final check: ensure description is not None or empty
        if body['snippet']['description'] is None:
            logger.error("Description is None in request body, setting fallback")
            body['snippet']['description'] = "Music track from archive.org"
        elif not body['snippet']['description']:
            logger.error("Description is empty in request body, setting fallback")
            body['snippet']['description'] = "Music track from archive.org"

        try:
            # Create media upload object
            media = MediaFileUpload(
                str(video_path),
                chunksize=-1,
                resumable=True,
                mimetype='video/*'
            )

            # Insert video
            insert_request = self.youtube.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=media
            )

            # Upload with progress
            logger.info("Uploading video to YouTube...")
            response = None
            while response is None:
                status, response = insert_request.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    logger.info(f"Upload progress: {progress}%")

            if 'id' in response:
                video_id = response['id']
                logger.info(f"Successfully uploaded video: https://www.youtube.com/watch?v={video_id}")
                return video_id
            else:
                raise RuntimeError(f"Upload failed: {response}")

        except HttpError as e:
            logger.error(f"YouTube API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Error uploading video: {e}")
            raise

    def find_existing_videos(self, archive_url: str, expected_titles: List[str]) -> Dict[str, str]:
        """
        Search for existing videos on YouTube that match the archive.org URL.
        
        Args:
            archive_url: The archive.org URL to search for in video descriptions
            expected_titles: List of expected video titles to match against
            
        Returns:
            Dictionary mapping video titles to video IDs for videos that were found
        """
        logger.info(f"Searching for existing videos with archive.org URL: {archive_url}")
        
        found_videos = {}
        
        try:
            # Search for videos containing the archive.org URL in the description
            # We'll search by the archive.org identifier (the part after /details/)
            identifier = archive_url.split('/details/')[-1].split('/')[0] if '/details/' in archive_url else ''
            
            if not identifier:
                logger.warning("Could not extract identifier from archive.org URL")
                return found_videos
            
            # Search for videos - we'll search by the identifier in the description
            # YouTube search API searches in title, description, and tags
            search_query = identifier
            
            logger.info(f"Searching YouTube for videos containing: {search_query}")
            
            # Search for videos owned by the authenticated user
            search_response = self.youtube.search().list(
                q=search_query,
                part='id,snippet',
                type='video',
                maxResults=50,  # Should be enough for most albums
                forMine=True  # Only search our own videos
            ).execute()
            
            # Match found videos to expected titles
            for item in search_response.get('items', []):
                video_id = item['id']['videoId']
                video_title = item['snippet']['title']
                video_description = item['snippet'].get('description', '')
                
                # Check if this video's description contains the archive.org URL
                if archive_url in video_description or identifier in video_description:
                    # Try to match by title (fuzzy match - check if expected title is in video title or vice versa)
                    for expected_title in expected_titles:
                        # Normalize titles for comparison (remove extra spaces, case insensitive)
                        normalized_expected = ' '.join(expected_title.lower().split())
                        normalized_video = ' '.join(video_title.lower().split())
                        
                        # Check if titles match (either exact match or one contains the other)
                        if (normalized_expected == normalized_video or 
                            normalized_expected in normalized_video or 
                            normalized_video in normalized_expected):
                            found_videos[expected_title] = video_id
                            logger.info(f"Found existing video: '{video_title}' -> {video_id}")
                            break
            
            logger.info(f"Found {len(found_videos)} existing videos out of {len(expected_titles)} expected")
            return found_videos
            
        except HttpError as e:
            logger.warning(f"Error searching for existing videos: {e}")
            logger.warning("Will proceed with uploading (may create duplicates)")
            return found_videos
        except Exception as e:
            logger.warning(f"Error searching for existing videos: {e}")
            logger.warning("Will proceed with uploading (may create duplicates)")
            return found_videos

    def get_playlist_items(self, playlist_id: str) -> List[Dict[str, str]]:
        """
        Get all videos in a playlist with their positions and titles.
        
        Args:
            playlist_id: YouTube playlist ID
            
        Returns:
            List of dictionaries with video_id, position, and title
        """
        items = []
        try:
            next_page_token = None
            while True:
                request = self.youtube.playlistItems().list(
                    part='snippet,contentDetails',
                    playlistId=playlist_id,
                    maxResults=50
                )
                if next_page_token:
                    request = request.execute()
                else:
                    response = request.execute()
                
                for item in response.get('items', []):
                    video_id = item['contentDetails']['videoId']
                    position = item['snippet'].get('position', 0)
                    title = item['snippet'].get('title', '')
                    items.append({
                        'video_id': video_id,
                        'position': position,
                        'title': title
                    })
                
                next_page_token = response.get('nextPageToken')
                if not next_page_token:
                    break
            
            # Sort by position
            items.sort(key=lambda x: x['position'])
            return items
        except HttpError as e:
            logger.error(f"Error getting playlist items: {e}")
            return []
        except Exception as e:
            logger.error(f"Error getting playlist items: {e}")
            return []

    def insert_video_to_playlist(self, playlist_id: str, video_id: str, position: int) -> bool:
        """
        Insert a video into a playlist at a specific position.
        
        Args:
            playlist_id: YouTube playlist ID
            video_id: YouTube video ID to insert
            position: Position in playlist (0-indexed)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.youtube.playlistItems().insert(
                part='snippet',
                body={
                    'snippet': {
                        'playlistId': playlist_id,
                        'resourceId': {
                            'kind': 'youtube#video',
                            'videoId': video_id
                        },
                        'position': position
                    }
                }
            ).execute()
            logger.info(f"Inserted video {video_id} at position {position} in playlist")
            return True
        except HttpError as e:
            logger.error(f"Failed to insert video at position {position}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error inserting video at position {position}: {e}")
            return False

    def find_existing_playlist(self, expected_title: str, archive_url: str = '') -> Optional[str]:
        """
        Search for an existing playlist on YouTube that matches the expected title.
        
        Args:
            expected_title: Expected playlist title to search for
            archive_url: Optional archive.org URL to verify in description
            
        Returns:
            Playlist ID if found, None otherwise
        """
        logger.info(f"Searching for existing playlist: {expected_title}")
        
        try:
            # Get all playlists owned by the authenticated user
            playlists_response = self.youtube.playlists().list(
                part='snippet,status',
                mine=True,
                maxResults=50  # Should be enough for most users
            ).execute()
            
            # Search for matching playlist
            for playlist in playlists_response.get('items', []):
                playlist_title = playlist['snippet']['title']
                playlist_description = playlist['snippet'].get('description', '')
                playlist_id = playlist['id']
                
                # Check if title matches (fuzzy match)
                normalized_expected = ' '.join(expected_title.lower().split())
                normalized_playlist = ' '.join(playlist_title.lower().split())
                
                if (normalized_expected == normalized_playlist or 
                    normalized_expected in normalized_playlist or 
                    normalized_playlist in normalized_expected):
                    # If archive_url provided, verify it's in the description
                    if archive_url:
                        if archive_url in playlist_description:
                            logger.info(f"Found existing playlist: '{playlist_title}' -> {playlist_id}")
                            return playlist_id
                    else:
                        # No URL to verify, just match by title
                        logger.info(f"Found existing playlist: '{playlist_title}' -> {playlist_id}")
                        return playlist_id
            
            logger.info("No existing playlist found")
            return None
            
        except HttpError as e:
            logger.warning(f"Error searching for existing playlist: {e}")
            return None
        except Exception as e:
            logger.warning(f"Error searching for existing playlist: {e}")
            return None

    def create_playlist(
        self,
        title: str,
        description: str,
        video_ids: List[str],
        privacy_status: str = 'private'
    ) -> str:
        """
        Create a YouTube playlist and add videos.

        Args:
            title: Playlist title
            description: Playlist description
            video_ids: List of YouTube video IDs to add
            privacy_status: Privacy status (private, unlisted, public)

        Returns:
            YouTube playlist ID
        """
        logger.info(f"Creating playlist: {title}")
        logger.info(f"Adding {len(video_ids)} videos to playlist")

        try:
            # Create playlist
            playlist_body = {
                'snippet': {
                    'title': title,
                    'description': description
                },
                'status': {
                    'privacyStatus': privacy_status
                }
            }

            playlist_response = self.youtube.playlists().insert(
                part='snippet,status',
                body=playlist_body
            ).execute()

            playlist_id = playlist_response['id']
            logger.info(f"Created playlist: https://www.youtube.com/playlist?list={playlist_id}")

            # Add videos to playlist
            for i, video_id in enumerate(video_ids, 1):
                logger.info(f"Adding video {i}/{len(video_ids)} to playlist...")
                try:
                    self.youtube.playlistItems().insert(
                        part='snippet',
                        body={
                            'snippet': {
                                'playlistId': playlist_id,
                                'resourceId': {
                                    'kind': 'youtube#video',
                                    'videoId': video_id
                                },
                                'position': i - 1  # 0-indexed
                            }
                        }
                    ).execute()
                    logger.info(f"Added video {i} to playlist")
                except HttpError as e:
                    logger.error(f"Failed to add video {i} to playlist: {e}")
                    # Continue with other videos

            logger.info(f"Successfully created playlist with {len(video_ids)} videos")
            return playlist_id

        except HttpError as e:
            logger.error(f"YouTube API error creating playlist: {e}")
            raise
        except Exception as e:
            logger.error(f"Error creating playlist: {e}")
            raise

    def update_video_privacy(self, video_id: str, privacy_status: str = 'public') -> bool:
        """
        Update the privacy status of a video.
        
        Args:
            video_id: YouTube video ID
            privacy_status: Privacy status (private, unlisted, public)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.youtube.videos().update(
                part='status',
                body={
                    'id': video_id,
                    'status': {
                        'privacyStatus': privacy_status
                    }
                }
            ).execute()
            logger.info(f"Updated video {video_id} to {privacy_status}")
            return True
        except HttpError as e:
            logger.error(f"Failed to update video {video_id} privacy: {e}")
            return False
        except Exception as e:
            logger.error(f"Error updating video {video_id} privacy: {e}")
            return False

    def update_playlist_privacy(self, playlist_id: str, privacy_status: str = 'public') -> bool:
        """
        Update the privacy status of a playlist.
        
        Args:
            playlist_id: YouTube playlist ID
            privacy_status: Privacy status (private, unlisted, public)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # First get the current playlist to preserve other fields
            playlist_response = self.youtube.playlists().list(
                part='snippet,status',
                id=playlist_id
            ).execute()
            
            if not playlist_response.get('items'):
                logger.error(f"Playlist {playlist_id} not found")
                return False
            
            playlist = playlist_response['items'][0]
            
            # Update privacy status - must include snippet in part even when only updating status
            self.youtube.playlists().update(
                part='snippet,status',
                body={
                    'id': playlist_id,
                    'snippet': playlist['snippet'],  # Preserve existing snippet data
                    'status': {
                        'privacyStatus': privacy_status
                    }
                }
            ).execute()
            logger.info(f"Updated playlist {playlist_id} to {privacy_status}")
            return True
        except HttpError as e:
            logger.error(f"Failed to update playlist {playlist_id} privacy: {e}")
            return False
        except Exception as e:
            logger.error(f"Error updating playlist {playlist_id} privacy: {e}")
            return False

    def delete_video(self, video_id: str) -> bool:
        """
        Delete a video from YouTube.
        
        Args:
            video_id: YouTube video ID to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.youtube.videos().delete(id=video_id).execute()
            logger.info(f"Deleted video {video_id}")
            return True
        except HttpError as e:
            logger.error(f"Failed to delete video {video_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error deleting video {video_id}: {e}")
            return False

    def make_videos_public(self, video_ids: List[str]) -> int:
        """
        Make multiple videos public.
        
        Args:
            video_ids: List of YouTube video IDs
            
        Returns:
            Number of videos successfully made public
        """
        logger.info(f"Making {len(video_ids)} videos public...")
        success_count = 0
        
        for i, video_id in enumerate(video_ids, 1):
            logger.info(f"Updating video {i}/{len(video_ids)} to public...")
            if self.update_video_privacy(video_id, 'public'):
                success_count += 1
        
        logger.info(f"Successfully made {success_count}/{len(video_ids)} videos public")
        return success_count

