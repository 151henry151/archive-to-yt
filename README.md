# Archive.org to YouTube Uploader

A Python tool that automatically downloads audio tracks from archive.org, creates videos with static background images, and uploads them to YouTube with proper metadata and playlists.

## Overview

This tool automates the process of:
1. Extracting metadata and track information from archive.org detail pages
2. Downloading audio files for each track
3. Creating videos by combining audio with background images
4. Uploading videos to YouTube with formatted descriptions
5. Creating a YouTube playlist containing all tracks

## Prerequisites

- Python 3.8 or higher
- `ffmpeg` installed and available in your PATH
  - **Linux**: `sudo apt-get install ffmpeg` (Debian/Ubuntu) or `sudo yum install ffmpeg` (RHEL/CentOS)
  - **macOS**: `brew install ffmpeg`
  - **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH
- YouTube API credentials (see setup instructions below)
- Internet connection

## Installation

1. Clone or download this repository:
```bash
cd archive-to-yt
```

2. Create a Python virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## YouTube API Setup

To use this tool, you need to set up YouTube API credentials. Follow these steps:

### Step 1: Create a Google Cloud Project

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Click on the project dropdown at the top
3. Click "New Project"
4. Enter a project name (e.g., "Archive to YouTube")
5. Click "Create"

### Step 2: Enable YouTube Data API v3

1. In your Google Cloud project, go to "APIs & Services" > "Library"
2. Search for "YouTube Data API v3"
3. Click on it and press "Enable"

### Step 3: Create OAuth 2.0 Credentials

1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "OAuth client ID"
3. If prompted, configure the OAuth consent screen:
   - Choose "External" (unless you have a Google Workspace account)
   - Fill in the required fields:
     - App name: "Archive to YouTube Uploader"
     - User support email: Your email
     - Developer contact: Your email
   - Click "Save and Continue" through the scopes (no need to add any)
   - Add yourself as a test user (if using External)
   - Click "Save and Continue" to finish
4. Back in Credentials, click "Create Credentials" > "OAuth client ID"
5. Choose "Desktop app" as the application type
6. Give it a name (e.g., "Archive to YouTube")
7. Click "Create"
8. Click "Download JSON" to download your credentials file

### Step 4: Place Credentials in Project

1. Create the `config` directory if it doesn't exist:
```bash
mkdir -p config
```

2. Move the downloaded JSON file to `config/client_secrets.json`:
```bash
# Rename and move your downloaded file
mv ~/Downloads/client_secret_*.json config/client_secrets.json
```

**Important**: The file must be named `client_secrets.json` and placed in the `config/` directory.

### Step 5: First-Time Authentication

When you run the tool for the first time:
1. A browser window will automatically open
2. Sign in with the Google account that has access to your YouTube channel
3. Grant permissions to the application
4. The credentials will be saved for future use

**Note**: If you're using a test account, make sure you've added yourself as a test user in the OAuth consent screen.

## Usage

### Basic Usage

Run the tool with an archive.org URL:

```bash
python upload.py https://archive.org/details/lf2007-11-21.a
```

Or alternatively:

```bash
python src/main.py https://archive.org/details/lf2007-11-21.a
```

### Command Line Options

```bash
python upload.py [URL] [OPTIONS]

Arguments:
  URL                    Archive.org detail page URL

Options:
  --temp-dir DIR         Directory for temporary files (default: temp)
  --credentials PATH     Path to YouTube API credentials (default: config/client_secrets.json)
```

### Example

```bash
python upload.py https://archive.org/details/lf2007-11-21.a
```

This will:
1. Extract metadata and track information
2. **Show a preview** of what will be uploaded (tracks, titles, durations, playlist info)
3. **Ask for confirmation** before proceeding
4. Check for existing videos on YouTube (prevents duplicates)
5. Download audio tracks (only for videos that don't exist)
6. Create videos with the background image (only for videos that don't exist)
7. Upload each video to YouTube (only videos that don't already exist)
8. Create a playlist with all tracks
9. Offer to make videos and playlist public after review

**Note**: The preview step allows you to review all track information, titles, durations, and playlist details before any files are downloaded or uploaded. This helps ensure everything looks correct before proceeding.

## How It Works

1. **Metadata Extraction**: Uses Archive.org Metadata API to extract:
   - Track list with names (parsed from description)
   - Artist, venue, date, location
   - Credits (taped by, transferred by)
   - Background image URL
   - Audio file URLs (directly from API file list)

2. **Audio Download**: Downloads each audio track from archive.org
   - **Resume capability**: Automatically detects and reuses existing downloads
   - Files are preserved if the process is interrupted
   - Only deleted after successful YouTube upload

3. **Video Creation**: Uses `ffmpeg` to create videos:
   - Combines audio with static background image
   - High-quality encoding (H.264 video, AAC audio at 192kbps)
   - 1080p resolution

4. **YouTube Upload**: Uploads each video with:
   - Formatted title (track name, artist, date)
   - Detailed description (venue, credits, original link)
   - Private visibility by default
   - **Duplicate detection**: Checks for existing videos before uploading

5. **Playlist Creation**: Creates a YouTube playlist with:
   - All uploaded videos in order (including existing videos)
   - Full metadata description
   - Private visibility by default

6. **Interactive Publish**: After upload completes:
   - Script provides a link to review the playlist
   - Optionally make all videos and playlist public
   - Confirmation with public playlist link

## Output

- Videos are uploaded to your YouTube channel (set to **private** by default)
- A playlist is created containing all tracks (also **private** by default)
- The tool outputs:
  - Progress for each track
  - Link to review the playlist
  - Option to make videos and playlist public
  - YouTube video URLs
  - Playlist URL

## Resume Capability

The tool includes automatic resume capability:

- **Existing files are detected**: If you run the tool again with the same archive.org URL, it will detect existing audio and video files and skip re-downloading/re-creating them
- **Files preserved on failure**: If the process is interrupted (e.g., network error, YouTube API issue), both audio and video files are preserved for resume
- **Cleanup after upload**: Files are only deleted after successful YouTube upload:
  - Audio files: preserved until successful upload (not deleted after video creation)
  - Video files: preserved until successful upload (not deleted after creation)
- **Identifier-based naming**: Files are named with the archive.org identifier, so each collection's files are uniquely identified
- **Skip redundant work**: If a video has already been created but upload failed, it will be reused instead of recreating it

This means you can safely interrupt the process and resume later without losing downloaded files or having to re-encode videos.

## Troubleshooting

### "ffmpeg is not installed"
- Install ffmpeg using your system's package manager
- Ensure it's in your PATH (test with `ffmpeg -version`)

### "YouTube API credentials not found"
- Make sure you've downloaded the OAuth2 credentials JSON file
- Place it at `config/client_secrets.json`
- See the YouTube API Setup section above

### "No tracks found"
- Verify the archive.org URL is correct
- Some archive.org pages may have different formats
- Check that the page contains track listings

### "Failed to download audio file"
- Check your internet connection
- Some audio files may be very large and take time to download
- Verify the archive.org page is accessible

### "Upload failed" or API errors
- Check your YouTube API quota (daily limits apply)
- Verify you have permission to upload to the YouTube channel
- Make sure you've completed the OAuth consent screen setup

### Videos are private
- This is by design - videos start as private
- You can change visibility in YouTube Studio after upload
- To make them public/unlisted, modify the code in `src/youtube_uploader.py` (change `privacyStatus`)

## File Structure

```
archive-to-yt/
├── README.md              # This file
├── ARCHITECTURE.md        # Technical documentation
├── requirements.txt       # Python dependencies
├── config/                # Configuration directory
│   ├── client_secrets.json  # YouTube API credentials (you provide)
│   └── client_token.json    # Saved OAuth token (auto-generated)
├── src/                   # Source code
│   ├── main.py           # Main entry point
│   ├── archive_scraper.py
│   ├── audio_downloader.py
│   ├── video_creator.py
│   ├── youtube_uploader.py
│   └── metadata_formatter.py
└── temp/                  # Temporary files (auto-cleaned)
```

## Technical Details

For detailed technical information about the architecture and implementation, see [ARCHITECTURE.md](ARCHITECTURE.md).

## License

This project is licensed under the GNU General Public License v3.0 (GPL-3.0).

See [LICENSE](LICENSE) file for details.

## Contributing

This is a personal tool, but suggestions and improvements are welcome!

