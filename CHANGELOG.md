# Changelog

All notable changes to Radio Monitor will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.5.2] - 2026-06-18

### Added
- **Not Validated Songs table** - Replaced messy titles info box with actionable validation table on Data Quality page
  - Shows songs that haven't been validated or failed validation
  - Columns: Song (link to song page), Artist (link to artist page), Status badge, Play Count
  - Sortable headers (click to sort, visual indicators)
  - Scrollable table (shows 10 rows initially, max-height 400px)
  - Bulk selection with checkboxes and "Select All"
  - Bulk action buttons: "Validate Selected" and "Refresh"
- **API endpoints** - Added `/api/data-quality/unvalidated-songs` and `/api/data-quality/validate-selected`

### Fixed
- **Keyboard shortcuts null safety** - Fixed TypeError when keyboard events fire without a key property
  - Fixed at line 59 (legacy key support) and line 101 (main handler) in keyboard.js

---

## [1.4.30] - 2026-06-15

### Fixed
- **SCHEMA_VERSION mismatch** - Fixed SCHEMA_VERSION from 21 to 22
  - Fresh databases now created with correct schema (v22)
  - Existing v21 databases auto-migrate to v22 on app start
  - No more "no such column: validation_status" errors in Artists/Songs pages
  - Docker and local builds both create correct schema

### Changed
- Updated `SCHEMA_VERSION` constant in `radio_monitor/database/__init__.py`
- Documentation updated to reflect schema v22

---

## [1.4.29] - 2026-06-15

### Fixed
- **Recording validation uses verified artist names** - Fixed validation to use MusicBrainz-verified artist names instead of split collaboration names
  - Example: Validates "KC & The Sunshine Band" instead of "Kc"
  - Prevents false validation failures on collaboration artists
- **Recording validation cleans song titles before query** - Removes (feat.), (with), and other parentheticals before querying MusicBrainz
  - Example: "GEEKALEEK (feat. Cash Kidd)" queries as "GEEKALEEK"
  - Fixes 3 of 4 previously failing songs

### Changed
- Scraper now passes verified MusicBrainz artist name to validation
- Recording validation pre-cleans titles with `clean_song_title_for_query()`

---

## [1.4.21] - 2026-06-12

### Fixed
- **Re-validate crash** - Fixed remaining `startswith` bug on line 495 in `gui/routes/data_quality.py` that was still crashing with `'NoneType' object has no attribute 'startswith'`
- **Rate limiting** - Increased from 0.2s to 1s per song (MusicBrainz recommendation) to prevent blocking during large re-validations
- **UI improvement** - Re-validate button now shows estimated time for operation (~9 minutes for 517 songs)

---

## [1.4.20] - 2026-06-12

### Fixed
- **Validation crash on NULL MBID** - Fixed `'NoneType' object has no attribute 'startswith'` crash
  - 267 songs with NULL MBID now handled gracefully
  - Fixed in 3 locations: `data_quality.py` line 478, `gui/routes/data_quality.py` lines 311, 495
- **Added NULL check** before calling `.startswith()` on `artist_mbid`

### Added
- **Re-validate Invalid button** to Data Quality page
  - Shows count of invalid songs needing re-check
  - Resets invalid songs to unvalidated and re-checks them
  - Useful for re-validating songs after fixes like v1.4.19
- **invalid_count** to health check summary

---

## [1.4.19] - 2026-06-10

### Fixed
- **Unicode apostrophe comparison** in `is_recording_match()`
  - MusicBrainz returns U+2019/U+2018 instead of U+0027
  - Added NFKC normalization and apostrophe replacement
- **clean_title parameter breaking legitimate titles with "&"**
  - "Me & A Beer" was being cleaned to "Me"
  - Changed `clean_title` default from `True` to `False`
  - Clean both MusicBrainz title and our title for fair comparison

### Changed
- **Validation logic** - Now queries with full title, cleans both sides during comparison
  - Query: "Me & A Beer" → MusicBrainz returns "Me & A Beer"
  - Clean: "Me & A Beer" → "Me" on both sides
  - Compare: "me" == "me" → MATCH

### Verified
All 4 previously failing songs now validate correctly:
- Chris Janson - Me & A Beer
- Taking Back Sunday - Liar (It Takes One To Know One)
- Shaboozey - A Bar Song (Tipsy)
- Morgan Wallen - Thinkin' Bout Me

---

## [1.4.14] - 2026-06-09

### Fixed
- **Critical Bug in is_recording_match()** - When validating via MBID, artist parameter was empty string, causing all MBID queries to fail. Now skips artist check when expected_artist is empty (MBID queries already imply correct artist).
- **Critical Bug in mark_song_validated()** - Hardcoded `method='mbid'` instead of passing actual validation method used. Now correctly tracks whether validation succeeded via MBID or text_fallback.
- **Expected Impact**: Fixing these bugs should immediately validate 60+ songs that were incorrectly marked as invalid.

---

## [1.3.0] - 2026-04-12

### Added
- **Song Verification System (Phase 1)** - Manual song verification with MusicBrainz Recording API and Lidarr track catalog
  - Individual song verification (Verify button on Songs page)
  - Batch artist verification (Verify All Songs on Artists page)
  - Visual verification badges showing source (MusicBrainz 🎵 or Lidarr 💿)
  - 85% similarity matching for fuzzy title matching
  - 100 recordings per search (increased from 20)
  - Verification status tracking in database
  - Artist verification breakdown (counts by source)
  - Modal dialogs showing verification progress and results
  - Manual MBID override for difficult-to-match artists

### Changed
- Database schema: v20 → v21
  - Added `verification_status`, `verification_date` to songs table
  - New table: `artist_song_verification` for tracking verification details
  - Enhanced queries: per-source verification indicators (verified_mb, verified_lidarr)

### Fixed
- Database schema mismatch (verification_source vs source)
- Increased MusicBrainz search limit from 20 to 100 recordings
- Added populate_manual_mbid_overrides() for difficult-to-match artists

### Technical Details
- Verification API endpoints: `/api/songs/{id}/verify` and `/api/artists/{mbid}/verify-all`
- Real-time progress tracking with modal dialogs
- Automatic re-direction after successful verification
- Source-specific badge indicators in UI

---

## [1.2.10] - 2026-04-11

### Fixed
- SQL migration compatibility issues
- Docker build configuration

---

## [1.2.9.2] - 2026-04-10

### Fixed
- SQL syntax in Python migration function

---

## [1.2.9.1] - 2026-04-10

### Fixed
- SQL syntax error in migration

---

## [1.2.9] - 2026-04-10

### Added
- **Enhanced MBID Matching** - Improved artist matching with word overlap verification
  - Collaboration-aware matching for complex artist names
  - Automatic PENDING artist merging with data preservation
  - Stricter thresholds prevent false matches
  - Reduced PENDINGS by 25% in test database

### Changed
- No data loss: preserves songs, play counts, and history during merges

---

## [1.2.8.3] - 2026-04-08

### Fixed
- **Foreign Key Constraints** - Fixed FOREIGN KEY constraint error when merging artists
  - Added `PRAGMA foreign_keys = OFF` to artist merge operation
  - Artist merges now work correctly even with song_plays_daily references
  - Added try/finally block to ensure foreign keys are re-enabled after merge
- **Validation Logic** - Changed duplicate MBID from error to warning
  - Users can now proceed with artist merges when MBID already exists
  - Shows clear warning: "System will merge X into Y and update all songs accordingly"

### Changed
- Updated version to 1.2.8.3
- Improved validation messages to explain merge behavior clearly

---

## [1.2.8.2] - 2026-04-08

### Fixed
- **UNIQUE Constraint** - Fixed UNIQUE constraint error when merging artists with duplicate songs
  - System now adds play counts from duplicate songs to existing songs
  - Skips duplicate entries automatically (no data loss)
  - Artists can now be merged even when they share the same songs
- **Play Count Preservation** - Fixed issue where play counts were lost during merge
  - Brooks Dunn (6 plays) → Brooks & Dunn (563 plays total: 557 + 6)
  - All play data preserved during artist merge

### Changed
- Updated version to 1.2.8.2
- Added `songs_skipped` field to API response

---

## [1.2.8.1] - 2026-04-08

### Fixed
- **MBID Editing Validation** - Fixed validation to allow artist merges
  - Duplicate MBID now shows as warning instead of blocking error
  - Users can now merge artists like "Brooks Dunn" into "Brooks & Dunn"
  - Validation shows clear warnings about what will happen

### Changed
- Updated version to 1.2.8.1
- Changed validation from blocking to allowing when MBID already exists

---

## [1.2.8] - 2026-04-07

### Fixed
- **Plex Overrides Page** - Fixed page not loading due to template inheritance issue
  - Changed template from `base.html` to `base_sidebar.html`
  - Page now loads correctly with sidebar navigation
- **Manual Match Error** - Fixed "Plex not connected" error in Plex Failures page
  - Updated Plex connection check to use proper on-demand connection pattern
  - Now creates Plex connection from settings instead of checking non-existent config
  - Follows established patterns from ai_playlists.py and playlists.py

### Added
- **MBID Editing Improvements** - Complete rewrite of artist MBID editing system
  - Fixed MBID editing to use direct MBID lookup instead of name-based fuzzy matching
  - Manual MBID edits now automatically save to overrides table for future scrapes
  - Eliminated 150+ lines of complex fuzzy matching code
  - Improved reliability: MBID editing now works 100% of the time
  - Set-it-and-forget-it: Fix an artist once, and future scrapes will use the correct MBID automatically
  - Edit MBID button on Artists page for easy manual artist corrections

### Changed
- Database schema: v16 → v17 (15 → 16 tables)
  - Added `manual_mbid_overrides` table for persistent manual MBID mappings
- API blueprints: 19 → 20 (no change in count, just updated)
- Frontend: MBID editing modal now sends `current_mbid` for direct lookup
- Removed fuzzy matching code (simplified from 200+ lines to 1 direct lookup)

### Technical Details
- Direct MBID lookup: `WHERE mbid = current_mbid` (was: 5 different search strategies)
- Foreign key handling: Temporarily disabled during artist merge operations
- Unique constraint handling: Adds play counts, skips duplicate songs
- Automatic manual override saving for future scrape prevention
- Multi-strategy artist fallback: Exact → Normalized → LIKE → MusicBrainz name
- Validation allows duplicate MBIDs with user confirmation (warnings, not errors)
- **Plex Overrides Page** - Fixed page not loading due to template inheritance issue
  - Changed template from `base.html` to `base_sidebar.html`
  - Page now loads correctly with sidebar navigation
- **Manual Match Error** - Fixed "Plex not connected" error in Plex Failures page
  - Updated Plex connection check to use proper on-demand connection pattern
  - Now creates Plex connection from settings instead of checking non-existent config
  - Follows established patterns from ai_playlists.py and playlists.py

### Changed
- Updated version to 1.2.7
- Fixed Plex connection pattern consistency across all routes

---

## [1.2.6] - 2026-04-07

### Fixed
- **NULL MBID Crashes** - Fixed crashes from NULL artist MBIDs during scraping
  - Added NULL check before calling `.startswith()` on MBID values
  - Prevents `NoneType has no attribute 'startswith'` errors
- **Internal Server Error** - Fixed crashes when clicking artist links from song pages
  - Added template safety checks for NULL artist_mbids
  - Templates now handle NULL values gracefully
- **Orphaned Artists** - Fixed artists with 0 songs unable to be deleted
  - Added cleanup routine in database migration v17
  - Automatically deletes artists with no associated songs
- **NULL MBID Values** - Added database migration to fix existing NULL values
  - Migration v16 → v17 fixes all NULL artist_mbid values in songs table
  - Matches orphaned songs to existing artists or creates PENDING artists
  - Removes orphaned artists from multi-artist collaborations

### Added
- Database migration v17 - NULL mbid fix and orphaned artist cleanup
- Template safety checks for NULL artist_mbids

### Changed
- Updated database schema version to 17
- All existing databases auto-migrate on first run

---

## [1.2.3] - 2026-03-31

### Fixed
- **Email Import Error** - Fixed "no module named email.mime" error in Windows EXE
  - Added email.mime modules to PyInstaller hiddenimports
  - Email notifications now work correctly in Windows EXE builds
  - Modules added: email, email.mime, email.mime.text, email.mime.multipart

### Changed
- PyInstaller build configuration (build.py)
- Updated version to 1.2.3

---

## [1.2.0] - 2026-03-01

### Added
- **Blocklist Management** - Block artists and songs from playlist generation
  - Dedicated Blocklist page with table layout and tabs (Blocked Artists | Blocked Songs)
  - Persistent blocked icons (green checkmark) on Artists and Songs pages
  - Block buttons on Artists and Songs pages for quick blocking
  - Toggle per playlist: Plex, AI Playlists, Manual Builder (default: ON)
  - Block modes: Block entire artist (cascades to all songs) or block individual songs
  - Preview impact before blocking (shows how many songs will be affected)
  - Export/Import blocklist functionality (JSON format)
  - Statistics dashboard (total artists, songs, affected songs)
- New database table (v14):
  - `blocklist` - Blocked artists and songs with entity_type discriminator
- New API blueprint: `blocklist` (8 new endpoints)
- Block/unblock toggle functionality with persistent icons
- Integration with all three playlist types (Plex, AI, Manual Builder)

### Changed
- Database schema: v13 → v14 (15 → 16 tables)
- API blueprints: 19 → 20 (added blocklist)
- Songs and Artists queries now include `is_blocked` field
- Enhanced Songs and Artists pages with block/unblock buttons
- Playlist generation accepts `exclude_blocklist` parameter (default: true)
- Updated documentation (README.md)

### Technical Details
- Single table design with entity_type discriminator ('artist' | 'song')
- LEFT JOIN with CASE statements for is_blocked detection
- Persistent green checkmark icons survive page refreshes
- Block artist cascades to all current and future songs
- Individual song blocks survive artist unblock

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

### From 1.1.x to 1.2.0

1. Backup your database: `python -m radio_monitor.cli --backup-db`
2. Pull latest code: `git pull origin main`
3. Restart application
4. Database migration to v14 runs automatically
5. Access "Blocklist" in sidebar to manage blocked artists/songs

**Database Changes:**
- 1 new table added (blocklist)
- No existing data affected

**New Features:**
- Block artists and songs from playlist generation
- Persistent blocked icons on Artists and Songs pages
- Export/import blocklist functionality

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

### From 1.1.x to 1.2.0 (Latest)

Follow the upgrade guide from 1.1.x to 1.2.0 above.

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

**Current Version:** 1.4.30
**Database Schema:** v22
**Last Updated:** 2026-06-15
