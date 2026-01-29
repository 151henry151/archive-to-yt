# Architecture Documentation

## System Overview

The Archive.org to YouTube uploader is a Python application that automates the conversion of archive.org audio collections into YouTube videos. The system is designed with a modular architecture, separating concerns into distinct components.

## Architecture Diagram

```
┌─────────────────┐
│   User Input    │
│  (archive.org   │
│      URL)        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  ArchiveScraper  │ ──► Extract metadata, tracks, image URL
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ AudioDownloader │ ──► Download audio files & background image
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  VideoCreator    │ ──► Combine audio + image → MP4 video
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ MetadataFormatter│ ──► Format titles & descriptions
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ YouTubeUploader  │ ──► Upload videos & create playlist
└─────────────────┘
```

## Component Details

### 1. ArchiveScraper (`src/archive_scraper.py`)

**Purpose**: Extract metadata and track information from archive.org items using the Metadata API.

**Key Methods**:
- `fetch_api_data()`: Fetches JSON metadata from Archive.org Metadata API
- `extract_metadata()`: Extracts all metadata fields from API response
- `_extract_tracks_from_description()`: Parses track list from description text
- `_extract_tracks_from_files()`: Infers tracks from audio filenames if description parsing fails
- `_extract_background_image()`: Finds background image from API file list
- `_find_audio_files()`: Gets audio files directly from API file list
- `get_audio_file_urls()`: Matches tracks to downloadable audio files

**Technologies**:
- `requests`: HTTP requests to Archive.org Metadata API
- Archive.org Metadata API: `https://archive.org/metadata/{identifier}`

**API Endpoint**:
- Uses Archive.org's public Metadata API (no authentication required)
- Returns structured JSON with metadata and complete file list
- More reliable than HTML scraping and future-proof

**Data Extracted**:
- Title, artist, venue, location, date (from API metadata)
- Credits (taped by, transferred by) (from API metadata)
- Track list with numbers and names (parsed from description or inferred from filenames)
- Background image URL (from API file list)
- Audio file URLs (directly from API file list with download URLs)

### 2. AudioDownloader (`src/audio_downloader.py`)

**Purpose**: Download audio files and images from archive.org.

**Key Methods**:
- `download()`: Download file with progress logging
- `cleanup()`: Remove temporary files

**Features**:
- Streaming downloads for large files
- Progress logging
- Automatic cleanup
- Error handling with partial file cleanup

### 3. VideoCreator (`src/video_creator.py`)

**Purpose**: Create MP4 videos by combining audio tracks with static background images.

**Key Methods**:
- `create_video()`: Main video creation method
- `_get_audio_duration()`: Get audio length using ffprobe

**FFmpeg Configuration**:
- **Video Codec**: H.264 (libx264)
- **Video Quality**: CRF 18 (visually lossless)
- **Video Preset**: slow (high quality encoding)
- **Resolution**: 1920x1080 (1080p) with aspect ratio preservation
- **Audio Codec**: AAC
- **Audio Bitrate**: 192 kbps (high quality, within YouTube limits)
- **Pixel Format**: yuv420p (maximum compatibility)

**Why These Settings**:
- CRF 18 provides excellent quality while keeping file sizes reasonable
- 192 kbps AAC is high quality audio within YouTube's recommended limits
- 1080p resolution is standard for YouTube uploads
- Slow preset ensures best quality encoding

### 4. MetadataFormatter (`src/metadata_formatter.py`)

**Purpose**: Format metadata into YouTube-friendly titles and descriptions.

**Key Methods**:
- `format_video_title()`: Format individual track video title
- `format_track_description()`: Format track-specific description
- `format_playlist_title()`: Format playlist title
- `format_playlist_description()`: Format full playlist description

**Description Format**:
- Track name
- Artist/band information
- Venue and location
- Date
- Credits (taped by, transferred by)
- Lineage information
- Link back to original archive.org URL

### 5. YouTubeUploader (`src/youtube_uploader.py`)

**Purpose**: Handle YouTube API authentication, video uploads, and playlist creation.

**Key Methods**:
- `_authenticate()`: OAuth2 authentication flow
- `upload_video()`: Upload video with metadata
- `create_playlist()`: Create playlist and add videos

**Authentication**:
- Uses OAuth2 with Google API
- Stores credentials in `config/client_token.json`
- Automatic token refresh
- Browser-based authentication on first run

**Upload Process**:
- Resumable uploads for large files
- Progress logging
- Error handling with retry capability
- Videos set to private by default

**API Scopes**:
- `youtube.upload`: Required for uploading videos and creating playlists

### 6. Main Orchestrator (`src/main.py`)

**Purpose**: Coordinate all components to execute the full workflow.

**Workflow**:
1. Initialize all components
2. Scrape archive.org page
3. Download background image
4. For each track:
   - Download audio
   - Create video
   - Upload to YouTube
   - Clean up temporary files
5. Create YouTube playlist
6. Final cleanup

**Error Handling**:
- Continues processing if individual tracks fail
- Comprehensive logging at each step
- Automatic cleanup on errors
- Graceful handling of interruptions

## Data Flow

### Input
- Archive.org detail page URL

### Processing
1. **Metadata Extraction**: Archive.org API JSON → Parsed metadata dictionary
2. **Audio Download**: URLs → Local audio files
3. **Video Creation**: Audio + Image → MP4 video files
4. **Formatting**: Metadata → YouTube titles/descriptions
5. **Upload**: Videos → YouTube API → Video IDs
6. **Playlist**: Video IDs → YouTube Playlist

### Output
- YouTube video URLs
- YouTube playlist URL
- All videos set to private

## File Management

### Temporary Files
- Stored in `temp/` directory (configurable)
- Audio files: Downloaded from archive.org
- Video files: Created by ffmpeg
- Background image: Downloaded once, reused for all tracks

### Cleanup Strategy
- Audio files: Deleted immediately after video creation
- Video files: Deleted immediately after YouTube upload
- Background image: Deleted after all tracks processed
- All cleanup happens automatically, even on errors

## Logging

### Log Levels
- **INFO**: Normal operation progress
- **WARNING**: Non-fatal issues
- **ERROR**: Fatal errors
- **DEBUG**: Detailed debugging information

### Log Format
```
TIMESTAMP - MODULE - LEVEL - MESSAGE
```

### Key Log Points
- Metadata extraction progress
- Download progress (every MB)
- Video creation status
- Upload progress (percentage)
- Playlist creation
- Error conditions

## Error Handling

### Retry Strategy
- Network errors: Not automatically retried (user can re-run)
- API errors: Logged with details
- File errors: Cleanup and continue

### Graceful Degradation
- If a track fails, processing continues with remaining tracks
- Partial uploads are logged
- Playlist is created with successfully uploaded videos only

## Dependencies

### Python Packages
- `requests`: HTTP client (for Archive.org API and file downloads)
- `google-api-python-client`: YouTube API client
- `google-auth-oauthlib`: OAuth2 authentication
- `google-auth-httplib2`: HTTP transport for auth
- `mutagen`: Audio metadata (optional, for future enhancements)
- `Pillow`: Image processing (optional, for future enhancements)

### System Dependencies
- `ffmpeg`: Video/audio processing (required)
- `ffprobe`: Audio duration detection (part of ffmpeg)

## Configuration

### Environment Variables
- None required (all configurable via command line)

### Configuration Files
- `config/client_secrets.json`: YouTube API OAuth2 credentials (user-provided)
- `config/client_token.json`: Saved OAuth token (auto-generated)

### Default Paths
- Temp directory: `temp/`
- Credentials: `config/client_secrets.json`
- Token: `config/client_token.json`

## Performance Considerations

### Processing Time
- Metadata extraction: ~0.5-1 second (API call is faster than HTML parsing)
- Audio download: Depends on file size (typically 1-5 MB per track)
- Video creation: ~10-30 seconds per track (depends on length and CPU)
- YouTube upload: Depends on file size and connection (typically 1-5 minutes per video)

### Optimization
- Videos are processed sequentially (simpler error handling)
- Temporary files cleaned up immediately after use
- High-quality encoding uses "slow" preset (better quality, slower encoding)

## Security Considerations

### Credentials
- OAuth2 credentials stored locally
- Token file should not be committed to version control
- Credentials file should be kept private

### Privacy
- Videos uploaded as private by default
- User must manually change visibility in YouTube Studio
- Original archive.org URLs included in descriptions

## Future Enhancements

### Potential Improvements
1. Parallel processing of tracks
2. Resume capability for interrupted uploads
3. Custom video templates/effects
4. Automatic thumbnail generation
5. Batch processing multiple archive.org URLs
6. Progress bars for better UX
7. Configuration file for default settings
8. Support for different video resolutions
9. Audio normalization/processing
10. Custom description templates

### API Limitations
- YouTube API has daily quota limits
- Large files may take significant time to upload
- Some archive.org pages may have non-standard formats

