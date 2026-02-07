# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.1] - 2026-01-31

### Fixed
- **Web UI: "Edit titles & visibility" button** – Button did nothing when clicked. Added missing `showEditFromPreview` function and element references (`btnEdit`, `btnEditBack`, `editPlaylistTitle`, `editPlaylistDescription`, `editTracksContainer`) so the edit form loads correctly from the preview step.
- **Terms/Privacy back link** – Back link on Terms and Privacy pages now points to the app root (`/archive-to-yt/app/`) instead of the landing page.
- **Web UI session/login** – Reverted session cookie path and Secure flag changes that broke the login flow; keep default path and `https_only=False` for reliable session persistence after OAuth redirect.

### Changed
- **Web UI layout** – Removed duplicate Terms of Service and Privacy Policy links from the top of the app; they remain in the footer only.

## [1.1.0] - 2026-01-31

### Added
- **Terms of Service** and **Privacy Policy** pages (footer links); Privacy Policy includes subsection on refreshing, storing, and deleting API data (no long-term cache, session-only OAuth, no persistent storage of YouTube content after the job, revoking access).
- **Web UI edit step**: Before processing, set title and description overrides and choose privacy (private / unlisted / public) for videos and playlist (YouTube API compliance).

### Changed
- **Production release** – Dropped beta designation. Web UI and CLI are both production-ready.

## [1.1.0-beta] - 2026-01-31

### Added
- **Web UI (beta)** – Browser-based interface alongside the CLI:
  - FastAPI backend with session-based YouTube OAuth (web flow); sign in once per session.
  - **Preview**: Enter archive.org URL → async preview job with real progress (fetch metadata, find audio, get durations per track). Poll `/api/preview/job/{id}` for step and progress bar.
  - **Process**: Start upload job → background run of same CLI workflow; poll `/api/job/{id}` for live progress (download, video creation, upload, playlist).
  - **Review**: After completion, link to private playlist; optional “Make public” to set videos and playlist to public via API.
  - Frontend: single-page app (landing, preview loading, preview, processing, review, complete); determinate/indeterminate progress bars and step messages.
  - Deploy: `python run_web.py` (port 18765) or Docker (`docker compose up`); path-based hosting supported via `BASE_URL` (see [WEB_UI_SETUP.md](WEB_UI_SETUP.md)).
- **Documentation**: [WEB_UI_SETUP.md](WEB_UI_SETUP.md) for OAuth (Web client, redirect URIs), Docker, and env vars; [docs/YouTube-API-Quota-Request-Design.md](docs/YouTube-API-Quota-Request-Design.md) for quota extension requests.

### Changed
- Version set to **beta** again; Web UI is not fully tested in all environments. CLI remains the recommended path for production use.
- Improved error when all YouTube uploads fail (e.g. quota exceeded): now raises a clear message with failure count and “likely due to YouTube API quota exceeded” instead of generic “Process returned no result”.

### Fixed
- When no videos were uploaded (e.g. quota), the process no longer returns `None` silently; it now raises a descriptive error so the UI shows the real cause.

## [1.0.0] - 2026-01-31

### Changed
- **First stable release** - Dropped beta designation
- Application is now considered production-ready and fully functional
- All core features implemented and tested with multiple archive.org URL formats

### Tested
- Verified working with 8 different archive.org URL formats
- Multi-disc recordings supported
- Various metadata formats handled correctly
- Resume capability tested and working
- YouTube upload and playlist creation verified

## [0.6.0-beta] - 2026-01-30

### Added
- Support for multi-disc recordings (d1t01, d2t01 filename patterns)
- Automatic extraction of disc 2+ tracks from filenames when description only lists disc 1
- Improved track extraction with better section detection and filtering
- Case-sensitive pattern matching for better false positive filtering
- Duplicate track detection to prevent extracting the same track multiple times
- Generic track naming ("Track 01", "Track 02") when descriptions only contain filenames
- Better handling of track names that are filenames (e.g., "Lane Family.2011-06-25.t01")
- FLAC preference over MP3 when extracting tracks from files to avoid duplicates

### Changed
- Track extraction now uses consecutive track pattern detection for more reliable section identification
- Improved invalid pattern filtering with case-sensitive checks for uppercase-only patterns
- `_extract_tracks_from_files()` now correctly extracts track numbers from T01, t01, d1t01 patterns
- Track-to-audio matching handles disc-based sequential numbering (track 11 matches d2t01, etc.)
- Better handling of descriptions where track names are filenames instead of actual song titles

### Fixed
- Fixed "Flinstones" being incorrectly filtered as invalid (case-sensitive pattern matching)
- Fixed track extraction creating duplicates when filenames are listed in description
- Fixed track number extraction from filenames (was extracting "20" from "2010" in dates)
- Fixed track-to-audio matching for disc-based files (d1t01, d2t01 patterns)
- Fixed sequential track numbering across multiple discs

### Tested
- **Verified working with multiple archive.org URL formats**:
  - `https://archive.org/details/lf2007-11-21.a` (original - 16 tracks with proper names)
  - `https://archive.org/details/lf2008-10-11` (multi-disc - 38 tracks, disc 1 with names, disc 2 without)
  - `https://archive.org/details/lf2010-04-02` (15 tracks with proper names)
  - `https://archive.org/details/lf2011-06-25` (20 tracks, filenames in description)
  - `https://archive.org/details/lf2008-05-12` (16 tracks with proper names)
  - `https://archive.org/details/lf2011-11-04.romp.flac16` (16 tracks, filenames in description)
  - `https://archive.org/details/lf2018-09-08` (18 tracks, filenames in description)
  - `https://archive.org/details/romp2011-11-04.flac16` (16 tracks, filenames in description)

## [0.5.0-beta] - 2026-01-30

### Added
- Track-to-audio matching verification: ensures matched audio files contain correct track number
- Detailed logging for audio file URLs and filenames during track processing
- `get_playlist_items()` method to retrieve playlist videos with their positions
- `insert_video_to_playlist()` method to insert videos at specific positions
- Automatic detection of gaps in existing playlists
- Logic to insert missing videos at correct positions when gaps are detected
- Track index-based video ID mapping to maintain correct track order

### Changed
- Improved track-to-audio matching with verification step to prevent incorrect matches
- Video ID collection now maintains correct track order using track index mapping
- Enhanced logging shows audio URL and filename for each track being processed

### Fixed
- Fixed critical bug where track 3 was getting track 1's audio (and similar mismatches)
- Fixed video ID ordering to ensure playlist maintains correct track sequence
- Fixed playlist gap detection to properly identify and fill missing videos

### Tested
- **Verified working correctly with example URL**: `https://archive.org/details/lf2007-11-21.a`
  - All 16 tracks correctly matched to their audio files
  - All videos uploaded with correct titles and audio
  - Playlist created with tracks in correct order
  - Gap detection and insertion working correctly

## [0.4.0-beta] - 2026-01-30

### Added
- Interactive publish workflow: after upload, script offers to make videos and playlist public
- `update_video_privacy()` method to change video privacy status (private/unlisted/public)
- `update_playlist_privacy()` method to change playlist privacy status
- `make_videos_public()` method to batch update multiple videos to public
- Automatic check for existing YouTube videos before uploading (prevents duplicates)
- `find_existing_videos()` method to search YouTube for videos with matching archive.org URL
- Script now skips download/video creation/upload if video already exists on YouTube

### Changed
- Videos and playlists are created as private by default
- After successful upload, script prompts user to review playlist and optionally make it public
- Improved workflow: check for existing videos before processing tracks

### Fixed
- Fixed YouTube playlist creation permissions by adding `youtube` scope in addition to `youtube.upload`
- Fixed performer vs recorder in descriptions (now correctly shows "performed by [Band]" and "Recorded by [Recorder]")
- Fixed venue cleaning to remove band name prefixes like [Romp]
- Fixed background image validation false alarm (images no longer validated as audio files)

## [0.3.1-beta] - 2026-01-30

### Added
- Video file resume capability: existing videos are detected and reused instead of recreating
- `find_existing_videos()` method to check for existing video files before starting
- Video files are preserved until successful YouTube upload (not deleted after creation)

### Changed
- Video creation now accepts `skip_if_exists` parameter (default: True)
- Video files are only deleted after successful YouTube upload, not after creation
- Resume check now shows both audio and video files that will be reused

### Fixed
- Video files are preserved if YouTube upload fails, allowing resume without re-encoding
- Improved resume capability to avoid redundant ffmpeg video creation work

## [0.3.0-beta] - 2026-01-29

### Added
- Resume capability: automatically detects and reuses existing audio file downloads
- Identifier-based file naming: files are named with archive.org identifier for unique identification
- Deferred cleanup: audio files are only deleted after successful YouTube upload (not after video creation)
- Progress preservation: if process is interrupted, audio files are preserved for resume
- `find_existing_files()` method to check for existing downloads before starting

### Changed
- Audio files are now named with format: `{identifier}_track_{number}_{filename}`
- Background images are now named with format: `{identifier}_background_image.jpg`
- Video files are now named with format: `{identifier}_video_{number}.mp4`
- Cleanup strategy: audio files only deleted after successful upload, not after video creation
- Download method now accepts `skip_if_exists` parameter (default: True)

### Fixed
- Audio files are preserved if video creation or upload fails, allowing resume
- Interrupted processes can now be resumed without re-downloading all files

## [0.2.0-beta] - 2026-01-29

### Changed
- **BREAKING**: Refactored `ArchiveScraper` to use Archive.org Metadata API instead of HTML scraping
  - Replaced BeautifulSoup-based HTML parsing with direct API calls
  - More reliable file detection and metadata extraction
  - Improved performance with single API call vs. HTML parsing

### Removed
- Removed `beautifulsoup4` dependency (no longer needed)
- Removed `lxml` dependency (was only used for BeautifulSoup)

### Fixed
- Fixed issue where audio files were not being detected on some archive.org pages
- Improved track-to-file matching with better filename pattern recognition

## [0.1.0-beta] - 2026-01-29

### Added
- Initial beta release
- Archive.org metadata extraction
- Audio file download functionality
- Video creation using ffmpeg with high-quality settings
- YouTube API integration with OAuth2 authentication
- Automatic playlist creation
- Metadata formatting for YouTube descriptions
- Comprehensive logging throughout
- Automatic cleanup of temporary files
- Full documentation (README.md, ARCHITECTURE.md)

[Unreleased]: https://github.com/151henry151/archive-to-yt/compare/v1.1.1...HEAD
[1.1.1]: https://github.com/151henry151/archive-to-yt/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/151henry151/archive-to-yt/compare/v1.1.0-beta...v1.1.0
[1.1.0-beta]: https://github.com/151henry151/archive-to-yt/compare/v1.0.0...v1.1.0-beta
[1.0.0]: https://github.com/151henry151/archive-to-yt/compare/v0.6.0-beta...v1.0.0
[0.6.0-beta]: https://github.com/151henry151/archive-to-yt/compare/v0.5.0-beta...v0.6.0-beta
[0.5.0-beta]: https://github.com/151henry151/archive-to-yt/compare/v0.4.0-beta...v0.5.0-beta
[0.4.0-beta]: https://github.com/151henry151/archive-to-yt/compare/v0.3.1-beta...v0.4.0-beta
[0.3.1-beta]: https://github.com/151henry151/archive-to-yt/compare/v0.3.0-beta...v0.3.1-beta
[0.3.0-beta]: https://github.com/151henry151/archive-to-yt/compare/v0.2.0-beta...v0.3.0-beta
[0.2.0-beta]: https://github.com/151henry151/archive-to-yt/compare/v0.1.0-beta...v0.2.0-beta
[0.1.0-beta]: https://github.com/151henry151/archive-to-yt/tag/v0.1.0-beta

