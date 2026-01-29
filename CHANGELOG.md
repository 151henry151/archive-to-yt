# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/151henry151/archive-to-yt/compare/v0.2.0-beta...HEAD
[0.2.0-beta]: https://github.com/151henry151/archive-to-yt/compare/v0.1.0-beta...v0.2.0-beta
[0.1.0-beta]: https://github.com/151henry151/archive-to-yt/tag/v0.1.0-beta

