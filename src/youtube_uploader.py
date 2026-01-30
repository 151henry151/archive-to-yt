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
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']


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
        description = str(description).strip()
        
        # YouTube description requirements:
        # - Must be a string (can be empty)
        # - Maximum 5000 characters
        if len(description) > 5000:
            description = description[:4997] + '...'
            logger.warning(f"Description truncated to 5000 characters")
        
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
        
        # Debug: Log the actual body being sent
        logger.debug(f"Request body title: '{body['snippet']['title']}'")
        logger.debug(f"Request body title type: {type(body['snippet']['title'])}")
        logger.debug(f"Request body title length: {len(body['snippet']['title']) if body['snippet']['title'] else 0}")
        logger.debug(f"Request body description length: {len(body['snippet']['description'])}")
        logger.debug(f"Request body description preview: {body['snippet']['description'][:100]}..." if len(body['snippet']['description']) > 100 else f"Request body description: '{body['snippet']['description']}'")

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

