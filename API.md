# Radio Monitor API Documentation

**Version:** 1.2.10
**Base URL:**
- Windows: `http://127.0.0.1:5000`
- Linux/Mac: `http://localhost:5000`
**Response Format:** JSON
**Authentication:** None (local only)

---

## Table of Contents

- [Overview](#overview)
- [Dashboard](#dashboard)
- [Monitor](#monitor)
- [Lidarr](#lidarr)
- [Plex](#plex)
- [Playlists](#playlists)
- [Playlist Builder](#playlist-builder) ✨ **NEW**
- [Settings](#settings)
- [Backup](#backup)
- [Activity](#activity)
- [Logs](#logs)
- [System](#system)
- [Search](#search)
- [Artists](#artists)
- [Songs](#songs)
- [Stations](#stations)
- [Notifications](#notifications)
- [Plex Failures](#plex-failures)
  - [SpotiFLAC Integration Endpoints](#spotiflac-integration-endpoints) ✨ **NEW**
- [Plex Overrides](#plex-overrides) ✨ **NEW**
- [AI Playlists](#ai-playlists)
- [Blocklist](#blocklist) ✨ **NEW**

---

## Overview

The Radio Monitor API provides REST endpoints for managing radio station monitoring, music tracking, Lidarr integration, Plex playlist management, and system administration.

### Response Format

All responses return JSON with the following structure:

**Success Response:**
```json
{
  "data": { ... }
}
```

**Error Response:**
```json
{
  "error": "Error message"
}
```

### Status Codes

- `200` - Success
- `201` - Created
- `400` - Bad Request (invalid parameters)
- `404` - Not Found
- `500` - Internal Server Error

### Pagination

Paginated endpoints use these standard parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | 1 | Page number (1-indexed) |
| `limit` | integer | 50 | Items per page |
| `sort` | string | varies | Sort field |
| `sort_dir` | string | varies | Sort direction (`asc` or `desc`) |

### Filtering

Filter parameters vary by endpoint but commonly include:

| Parameter | Type | Description |
|-----------|------|-------------|
| `search` | string | Text search |
| `station_id` | string | Filter by station ID |
| `days` | integer | Filter to last N days |
| `min_plays` / `max_plays` | integer | Play count range |
| `last_seen_after` / `last_seen_before` | date | Date range (YYYY-MM-DD) |

---

## Dashboard

### GET `/`

Render main dashboard page.

### GET `/charts`

Render charts page.

### GET `/api/stats`

Get database statistics.

**Response:**
```json
{
  "total_artists": 808,
  "total_songs": 1560,
  "total_plays": 45000,
  "plays_today": 125
}
```

### GET `/api/plays/recent`

Get recent plays for dashboard live feed.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 10 | Number of plays to return |
| `station_id` | string | null | Filter by station ID (empty = all) |

**Response:**
```json
[
  {
    "timestamp": "2026-02-12 12:34:56",
    "artist_name": "Taylor Swift",
    "song_title": "Anti-Hero",
    "station_id": "station_name": ""
  }
]
```

### GET `/api/charts/plays-over-time`

Get plays over time data for line chart.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | integer | 30 | Number of days to look back |
| `station_id` | string | null | Filter by station ID |

**Response:**
```json
{
  "dates": ["2026-01-01", "2026-01-02", ...],
  "plays": [450, 520, 480, ...]
}
```

### GET `/api/charts/top-songs`

Get top songs data for bar chart.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 20 | Maximum songs to return |
| `days` | integer | 30 | Number of days to look back |
| `station_id` | string | null | Filter by station ID |

**Response:**
```json
{
  "songs": [
    {"artist": "Taylor Swift", "title": "Anti-Hero", "plays": 125},
    ...
  ]
}
```

### GET `/api/charts/top-artists`

Get top artists data for bar chart.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 20 | Maximum artists to return |
| `days` | integer | null | Number of days to look back |
| `station_id` | string | null | Filter by station ID |

**Response:**
```json
{
  "artists": [
    {"name": "Taylor Swift", "plays": 450},
    ...
  ]
}
```

### GET `/api/charts/station-distribution`

Get station distribution data for pie chart.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | integer | null | Number of days to look back (null = all time) |

**Response:**
```json
{
  "stations": [
    {"name": "B96", "plays": 1234},
    {"name": "US99", "plays": 987}
  ]
}
```

### GET `/api/stations/dropdown`

Get all stations for dropdown filters (simple format).

**Response:**
```json
{
  "stations": [
    {"id": "name": ""},
    ...
  ]
}
```

### GET `/api/mbid-retry/stats`

Get MBID retry statistics.

**Response:**
```json
{
  "pending_count": 0,
  "last_retry_time": "2026-02-08 10:30:00",
  "total_retried": 150,
  "resolved": 145,
  "failed": 5,
  "deleted_old": 10
}
```

---

## Monitor

### GET `/monitor`

Render monitor controls page.

### POST `/api/monitor/start`

Start monitoring.

**Response:**
```json
{
  "status": "started",
  "message": "Monitoring started"
}
```

### POST `/api/monitor/stop`

Stop monitoring.

**Response:**
```json
{
  "status": "stopped",
  "message": "Monitoring stopped"
}
```

### GET `/api/monitor/status`

Get monitor status.

**Response:**
```json
{
  "running": true,
  "interval": 10,
  "next_run": "2026-02-12T15:30:00"
}
```

### POST `/api/monitor/scrape`

Trigger immediate manual scrape.

**Response:**
```json
{
  "success": true,
  "message": "Scrape complete",
  "songs_scraped": 150,
  "stations_scraped": 8
}
```

### PUT `/api/stations/<station_id>`

Update station settings.

**Request Body:**
```json
{
  "enabled": true,
  "consecutive_failures": 0
}
```

**Response:**
```json
{
  "success": true
}
```

### DELETE `/api/stations/<station_id>`

Delete a station.

**Response:**
```json
{
  "success": true,
  "message": "Station us99 deleted successfully"
}
```

### POST `/api/stations/add`

Add a new station.

**Request Body:**
```json
{
  "id": "station_id",
  "name": "Station Name",
  "url": "https://...",
  "genre": "Genre",
  "market": "Market",
  "wait_time": 10
}
```

**Response:**
```json
{
  "success": true,
  "message": "Station station_id added successfully"
}
```

### POST `/api/stations/<station_id>/test`

Test the scraper for a specific station by running it once and returning results.

**Response:**
```json
{
  "success": true,
  "message": "Scrape complete - found 12 songs",
  "songs_found": 12
}
```

**Error Response:**
```json
{
  "success": false,
  "message": "Scrape failed: Connection timeout"
}
```

### GET `/api/status/lidarr`

Get Lidarr connection status.

**Response:**
```json
{
  "success": true,
  "message": "Connected (Lidarr v3.1.0.4875)"
}
```

### GET `/api/status/plex`

Get Plex connection status.

**Response:**
```json
{
  "success": true,
  "message": "Connected to ServerName (Plex 1.32.0)"
}
```

---

## Lidarr

### GET `/lidarr`

Render Lidarr import page.

### GET `/api/lidarr/artists`

Get artists that need Lidarr import.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `min_plays` | integer | 5 | Minimum total plays |
| `station` | string | "all" | Station ID filter |

**Response:**
```json
[
  {
    "mbid": "20244d07-534f-4eff-b4d4-930878889970",
    "name": "Taylor Swift",
    "total_plays": 15
  }
]
```

### POST `/api/lidarr/import`

Import selected artists to Lidarr.

**Request Body:**
```json
{
  "mbids": ["mbid1", "mbid2", ...]
}
```

**Response:**
```json
{
  "success": true,
  "imported": 45,
  "already_exists": 5,
  "failed": 0,
  "results": [...]
}
```

### POST `/api/test/lidarr`

Test Lidarr connection (from settings page).

**Request Body:**
```json
{
  "url": "http://localhost:8686",
  "api_key": "your-api-key"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Connected (Lidarr v3.1.0.4875)"
}
```

### GET `/api/lidarr/root-folders`

Get available root folders from Lidarr.

**Response:**
```json
{
  "success": true,
  "folders": [
    {"path": "/data/music", "freeSpace": 1000000000, "id": 1}
  ]
}
```

### GET `/api/lidarr/quality-profiles`

Get available quality profiles from Lidarr.

**Response:**
```json
{
  "success": true,
  "profiles": [
    {"id": 1, "name": "Lossless"},
    {"id": 2, "name": "High Quality"}
  ]
}
```

### GET `/api/lidarr/metadata-profiles`

Get available metadata profiles from Lidarr.

**Response:**
```json
{
  "success": true,
  "profiles": [
    {"id": 1, "name": "Standard"},
    {"id": 2, "name": "Strict"}
  ]
}
```

### POST `/api/lidarr/reset-import-status`

Reset all artists to "Needs Import" status.

**Response:**
```json
{
  "success": true,
  "count": 453,
  "message": "Reset 453 artists to 'Needs Import'"
}
```

### POST `/api/lidarr/import/<mbid>`

Import a single artist to Lidarr.

**Response:**
```json
{
  "success": true,
  "message": "Imported successfully",
  "already_exists": false
}
```

---

## Plex

### GET `/plex`

Render Plex playlist page.

### POST `/api/plex/preview`

Preview songs for Plex playlist.

**Request Body:**
```json
{
  "filters": {
    "days": 7,
    "station_ids": ["us99"],
    "limit": 50
  }
}
```

**Response:**
```json
{
  "songs": [
    {
      "song_id": 123,
      "song_title": "Anti-Hero",
      "artist_name": "Taylor Swift",
      "play_count": 15
    }
  ]
}
```

### POST `/api/plex/create`

Create Plex playlist.

**Request Body:**
```json
{
  "name": "Radio Hits",
  "mode": "merge",
  "filters": {
    "days": 7,
    "station_ids": ["us99"],
    "limit": 50
  }
}
```

**Response:**
```json
{
  "added": 45,
  "not_found": 5,
  "not_found_list": [...]
}
```

### POST `/api/test/plex`

Test Plex connection (from settings page).

**Request Body:**
```json
{
  "url": "http://localhost:32400",
  "token": "your-plex-token"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Connected to MyServer (Plex 1.32.0)"
}
```

### GET `/api/plex/libraries`

Get available music libraries from Plex.

**Response:**
```json
{
  "success": true,
  "libraries": [
    {"name": "Music", "key": "/library/sections/1"},
    {"name": "Music Library", "key": "/library/sections/2"}
  ]
}
```

---

## Playlists

### GET `/playlists`

Render playlist management page.

### GET `/api/plex/playlists`

Get all playlists (manual and auto).

**Response:**
```json
{
  "playlists": [...]
}
```

### POST `/api/plex/playlists`

Create new playlist (manual or auto).

**Request Body:**
```json
{
  "name": "Playlist Name",
  "is_auto": true,
  "interval_minutes": 360,
  "station_ids": ["us99"],
  "max_songs": 50,
  "mode": "merge",
  "min_plays": 5,
  "max_plays": 100,
  "days": 30,
  "enabled": true,
  "enable_various_artists_fallback": false,
  "various_artists_timeout_ms": 5000
}
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | string | required | Playlist name |
| `is_auto` | boolean | false | Auto-update playlist on schedule |
| `interval_minutes` | integer | null | Update interval (required if is_auto=true) |
| `station_ids` | array | required | Station IDs to include |
| `max_songs` | integer | required | Maximum songs in playlist |
| `mode` | string | required | Playlist mode (merge, replace, append, create, snapshot, recent, random) |
| `min_plays` | integer | 1 | Minimum plays per song |
| `max_plays` | integer | null | Maximum plays per song (optional) |
| `days` | integer | null | Only include songs from last N days |
| `enabled` | boolean | true | Enable/disable playlist |
| `enable_various_artists_fallback` | boolean | false | Search 'Various Artists' compilations when standard matching fails |
| `various_artists_timeout_ms` | integer | 5000 | Max search time per song in milliseconds (1000-30000) |

**Response:**
```json
{
  "success": true,
  "playlist": {...},
  "message": "Playlist created successfully. It is being populated in background..."
}
```

### PUT `/api/plex/playlists/<int:playlist_id>`

Update existing playlist.

**Request Body:**
```json
{
  "name": "New Name",
  "is_auto": true,
  "interval_minutes": 60,
  "enable_various_artists_fallback": true,
  "various_artists_timeout_ms": 7000
}
```

**Parameters:** Same as POST (all fields optional except playlist_id)

**Response:**
```json
{
  "success": true,
  "playlist": {...}
}
```

### DELETE `/api/plex/playlists/<int:playlist_id>`

Delete playlist.

**Response:**
```json
{
  "success": true,
  "message": "Playlist deleted"
}
```

### POST `/api/plex/playlists/<int:playlist_id>/toggle-auto`

Toggle playlist between manual and auto.

**Request Body:**
```json
{
  "is_auto": true,
  "interval_minutes": 360
}
```

**Response:**
```json
{
  "success": true,
  "message": "Auto updates enabled"
}
```

### POST `/api/plex/playlists/<int:playlist_id>/execute`

Execute playlist immediately (create or update).

**Response:**
```json
{
  "success": true,
  "added": 37,
  "not_found": 13
}
```

### POST `/api/plex/playlists/<int:playlist_id>/trigger`

Trigger immediate update of auto playlist (alias for execute).

**Response:**
```json
{
  "success": true,
  "message": "Update triggered"
}
```

---

## Playlist Builder ✨ **NEW**

**Version:** 1.1.7
**Purpose:** Create custom playlists by manually selecting songs from the catalog

### GET `/playlist-builder`

Render manual playlist builder page.

### GET `/api/playlist-builder/songs`

Get paginated list of songs for browsing and selection.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | 1 | Page number (1-indexed) |
| `limit` | integer | 100 | Items per page (max 500) |
| `view_mode` | string | "song" | "artist" (grouped) or "song" (flat) |
| `station_ids` | string | null | Comma-separated station IDs (e.g., "us99,b96") |
| `from_date` | string | null | Start date (YYYY-MM-DD) |
| `to_date` | string | null | End date (YYYY-MM-DD) |
| `min_plays` | integer | null | Minimum play count |
| `search` | string | null | Search song title OR artist name |

**Response (view_mode=song):**
```json
{
  "songs": [
    {
      "id": 123,
      "title": "Blinding Lights",
      "artist_name": "The Weeknd",
      "artist_mbid": "5bc41f77-cce4-4e76-a3e9-324c0201824f",
      "total_plays": 15,
      "last_seen_at": "2026-02-23T10:30:00",
      "first_seen_at": "2026-02-15T08:00:00"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 100,
    "total_items": 1500,
    "total_pages": 15
  }
}
```

**Response (view_mode=artist):**
```json
{
  "artists": [
    {
      "artist_mbid": "5bc41f77-cce4-4e76-a3e9-324c0201824f",
      "artist_name": "The Weeknd",
      "songs": [
        {
          "id": 123,
          "title": "Blinding Lights",
          "total_plays": 15,
          "last_seen_at": "2026-02-23T10:30:00"
        }
      ]
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 50,
    "total_items": 800,
    "total_pages": 16
  }
}
```

### POST `/api/playlist-builder/select`

Add or remove songs from current selection.

**Request Body:**
```json
{
  "action": "add",
  "song_ids": [123, 456, 789]
}
```

| Action | Description |
|--------|-------------|
| `add` | Add songs to selection (ignores already selected) |
| `remove` | Remove songs from selection |
| `toggle` | Toggle songs (add if not selected, remove if selected) |
| `set` | Replace selection with these songs |

**Response:**
```json
{
  "success": true,
  "selected_count": 25,
  "message": "Added 3 songs to selection"
}
```

### GET `/api/playlist-builder/selections`

Get current song selections.

**Response:**
```json
{
  "selections": [
    {
      "id": 123,
      "title": "Blinding Lights",
      "artist_name": "The Weeknd",
      "total_plays": 15
    }
  ],
  "total_count": 25
}
```

### DELETE `/api/playlist-builder/selections`

Clear all current selections.

**Response:**
```json
{
  "success": true,
  "message": "Cleared all selections"
}
```

### GET `/api/playlists/manual`

Get all manual playlists.

**Query Parameters:**
- `sort` - Sort field (name, created_at, song_count)
- `direction` - Sort direction (asc, desc)

**Response:**
```json
{
  "playlists": [
    {
      "id": 1,
      "name": "My Favorites",
      "song_count": 25,
      "created_at": "2026-02-23T12:00:00",
      "updated_at": "2026-02-23T14:30:00"
    }
  ]
}
```

### POST `/api/playlists/manual`

Create a new manual playlist.

**Request Body:**
```json
{
  "name": "My Favorites",
  "song_ids": [123, 456, 789],
  "sync_to_plex": true,
  "enable_various_artists_fallback": false,
  "various_artists_timeout_ms": 5000
}
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | string | required | Playlist name |
| `song_ids` | array | required | Song IDs to include (from current builder selections) |
| `sync_to_plex` | boolean | false | Sync to Plex after creation |
| `enable_various_artists_fallback` | boolean | false | Search 'Various Artists' compilations when standard matching fails |
| `various_artists_timeout_ms` | integer | 5000 | Max search time per song in milliseconds (1000-30000) |

**Response:**
```json
{
  "success": true,
  "playlist": {
    "id": 1,
    "name": "My Favorites",
    "song_count": 3,
    "created_at": "2026-02-23T15:00:00"
  },
  "plex_playlist_key": 12345,
  "message": "Playlist created successfully and synced to Plex"
}
```

### GET `/api/playlists/manual/<int:playlist_id>`

Get details of a specific manual playlist.

**Response:**
```json
{
  "playlist": {
    "id": 1,
    "name": "My Favorites",
    "song_count": 25,
    "created_at": "2026-02-23T12:00:00",
    "updated_at": "2026-02-23T14:30:00",
    "enable_various_artists_fallback": false,
    "various_artists_timeout_ms": 5000
  },
  "songs": [
    {
      "id": 123,
      "title": "Blinding Lights",
      "artist_name": "The Weeknd",
      "added_at": "2026-02-23T12:05:00"
    }
  ]
}
```

### PUT `/api/playlists/manual/<int:playlist_id>`

Update an existing manual playlist.

**Request Body:**
```json
{
  "name": "My Favorites (Updated)",
  "add_song_ids": [789, 1011],
  "remove_song_ids": [123],
  "sync_to_plex": true,
  "enable_various_artists_fallback": true,
  "various_artists_timeout_ms": 7000
}
```

**Parameters:** Same as POST (all fields optional except playlist_id)

**Response:**
```json
{
  "success": true,
  "playlist": {
    "id": 1,
    "name": "My Favorites (Updated)",
    "song_count": 26,
    "updated_at": "2026-02-23T15:30:00"
  },
  "message": "Playlist updated successfully"
}
```

### DELETE `/api/playlists/manual/<int:playlist_id>`

Delete a manual playlist.

**Response:**
```json
{
  "success": true,
  "message": "Playlist deleted successfully",
  "plex_deleted": true
}
```

### POST `/api/playlists/manual/<int:playlist_id>/sync-plex`

Manually sync a playlist to Plex.

**Response:**
```json
{
  "success": true,
  "plex_playlist_key": 12345,
  "matched_songs": 25,
  "unmatched_songs": 2,
  "message": "Synced to Plex successfully"
}
```

---

## Settings

### GET `/settings`

Render settings page.

### GET `/api/settings`

Get current settings.

**Response:** Complete settings object (all sections: lidarr, plex, monitor, database, gui, logging)

### POST `/api/settings/update`

Update settings.

**Request Body:**
```json
{
  "lidarr": {...},
  "plex": {...},
  "monitor": {...}
}
```

**Response:**
```json
{
  "success": true,
  "message": "Settings saved successfully"
}
```

### POST `/api/settings/test-musicbrainz`

Test MusicBrainz connection.

**Response:**
```json
{
  "success": true,
  "message": "MusicBrainz API is reachable"
}
```

### POST `/api/settings/export-db`

Export database for sharing with friends.

**Request Body:**
```json
{
  "filename": "radio_monitor_shared.db"
}
```

**Response:**
```json
{
  "success": true,
  "path": "/path/to/export.db",
  "message": "Database exported successfully"
}
```

### POST `/api/settings/import-db`

Import shared database from a friend.

**Request Body:**
```json
{
  "source_path": "/path/to/shared.db"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Database imported successfully"
}
```

---

## Backup

### GET `/api/backups`

Get list of all database backups.

**Response:**
```json
[
  {
    "name": "radio_songs_2026-02-06_143022.db",
    "size_mb": 2.5,
    "created_at": "2026-02-06T14:30:22",
    "is_valid": true
  }
]
```

### GET `/api/backups/stats`

Get backup statistics.

**Response:**
```json
{
  "total_count": 5,
  "total_size_mb": 12.5,
  "oldest": "2026-02-01T03:00:00",
  "newest": "2026-02-06T14:30:22",
  "invalid_count": 0
}
```

### POST `/api/backup/create`

Create a manual database backup.

**Response:**
```json
{
  "success": true,
  "backup_path": "backups/radio_songs_2026-02-06_143022.db"
}
```

### POST `/api/backup/restore`

Restore database from backup.

**Request Body:**
```json
{
  "backup_path": "backups/radio_songs_2026-02-06_143022.db"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Database restored successfully"
}
```

### GET `/api/backup/download/<path:filename>`

Download a backup file.

**Response:** File download

### DELETE `/api/backup/delete`

Delete a backup file.

**Request Body:**
```json
{
  "backup_path": "backups/radio_songs_2026-02-06_143022.db"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Backup deleted successfully"
}
```

---

## Activity

### GET `/activity`

Render activity timeline page.

### GET `/api/activity/recent`

Get recent activity entries (for dashboard feed).

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 20 | Number of entries (max 100) |

**Response:**
```json
[
  {
    "id": 1,
    "timestamp": "2026-02-09 12:34:56",
    "event_type": "scrape",
    "severity": "success",
    "title": "Scrape completed",
    "description": "Processed 15 songs from 3 stations",
    "metadata": {"songs": 15, "stations": 3},
    "source": "system"
  }
]
```

### GET `/api/activity`

Get activity log with pagination and filtering.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | 1 | Page number |
| `limit` | integer | 50 | Items per page (max 200) |
| `event_type` | string | null | Filter by event type |
| `severity` | string | null | Filter by severity |
| `days` | integer | null | Last N days |

**Response:**
```json
{
  "activities": [...],
  "page": 1,
  "limit": 50,
  "total": 150,
  "filters": {...}
}
```

### GET `/api/activity/stats`

Get activity statistics.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | integer | 7 | Number of days to look back |

**Response:**
```json
{
  "total_events": 150,
  "by_type": {"scrape": 50, "import": 20},
  "by_severity": {"info": 100, "warning": 30, "error": 5, "success": 15},
  "error_count": 5,
  "days": 7
}
```

---

## Logs

### GET `/logs`

Render log viewer page.

### GET `/api/logs`

Get log entries with filtering.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tail` | integer | 1000 | Lines from end (max 10000) |
| `level` | string | null | Filter by log level |
| `search` | string | null | Search string |

**Response:**
```json
{
  "success": true,
  "logs": [
    {
      "line_number": 1,
      "timestamp": "2026-02-12 10:30:00",
      "level": "INFO",
      "message": "Starting scraper",
      "raw": "2026-02-12 10:30:00 - INFO - Starting scraper"
    }
  ],
  "total_lines": 5000,
  "file_size": 256000,
  "file_size_human": "250.00 KB"
}
```

### GET `/api/logs/download`

Download full log file.

**Response:** File download

### DELETE `/api/logs`

Clear log file (with confirmation).

**Request Body:**
```json
{
  "confirm": "CLEAR_LOGS"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Log file cleared successfully",
  "backup_path": "path/to/backup"
}
```

### GET `/api/logs/stats`

Get log file statistics.

**Response:**
```json
{
  "success": true,
  "exists": true,
  "stats": {
    "file_path": "radio_monitor.log",
    "file_size": 256000,
    "file_size_human": "250.00 KB",
    "total_lines": 5000,
    "level_counts": {
      "DEBUG": 1000,
      "INFO": 3500,
      "WARNING": 400,
      "ERROR": 100
    }
  }
}
```

---

## System

### GET `/api/system/status`

Get comprehensive system status.

**Response:**
```json
{
  "database": {
    "status": "ok",
    "size_mb": 1.2,
    "version": 6
  },
  "scheduler": {
    "status": "running",
    "jobs": 3
  },
  "lidarr": {
    "status": "connected",
    "url": "http://localhost:8686"
  },
  "plex": {
    "status": "connected",
    "url": "http://localhost:32400"
  },
  "scrapers": {
    "status": "idle",
    "active_stations": 8
  },
  "uptime": "2 days, 4 hours"
}
```

### GET `/api/system/health`

Get simplified health check (for monitoring tools).

**Response:**
```json
{
  "status": "healthy",
  "checks": {
    "database": "ok",
    "scheduler": "ok",
    "lidarr": "ok"
  }
}
```

---

## Search

### GET `/api/search`

Global search across all entities.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `q` | string | required | Search query |
| `types` | string | all | Comma-separated list (artists,songs,stations,playlists) |
| `limit` | integer | 10 | Maximum results per type (max 50) |

**Response:**
```json
{
  "query": "taylor",
  "results": {
    "artists": [...],
    "songs": [...],
    "stations": [...],
    "playlists": [...]
  },
  "total": 45
}
```

### GET `/api/search/artists`

Quick search for artists (autocomplete).

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `q` | string | required | Search query |
| `limit` | integer | 10 | Maximum results (max 50) |

**Response:**
```json
[
  {"id": "...", "name": "Taylor Swift", "song_count": 15}
]
```

### GET `/api/search/songs`

Quick search for songs (autocomplete).

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `q` | string | required | Search query |
| `limit` | integer | 10 | Maximum results (max 50) |

**Response:**
```json
[
  {"id": 1, "title": "Anti-Hero", "artist": "Taylor Swift"}
]
```

---

## Artists

### GET `/artists`

Render artists list page with pagination and filtering.

### GET `/artists/<mbid>`

Render artist detail page.

### GET `/api/artists`

API endpoint for artists with filtering and pagination.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | 1 | Page number |
| `limit` | integer | 50 | Items per page |
| `search` | string | null | Search in name |
| `needs_import` | string | null | Filter: only, imported, all |
| `station_id` | string | null | Filter by first seen station |
| `first_seen_after` | date | null | Filter by first seen date (YYYY-MM-DD) |
| `last_seen_after` | date | null | Filter by last seen date (YYYY-MM-DD) |
| `total_plays_min` | integer | null | Minimum total plays |
| `total_plays_max` | integer | null | Maximum total plays |
| `sort` | string | "name" | Sort field: name, plays, last_seen, first_seen |

**Response:**
```json
{
  "items": [
    {
      "mbid": "...",
      "name": "Taylor Swift",
      "first_seen_station": "first_seen_at": "2026-01-01 12:00:00",
      "last_seen_at": "2026-02-12 15:30:00",
      "needs_lidarr_import": false,
      "lidarr_imported_at": "2026-01-15 10:00:00",
      "total_plays": 450,
      "song_count": 15,
      "stations": [{"id": "name": "US99"}],
      "station_names": "US99, B96"
    }
  ],
  "pagination": {
    "page": 1,
    "pages": 17,
    "total": 808,
    "limit": 50
  }
}
```

### GET `/api/artists/<mbid>`

Get single artist details.

**Response:**
```json
{
  "mbid": "...",
  "name": "Taylor Swift",
  "first_seen_station": "station_name": "US99",
  "first_seen_at": "...",
  "last_seen_at": "...",
  "needs_lidarr_import": false,
  "lidarr_imported_at": "...",
  "total_plays": 450,
  "song_count": 15
}
```

### GET `/api/artists/<mbid>/songs`

Get artist's songs.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 100 | Maximum songs |

**Response:**
```json
{
  "items": [
    {
      "id": 123,
      "song_title": "Anti-Hero",
      "play_count": 125,
      "first_seen_at": "...",
      "last_seen_at": "..."
    }
  ],
  "count": 15
}
```

### GET `/api/artists/<mbid>/history`

Get artist's play history.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | integer | 30 | Number of days |

**Response:**
```json
{
  "items": [
    {
      "date": "2026-02-12",
      "play_count": 15,
      "station_name": "US99"
    }
  ],
  "count": 90,
  "days": 30
}
```

### POST `/api/artists/retry-pending`

Retry MBID lookup for all PENDING artists.

**Description:** Triggers a background job to retry MusicBrainz lookup for all artists with PENDING MBIDs. This is useful after fixing MusicBrainz data or resolving network issues. The job runs asynchronously in the background.

**Response (Asynchronous - with scheduler):**
```json
{
  "success": true,
  "message": "MBID retry started for 15 PENDING artist(s)",
  "pending_count": 15,
  "estimated_time_seconds": 120
}
```

**Response (Synchronous - without scheduler):**
```json
{
  "success": true,
  "message": "MBID retry complete: 8 resolved, 7 still failed",
  "pending_count": 15,
  "resolved": 8,
  "failed": 7
}
```

**Response (No PENDING artists):**
```json
{
  "success": true,
  "message": "No PENDING artists to retry",
  "pending_count": 0
}
```

**Error Response:**
```json
{
  "error": "Database not initialized"
}
```

### GET `/api/artists/pending-count`

Get count of PENDING artists (artists without valid MusicBrainz IDs).

**Response:**
```json
{
  "pending_count": 15
}
```

### POST `/api/artists/update-mbid`

Update an artist's MBID and merge with existing artist if needed.

**Version:** 1.2.10+ - **NEW IMPLEMENTATION:**

**Request Body:**
```json
{
  "artist_name": "Brooks Dunn",
  "current_mbid": "PENDING-04d427179698d27cb762e3a10bff2a42",
  "mbid": "f30118c5-f783-4969-8427-f3c096378267"
}
```

**Parameters:**
- `artist_name` (string): Current artist name for display purposes
- `current_mbid` (string): **Current MBID** of the artist to update (used for lookup)
- `mbid` (string): **New MBID** to set (can be existing artist's MBID for merge)

**Behavior:**
1. Finds artist by `current_mbid` (direct lookup, no fuzzy matching)
2. If new MBID already exists → **merge** artists (combines play counts, deletes old artist)
3. If new MBID doesn't exist → **update** artist in-place
4. Saves to `manual_mbid_overrides` table for future scrapes
5. Handles foreign key constraints (song_plays_daily references)
6. Handles unique constraints (duplicate songs)

**Response (Merge into existing artist):**
```json
{
  "success": true,
  "message": "MBID override saved! Merged 0 song(s) into existing artist \"Brooks & Dunn\", added play counts to 5 existing song(s). Future scrapes will automatically use the correct MBID.",
  "old_name": "Brooks Dunn",
  "new_name": "Brooks & Dunn",
  "mbid": "f30118c5-f783-4969-8427-f3c096378267",
  "songs_updated": 0,
  "songs_skipped": 5
}
```

**Response (Update in-place):**
```json
{
  "success": true,
  "message": "Artist updated successfully! 5 song(s) updated. Future scrapes will automatically use the correct MBID.",
  "old_name": "PENDING-12345",
  "new_name": "Billy Joel",
  "mbid": "5bc41f77-cce4-4e76-a3e9-324c0201824f",
  "songs_updated": 5
}
```

**Error Response:**
```json
{
  "error": "Artist not found with MBID: PENDING-12345"
}
```

**Changes in v1.2.8.3:**
- Added `current_mbid` parameter (required for direct lookup)
- Removed fuzzy matching (now uses exact MBID lookup)
- Handles foreign key constraints (song_plays_daily)
- Handles unique constraints (duplicate song titles)
- Automatically saves to manual overrides for future scrapes

### DELETE `/api/artists/<mbid>`

Delete an artist and all related data.

**Description:** Deletes the artist record, all songs by this artist, all play history for those songs, all Plex match failures, and manual MBID overrides.

**Response:**
```json
{
  "success": true,
  "message": "Deleted 'Billy Joel' and 5 songs (12 plays)",
  "artist_name": "Billy Joel",
  "mbid": "5bc41f77-cce4-4e76-a3e9-324c0201824f",
  "songs_deleted": 5,
  "plays_deleted": 12,
  "plex_failures_deleted": 2,
  "overrides_deleted": 0
}
```

---

## Songs

### GET `/songs`

Render songs list page with pagination and filtering.

### GET `/songs/<int:song_id>`

Render song detail page.

### GET `/api/songs`

API endpoint for songs with filtering and pagination.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | 1 | Page number |
| `limit` | integer | 50 | Items per page |
| `search` | string | null | Search in title or artist |
| `artist_name` | string | null | Filter by artist name |
| `station_id` | string | null | Filter by station |
| `last_seen_after` | date | null | Filter by last seen date (YYYY-MM-DD) |
| `last_seen_before` | date | null | Filter by last seen date (YYYY-MM-DD) |
| `plays_min` | integer | null | Minimum play count |
| `plays_max` | integer | null | Maximum play count |
| `sort` | string | "title" | Sort field: title, artist, plays, last_seen |

**Response:**
```json
{
  "items": [
    {
      "id": 123,
      "song_title": "Anti-Hero",
      "artist_name": "Taylor Swift",
      "artist_mbid": "...",
      "lidarr_imported_at": "...",
      "play_count": 125,
      "first_seen_at": "...",
      "last_seen_at": "...",
      "stations": [{"id": "name": "US99"}],
      "station_names": "US99, B96"
    }
  ],
  "pagination": {
    "page": 1,
    "pages": 32,
    "total": 1560,
    "limit": 50
  }
}
```

### GET `/api/songs/<int:song_id>`

Get single song details.

**Response:**
```json
{
  "id": 123,
  "song_title": "Anti-Hero",
  "artist_name": "Taylor Swift",
  "artist_mbid": "...",
  "artist_name_canonical": "...",
  "play_count": 125,
  "first_seen_at": "...",
  "last_seen_at": "...",
  "first_seen_station": "station_name": "lidarr_imported_at": "..."
}
```

### GET `/api/songs/<int:song_id>/history`

Get song's play history.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | integer | 30 | Number of days |

**Response:**
```json
{
  "items": [
    {
      "date": "2026-02-12",
      "play_count": 5,
      "station_name": "US99"
    }
  ],
  "count": 90,
  "days": 30
}
```

---

## Stations

### GET `/stations`

Render stations list page with health status.

### GET `/stations/<station_id>`

Render station detail page.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | integer | 30 | Number of days for stats |

### GET `/api/stations`

Get all stations.

**Response:**
```json
{
  "items": [
    {
      "id": "us99",
      "name": "US99 99.5fm Chicago",
      "url": "https://us99.iheart.com",
      "genre": "Top 40",
      "market": "Chicago",
      "wait_time": 10,
      "enabled": true,
      "consecutive_failures": 0,
      "last_failure_at": null,
      "created_at": "2026-01-01 10:00:00",
      "songs_scraped": 1234,
      "last_scrape_at": "2026-02-25 10:30:00",
      "status": "Active",
      "status_class": "success"
    }
  ],
  "count": 12
}
```

### GET `/api/stations/<station_id>`

Get single station details.

**Response:**
```json
{
  "station": {
    "id": "name": "US99",
    ...
  },
  "stats": {
    "unique_songs": 450,
    "unique_artists": 125,
    "total_plays": 5000
  },
  "top_songs": [...]
}
```

### PUT `/api/stations/<station_id>`

Update station settings.

**Request Body:**
```json
{
  "enabled": true
}
```

**Response:**
```json
{
  "success": true
}
```

---

## Notifications

### GET `/notifications`

Render notifications management page.

### GET `/api/notifications`

Get all notification configurations.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enabled_only` | boolean | false | Only return enabled notifications |

**Response:**
```json
{
  "notifications": [
    {
      "id": 1,
      "name": "Discord Alerts",
      "notification_type": "discord",
      "config": {"webhook_url": "..."},
      "triggers": ["scrape_complete", "error"],
      "enabled": true
    }
  ]
}
```

### GET `/api/notifications/<int:notification_id>`

Get specific notification configuration.

**Response:** Single notification object

### POST `/api/notifications`

Create new notification configuration.

**Request Body:**
```json
{
  "notification_type": "discord",
  "name": "Alerts",
  "config": {"webhook_url": "https://..."},
  "triggers": ["scrape_complete"],
  "enabled": true
}
```

**Response:**
```json
{
  "success": true,
  "notification_id": 1
}
```

### PUT `/api/notifications/<int:notification_id>`

Update notification configuration.

**Request Body:**
```json
{
  "name": "New Name",
  "enabled": false
}
```

**Response:**
```json
{
  "success": true
}
```

### DELETE `/api/notifications/<int:notification_id>`

Delete notification configuration.

**Response:**
```json
{
  "success": true
}
```

### POST `/api/notifications/<int:notification_id>/test`

Send test notification.

**Request Body:**
```json
{
  "title": "Custom Title",
  "message": "Custom message"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Test notification sent successfully"
}
```

### GET `/api/notifications/<int:notification_id>/history`

Get notification send history.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 50 | Items per page |
| `offset` | integer | 0 | Pagination offset |
| `success_only` | boolean | null | Filter by success |

**Response:**
```json
{
  "history": [...],
  "total": 100,
  "limit": 50,
  "offset": 0
}
```

### GET `/api/notifications/<int:notification_id>/stats`

Get statistics for specific notification.

**Response:**
```json
{
  "total_sent": 150,
  "successful": 145,
  "failed": 5,
  "success_rate": 96.7
}
```

### GET `/api/triggers`

Get available notification triggers.

**Response:**
```json
{
  "triggers": [
    {"key": "scrape_complete", "label": "Scrape Complete"},
    {"key": "error", "label": "Error"},
    ...
  ]
}
```

### GET `/api/history`

Get all notification history across all notifications.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 50 | Items per page |
| `offset` | integer | 0 | Pagination offset |
| `success_only` | boolean | null | Filter by success |

**Response:**
```json
{
  "history": [...],
  "total": 500,
  "limit": 50,
  "offset": 0
}
```

### GET `/api/types`

Get available notification types with their config schemas.

**Response:**
```json
{
  "types": {
    "discord": {
      "name": "Discord",
      "description": "Send notifications to Discord via webhook",
      "config_fields": [
        {"name": "webhook_url", "type": "url", "required": true}
      ]
    },
    "slack": {...},
    "email": {...}
  }
}
```

---

## Plex Failures

### GET `/plex-failures`

Render Plex failures list page.

### GET `/api/failures`

Get Plex failures with filtering and pagination.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `resolved` | string | "all" | Filter: all, true, false |
| `reason` | string | null | Filter by failure reason |
| `limit` | integer | 50 | Items per page |
| `offset` | integer | 0 | Pagination offset |

**Response:**
```json
{
  "failures": [
    {
      "id": 1,
      "song": {
        "song_title": "Song Title",
        "artist_name": "Artist"
      },
      "failure_date": "2026-02-12 10:00:00",
      "failure_reason": "not_found_in_library",
      "search_attempts": 3,
      "search_terms": "Song Title Artist",
      "resolved": false,
      "resolved_at": null,
      "playlist": {"name": "Playlist Name"}
    }
  ],
  "total": 50,
  "limit": 50,
  "offset": 0
}
```

### GET `/api/failures/<int:failure_id>`

Get details of specific failure.

**Response:** Single failure object

### POST `/api/failures/<int:failure_id>/dismiss`

Delete a specific failure record (dismiss).

**Response:**
```json
{
  "success": true
}
```

### POST `/api/failures/<int:failure_id>/retry`

Retry matching a failed song in Plex.

**Response:**
```json
{
  "success": true,
  "found": true,
  "message": "Found: Song Title - Artist"
}
```

### GET `/api/failures/stats`

Get failure statistics.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | integer | 30 | Number of days |

**Response:**
```json
{
  "total_failures": 100,
  "resolved": 80,
  "active": 20,
  "by_reason": {
    "not_found_in_library": 15,
    "metadata_mismatch": 5
  }
}
```

### POST `/api/failures/export`

Export failures to CSV.

**Request Body:**
```json
{
  "resolved": "all",
  "days": 30
}
```

**Response:** CSV file download

### POST `/api/failures/clear-all`

Delete ALL failure records.

**Request Body:**
```json
{
  "confirmed": true
}
```

**Response:**
```json
{
  "success": true,
  "deleted": 100
}
```

---

### SpotiFLAC Integration Endpoints

#### GET `/api/spotiflac/search-spotify`

Search Spotify for tracks matching song_title and artist_name.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `song_title` | string | Yes | Song title to search for |
| `artist_name` | string | Yes | Artist name to search for |

**Response:**
```json
{
  "results": [
    {
      "title": "Blinding Lights",
      "artist": "The Weeknd",
      "album": "After Hours",
      "url": "https://open.spotify.com/track/123456",
      "duration": "3:20",
      "isrc": "USUM72002912"
    }
  ],
  "count": 10
}
```

#### POST `/api/spotiflac/download`

Start a SpotiFLAC download job (track or album).

**Request Body:**
```json
{
  "plex_failure_id": 123,
  "spotify_url": "https://open.spotify.com/track/123456",
  "services": ["tidal", "qobuz", "amazon"]
}
```

**Required Fields:** `plex_failure_id`, `spotify_url`

**Optional Fields:** `services` (default: `["tidal", "qobuz", "amazon"]`)

**Response (Track):**
```json
{
  "success": true,
  "job_id": 123,
  "file_path": "/temp_downloads/The Weeknd - Blinding Lights.flac",
  "service_used": "tidal",
  "url_type": "track"
}
```

**Response (Album):**
```json
{
  "success": true,
  "job_id": 123,
  "files_downloaded": [
    "/temp_downloads/album/01 - Track 1.flac",
    "/temp_downloads/album/02 - Track 2.flac"
  ],
  "service_used": "qobuz",
  "url_type": "album"
}
```

**Error Response:**
```json
{
  "success": false,
  "error": "Download failed: Service unavailable"
}
```

#### POST `/api/spotiflac/auto-move`

Automatically move downloaded file to Lidarr artist folder.

**Request Body:**
```json
{
  "source_file": "/temp_downloads/The Weeknd - Blinding Lights.flac",
  "artist_name": "The Weeknd",
  "lidarr_path": "/data/music",
  "url_type": "track"
}
```

**Required Fields:** `source_file`, `artist_name`, `lidarr_path`

**Optional Fields:** `url_type` (default: `"track"`)

**Response:**
```json
{
  "success": true,
  "destination_path": "/data/music/The Weeknd/The Weeknd - Blinding Lights.flac",
  "message": "File moved to /data/music/The Weeknd/The Weeknd - Blinding Lights.flac"
}
```

**Error Response:**
```json
{
  "success": false,
  "error": "Source file does not exist: /temp_downloads/file.flac"
}
```

#### GET `/api/lidarr/artist-path`

Get the Lidarr folder path for an artist.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `artist_name` | string | Yes | Artist name |
| `url_type` | string | No | 'track' or 'album' (default: 'track') |

**Response:**
```json
{
  "path": "/data/music/The Weeknd",
  "exists": true,
  "naming_convention": "{artist} - {album} - {track} - {title}"
}
```

---

## Plex Overrides

### GET `/plex-overrides`

Render Plex manual overrides management page.

### GET `/api/plex-overrides`

Get all Plex manual overrides (JSON API).

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `active_only` | boolean | true | Only return active overrides |

**Response:**
```json
{
  "overrides": [
    {
      "id": 1,
      "song_id": 123,
      "plex_track_key": "45678",
      "plex_track_title": "Song Title",
      "plex_artist_name": "Artist Name",
      "plex_album_title": "Album Title",
      "plex_year": 2023,
      "plex_duration_ms": 180000,
      "created_at": "2026-04-07 10:00:00",
      "updated_at": "2026-04-07 10:00:00",
      "is_active": true,
      "notes": "Manual match",
      "song": {
        "title": "Song Title",
        "artist": "Artist Name"
      }
    }
  ]
}
```

### GET `/api/plex-overrides/<int:song_id>`

Get override for a specific song.

**Response:**
```json
{
  "override": {
    "id": 1,
    "song_id": 123,
    "plex_track_key": "45678",
    "plex_track_title": "Song Title",
    "plex_artist_name": "Artist Name",
    "plex_album_title": "Album Title",
    "plex_year": 2023,
    "plex_duration_ms": 180000,
    "created_at": "2026-04-07 10:00:00",
    "updated_at": "2026-04-07 10:00:00",
    "is_active": true,
    "notes": "Manual match"
  }
}
```

### POST `/api/plex-overrides`

Add a new manual override.

**Request Body:**
```json
{
  "song_id": 123,
  "plex_track_key": "45678",
  "plex_track_title": "Song Title",
  "plex_artist_name": "Artist Name",
  "plex_album_title": "Album Title",
  "plex_year": 2023,
  "plex_duration_ms": 180000,
  "notes": "Manual match"
}
```

**Required Fields:** `song_id`, `plex_track_key`, `plex_track_title`, `plex_artist_name`

**Optional Fields:** `plex_album_title`, `plex_year`, `plex_duration_ms`, `notes`

**Response:**
```json
{
  "success": true,
  "override_id": 1
}
```

### PUT `/api/plex-overrides/<int:override_id>/toggle`

Toggle override active state (enable/disable without deleting).

**Request Body:**
```json
{
  "is_active": false
}
```

**Response:**
```json
{
  "success": true,
  "is_active": false
}
```

### DELETE `/api/plex-overrides/<int:override_id>`

Delete an override.

**Response:**
```json
{
  "success": true
}
```

### GET `/api/plex-search-for-override`

Search Plex library for manual override matching.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `song_title` | string | Yes | Song title to search for |
| `artist_name` | string | Yes | Artist name to search for |

**Response:**
```json
{
  "search_title": "Song Title",
  "search_artist": "Artist Name",
  "results": [
    {
      "rating_key": 45678,
      "title": "Song Title",
      "artist": "Artist Name",
      "album": "Album Title",
      "year": 2023,
      "duration_ms": 180000,
      "duration_formatted": "3:00"
    }
  ],
  "total": 1
}
```

---

## AI Playlists (Experimental)

### GET `/ai-playlists`

Render AI Playlists page.

### POST `/api/ai-playlists/generate`

Generate AI-powered playlist using OpenRouter.ai.

**Request Body:**
```json
{
  "playlist_name": "Party Mix",
  "instructions": "Upbeat party songs with high energy",
  "stations": ["us99", "wlit"],
  "min_plays": 10,
  "first_seen": "2026-01-01",
  "last_seen": "2026-02-16",
  "max_songs": 50
}
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `playlist_name` | string | Yes | Name for playlist in Plex |
| `instructions` | string | Yes | Natural language description of mood/theme |
| `stations` | array | No | Station names (empty = all stations) |
| `min_plays` | integer | No | Minimum play count (default: 1) |
| `first_seen` | string | No | First seen date filter (YYYY-MM-DD) |
| `last_seen` | string | No | Last seen date filter (YYYY-MM-DD) |
| `max_songs` | integer | No | Maximum songs (1-1500, default: 50) |

**Success Response:**
```json
{
  "status": "success",
  "message": "Created playlist 'Party Mix' with 42 songs",
  "playlist_name": "Party Mix",
  "songs_requested": 50,
  "songs_returned": 47,
  "songs_added": 42,
  "songs_skipped": 5,
  "songs_hallucinated": 2,
  "plex_url": "https://plex.tv/..."
}
```

**Warning Response (Empty Playlist):**
```json
{
  "status": "warning",
  "message": "Created empty playlist 'Party Mix' - none of the selected songs were found in your Plex library",
  "playlist_name": "Party Mix",
  "songs_added": 0,
  "songs_requested": 50,
  "songs_returned": 47,
  "songs_skipped": 47,
  "songs_hallucinated": 0,
  "plex_url": "https://plex.tv/..."
}
```

**Partial Success Response:**
```json
{
  "status": "partial",
  "message": "Created playlist 'Party Mix' with 42 songs (25 songs not found in Plex - check Plex Failures page)",
  "playlist_name": "Party Mix",
  "songs_requested": 50,
  "songs_returned": 67,
  "songs_added": 42,
  "songs_skipped": 25,
  "songs_hallucinated": 3,
  "plex_url": "https://plex.tv/..."
}
```

**Error Responses:**

```json
// API Key Missing
{
  "status": "error",
  "message": "OpenRouter API key not configured. Please add it in Settings.",
  "error_code": "API_KEY_MISSING"
}

// No Songs Match
{
  "status": "error",
  "message": "No songs found matching the specified filters",
  "error_code": "NO_SONGS"
}

// Playlist Exists
{
  "status": "error",
  "message": "Playlist 'Party Mix' already exists in Plex. Please choose a different name.",
  "error_code": "PLAYLIST_EXISTS"
}

// Validation Error
{
  "status": "error",
  "message": "max_songs must be between 1 and 1500",
  "error_code": "INVALID_INPUT"
}

// Rate Limited
{
  "status": "error",
  "message": "Please wait 45 seconds before generating another playlist",
  "error_code": "RATE_LIMITED",
  "retry_after": 45
}
```

### GET `/api/ai-playlists/history`

Get AI playlist generation history with pagination.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | 1 | Page number (1-indexed) |
| `limit` | integer | 20 | Items per page (1-100) |
| `status` | string | null | Filter by status: success, failed, warning, partial |

**Response:**
```json
{
  "items": [
    {
      "id": 1,
      "timestamp": "2026-02-16T14:30:00",
      "playlist_name": "Party Mix",
      "model": "qwen/qwen3-next-80b-a3b-instruct:free",
      "instructions": "Upbeat party songs",
      "status": "success",
      "songs_requested": 50,
      "songs_returned": 47,
      "songs_added_to_plex": 42,
      "songs_skipped": 5,
      "songs_hallucinated": 2,
      "error_message": null,
      "plex_url": "https://plex.tv/...",
      "filters_json": "{\"stations\":[\"us99\"],\"min_plays\":10,\"max_songs\":50}",
      "created_at": "2026-02-16T14:30:00"
    }
  ],
  "total": 15,
  "page": 1,
  "limit": 20
}
```

**Status Values:**
- `success` - Playlist created successfully
- `failed` - Generation failed (API error, no songs, etc.)
- `warning` - Playlist created but empty (no Plex matches)
- `partial` - Playlist created with some songs not in Plex

---

## Code Examples

### cURL Examples

```bash
# Get statistics
curl http://127.0.0.1:5000/api/stats

# Get recent plays
curl "http://127.0.0.1:5000/api/plays/recent?limit=25&station_id=us99"

# Search artists
curl "http://127.0.0.1:5000/api/artists?search=taylor&min_plays=10"

# Import to Lidarr
curl -X POST http://127.0.0.1:5000/api/lidarr/import \
  -H "Content-Type: application/json" \
  -d '{"mbids": ["mbid1", "mbid2"]}'

# Create playlist
curl -X POST http://127.0.0.1:5000/api/plex/playlists \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Top Hits",
    "is_auto": true,
    "interval_minutes": 360,
    "station_ids": ["us99"],
    "max_songs": 50,
    "mode": "merge",
    "min_plays": 5,
    "days": 30
  }'
```

### Python Examples

```python
import requests

BASE_URL = "http://127.0.0.1:5000"

# Get statistics
response = requests.get(f"{BASE_URL}/api/stats")
stats = response.json()

# Get artists with filtering
params = {
    "search": "taylor",
    "total_plays_min": 10,
    "page": 1,
    "limit": 50
}
response = requests.get(f"{BASE_URL}/api/artists", params=params)
artists = response.json()

# Import to Lidarr
data = {"mbids": ["mbid1", "mbid2"]}
response = requests.post(f"{BASE_URL}/api/lidarr/import", json=data)
result = response.json()

# Create Plex playlist
playlist_data = {
    "name": "Top Hits",
    "is_auto": True,
    "interval_minutes": 360,
    "station_ids": ["us99"],
    "max_songs": 50,
    "mode": "merge",
    "min_plays": 5,
    "days": 30
}
response = requests.post(f"{BASE_URL}/api/plex/playlists", json=playlist_data)
result = response.json()
```

### JavaScript Examples

```javascript
const BASE_URL = 'http://127.0.0.1:5000';

// Get statistics
async function getStats() {
  const response = await fetch(`${BASE_URL}/api/stats`);
  return await response.json();
}

// Get artists with filtering
async function getArtists(filters) {
  const params = new URLSearchParams(filters);
  const response = await fetch(`${BASE_URL}/api/artists?${params}`);
  return await response.json();
}

// Usage
const artists = await getArtists({
  search: 'taylor',
  total_plays_min: 10,
  page: 1,
  limit: 50
});

// Import to Lidarr
async function importToLidarr(mbids) {
  const response = await fetch(`${BASE_URL}/api/lidarr/import`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({mbids})
  });
  return await response.json();
}

// Create Plex playlist
async function createPlaylist(playlist) {
  const response = await fetch(`${BASE_URL}/api/plex/playlists`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(playlist)
  });
  return await response.json();
}
```

---

## Blocklist ✨ **NEW**

Manage blocked artists and songs that should be excluded from playlist generation.

### GET /blocklist

View the main blocklist management page.

**Response:** HTML page with blocklist management interface

---

### GET /api/blocklist

Get paginated list of blocked items.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `entity_type` | string | - | Filter by type: 'artist' or 'song' |
| `page` | integer | 1 | Page number |
| `limit` | integer | 50 | Items per page |

**Response:**
```json
{
  "items": [
    {
      "id": 1,
      "entity_type": "artist",
      "entity_id": "5bc41f77-cce4-4e76-a3e9-324c0201824f",
      "artist_mbid": "5bc41f77-cce4-4e76-a3e9-324c0201824f",
      "song_id": null,
      "artist_name": "Taylor Swift",
      "song_title": null,
      "reason": "Explicit content",
      "created_at": "2026-03-01T12:00:00"
    }
  ],
  "total": 1,
  "page": 1,
  "limit": 50,
  "pages": 1
}
```

---

### GET /api/blocklist/stats

Get blocklist statistics.

**Response:**
```json
{
  "total_artists": 12,
  "total_songs": 47,
  "total_affected_songs": 156
}
```

---

### POST /api/blocklist/add

Add artists or songs to the blocklist.

**Request Body:**
```json
{
  "items": [
    {
      "type": "artist",
      "id": "5bc41f77-cce4-4e76-a3e9-324c0201824f",
      "block_all": true
    },
    {
      "type": "song",
      "id": 123,
      "artist_mbid": "5bc41f77-cce4-4e76-a3e9-324c0201824f"
    }
  ],
  "reason": "Overplayed"
}
```

**Response:**
```json
{
  "success": true,
  "added": 2,
  "skipped": 0,
  "message": "Successfully added 2 items to blocklist"
}
```

---

### POST /api/blocklist/preview

Preview impact before blocking items.

**Request Body:**
```json
{
  "items": [
    {
      "type": "artist",
      "id": "5bc41f77-cce4-4e76-a3e9-324c0201824f",
      "block_all": true
    }
  ]
}
```

**Response:**
```json
{
  "total_songs_affected": 23,
  "breakdown": {
    "artists": 1,
    "songs": 0,
    "total_songs": 23
  }
}
```

---

### DELETE /api/blocklist/:id

Remove item from blocklist by ID.

**URL Parameters:**
- `id` (integer) - Blocklist entry ID

**Response:**
```json
{
  "success": true,
  "message": "Item removed from blocklist"
}
```

---

### POST /api/blocklist/export

Export blocklist to JSON.

**Response:**
```json
{
  "version": "1.0",
  "exported_at": "2026-03-01T12:00:00",
  "items": [
    {
      "type": "artist",
      "mbid": "5bc41f77-cce4-4e76-a3e9-324c0201824f",
      "name": "Taylor Swift",
      "block_all": true,
      "reason": "Explicit content"
    }
  ]
}
```

---

### POST /api/blocklist/import

Import blocklist from JSON.

**Request Body:**
```json
{
  "items": [
    {
      "type": "artist",
      "mbid": "5bc41f77-cce4-4e76-a3e9-324c0201824f",
      "name": "Taylor Swift",
      "block_all": true,
      "reason": "Explicit content"
    }
  ]
}
```

**Response:**
```json
{
  "success": true,
  "imported": 1,
  "skipped": 0,
  "invalid": 0,
  "message": "Imported 1 items, skipped 0 duplicates, 0 invalid entries"
}
```

---

### GET /api/blocklist/search

Search for artists or songs to add to blocklist.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `q` | string | Yes | Search query (artist name or song title) |
| `type` | string | No | Filter by type: 'artist' or 'song' |
| `limit` | integer | No | Max results (default: 10) |

**Response:**
```json
{
  "results": [
    {
      "type": "artist",
      "mbid": "5bc41f77-cce4-4e76-a3e9-324c0201824f",
      "name": "Taylor Swift",
      "song_count": 23
    },
    {
      "type": "song",
      "id": 123,
      "title": "Shape of You",
      "artist_name": "Ed Sheeran",
      "artist_mbid": "1aa2bf69-d6bc-4c8f-9e53-2f695f4ffc84"
    }
  ]
}
```

---

### Blocklist Integration with Playlists

All three playlist types support blocklist exclusion:

#### Plex Playlists

**POST /api/plex/playlists/:id/execute**

Add `exclude_blocklist` parameter to request body:

```json
{
  "exclude_blocklist": true
}
```

#### AI Playlists

**POST /api/ai-playlists/generate**

Add `exclude_blocklist` parameter to request body:

```json
{
  "instructions": "Upbeat party songs",
  "exclude_blocklist": true
}
```

#### Manual Playlist Builder

**GET /api/playlist-builder/songs**

Add query parameter:

```
?exclude_blocklist=true
```

**Default Behavior:** All playlists exclude blocklisted items by default (`exclude_blocklist=true`)

---

### JavaScript Examples

```javascript
// Add artist to blocklist
async function blockArtist(mbid, reason) {
  const response = await fetch('/api/blocklist/add', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      items: [{type: 'artist', id: mbid, block_all: true}],
      reason: reason
    })
  });
  return await response.json();
}

// Get blocklist stats
async function getBlocklistStats() {
  const response = await fetch('/api/blocklist/stats');
  return await response.json();
}

// Remove from blocklist
async function unblockItem(blocklistId) {
  const response = await fetch(`/api/blocklist/${blocklistId}`, {
    method: 'DELETE'
  });
  return await response.json();
}

// Export blocklist
async function exportBlocklist() {
  const response = await fetch('/api/blocklist/export', {
    method: 'POST'
  });
  return await response.json();
}
```

---

## Thread Safety Note

All API endpoints use fresh database cursors from `current_app.config.get('db')` to ensure thread safety:

```python
db = current_app.config.get('db')
cursor = db.get_cursor()
try:
    # Work with cursor
finally:
    cursor.close()
```

---

## Error Handling

All endpoints return consistent error responses:

```json
{
  "error": "Error message"
}
```

Common HTTP status codes:
- `400` - Bad Request (invalid parameters)
- `404` - Not Found
- `500` - Internal Server Error
- `503` - Service Unavailable

---

## Version History

- **1.2.7** (2026-04-07) - Fixed Plex Overrides blueprint and manual matching - 20 blueprints total
- **1.2.6** (2026-04-07) - Fixed database NULL mbid issues and orphaned artist cleanup - 20 blueprints total  
- **1.2.3** (2026-03-15) - Added Plex Overrides blueprint - 21 blueprints total
- **1.2.0** (2026-03-01) - Added Blocklist blueprint - 20 blueprints total
- **1.1.7** (2026-02-23) - Added Playlist Builder blueprint - 19 blueprints total
- **1.0.0** (2026-02-17) - Added AI Playlists blueprint (experimental feature) - 18 blueprints total
- **1.0.0** (2026-02-12) - Initial API documentation with all 16 blueprints
