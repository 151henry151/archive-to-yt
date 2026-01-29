# Project Plan: Archive.org to YouTube Uploader

## Overview
This tool will automate the process of downloading audio tracks from archive.org, creating videos with static background images, and uploading them to YouTube with proper metadata and playlists.

## Technical Architecture

### Core Components

1. **Archive.org Metadata Extractor**
   - Parse archive.org detail pages to extract:
     - Track list (numbered tracks with names)
     - Metadata (artist, venue, date, location, credits, etc.)
     - Background image URL
     - Audio file URLs for each track
   - Approach: Use `requests` + `BeautifulSoup` for HTML parsing, or `internetarchive` Python library if available

2. **Audio Downloader**
   - Download audio files for each track from archive.org
   - Handle different audio formats (FLAC, MP3, etc.)
   - Store temporarily for processing

3. **Video Creator**
   - Use `ffmpeg` to combine:
     - Audio track (from archive.org)
     - Static background image (from archive.org page)
   - Create MP4 videos with appropriate duration matching audio length
   - Handle aspect ratios and video encoding settings
   - Use high-quality audio encoding (AAC 192kbps or higher, within YouTube limits)
   - Preserve original audio quality when possible

4. **YouTube Uploader**
   - Authenticate with YouTube Data API v3
   - Upload videos with:
     - Title (track name)
     - Description (formatted metadata)
     - Thumbnail (background image)
   - Handle upload progress and errors

5. **Playlist Creator**
   - After all videos uploaded, create YouTube playlist
   - Add all videos to playlist in order
   - Set playlist description with full archive.org metadata

6. **Metadata Formatter**
   - Format track-specific descriptions:
     - Track name
     - Artist/Band
     - Venue and location
     - Date
     - Credits (Taped by, Transferred by)
     - Link back to original archive.org URL

## Technology Stack

### Python Packages
- `requests` - HTTP requests for archive.org
- `beautifulsoup4` - HTML parsing for metadata extraction
- `google-api-python-client` - YouTube Data API v3
- `google-auth-httplib2` - Authentication for YouTube API
- `google-auth-oauthlib` - OAuth2 flow for YouTube
- `mutagen` or `pydub` - Audio file handling/metadata
- `Pillow` - Image processing (if needed)

### External Dependencies
- `ffmpeg` - Video/audio processing (system dependency)
- YouTube API credentials (OAuth2 client credentials)

## Project Structure

```
archive-to-yt/
├── README.md
├── ARCHITECTURE.md
├── requirements.txt
├── .env.example
├── config/
│   └── youtube_credentials.json (user-provided)
├── src/
│   ├── __init__.py
│   ├── archive_scraper.py      # Archive.org metadata extraction
│   ├── audio_downloader.py     # Download audio files
│   ├── video_creator.py        # Create videos with ffmpeg
│   ├── youtube_uploader.py     # YouTube API integration
│   ├── metadata_formatter.py   # Format descriptions
│   └── main.py                 # Main orchestration
├── temp/                       # Temporary files (audio, videos)
└── tests/                      # Unit tests (optional)
```

## Implementation Steps

### Phase 1: Setup & Archive.org Integration
1. Set up Python virtual environment
2. Install dependencies
3. Implement archive.org metadata scraper
   - Extract track list from page
   - Extract metadata fields
   - Find background image URL
   - Find audio file URLs
4. Test with example URL

### Phase 2: Audio & Video Processing
1. Implement audio file downloader
2. Implement video creator using ffmpeg
   - Test with single track first
   - Ensure proper video encoding
3. Test end-to-end: download → create video

### Phase 3: YouTube Integration
1. Set up YouTube API credentials
2. Implement OAuth2 authentication flow
3. Implement video upload with metadata
4. Test single video upload

### Phase 4: Metadata & Description Formatting
1. Implement metadata formatter
2. Create track-specific descriptions
3. Create playlist description template

### Phase 5: Orchestration & Playlist
1. Implement main workflow
2. Process all tracks sequentially
3. Create playlist after all uploads
4. Add error handling and logging

### Phase 6: Documentation & Polish
1. Create README.md with:
   - Clear setup instructions
   - YouTube API credentials setup guide (step-by-step)
   - Usage examples
   - Troubleshooting section
2. Create ARCHITECTURE.md
3. Add inline documentation
4. Implement automatic cleanup of temporary files
5. Add comprehensive logging throughout
6. Add configuration examples

## Configuration Requirements

### YouTube API Setup
- Detailed step-by-step instructions will be in README.md:
  1. Create Google Cloud project
  2. Enable YouTube Data API v3
  3. Create OAuth2 credentials (Desktop application)
  4. Download credentials JSON file
  5. Place credentials in config/ directory
  6. First run will open browser for OAuth authorization

### Environment Variables
- `YOUTUBE_CREDENTIALS_PATH` - Path to OAuth2 credentials (default: config/client_secrets.json)
- `TEMP_DIR` - Directory for temporary files (default: temp/, auto-cleaned)

### Logging
- Use Python `logging` module with clear levels (INFO, WARNING, ERROR)
- Log all major operations (downloads, video creation, uploads)
- Progress indicators for long-running operations

## Error Handling Considerations

- Handle missing metadata gracefully
- Retry failed downloads/uploads
- Clean up temporary files on errors
- Validate archive.org URL format
- Handle YouTube API quota limits
- Handle missing background images

## Testing Strategy

- Test with provided example URL: `https://archive.org/details/lf2007-11-21.a`
- Verify all 16 tracks are processed correctly
- Verify metadata extraction accuracy
- Verify video quality and duration
- Verify YouTube uploads and playlist creation

## Future Enhancements (Out of Scope for Initial Build)

- Progress bars for uploads
- Resume capability for interrupted uploads
- Batch processing multiple archive.org URLs
- Custom video templates/effects
- Automatic thumbnail generation

