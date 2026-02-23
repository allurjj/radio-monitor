# Radio Monitor - Architecture Documentation

**Version:** 1.0.0
**Database Schema:** v7 (10 tables)
**Python:** 3.10+
**Framework:** Flask 3.0+ with APScheduler

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Technology Stack](#technology-stack)
3. [Project Structure](#project-structure)
4. [Directory Map](#directory-map)
5. [Component Relationships](#component-relationships)
6. [Data Flow Diagrams](#data-flow-diagrams)
7. [Database Schema](#database-schema)
8. [Integration Points](#integration-points)
9. [Design Patterns](#design-patterns)
10. [API Routes](#api-routes)

---

## Project Overview

Radio Monitor is a Python-based web application that monitors radio stations, discovers new music, and integrates with Lidarr and Plex. It provides a web-based GUI for management and control.

### Core Capabilities

- **Radio Scraping:** Monitors 8+ radio stations using Selenium WebDriver
- **Music Discovery:** Automatically identifies artists and songs
- **MusicBrainz Integration:** Artist metadata lookup with MBID resolution
- **Lidarr Integration:** One-click artist import with station filtering
- **Plex Integration:** 7-mode playlist creation with fuzzy matching
- **Auto Playlists:** Scheduled playlists with configurable filters
- **Notifications:** 17 providers (Discord, Slack, Email, Telegram, etc.)
- **Web GUI:** Browser-based management with real-time status

### Architecture Principles

1. **Modular Design:** Separated concerns (database, GUI, integrations)
2. **Thread Safety:** Fresh database cursors per request
3. **Blueprint Routes:** Flask blueprints for modular GUI
4. **Background Jobs:** APScheduler for scraping and maintenance
5. **Settings Management:** JSON-based configuration

---

## Technology Stack

### Backend

- **Python 3.10+** - Core language
- **Flask 3.0+** - Web framework
- **SQLite 3** - Database (file-based)
- **APScheduler 3.10+** - Background job scheduling
- **Selenium 4.x** - Web scraping
- **Requests 2.x** - HTTP client for API calls

### Frontend

- **Bootstrap 5.3** - UI framework
- **Bootstrap Icons** - Icon library
- **Vanilla JavaScript** - No frameworks (React/Vue)
- **Chart.js** - Data visualization
- **Jinja2** - Template engine

### External Services

- **MusicBrainz API** - Artist/song metadata
- **Lidarr API** - Artist import
- **Plex API** - Playlist management
- **Apprise** - Multi-provider notifications

---

## Project Structure

```
radio_monitor/
├── cli.py                    # Command-line interface
├── service.py                # Windows service wrapper
│
├── database/                 # Database layer (6 modules)
│   ├── __init__.py           # RadioDatabase class
│   ├── schema.py             # CREATE TABLE statements
│   ├── migrations.py         # Schema migrations
│   ├── queries.py            # SELECT operations
│   ├── crud.py               # INSERT/UPDATE/DELETE
│   ├── exports.py            # Lidarr/Plex export queries
│   ├── activity.py           # Activity logging
│   ├── plex_failures.py      # Plex failure tracking
│   ├── notifications.py      # Notification queries
│   └── database_backup.py    # Backup/restore
│
├── gui/                      # Flask web application
│   ├── __init__.py           # App initialization, blueprint registration
│   └── routes/               # 16 modular blueprints
│       ├── dashboard.py       # Dashboard with stats
│       ├── monitor.py         # Monitor controls
│       ├── lidarr.py         # Lidarr import
│       ├── plex.py           # Plex playlists
│       ├── playlists.py      # Playlist management
│       ├── settings.py       # Settings page
│       ├── backup.py         # Backup/restore
│       ├── system.py         # System status (API only)
│       ├── activity.py       # Activity timeline
│       ├── logs.py           # Log viewer
│       ├── search.py         # Global search
│       ├── artists.py        # Artist list/detail
│       ├── songs.py          # Song list/detail
│       ├── stations.py       # Station list/detail
│       ├── notifications.py  # Notification config
│       ├── plex_failures.py # Plex failure management
│       └── wizard.py        # Setup wizard
│
├── scrapers.py              # Radio station scraping (Selenium)
├── mbid.py                 # MusicBrainz API + fuzzy matching
├── mbid_retry.py           # PENDING artist retry manager
├── lidarr.py               # Lidarr API client
├── plex.py                 # Plex API client + fuzzy matching
├── auto_playlists.py       # Auto playlist scheduler
├── notifications.py        # Multi-provider notifications
├── scheduler.py            # APScheduler wrapper
├── normalization.py        # Text normalization (Unicode)
├── cleanup.py              # Maintenance jobs
├── backup.py               # Database backup/restore
├── cache.py                # Simple caching layer
│
├── tests/                   # Unit and integration tests
│   ├── conftest.py          # Pytest fixtures
│   ├── test_database.py
│   ├── test_api.py
│   ├── test_notifications.py
│   ├── test_plex_failures.py
│   ├── test_mbid.py
│   ├── test_plex_matching.py
│   └── test_normalization.py
│
└── integrations/            # External API integrations (future)
    └── (planned for other services)

templates/                   # Jinja2 HTML templates
├── base.html               # Base template (legacy)
├── base_sidebar.html       # Sidebar base (current)
├── dashboard.html          # Dashboard page
├── monitor.html            # Monitor controls
├── lidarr.html             # Lidarr import
├── plex.html               # Plex playlists
├── playlists.html          # Playlist management
├── settings.html           # Settings
├── wizard.html             # Setup wizard
├── stations.html           # Station list/detail
├── artists.html            # Artist list/detail
├── artist_detail.html      # Artist detail page
├── songs.html              # Song list/detail
├── song_detail.html        # Song detail page
├── station_detail.html     # Station detail page
├── charts.html             # Charts page
├── activity.html           # Activity timeline
├── logs.html               # Log viewer
├── notifications.html      # Notification config
├── plex_failures.html      # Plex failures
└── backup.html             # Backup/restore

static/                      # Static assets
├── css/
│   ├── ui-polish.css       # UI refinements
│   ├── sidebar.css         # Sidebar styling
│   ├── theme.css           # Theme variables
│   ├── theme-dark.css      # Dark mode overrides
│   ├── typography.css      # Font system
│   ├── components.css      # Reusable components
│   ├── empty-state.css     # Empty state styling
│   ├── skeleton.css        # Loading skeletons
│   └── toast.css          # Toast notifications
└── js/
    ├── theme.js            # Theme toggle
    ├── sidebar-status.js   # Real-time status icons (top bar)
    ├── dashboard.js        # Dashboard functionality
    ├── log-viewer.js       # Log viewer
    ├── toast.js            # Toast notifications
    ├── confirm.js          # Confirmation dialogs
    ├── keyboard.js         # Keyboard shortcuts
    ├── performance.js      # Performance utilities
    └── loading.js          # Loading states

docs/                        # Documentation
├── phases/                 # Phase implementation summaries
│   ├── PHASE1.md
│   ├── PHASE2.md
│   └── ...
├── QUICKSTART.md
├── INSTALL.md
├── TROUBLESHOOTING.md
├── API.md
└── ARCHITECTURE.md         # This file
```

---

## Directory Map

### Core Modules

| Module | Purpose | Key Classes/Functions |
|--------|---------|----------------------|
| `cli.py` | CLI entry point | `main()`, command handlers |
| `database/__init__.py` | Database interface | `RadioDatabase` class |
| `database/schema.py` | Table definitions | `create_tables()`, `populate_stations()` |
| `database/queries.py` | SELECT operations | `get_statistics()`, `get_top_songs()`, etc. |
| `database/crud.py` | INSERT/UPDATE/DELETE | `add_artist()`, `add_song()`, etc. |
| `database/exports.py` | Export queries | `get_artists_for_lidarr_export()` |
| `gui/__init__.py` | Flask app | `init_gui()`, `run_app()` |
| `scheduler.py` | Job scheduling | `RadioScheduler` class |

### Integration Modules

| Module | Purpose | API Methods Called |
|--------|---------|-------------------|
| `scrapers.py` | Radio scraping | Selenium WebDriver |
| `mbid.py` | MusicBrainz lookup | `ws/2/artist/` |
| `lidarr.py` | Lidarr import | `/api/v1/artist/lookup`, `/api/v1/artist` |
| `plex.py` | Plex playlists | `/library/sections/{id}/all`, `/playlists` |
| `notifications.py` | Notifications | Apprise (17 providers) |

### GUI Routes (16 Blueprints)

| Blueprint | Purpose | Routes |
|-----------|---------|--------|
| `dashboard` | Main dashboard | `/`, `/api/dashboard` |
| `monitor` | Monitor controls | `/monitor`, `/api/monitor/*` |
| `lidarr` | Lidarr import | `/lidarr`, `/api/lidarr/*` |
| `plex` | Plex playlists | `/plex`, `/api/plex/*` |
| `playlists` | Playlist management | `/playlists`, `/api/playlists/*` |
| `settings` | Settings | `/settings`, `/api/settings` |
| `backup` | Backup/restore | `/backup`, `/api/backup/*` |
| `system` | System status (API) | `/api/system/*` |
| `activity` | Activity timeline | `/activity`, `/api/activity` |
| `logs` | Log viewer | `/logs`, `/api/logs` |
| `search` | Global search | `/search`, `/api/search` |
| `artists` | Artist list/detail | `/artists`, `/api/artists/*` |
| `songs` | Song list/detail | `/songs`, `/api/songs/*` |
| `stations` | Station list/detail | `/stations`, `/api/stations/*` |
| `notifications` | Notification config | `/notifications`, `/api/notifications` |
| `plex_failures` | Plex failures | `/plex-failures`, `/api/failures/*` |
| `wizard` | Setup wizard | `/wizard`, `/api/wizard` |

---

## Component Relationships

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Layer                            │
├─────────────────────────────────────────────────────────────────┤
│  CLI (cli.py)          │  Web GUI (Flask + Blueprint Routes)  │
│  - Commands             │  - Templates (Jinja2)                │
│  - Manual operations   │  - Static assets (CSS/JS)            │
└──────────────┬──────────────────────────────┬─────────────────┘
               │                              │
               ▼                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Application Layer                         │
├─────────────────────────────────────────────────────────────────┤
│  Scheduler (APScheduler)  │  Settings (JSON)                  │
│  - Scraping job           │  - radio_monitor_settings.json     │
│  - Backup job            │                                   │
│  - Cleanup jobs          │                                   │
│  - MBID retry            │                                   │
│  - Auto playlists        │                                   │
└──────────────────┬─────────────────────────────────────────────┘
                   │
       ┌───────────┼───────────┬──────────────────┐
       ▼           ▼           ▼                  ▼
┌──────────┐ ┌─────────┐ ┌──────────┐    ┌──────────────┐
│ Database │ │Scrapers │ │Integrations│   │Notifications │
│(SQLite) │ │(Selenium│ │ - Lidarr  │    │ (Apprise)    │
│          │ │ + MBID) │ │ - Plex    │    │              │
│ 10 tables│ │         │ │ - MB      │    │ 17 providers │
└──────────┘ └─────────┘ └──────────┘    └──────────────┘
```

### Request Flow (GUI)

```
Browser Request
    │
    ▼
Flask App (__init__.py)
    │
    ▼
Blueprint Route (e.g., dashboard.py)
    │
    ├─► Load Database (fresh cursor)
    │       │
    │       ▼
    │   Query/CRUD Operation
    │       │
    │       ▼
    │   Return Data
    │
    ├─► Load Settings (if needed)
    │
    ├─► Call External APIs (Lidarr, Plex, MB)
    │
    ▼
Render Template (Jinja2)
    │
    ▼
Return HTML Response
```

### Background Job Flow (Scheduler)

```
APScheduler (BackgroundScheduler)
    │
    ├─► Scraping Job (every 10 min)
    │       │
    │       ▼
    │   scrapers.py ─► Selenium ─► Station Websites
    │       │
    │       ▼
    │   Database CRUD (artists, songs, plays)
    │
    ├─► Backup Job (daily 3 AM)
    │       │
    │       ▼
    │   backup.py ─► Copy database file
    │
    ├─► Cleanup Jobs (daily 4 AM)
    │       │
    │       ▼
    │   cleanup.py ─► Delete old logs/entries
    │
    ├─► MBID Retry Job (daily)
    │       │
    │       ▼
    │   mbid_retry.py ─► MusicBrainz API
    │
    └─► Auto Playlist Jobs (configurable)
            │
            ▼
        auto_playlists.py ─► Plex API
```

---

## Data Flow Diagrams

### 1. Scraping Workflow

```
┌─────────────┐
│   Scheduler │
│   Trigger   │
└──────┬──────┘
       │
       ▼
┌──────────────────────────────────────────────┐
│         scrapers.py: scrape_station()        │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│    Selenium: Load station website           │
│    - Wait for page load                     │
│    - Extract song/artist data               │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│    Filter & Clean Data                       │
│    - Remove taglines/advertisements          │
│    - Normalize text                          │
└──────────────┬───────────────────────────────┘
               │
       ┌───────┴────────┐
       ▼                ▼
┌─────────────┐  ┌──────────────┐
│ New Artist? │  │  New Song?   │
└──────┬──────┘  └──────┬───────┘
       │ Yes              │ Yes
       ▼                 ▼
┌─────────────┐  ┌──────────────┐
│ Lookup MBID│  │ Add to DB    │
│(MusicBrainz)│  │ (CRUD)       │
└──────┬──────┘  └──────┬───────┘
       │                 │
       └────────┬────────┘
                │
                ▼
┌──────────────────────────────────────────────┐
│    Record Play (song_plays_daily)           │
│    - Check for duplicates (time window)      │
│    - Update play count                      │
│    - Track date/hour/minute/station         │
│    - Skip if within detection window         │
└──────────────────────────────────────────────┘
```

### 2. Lidarr Import Workflow

```
┌─────────────────┐
│  GUI Request    │
│  (Import Tab)   │
└────────┬────────┘
         │
         ▼
┌──────────────────────────────────────────────┐
│    Get Artists for Import                    │
│    - Filter: needs_lidarr_import = 1        │
│    - Filter: total_plays >= min_plays       │
│    - Optional: filter by station_id          │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│    For Each Artist:                          │
│    1. Lookup MBID in Lidarr                 │
│       GET /api/v1/artist/lookup?term=mbid   │
│    2. Configure (root folder, quality)      │
│    3. Add to Lidarr                        │
│       POST /api/v1/artist                   │
│    4. Handle 409 (already exists)            │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│    Mark as Imported                          │
│    - Set lidarr_imported_at = now()          │
│    - Set needs_lidarr_import = 0            │
└──────────────────────────────────────────────┘
```

### 3. Plex Playlist Workflow

```
┌─────────────────┐
│  GUI Request    │
│  (Plex Tab)    │
└────────┬────────┘
         │
         ▼
┌──────────────────────────────────────────────┐
│    Get Songs from Database                  │
│    - Apply filters (station, plays, days)   │
│    - Apply mode (top, recent, random)       │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│    Search Plex Library                      │
│    - Strategy 1: Exact match                │
│    - Strategy 2: Normalized match           │
│    - Strategy 3: Fuzzy match (Levenshtein)  │
│    - Strategy 4: Partial match              │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│    Create/Update Playlist                   │
│    - Mode: Merge (add to existing)          │
│    - Mode: Replace (clear, then add)        │
│    - Mode: Append (add to end)              │
│    - Mode: Create (new playlist)            │
│    - Mode: Snapshot (exact copy)            │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│    Log Failures                              │
│    - Record unmatched songs                  │
│    - Track search attempts                   │
└──────────────────────────────────────────────┘
```

### 4. GUI Request Flow

```
┌─────────────┐
│   Browser   │
│   Request   │
└──────┬──────┘
       │
       ▼
┌──────────────────────────────────────────────┐
│  Flask App (gui/__init__.py)                │
│  - Load database from app.config           │
│  - Load settings from app.config           │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│  Blueprint Route (e.g., artists.py)         │
│  - Get fresh cursor: db.get_cursor()        │
│  - Execute query                          │
│  - Close cursor                            │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│  Process Data                               │
│  - Pagination                              │
│  - Filtering                               │
│  - Sorting                                │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│  Render Template (Jinja2)                   │
│  - Pass data to template                   │
│  - Apply theme (light/dark)                │
│  - Include sidebar, nav, etc.              │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌─────────────┐
│   HTML      │
│   Response  │
└────────────┘

For API endpoints:
┌──────────────────────────────────────────────┐
│  Return JSON Response                       │
│  - jsonify(data)                           │
└──────────────────────────────────────────────┘
```

---

## Database Schema

### Schema Version 6 - 10 Tables

```
┌─────────────────────────────────────────────────────────────────┐
│                      CORE TABLES (5)                           │
├─────────────────────────────────────────────────────────────────┤
│  stations              artists               songs             │
│  ─────────             ─────────             ─────             │
│  id (PK)              mbid (PK)             id (PK)           │
│  name                 name                  artist_mbid (FK)   │
│  url                  first_seen_station    artist_name       │
│  genre                first_seen_at         song_title        │
│  market               last_seen_at          first_seen_at     │
│  has_mbid             needs_lidarr_import  last_seen_at      │
│  scraper_type         lidarr_imported_at    play_count        │
│  enabled                                     │
│  consecutive_failures                          │
│  last_failure_at                             │
│  created_at                                 │
│                                              │
│  song_plays_daily                             │
│  ─────────────────                           │
│  date (PK)              schema_version       │
│  hour (PK)              ─────────            │
│  song_id (PK)           version (PK)         │
│  station_id (PK)        applied_at          │
│  play_count             description          │
│                         (FK: song->artist)  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                   FEATURE TABLES (5)                            │
├─────────────────────────────────────────────────────────────────┤
│  playlists             activity_log         plex_match_failures │
│  ─────────             ─────────            ─────────────────   │
│  id (PK)              id (PK)              id (PK)            │
│  name                 timestamp             song_id (FK)        │
│  is_auto              event_type            playlist_id (FK)    │
│  interval_minutes     event_severity        failure_date       │
│  station_ids          title                 failure_reason      │
│  max_songs            description           search_attempts     │
│  mode                 metadata              search_terms_used   │
│  min_plays            source                resolved            │
│  max_plays              (FK: playlist->resolved_at          │
│  days                   station)            (FK: failure->song) │
│  enabled                                                            │
│  last_updated        notifications          notification_history│
│  next_update          ─────────            ─────────────────   │
│  plex_playlist_name  id (PK)              id (PK)            │
│  consecutive_failures notification_type    notification_id (FK)│
│  created_at          name                 sent_at             │
│                      enabled              event_type          │
│  (FK: playlist->    config               event_severity      │
│   station)           triggers             title               │
│                      created_at           message             │
│                      last_triggered        success             │
│                      failure_count        error_message       │
│                                           (FK: history->     │
│                                             notification)   │
└─────────────────────────────────────────────────────────────────┘
```

### Table Details

#### 1. `stations` - Radio Station Metadata
- **Primary Key:** `id` (text, e.g., 'wtmx', 'us99')
- **Indexes:** `idx_stations_enabled` on `enabled`
- **Purpose:** Stores station configuration and health status
- **Health Tracking:** `consecutive_failures`, `last_failure_at`
- **Auto-Disable:** Stations disabled after ~24 hours of failures

#### 2. `artists` - Artist Information
- **Primary Key:** `mbid` (MusicBrainz ID, NULL = PENDING)
- **Indexes:** `name`, `needs_lidarr_import`, `last_seen_at`, `first_seen_at`
- **Lidarr Import:** `needs_lidarr_import` flag, `lidarr_imported_at` timestamp
- **Discovery:** `first_seen_station`, `first_seen_at`
- **Relationships:** Foreign key to `stations(first_seen_station)`

#### 3. `songs` - Song Catalog
- **Primary Key:** `id` (auto-increment integer)
- **Indexes:** `play_count`, `last_seen_at`, `first_seen_at`, `artist_name`, `song_title`
- **Unique Constraint:** `(artist_mbid, song_title)` - prevents duplicates
- **Relationships:** Foreign key to `artists(mbid)`
- **Stats:** `play_count` aggregated from `song_plays_daily`

#### 4. `song_plays_daily` - Daily Play Tracking
- **Composite Primary Key:** `(date, hour, song_id, station_id)`
- **Columns:** `date`, `hour`, `minute` (nullable, v7+), `song_id`, `station_id`, `play_count`
- **Indexes:** `date`, `(song_id, station_id, date)`
- **Purpose:** Granular play tracking for charts and analytics with minute precision
- **Duplicate Detection:** Time-window deduplication (default: 20 minutes) prevents scrape overlaps
- **Relationships:** Foreign keys to `songs(id)` and `stations(id)`

#### 5. `schema_version` - Schema Version Tracking
- **Primary Key:** `version` (integer)
- **Purpose:** Track database schema migrations
- **Current Version:** 7

#### 6. `playlists` - Unified Playlists (Manual + Auto)
- **Primary Key:** `id` (auto-increment integer)
- **Indexes:** `enabled`, `next_update`, `is_auto`
- **Modes:** `merge`, `replace`, `append`, `create`, `snapshot`, `recent`, `random`
- **Filters:** `station_ids`, `max_songs`, `min_plays`, `max_plays`, `days`
- **Auto:** `is_auto`, `interval_minutes`, `next_update`
- **Health:** `consecutive_failures`

#### 7. `activity_log` - System Activity Tracking
- **Primary Key:** `id` (auto-increment integer)
- **Indexes:** `timestamp`, `event_type`, `event_severity`
- **Event Types:** `scrape`, `import`, `playlist`, `notification`, `error`
- **Severity:** `info`, `warning`, `error`, `critical`
- **Metadata:** JSON string for additional context

#### 8. `plex_match_failures` - Plex Matching Failures
- **Primary Key:** `id` (auto-increment integer)
- **Indexes:** `song_id`, `failure_date`, `resolved`
- **Purpose:** Track songs that failed to match in Plex
- **Retry Tracking:** `search_attempts`, `search_terms_used`
- **Resolution:** `resolved`, `resolved_at`
- **Auto-Cleanup:** Deleted after 7 days (non-critical)

#### 9. `notifications` - Notification Configurations
- **Primary Key:** `id` (auto-increment integer)
- **Indexes:** `enabled`, `notification_type`
- **Types:** 17 providers (Discord, Slack, Email, Telegram, etc.)
- **Config:** JSON string with provider-specific settings
- **Triggers:** JSON string with event triggers
- **Health:** `failure_count`, `last_triggered`

#### 10. `notification_history` - Notification Send History
- **Primary Key:** `id` (auto-increment integer)
- **Indexes:** `notification_id`, `sent_at`, `event_type`, `success`
- **Purpose:** Track notification delivery and failures
- **Debugging:** `error_message` for failed sends

### Key Relationships

```
stations (1) ──< (N) artists
  └─ first_seen_station

artists (1) ──< (N) songs
  └─ artist_mbid

songs (1) ──< (N) song_plays_daily
  └─ song_id

stations (1) ──< (N) song_plays_daily
  └─ station_id

playlists (1) ──< (N) plex_match_failures
  └─ playlist_id

songs (1) ──< (N) plex_match_failures
  └─ song_id

notifications (1) ──< (N) notification_history
  └─ notification_id
```

---

## Integration Points

### 1. MusicBrainz API

**Purpose:** Artist metadata lookup and MBID resolution

**Endpoints Used:**
- `GET /ws/2/artist/?query=artist:{name}&fmt=json&limit=5`
- `GET /ws/2/artist/{mbid}?inc=url-rels&fmt=json`

**Implementation:** `mbid.py`
- Fuzzy matching for artist names
- Collaboration extraction (handles "feat.", "&")
- Retry logic for PENDING artists
- Rate limiting (1 request per second)

**Data Flow:**
```
Scraper discovers new artist
    │
    ▼
lookup_artist_mbid(artist_name)
    │
    ▼
MusicBrainz API
    │
    ├─► Exact match found → Return MBID
    ├─► Fuzzy match found → Return MBID
    └─► No match → Return "PENDING"
```

### 2. Lidarr API

**Purpose:** Import artists with quality profiles and metadata

**Endpoints Used:**
- `GET /api/v1/artist/lookup?term=lidarr:{mbid}`
- `POST /api/v1/artist`
- `GET /api/v1/rootFolder`
- `GET /api/v1/qualityprofile`
- `GET /api/v1/metadataProfile`

**Implementation:** `lidarr.py`
- Lookup-first approach (validates MBID before import)
- Handles 409 Conflict (artist already exists)
- Station filtering (import by discovery source)

**Data Flow:**
```
GUI: Click "Import Selected"
    │
    ▼
Get artists (needs_lidarr_import = 1, total_plays >= 5)
    │
    ▼
For each artist:
    1. Lookup: GET /api/v1/artist/lookup?term=lidarr:{mbid}
    2. Configure: Set root folder, quality profile
    3. Add: POST /api/v1/artist
    4. Handle 409 (already exists = success)
    │
    ▼
Mark as imported (lidarr_imported_at = now())
```

**Configuration:**
- API key stored in `lidarr_api_key.txt` (file)
- URL in `radio_monitor_settings.json`
- Root folder, quality profile, monitored flag

### 3. Plex API

**Purpose:** Create and manage playlists with fuzzy matching

**Endpoints Used:**
- `GET /library/sections/{id}/all` (search tracks)
- `GET /playlists` (list playlists)
- `POST /playlists` (create playlist)
- `PUT /playlists/{id}` (update playlist)
- `DELETE /playlists/{id}` (delete playlist)

**Implementation:** `plex.py`
- Multi-strategy fuzzy matching (4 strategies)
- Unicode normalization (apostrophes, accents)
- 7 playlist modes (merge, replace, append, create, snapshot, recent, random)

**Data Flow:**
```
GUI: Create Playlist
    │
    ▼
Get songs from database (filtered)
    │
    ▼
For each song:
    1. Strategy 1: Exact match (title + artist)
    2. Strategy 2: Normalized match (Title Case, apostrophes)
    3. Strategy 3: Fuzzy match (Levenshtein >= 90%)
    4. Strategy 4: Partial match (substring)
    │
    ├─► Match found → Add to playlist
    └─► No match → Log failure
    │
    ▼
Create/Update Playlist in Plex
    │
    ├─► Mode: Merge (add to existing)
    ├─► Mode: Replace (clear, then add)
    ├─► Mode: Append (add to end)
    ├─► Mode: Create (new playlist)
    └─► Mode: Snapshot (exact copy)
```

**Fuzzy Matching:**
- Levenshtein distance algorithm
- Normalization: `AIN'T IT FUN` → `Ain't It Fun`
- Title variations: Remove (feat.), (remix), etc.
- Apostrophe handling: U+0027 ↔ U+2019

### 4. Apprise (Notifications)

**Purpose:** Multi-provider notifications (17 providers)

**Providers:**
- Discord, Slack, Email, Telegram
- Gotify, Ntfy.sh, Mattermost, Rocket.Chat
- Matrix, Pushover, Pushbullet, Prowl, Boxcar
- MQTT (IoT/home automation)

**Implementation:** `notifications.py`
- JSON configuration for each provider
- Trigger-based notification rules
- Retry logic with exponential backoff
- Failure tracking

**Data Flow:**
```
Event occurs (scrape, import, error, etc.)
    │
    ▼
Check notification triggers
    │
    ▼
For each matching notification:
    1. Load provider config (API key, URL, etc.)
    2. Compose message (title, body)
    3. Send via Apprise
    4. Log to notification_history
    │
    ├─► Success → Increment success count
    └─► Failure → Log error, increment failure_count
```

**Configuration:**
```json
{
  "notification_type": "discord",
  "name": "Discord Webhook",
  "enabled": true,
  "config": {
    "webhooks": ["https://discord.com/api/webhooks/..."]
  },
  "triggers": ["scrape_complete", "import_complete", "error"]
}
```

---

## Design Patterns

### 1. Thread-Safe Database Access

**Problem:** SQLite cursors cannot be shared across threads in Flask multi-threaded mode.

**Solution:** Always use fresh cursors per request.

```python
# CORRECT - Thread-safe
from flask import current_app

@app.route('/api/artists')
def get_artists():
    db = current_app.config.get('db')
    cursor = db.get_cursor()  # Fresh cursor
    try:
        return queries.get_all_artists(cursor)
    finally:
        cursor.close()

# WRONG - Causes threading issues
from radio_monitor.gui import db

def get_artists():
    return db.get_all_artists()  # Reuses cursor - will fail!
```

**Implementation:**
- `RadioDatabase.get_cursor()` creates fresh cursor
- Flask request context stores DB in `app.config['db']`
- Background jobs use `get_thread_local_connection()`

### 2. Blueprint-Based Route Organization

**Problem:** Large monolithic Flask apps are hard to maintain.

**Solution:** Modular blueprints for each feature.

```python
# gui/routes/artists.py
artists_bp = Blueprint('artists', __name__)

@artists_bp.route('/artists')
def list_artists():
    # ...

@artists_bp.route('/artists/<mbid>')
def artist_detail(mbid):
    # ...

@artists_bp.route('/api/artists')
def api_artists():
    # ...

# Register in gui/__init__.py
app.register_blueprint(artists_bp)
```

**Benefits:**
- Separation of concerns
- Easier testing
- Reusable components
- Clear URL routing

### 3. Settings Management

**Problem:** Configuration needs to be accessible across CLI and GUI.

**Solution:** JSON-based settings with loader function.

```json
{
  "lidarr": {
    "url": "http://localhost:8686",
    "api_key_file": "lidarr_api_key.txt"
  },
  "plex": {
    "url": "http://localhost:32400",
    "token": "your-plex-token"
  },
  "monitor": {
    "database_file": "radio_songs.db",
    "scrape_interval_minutes": 10
  }
}
```

**Access Pattern:**
```python
# Load settings
from radio_monitor.gui import load_settings
settings = load_settings() or {}

# Get Lidarr URL
lidarr_url = settings.get('lidarr', {}).get('url')
```

**Critical:** Always use `load_settings()` function, never import module-level `settings`.

### 4. Activity Logging

**Problem:** Need to track system events for debugging and auditing.

**Solution:** Centralized activity logging with structured events.

```python
from radio_monitor.database import activity

def log_event(db, event_type, title, description=None,
              severity='info', metadata=None, source='system'):
    """Log an event to the activity log

    Args:
        db: RadioDatabase instance
        event_type: Type of event (scrape, import, error, etc.)
        title: Event title
        description: Detailed description
        severity: info, warning, error, critical
        metadata: JSON string with additional context
        source: Source of event (system, user, scheduler)
    """
    activity.log_activity(db.cursor, db.conn, event_type,
                         title, description, severity, metadata, source)
```

**Event Types:**
- `scrape_start`, `scrape_complete`, `scrape_error`
- `import_start`, `import_complete`, `import_error`
- `playlist_create`, `playlist_update`, `playlist_error`
- `notification_sent`, `notification_failed`
- `backup_complete`, `cleanup_complete`

### 5. Scheduler Integration

**Problem:** Need background jobs for scraping, backups, and maintenance.

**Solution:** APScheduler wrapper with Flask integration.

```python
# Initialize scheduler with scraping function
def scrape_job():
    try:
        logger.info("Starting scheduled scrape")
        scrape_all_stations(db)
        logger.info("Scheduled scrape complete")
    except Exception as e:
        logger.error(f"Error during scheduled scrape: {e}")

scheduler = RadioScheduler(scrape_job, scrape_interval_minutes=10)

# Start scheduler
scheduler.scheduler.start()

# Control scraping
scheduler.start()  # Resume scraping
scheduler.stop()   # Pause scraping
```

**Job Types:**
- **Scraping Job:** Every 10 minutes (configurable)
- **Backup Job:** Daily at 3 AM (configurable)
- **Cleanup Jobs:** Daily at 4 AM (activity, logs, Plex failures)
- **MBID Retry Job:** Daily (retry PENDING artists)
- **Auto Playlist Jobs:** Configurable intervals

### 6. Graceful Shutdown

**Problem:** Background jobs need to stop cleanly on exit.

**Solution:** Signal handlers and cleanup functions.

```python
import signal

def signal_handler(sig, frame):
    logger.info("\nShutdown signal received. Stopping gracefully...")
    try:
        # Cancel any ongoing scraping
        cancel_scraping()

        # Use GUI cleanup function
        cleanup()

    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

    logger.info("Shutdown complete. Goodbye!")
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
```

**Cleanup Steps:**
1. Cancel ongoing scraping
2. Shutdown scheduler (wait for jobs)
3. Close database connection
4. Exit cleanly

---

## API Routes

### REST API Endpoints

**Dashboard**
- `GET /` - Dashboard page
- `GET /api/dashboard/stats` - Dashboard statistics
- `GET /api/dashboard/recent-plays` - Recent plays feed

**Monitor**
- `GET /monitor` - Monitor page
- `POST /api/monitor/start` - Start monitoring
- `POST /api/monitor/stop` - Stop monitoring
- `GET /api/monitor/status` - Current status

**Lidarr**
- `GET /lidarr` - Lidarr import page
- `GET /api/lidarr/artists` - Artists needing import
- `POST /api/lidarr/import` - Import selected artists
- `POST /api/lidarr/test` - Test Lidarr connection

**Plex**
- `GET /plex` - Plex playlists page
- `GET /api/plex/playlists` - List Plex playlists
- `POST /api/plex/create` - Create playlist
- `POST /api/plex/test` - Test Plex connection

**Playlists**
- `GET /playlists` - Playlist management page
- `GET /api/playlists` - List all playlists
- `POST /api/playlists` - Create playlist
- `PUT /api/playlists/<id>` - Update playlist
- `DELETE /api/playlists/<id>` - Delete playlist
- `POST /api/playlists/<id>/run` - Run playlist now

**Settings**
- `GET /settings` - Settings page
- `GET /api/settings` - Get current settings
- `POST /api/settings` - Save settings

**Backup**
- `GET /backup` - Backup/restore page
- `POST /api/backup/create` - Create backup
- `POST /api/backup/restore` - Restore backup
- `GET /api/backup/list` - List backups

**System**
- `GET /api/system/status` - System status (used by top bar status icons)
- `GET /api/system/health` - Health check

**Activity**
- `GET /activity` - Activity timeline page
- `GET /api/activity` - Get activity log (paginated, filtered)

**Logs**
- `GET /logs` - Log viewer page
- `GET /api/logs` - Get log entries (filtered)

**Search**
- `GET /search` - Search page
- `GET /api/search` - Global search (artists, songs, stations)

**Artists**
- `GET /artists` - Artist list page
- `GET /artists/<mbid>` - Artist detail page
- `GET /api/artists` - Get artists (paginated, filtered)

**Songs**
- `GET /songs` - Song list page
- `GET /songs/<id>` - Song detail page
- `GET /api/songs` - Get songs (paginated, filtered)

**Stations**
- `GET /stations` - Station list page
- `GET /stations/<id>` - Station detail page
- `GET /api/stations` - Get all stations
- `POST /api/stations` - Add station
- `DELETE /api/stations/<id>` - Delete station

**Notifications**
- `GET /notifications` - Notification config page
- `GET /api/notifications` - Get all notifications
- `POST /api/notifications` - Create notification
- `PUT /api/notifications/<id>` - Update notification
- `DELETE /api/notifications/<id>` - Delete notification

**Plex Failures**
- `GET /plex-failures` - Plex failures page
- `GET /api/failures` - Get failures (paginated)
- `POST /api/failures/<id>/dismiss` - Dismiss failure
- `POST /api/failures/<id>/retry` - Retry match
- `POST /api/failures/clear-all` - Clear all failures

**Wizard**
- `GET /wizard` - Setup wizard page
- `POST /api/wizard/validate` - Validate step
- `POST /api/wizard/complete` - Complete wizard

---

## Development Guidelines

### Code Style

1. **Use meaningful variable names**
   ```python
   # Good
   artists_for_import = db.get_artists_for_import(min_plays=5)

   # Bad
   a = db.get_artists_for_import(min_plays=5)
   ```

2. **Add docstrings to functions**
   ```python
   def scrape_station(station_id, db):
       """Scrape a single radio station for current songs

       Args:
           station_id: Station ID from database
           db: RadioDatabase instance

       Returns:
           dict: Scrape results with keys:
               - songs_scraped: Number of songs found
               - artists_added: Number of new artists
               - songs_added: Number of new songs
               - plays_recorded: Number of plays recorded
       """
   ```

3. **Handle errors gracefully**
   ```python
   try:
       result = import_artist_to_lidarr(mbid, name, settings)
   except requests.exceptions.ConnectionError:
       logger.error(f"Lidarr connection failed: {name}")
       return False, "Lidarr connection failed"
   except Exception as e:
       logger.error(f"Unexpected error: {e}")
       return False, str(e)
   ```

4. **ALWAYS use fresh cursors**
   ```python
   # CORRECT
   from flask import current_app

   @app.route('/api/artists')
   def get_artists():
       db = current_app.config.get('db')
       cursor = db.get_cursor()
       try:
           return queries.get_all_artists(cursor)
       finally:
           cursor.close()
   ```

### Before Committing

1. **Run smoke test**
   ```bash
   python -m radio_monitor.cli --test
   ```

2. **Test GUI**
   - Load all pages
   - Test new functionality
   - Check for console errors

3. **Check logs**
   ```bash
   tail -f radio_monitor.log | grep ERROR
   ```

4. **Update documentation**
   - Update this file if architecture changes
   - Update CLAUDE.md with new features
   - Add inline comments for complex logic

---

## Performance Considerations

### Database Optimization

1. **Indexes:** All frequently queried columns are indexed
   - `artists(name)`, `artists(needs_lidarr_import)`
   - `songs(play_count)`, `songs(last_seen_at)`
   - `song_plays_daily(date)`, `song_plays_daily(song_id, station_id)`

2. **Pagination:** Large datasets use pagination
   - Default: 50 items per page
   - Configurable: 10, 25, 50, 100

3. **Connection Pooling:** Fresh cursors per request (thread-safe)

### Web Scraping

1. **Chrome WebDriver:** Headless mode for performance
2. **Wait Times:** 10-15 seconds per station (configurable)
3. **Cancellation:** Graceful cancellation support
4. **Rate Limiting:** 1 request/second for MusicBrainz API

### Caching

1. **Simple Cache:** `cache.py` for in-memory caching
2. **Browser Caching:** Disabled in development (`SEND_FILE_MAX_AGE_DEFAULT = 0`)

---

## Security Considerations

### API Keys

- **Lidarr:** Stored in `lidarr_api_key.txt` (file, not in Git)
- **Plex:** Stored in `radio_monitor_settings.json` (file, not in Git)
- **Notification Providers:** Stored in `radio_monitor_settings.json`

### Flask Secret Key

- Current: `'radio-monitor-secret-key-change-in-production'`
- **TODO:** Generate secure key for production

### Input Validation

- All user inputs sanitized (Jinja2 auto-escaping)
- SQL queries use parameterized statements (no SQL injection)
- API calls use timeouts (30 seconds default)

### Network Access

- GUI binds to `0.0.0.0` (all interfaces)
- Default port: 5000
- Windows: `http://127.0.0.1:5000`
- Linux/Mac: `http://localhost:5000`

---

## Troubleshooting

### Common Issues

**"Database not initialized"**
```python
db = current_app.config.get('db')
if not db:
    return jsonify({'error': 'Database not initialized'}), 500
```

**"Recursive use of cursors"**
- **Cause:** Reusing cursor across threads
- **Solution:** Always use `db.get_cursor()` for fresh cursor

**"'NoneType' object has no attribute 'get'"**
- **Cause:** Importing module-level `settings` before initialization
- **Solution:** Use `load_settings()` function

**Artists showing as MBIDs**
```bash
python -m radio_monitor.cli --retry-pending
```

**Plex playlist creation fails**
1. Verify Plex connection in Settings
2. Check Plex token is valid
3. Check Plex Failures page for specific errors

### Logging

- **Log file:** `radio_monitor.log`
- **Level:** INFO (default)
- **Format:** `%(asctime)s - %(levelname)s - %(message)s`

**View logs:**
```bash
tail -f radio_monitor.log
grep ERROR radio_monitor.log
grep "SCRAPER" radio_monitor.log
```

---

## Future Enhancements

### Planned Features

1. **Additional Integrations**
   - Spotify integration
   - Last.fm scrobbling
   - YouTube Music playlists

2. **Advanced Analytics**
   - Trending songs detection
   - Genre clustering
   - Artist similarity graphs

3. **Performance**
   - Redis caching layer
   - Asynchronous scraping
   - Database connection pooling

4. **UI/UX**
   - Real-time WebSocket updates
   - Dark mode improvements
   - Mobile app (React Native)

### Architecture Improvements

1. **Microservices:** Split scraping, GUI, and integrations
2. **Message Queue:** RabbitMQ/Redis for job queue
3. **Containerization:** Docker support
4. **Testing:** Increase test coverage to 80%+

---

## Contributing

### Adding New Features

1. **Create feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Follow architecture patterns**
   - Add routes to `gui/routes/`
   - Add database queries to `database/queries.py` or `database/crud.py`
   - Update templates in `templates/`
   - Add static assets to `static/`

3. **Test thoroughly**
   - Run smoke test
   - Test GUI manually
   - Check logs for errors

4. **Update documentation**
   - Update this file (`ARCHITECTURE.md`)
   - Update `CLAUDE.md` with new features
   - Add inline comments

5. **Submit pull request**
   - Describe changes
   - Link to related issues
   - Include screenshots if GUI changes

---

## License

This project is provided as-is for personal use.

---

**Last Updated:** 2026-02-12
**Version:** 1.0.0 (Phase 8 Complete)
**Schema Version:** 6 (10 tables)
