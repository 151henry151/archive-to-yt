# Archive.org to YouTube Uploader

A Python tool that automatically downloads audio tracks from archive.org, creates videos with static background images, and uploads them to YouTube with proper metadata and playlists. Use it from the **command line** or the **Web UI**.

- **Home page:** [hromp.com/archive-to-yt](https://hromp.com/archive-to-yt/)
- **Live Web UI:** [hromp.com/archive-to-yt/app](https://hromp.com/archive-to-yt/app/) — try it in your browser

## Prerequisites

- Python 3.8 or higher
- `ffmpeg` installed and available in your PATH
  - **Linux**: `sudo apt-get install ffmpeg` (Debian/Ubuntu) or `sudo yum install ffmpeg` (RHEL/CentOS)
  - **macOS**: `brew install ffmpeg`
  - **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH
- YouTube API credentials (see setup instructions below)

## Installation

1. Clone this repository:
```bash
git clone <repository-url>
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

### Step 1: Create a Google Cloud Project

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (e.g., "Archive to YouTube")

### Step 2: Enable YouTube Data API v3

1. Go to "APIs & Services" > "Library"
2. Search for "YouTube Data API v3" and enable it

### Step 3: Create OAuth 2.0 Credentials

1. Go to "APIs & Services" > "Credentials"
2. Configure the OAuth consent screen (if prompted):
   - Choose "External"
   - Fill in required fields (app name, email)
   - Add yourself as a test user
3. Create OAuth client ID:
   - Choose "Desktop app"
   - Download the JSON file

### Step 4: Place Credentials

1. Create the `config` directory:
```bash
mkdir -p config
```

2. Move the downloaded JSON file to `config/client_secrets.json`:
```bash
mv ~/Downloads/client_secret_*.json config/client_secrets.json
```

### Step 5: First-Time Authentication

When you run the tool for the first time, a browser window will open for authentication. Sign in with your Google account and grant permissions.

## Usage

### Command line (CLI)

Run the tool with an archive.org URL:

```bash
python upload.py https://archive.org/details/lf2007-11-21.a
```

#### Command line options

```bash
python upload.py <URL> [--temp-dir DIR] [--credentials PATH]
```

- `URL`: Archive.org detail page URL (required)
- `--temp-dir`: Directory for temporary files (default: `temp`)
- `--credentials`: Path to YouTube API credentials (default: `config/client_secrets.json`)

### Workflow

1. **Preview**: Shows track information, titles, durations, and playlist details
2. **Confirmation**: Prompts for user confirmation before proceeding
3. **Check existing**: Checks for existing videos on YouTube (prevents duplicates)
4. **Download**: Downloads audio tracks and background image (skips if files exist)
5. **Create videos**: Combines audio with background image using ffmpeg (skips if videos exist)
6. **Upload**: Uploads videos to YouTube (skips if already uploaded)
7. **Create playlist**: Creates or updates YouTube playlist with all tracks
8. **Review**: Offers option to make videos and playlist public

### Web UI

A browser-based interface with the same workflow: sign in with YouTube, enter an archive.org URL, preview, optionally edit titles and descriptions and set privacy (private/unlisted/public), then process. Uploads run in the background with live progress; you can review the playlist and optionally make it public.

**Try it:** [Live Web UI](https://hromp.com/archive-to-yt/app/) | [Home page](https://hromp.com/archive-to-yt/)

#### Web UI setup (OAuth and config)

The Web UI uses a **Web application** OAuth client (not the Desktop client used by the CLI). You need both YouTube Data API v3 and a Web OAuth client:

1. **Google Cloud Console** → APIs & Services → **Credentials**
2. Create (or edit) an **OAuth 2.0 Client ID**
3. **Application type:** **Web application**
4. **Authorized redirect URIs** — add the callback URL for where you will run the app:
   - Local: `http://localhost:18765/api/auth/youtube/callback`
   - Your domain: `https://your-domain.com/api/auth/youtube/callback`
   - Path-based (e.g. hromp.com): `https://hromp.com/archive-to-yt/app/api/auth/youtube/callback`
5. Download the JSON and save it as **`config/client_secrets.json`**

You can have both Desktop (CLI) and Web (Web UI) client IDs in the same Google Cloud project; the same `client_secrets.json` file can include both. The app uses the correct client based on how it’s run.

#### Running the Web UI locally

1. Install dependencies (see [Installation](#installation)) and create `config/client_secrets.json` (see above).
2. Set a session secret (required for cookies):
   ```bash
   export SECRET_KEY="your-secret-key-for-sessions"
   ```
3. Start the server:
   ```bash
   python run_web.py
   ```
4. Open **http://localhost:18765** in your browser.

Default port is **18765**; override with `PORT=8080 python run_web.py` if needed.

#### Running the Web UI with Docker

The Web UI runs in a container that includes Python, ffmpeg, and the app. You must provide credentials and a session secret via the host.

1. Create **`config/client_secrets.json`** on your machine (see [Web UI setup](#web-ui-setup-oauth-and-config) above).
2. Set environment variables and start:
   ```bash
   export SECRET_KEY="your-secret-key"
   docker compose up --build
   ```
3. Open **http://localhost:18765**.

**What the container does:**

- **Image:** Built from `Dockerfile` (Python 3.12, ffmpeg, app dependencies).
- **Port:** **18765** (mapped to host).
- **Volumes:**
  - `./config` → `/app/config` (read-only) — so `config/client_secrets.json` is available inside the container.
  - Named volume `archive-to-yt-temp` → `/app/temp` — temporary downloads and videos (persist across restarts for resume).
- **Environment:** Set `SECRET_KEY` (required). Optionally set `PORT`, `BASE_URL` (see below).

**Example with custom port and base URL (e.g. behind a reverse proxy):**

```bash
export SECRET_KEY="your-secret-key"
export BASE_URL="https://your-domain.com/archive-to-yt"
docker compose up --build
```

For **path-based deployment** (app served under a path like `/archive-to-yt/app/`), set `BASE_URL` to the full public URL and add that callback to OAuth redirect URIs. See [WEB_UI_SETUP.md](WEB_UI_SETUP.md) for details.

#### Web UI environment variables

| Variable    | Default     | Description |
|------------|-------------|-------------|
| `PORT`     | 18765       | Port the server listens on |
| `HOST`     | 0.0.0.0     | Host to bind to |
| `SECRET_KEY` | *(none)*  | **Required.** Secret for signing session cookies |
| `BASE_URL` | *(none)*   | Public URL of the app (for OAuth redirects when behind a proxy or path) |

## Features

- **Title/description overrides & privacy**: Web UI lets you edit playlist title/description and set visibility (private/unlisted/public) before processing
- **Multi-disc support**: Automatically handles multi-disc recordings (d1t01, d2t01 patterns)
- **Resume capability**: Detects and reuses existing downloads and videos
- **Duplicate detection**: Checks for existing YouTube videos before uploading
- **Preview mode**: Shows what will be uploaded before any downloads
- **Automatic cleanup**: Temporary files deleted after successful upload
- **High-quality encoding**: 1080p H.264 video with AAC audio at 192kbps

## Resume Capability

The tool automatically detects existing files and resumes from where it left off:

- **Audio files**: Preserved until successful YouTube upload
- **Video files**: Preserved until successful YouTube upload
- **Identifier-based naming**: Files named with archive.org identifier for unique identification
- **Skip redundant work**: Reuses existing downloads and videos instead of recreating

You can safely interrupt the process and resume later without losing progress.

## Troubleshooting

### "ffmpeg is not installed"
Install ffmpeg and ensure it's in your PATH (test with `ffmpeg -version`).

### "YouTube API credentials not found"
Place your OAuth2 credentials JSON file at `config/client_secrets.json`.

### "No tracks found"
Verify the archive.org URL is correct and contains track listings.

### "Upload failed" or API errors
- Check your YouTube API quota (daily limits apply)
- Verify OAuth consent screen setup is complete
- Ensure you have permission to upload to your YouTube channel

### Videos are private
This is by design. Videos start as private. You can make them public through the interactive prompt after upload or in YouTube Studio.

## File Structure

```
archive-to-yt/
├── README.md              # This file
├── ARCHITECTURE.md        # Technical documentation
├── WEB_UI_SETUP.md        # Web UI OAuth, Docker, and deployment
├── requirements.txt       # Python dependencies
├── upload.py              # CLI entry point
├── run_web.py             # Web UI server entry point
├── config/                # Configuration directory
│   ├── client_secrets.json  # YouTube API credentials (you provide)
│   └── client_token.json    # Saved OAuth token (CLI; auto-generated)
├── src/                   # Core logic (shared by CLI and Web UI)
│   ├── main.py
│   ├── archive_scraper.py
│   ├── audio_downloader.py
│   ├── video_creator.py
│   ├── youtube_uploader.py
│   └── metadata_formatter.py
├── backend/               # Web UI API (FastAPI)
│   ├── main.py
│   └── api/               # auth, preview, process
├── frontend/              # Web UI (HTML, CSS, JS)
├── docs/                  # Additional documentation (e.g. quota request)
├── Dockerfile             # Web UI container
├── docker-compose.yml
└── temp/                  # Temporary files (auto-cleaned)
```

## Technical Details

For detailed technical information about the architecture and implementation, see [ARCHITECTURE.md](ARCHITECTURE.md).

## License

This project is licensed under the GNU General Public License v3.0 (GPL-3.0).

See [LICENSE](LICENSE) file for details.
