# Radio Monitor

**Version:** 1.1.7
**Database Schema:** v12 (12 tables)
**Python:** 3.10+
**License:** MIT

---

## 📻 What is Radio Monitor?

Radio Monitor is a comprehensive web application for automatically discovering music from radio stations and integrating with your personal media library (Lidarr and Plex).

### ✨ Key Features

1. **Radio Scraping** - Monitors 8+ radio stations with real-time song identification
2. **Music Discovery** - Identifies artists and songs using MusicBrainz API
3. **Lidarr Integration** - One-click import of discovered artists to Lidarr
4. **Plex Integration** - Creates dynamic Plex playlists with fuzzy matching
5. **Manual Playlist Builder** - Create custom playlists by manually selecting songs ✨ **NEW**
6. **AI-Powered Playlists** - Generate playlists using natural language instructions (Experimental)
7. **Web GUI** - Browser-based management with modern sidebar navigation
8. **Analytics** - Play counts, charts, and activity timeline
9. **Automation** - Scheduled scraping, importing, and playlist creation
10. **Notifications** - 17 notification providers (Discord, Slack, Email, Telegram, etc.)

---

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/allurjj/radio-monitor.git
cd radio-monitor

# Install dependencies
pip install -r requirements.txt

# Initialize the database
python -m radio_monitor.cli --init-db

# Start the GUI
python -m radio_monitor.cli --gui
```

### Access the Web Interface

Open your browser to: **http://127.0.0.1:5000** (Windows) or **http://localhost:5000** (Linux/Mac)

Default credentials:
- **Username:** admin
- **Password:** admin (change immediately after first login)

---

## 📚 Features Overview

### Core Features

| Feature | Description |
|---------|-------------|
| **Radio Scraping** | Monitors Chicago area radio stations (WTMX, US99, WLS, etc.) |
| **Music Discovery** | Artist MBID lookup with MusicBrainz API integration |
| **Lidarr Import** | Import artists with quality profile and root folder selection |
| **Plex Playlists** | 7 playlist modes: merge, replace, append, create, snapshot, recent, random |
| **Manual Playlist Builder** | Create custom playlists by manually selecting songs from your catalog ✨ |
| **AI Playlists** | Natural language playlist generation ("Upbeat party songs") |
| **Web GUI** | 18 integrated blueprints with modern *arr-style design |
| **Analytics** | Play counts, charts, and activity timeline |
| **Automation** | APScheduler for background jobs |
| **Notifications** | 17 providers (Discord, Slack, Email, Telegram, etc.) |

---

## 🆕 New in Version 1.1.7

### Manual Playlist Builder

**Create custom playlists by manually selecting songs from your radio monitoring database.**

#### Key Capabilities:
- **Browse Entire Catalog**: Access all discovered songs with powerful filters
- **Two View Modes**: By Artist (grouped) or By Song (flat list)
- **Advanced Filtering**: Station, date range, play counts, search
- **Multi-Select**: Select songs across pages and sessions
- **Persistent Selections**: Selections saved even if you navigate away
- **Plex Integration**: One-click playlist creation in Plex
- **Full CRUD**: Create, edit, and delete playlists

#### How to Use:
1. Navigate to **Playlist Builder** in the sidebar
2. Use filters to find songs you want to include
3. Click checkboxes to select songs
4. Click **"Create Playlist"** and enter a name
5. Playlist is saved and optionally synced to Plex

#### Documentation:
- **User Guide**: [docs/MANUAL_PLAYLIST_BUILDER.md](docs/MANUAL_PLAYLIST_BUILDER.md)
- **API Documentation**: [API.md](API.md) (Playlist Builder blueprint)

---

## 📖 Documentation

### User Documentation
- **Installation Guide**: [INSTALL.md](INSTALL.md)
- **API Documentation**: [API.md](API.md)
- **Troubleshooting**: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **Manual Playlist Builder**: [docs/MANUAL_PLAYLIST_BUILDER.md](docs/MANUAL_PLAYLIST_BUILDER.md)
- **AI Playlists Feature**: [docs/AI_PLAYLISTS_FEATURE.md](docs/AI_PLAYLISTS_FEATURE.md)

### Developer Documentation
- **Architecture**: [ARCHITECTURE.md](ARCHITECTURE.md)
- **Development Guidelines**: [CLAUDE.md](CLAUDE.md)
- **Memory & Patterns**: [MEMORY.md](MEMORY.md)

### Build & Deployment
- **Docker**: [docker/Dockerfile](docker/Dockerfile)
- **Windows EXE**: [WINDOWS_EXE_BUILD_GUIDE.md](WINDOWS_EXE_BUILD_GUIDE.md)
- **Docker Guide**: [DOCKER.md](DOCKER.md)

---

## 🗄️ Database Schema

**Current Version:** v12 (12 tables)

### Core Tables (5)
- `stations` - Radio station metadata and health tracking
- `artists` - Artist MBIDs and metadata
- `songs` - Song titles with play counts
- `song_plays_daily` - Hourly play tracking
- `schema_version` - Migration tracking

### Feature Tables (7)
- `playlists` - Automated Plex playlist configurations
- `activity_log` - System activity tracking
- `plex_match_failures` - Failed Plex match attempts
- `notifications` - Notification provider configurations
- `notification_history` - Notification delivery history
- `manual_mbid_overrides` - Manual MBID corrections
- `ai_playlist_generations` - AI playlist generation history

### New in v12 (Manual Playlist Builder)
- `manual_playlists` - User-created manual playlists
- `manual_playlist_songs` - Songs in manual playlists (many-to-many)
- `playlist_builder_state` - Persistent user selections

---

## 🛠️ CLI Commands

```bash
# Start GUI
python -m radio_monitor.cli --gui

# One-time scrape
python -m radio_monitor.cli --scrape-once

# Import to Lidarr
python -m radio_monitor.cli --import-lidarr

# Create Plex playlists
python -m radio_monitor.cli --create-playlists

# Backup database
python -m radio_monitor.cli --backup-db

# Retry failed MBID lookups
python -m radio_monitor.cli --retry-pending

# Smoke test
python -m radio_monitor.cli --test
```

---

## 🔧 Configuration

### Settings File: `radio_monitor_settings.json`

```json
{
  "lidarr": {
    "url": "http://localhost:8686",
    "api_key": "your-api-key"
  },
  "plex": {
    "url": "http://localhost:32400",
    "token": "your-plex-token"
  },
  "duplicate_detection_window_minutes": 75,
  "gui": {
    "host": "0.0.0.0",
    "port": 5000,
    "debug": false
  }
}
```

---

## 📊 Database Scale

- **Artists:** 800+
- **Songs:** 1,500+
- **Radio Stations:** 12 (Chicago area + genre stations)
- **Database Growth:** ~29 MB/year (with hourly play tracking)

---

## 🚢 Deployment

### Docker (Recommended)

```bash
# Build image
docker build -t radio-monitor -f docker/Dockerfile .

# Run container
docker run -d \
  -p 5000:5000 \
  -v radio_monitor_data:/app/data \
  --name radio-monitor \
  radio-monitor
```

### Windows EXE

See [WINDOWS_EXE_BUILD_GUIDE.md](WINDOWS_EXE_BUILD_GUIDE.md) for complete instructions.

### Source Installation

See [INSTALL.md](INSTALL.md) for prerequisites and setup.

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Check [FUTURE_ENHANCEMENTS.md](FUTURE_ENHANCEMENTS.md) for planned features
2. Fork the repository
3. Create a feature branch
4. Make your changes
5. Submit a pull request

---

## 📝 Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

### Recent Releases

- **1.1.7** (2026-02-23) - Manual Playlist Builder feature
- **1.1.6** (2026-02-23) - MBID Status Filter
- **1.1.5** (2026-02-22) - Dynamic version management
- **1.1.4** (2026-02-21) - Database query optimizations

---

## 🐛 Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| "Database not initialized" | Run `python -m radio_monitor.cli --init-db` |
| Artists showing as MBIDs | Run `python -m radio_monitor.cli --retry-pending` |
| GUI won't start | Check if port 5000 is already in use |
| Plex connection failed | Verify URL and token in Settings |

For more troubleshooting, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

---

## 📞 Support

- **GitHub Issues:** https://github.com/allurjj/radio-monitor/issues
- **Documentation:** https://github.com/allurjj/radio-monitor
- **Release Notes:** https://github.com/allurjj/radio-monitor/releases

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

## ⭐ Star History

If you find this project useful, please consider giving it a star on GitHub!

https://github.com/allurjj/radio-monitor

---

**Version:** 1.1.7
**Python:** 3.10+
**Database:** SQLite (Schema v12)
**Last Updated:** 2026-02-23
