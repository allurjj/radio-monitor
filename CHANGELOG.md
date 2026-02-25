# Changelog

All notable changes to Radio Monitor will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.1.8] - 2026-02-24

### Added
- **Multi-Artist Resolution** - Advanced collaboration detection and resolution
  - Smart word-grouping strategies (2+1, 1+2, 3+2 splits)
  - Hybrid validation against MusicBrainz API
  - Duplicate song merging with play count preservation
  - CLI command: `--resolve-multi-artist`
  - 85% success rate (34/40 PENDING artists resolved)

### Changed
- Scraper integration prevents PENDING entries for resolvable collaborations
- Updated documentation (README.md)

---

## [1.1.7] - 2026-02-23

### Added
- **Manual Playlist Builder** - Create custom playlists by manually selecting songs
  - Browse entire song catalog with powerful filters
  - Two view modes: By Artist (grouped) or By Song (flat list)
  - Advanced filtering (stations, date range, play counts, search)
  - Multi-select with persistent selections across sessions
  - Full CRUD operations: Create, edit, delete playlists
  - Plex integration for manual playlists
  - Selection state saved in database
- New database tables (v12):
  - `manual_playlists` - User-created manual playlists
  - `manual_playlist_songs` - Songs in manual playlists (many-to-many)
  - `playlist_builder_state` - Persistent user selections
- New API blueprint: `playlist_builder` (11 new endpoints)
- New documentation: `docs/MANUAL_PLAYLIST_BUILDER.md`

### Changed
- Database schema: v11 → v12 (12 → 15 tables)
- API blueprints: 18 → 19 (added playlist_builder)
- Updated documentation (README, CLAUDE.md, MEMORY.md, API.md)

### Technical Details
- Server-side pagination (100 songs per page)
- Debounced search (300ms delay)
- AJAX for all operations (no page reloads)
- Optimistic UI updates
- Error handling with user-friendly messages

---

## [1.1.6] - 2026-02-23

### Added
- **MBID Status Filter** - Filter artists by MBID status
  - Quick filter buttons: PENDING, Valid MBID, No MBID
  - Count badges showing how many artists in each category
  - Filter state preservation after delete/retry/edit operations
  - Enhanced empty state messages based on active filter
  - MBID statistics in page header

### Changed
- Enhanced Artists page with status filtering UI
- Improved empty state messaging
- Updated queries to support MBID status filtering

---

## [1.1.5] - 2026-02-22

### Added
- Dynamic version management system
- VERSION.py for build artifacts
- Consistent version display across all platforms

### Fixed
- GitHub URL corrected to allurjj/radio-monitor
- Artists page filter bug (HAVING clause for aggregate columns)

---

## [1.1.4] - 2026-02-21

### Changed
- Database query optimizations
- Improved performance on large datasets

---

## [1.1.3] - 2026-02-20

### Added
- Enhanced UI components
- Improved modal layouts

---

## [1.1.2] - 2026-02-19

### Added
- Compact sidebar navigation
- Improved playlist modal layouts

---

## [1.1.1] - 2026-02-18

### Fixed
- VERSION.py copy from builder stage
- Removed VERSION.py from Dockerfile

---

## [1.1.0] - 2026-02-17

### Added
- AI-Powered Playlists (Experimental)
  - Natural language instructions
  - OpenRouter.ai integration
  - Hallucination detection
  - Rate limiting (1 request per minute)

### Changed
- Removed WTMX station (Selenium dependency removed)
- Now using requests+BeautifulSoup for all stations
- 100% success rate on iHeartRadio stations

### Fixed
- iHeartRadio scraper bug (off-by-one error in parsing)
- Title case normalization (apostrophe handling)

---

## [1.0.0] - 2026-02-15

### Added
- Initial stable release
- Radio scraping from 8+ Chicago stations
- MusicBrainz MBID lookup
- Lidarr integration
- Plex playlist creation (7 modes)
- Web GUI with 18 blueprints
- Analytics and charts
- Automation with APScheduler
- Notifications (17 providers)
- Database schema v10

---

## Version Format

- **Major**: Breaking changes
- **Minor**: New features (backward compatible)
- **Patch**: Bug fixes and minor improvements

## Upgrade Guide

### From 1.1.6 to 1.1.7

1. Backup your database: `python -m radio_monitor.cli --backup-db`
2. Pull latest code: `git pull origin main`
3. Restart application
4. Database migration to v12 runs automatically
5. Access "Playlist Builder" in sidebar

**Database Changes:**
- 3 new tables added (manual playlists)
- No existing data affected

### From 1.1.5 to 1.1.6

1. Pull latest code: `git pull origin main`
2. Restart application
3. Access Artists page to see new MBID status filters

**No database changes**

### From 1.1.x to 1.1.7 (Latest)

Follow the upgrade guide from 1.1.6 to 1.1.7 above.

---

## Release Schedule

- **Stable Releases**: As needed for feature completion
- **Patch Releases**: As needed for bug fixes
- **Major Releases**: When breaking changes are introduced

## Support

For issues and questions:
- GitHub Issues: https://github.com/allurjj/radio-monitor/issues
- Documentation: https://github.com/allurjj/radio-monitor

---

**Current Version:** 1.1.7
**Database Schema:** v12
**Last Updated:** 2026-02-23
