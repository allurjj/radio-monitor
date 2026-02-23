# Radio Monitor Installation Guide

**Version:** 1.1.3
**Last Updated:** 2026-02-22

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation Methods](#installation-methods)
3. [Step-by-Step Installation](#step-by-step-installation)
4. [Configuration](#configuration)
5. [Running the Application](#running-the-application)
6. [Network Access](#network-access)
7. [Troubleshooting Installation](#troubleshooting-installation)
8. [Upgrading](#upgrading)

---

## Prerequisites

### System Requirements

- **Operating System:** Windows 10+, macOS 10.15+, or Linux (Ubuntu 20.04+)
- **Memory:** 4GB RAM minimum (8GB recommended)
- **Disk Space:** 500MB minimum (plus database growth)
- **Network:** Internet connection for MusicBrainz, Lidarr, and Plex APIs

### Software Requirements

- **Python:** 3.8 or higher (3.10+ recommended)
  - Windows: Download from [python.org](https://www.python.org/downloads/)
  - Linux: `sudo apt-get install python3.10 python3-pip`
  - macOS: `brew install python@3.10`

- **SQLite3:** Included with Python (no separate installation needed)

- **Web Browser:** Chrome, Firefox, Edge, or Safari (for web GUI)
  - Note: Chrome/ChromeDriver NO LONGER REQUIRED (Selenium removed in v1.1.0)

### External Services (Optional)

- **Lidarr:** For artist import (recommended)
  - Download: [Lidarr.github.io](https://lidarr.audio/)
  - Requires API key from Lidarr Settings → General

- **Plex Media Server:** For playlist creation (recommended)
  - Download: [plex.tv](https://www.plex.tv/)
  - Requires X-Plex-Token from Plex account

- **MusicBrainz API:** Free, no account required
  - Rate limit: 1 request per second (enforced automatically)

---

## Installation Methods

### Method 1: Git Clone (Recommended)

Best for updates and version control:

```bash
# Clone repository
git clone https://github.com/yourusername/radio-monitor.git
cd radio-monitor

# Or download and extract ZIP file from GitHub Releases
```

### Method 2: Download ZIP

For users without Git:

1. Go to [GitHub Releases](https://github.com/yourusername/radio-monitor/releases)
2. Download latest `radio-monitor-v1.0.0.zip`
3. Extract to desired location (e.g., `C:\RadioMonitor` or `~/radio-monitor`)
4. Open terminal/command prompt in extracted directory

### Method 3: Direct Installation

For Python package installation (not yet available):

```bash
pip install radio-monitor
```

---

## Step-by-Step Installation

### Step 1: Verify Python Installation

Open terminal/command prompt and check Python version:

```bash
python --version
# OR
python3 --version
```

**Expected output:** `Python 3.8.0` or higher

**If not installed:**
- **Windows:** Download and install from [python.org](https://www.python.org/downloads/)
  - ✅ Check "Add Python to PATH" during installation
- **Linux:** `sudo apt-get update && sudo apt-get install python3.10 python3-pip python3-venv`
- **macOS:** `brew install python@3.10`

### Step 2: Create Virtual Environment (Recommended)

Virtual environments prevent dependency conflicts:

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate

# Linux/macOS:
source venv/bin/activate
```

**You'll see `(venv)` in your terminal prompt when activated**

### Step 3: Install Dependencies

Install required Python packages:

```bash
# Ensure pip is up-to-date
python -m pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

**If `requirements.txt` doesn't exist, install core dependencies manually:**

```bash
pip install Flask Flask-Cors APScheduler requests musicbrainzngs \
            python-dotenv plexapi python-dateutil
```

**Dependencies installed:**
- `Flask` - Web framework for GUI
- `APScheduler` - Background job scheduling
- `requests` - HTTP client for web scraping
- `beautifulsoup4` - HTML parsing for web scraping
- `musicbrainzngs` - MusicBrainz API wrapper
- `plexapi` - Plex Media Server API wrapper
- `python-dotenv` - Environment variable management

**Note:** Selenium and ChromeDriver are NO LONGER REQUIRED (removed in v1.1.0)

### Step 5: Create Configuration File

Run the setup wizard to create `radio_monitor_settings.json`:

```bash
python -m radio_monitor.cli --gui
```

Or manually create `radio_monitor_settings.json`:

```json
{
  "lidarr": {
    "url": "http://localhost:8686",
    "api_key_file": "lidarr_api_key.txt"
  },
  "plex": {
    "url": "http://localhost:32400",
    "token": "your-plex-token-here"
  },
  "monitor": {
    "database_file": "radio_songs.db",
    "stations": ["b96", "kissfm", "q101"]
  },
  "notifications": {
    "enabled": false
  }
}
```

### Step 6: Test Installation

Verify all components work:

```bash
# Run smoke test
python -m radio_monitor.cli --test
```

**Expected output:**
```
✓ Database initialized: radio_songs.db
✓ Database schema: version 6
✓ Lidarr API: Connected
✓ Plex API: Connected
✓ MusicBrainz API: Connected
✓ All systems operational
```

**If errors occur, see [Troubleshooting](#troubleshooting-installation)**

---

## Configuration

### Setup Wizard (Recommended)

The web-based setup wizard guides you through configuration:

1. Start the GUI: `python -m radio_monitor.cli --gui`
2. Open browser to **http://127.0.0.1:5000** (Windows) or **http://localhost:5000** (Linux/Mac)
3. Click **"Setup Wizard"** in sidebar
4. Follow 5-step wizard:
   - **Step 1:** Database file location
   - **Step 2:** Lidarr connection (URL + API key)
   - **Step 3:** Plex connection (URL + token)
   - **Step 4:** Radio station selection
   - **Step 5:** Notification preferences

### Manual Configuration

Edit `radio_monitor_settings.json` directly:

```json
{
  "lidarr": {
    "url": "http://192.168.1.100:8686",
    "api_key_file": "lidarr_api_key.txt",
    "root_folder": "/music/Artists",
    "quality_profile_id": 1
  },
  "plex": {
    "url": "http://192.168.1.100:32400",
    "token": "abc123xyz789",
    "music_library_name": "Music"
  },
  "monitor": {
    "database_file": "radio_songs.db",
    "scrape_interval_minutes": 10,
    "stations": [
      {"name": "B96", "url": "http://b96.cbslocal.com", "enabled": true},
      {"name": "KISS-FM", "url": "http://kissfmchicago.iheart.com", "enabled": true}
    ],
    "station_health_disable_days": 30
  },
  "database": {
    "backup_enabled": true,
    "backup_path": "backups/",
    "backup_retention_days": 30
  },
  "notifications": {
    "enabled": true,
    "providers": [
      {"type": "discord", "webhook_url": "https://discord.com/api/webhooks/..."},
      {"type": "email", "smtp_host": "smtp.gmail.com", "smtp_port": 587}
    ],
    "on_new_artist": true,
    "on_import_error": true
  }
}
```

### Lidarr API Key Setup

1. Open Lidarr web GUI
2. Go to **Settings → General → Security**
3. Click **"+"** button to add API key
4. Copy API key to file: `lidarr_api_key.txt` (in project root)
5. Reference file in settings: `"api_key_file": "lidarr_api_key.txt"`

**OR** paste API key directly in settings:

```json
{
  "lidarr": {
    "url": "http://localhost:8686",
    "api_key": "your-api-key-here"
  }
}
```

### Plex Token Setup

**Method 1: Web Interface (Easiest)**

1. Open Plex web app: https://app.plex.tv/desktop
2. Sign in to your Plex account
3. Go to **Settings → Auth Token**
4. Copy token

**Method 2: Command Line**

```bash
# Get token from Plex (requires your Plex username/password)
python -c "from plexapi.myplex import MyPlexAccount; account = MyPlexAccount('user', 'pass'); print(account.authenticationToken)"
```

### Station Configuration

Default stations (Chicago area) are included. To add custom stations:

1. Go to **Stations** page in web GUI
2. Click **"Add Station"**
3. Enter station name and URL
4. Click **"Test Connection"** to verify scraping works
5. Click **"Save"**

**Supported station types:**
- iHeartRadio stations (e.g., KISS-FM)
- CBS Local stations (e.g., B96)
- Stations with HTML song history pages

---

## Running the Application

### Start Web GUI

```bash
python -m radio_monitor.cli --gui
```

**Access GUI:** Open browser to:
- **Windows:** http://127.0.0.1:5000
- **Linux/macOS:** http://localhost:5000
- **Other devices:** http://192.168.1.100:5000 (your PC's IP address)

**GUI includes:**
- Dashboard with live stats
- Monitor controls (start/stop scraping)
- Lidarr import interface
- Plex playlist creator
- Settings management
- Charts and analytics

### Start Monitor Only (CLI)

```bash
# Start monitoring (scraping stations in background)
python -m radio_monitor.cli --monitor

# Scrape once (immediate)
python -m radio_monitor.cli --scrape-once

# Import to Lidarr
python -m radio_monitor.cli --import-lidarr

# Create Plex playlists
python -m radio_monitor.cli --create-playlists

# Backup database
python -m radio_monitor.cli --backup-db

# Retry failed MBID lookups
python -m radio_monitor.cli --retry-pending
```

### Start as Background Service

**Windows (Task Scheduler):**

1. Open Task Scheduler
2. Create Basic Task
3. Trigger: "At startup"
4. Action: "Start a program"
   - Program: `C:\Python310\python.exe`
   - Arguments: `-m radio_monitor.cli --monitor`
   - Start in: `C:\RadioMonitor`

**Linux (systemd):**

Create `/etc/systemd/system/radio-monitor.service`:

```ini
[Unit]
Description=Radio Monitor Service
After=network.target

[Service]
Type=simple
User=yourusername
WorkingDirectory=/home/yourusername/radio-monitor
Environment="PATH=/home/yourusername/radio-monitor/venv/bin"
ExecStart=/home/yourusername/radio-monitor/venv/bin/python -m radio_monitor.cli --monitor
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable radio-monitor
sudo systemctl start radio-monitor
sudo systemctl status radio-monitor
```

**macOS (launchd):**

Create `~/Library/LaunchAgents/com.radio-monitor.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.radio-monitor</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/python3</string>
        <string>-m</string>
        <string>radio_monitor.cli</string>
        <string>--monitor</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/yourusername/radio-monitor</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

Load and start:

```bash
launchctl load ~/Library/LaunchAgents/com.radio-monitor.plist
launchctl start com.radio-monitor
```

---

## Network Access

By default, Radio Monitor listens on `0.0.0.0:5000` (all network interfaces).

### Access from Other Devices

1. **Find your PC's IP address:**

**Windows:**
```bash
ipconfig
# Look for "IPv4 Address" (e.g., 192.168.1.100)
```

**Linux/macOS:**
```bash
ifconfig | grep inet
# OR
ip addr show | grep inet
```

2. **Access from other device:**

Open browser on phone/tablet/other computer:
- **http://192.168.1.100:5000** (replace with your IP)

### Firewall Configuration

**Windows:**

1. Open Windows Defender Firewall
2. Advanced Settings → Inbound Rules → New Rule
3. Port: 5000, TCP, Allow the connection
4. Name: "Radio Monitor"

**Linux (UFW):**

```bash
sudo ufw allow 5000/tcp
sudo ufw reload
```

**Linux (firewalld):**

```bash
sudo firewall-cmd --permanent --add-port=5000/tcp
sudo firewall-cmd --reload
```

**macOS:**

```bash
# Add firewall rule (System Preferences → Security & Privacy → Firewall)
# Or disable firewall temporarily for testing
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate
```

### Reverse Proxy (Nginx)

For domain access and HTTPS:

**Nginx config:**

```nginx
server {
    listen 80;
    server_name radio-monitor.example.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Enable HTTPS with Let's Encrypt:**

```bash
sudo certbot --nginx -d radio-monitor.example.com
```

---

## Troubleshooting Installation

### Issue: "python: command not found"

**Solution:**

**Windows:**
- Reinstall Python with "Add to PATH" checked
- Or use `py` instead of `python` (Windows launcher)

**Linux:**
```bash
sudo update-alternatives --install /usr/bin/python python /usr/bin/python3.10 1
```

### Issue: "No module named 'flask'"

**Solution:**

```bash
# Ensure virtual environment is activated
# Windows:
venv\Scripts\activate

# Linux/macOS:
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Issue: "ChromeDriver not found"

**Removed in v1.1.0** - Selenium and ChromeDriver are no longer required

### Issue: "Database file not found"

**Solution:**

```bash
# Create empty database
python -m radio_monitor.cli --test
# This initializes radio_songs.db automatically
```

### Issue: "Lidarr connection failed"

**Solution:**

1. Verify Lidarr is running: `http://localhost:8686`
2. Check API key in Lidarr Settings → Security
3. Test API key:
```bash
curl -H "X-Api-Key: your-key" http://localhost:8686/api/v1/system/status
```
4. Check firewall settings

### Issue: "Plex token invalid"

**Solution:**

1. Verify token is correct (regenerate from Plex web)
2. Test token:
```bash
curl -H "X-Plex-Token: your-token" http://localhost:32400
```
3. Check Plex Media Server is running

### Issue: "Port 5000 already in use"

**Solution:**

**Windows:**
```bash
netstat -ano | findstr :5000
taskkill /PID <PID> /F
```

**Linux/macOS:**
```bash
lsof -i :5000
kill -9 <PID>
```

**OR** change port in `radio_monitor/cli.py`:

```python
app.run(host='0.0.0.0', port=5001)  # Change 5000 to 5001
```

### Issue: "Permission denied" on Linux/macOS

**Solution:**

```bash
# Fix file permissions
chmod +x radio_monitor/cli.py
chmod -R 755 radio_monitor/

# If using virtual environment
chmod +x venv/bin/python
```

### Issue: Web scraping fails

**Solution (v1.1.0):**

1. Verify internet connection
2. Check iHeartRadio website is accessible
3. Review application logs (Logs page in GUI)
4. Try manual scrape: `python -m radio_monitor.cli --scrape-once`

### Issue: High memory usage

**Solution:**

```bash
# Limit database size (enable auto-backup and cleanup)
# Edit radio_monitor_settings.json:
{
  "database": {
    "backup_enabled": true,
    "backup_retention_days": 30,
    "auto_vacuum_enabled": true
  }
}
```

---

## Upgrading

### From Earlier Versions

**Backup First:**

```bash
# Backup database
cp radio_songs.db radio_songs.db.backup

# Backup settings
cp radio_monitor_settings.json radio_monitor_settings.json.backup
```

**Upgrade Code:**

```bash
# If using git
git pull origin main

# If using downloaded ZIP
# Download new version and extract to new directory
# Copy radio_songs.db and radio_monitor_settings.json to new directory
```

**Run Migration:**

```bash
# Test upgrade (runs database schema migrations if needed)
python -m radio_monitor.cli --test
```

### Database Schema Migrations

Radio Monitor automatically migrates database schema on startup:

- Schema v1 → v6: Automatic (adds playlists, activity_log, notifications tables)
- No manual SQL commands needed
- Migration logs saved to `radio_monitor.log`

**Check schema version:**

```bash
sqlite3 radio_songs.db "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1;"
```

---

## Installation Verification

After installation, verify all components:

```bash
# 1. Check Python version (3.8+)
python --version

# 2. Check dependencies installed
pip list | grep -E "Flask|APScheduler|requests|musicbrainzngs|plexapi"

# 3. Run smoke test
python -m radio_monitor.cli --test

# 4. Start GUI
python -m radio_monitor.cli --gui
# Open browser to http://127.0.0.1:5000

# 5. Verify pages load
# - Dashboard: http://127.0.0.1:5000/
# - Charts: http://127.0.0.1:5000/charts
# - Settings: http://127.0.0.1:5000/settings

# 6. Test scrapes
python -m radio_monitor.cli --scrape-once
# Check GUI for new songs

# 7. Test Lidarr import
python -m radio_monitor.cli --import-lidarr
# Check Lidarr for new artists

# 8. Test Plex playlists
python -m radio_monitor.cli --create-playlists
# Check Plex for new playlists
```

---

## Next Steps

After successful installation:

1. **[User Guide](docs/USER_GUIDE.md)** - Learn all features
2. **[API Reference](API.md)** - Integrate with other tools
3. **[Troubleshooting](TROUBLESHOOTING.md)** - Resolve common issues
4. **[Architecture Documentation](ARCHITECTURE.md)** - Understand codebase

---

## Getting Help

**Documentation:**
- [README.md](README.md) - Project overview
- [docs/](docs/) - Complete documentation index

**Community:**
- GitHub Issues: [github.com/yourusername/radio-monitor/issues](https://github.com/yourusername/radio-monitor/issues)
- Discussions: [github.com/yourusername/radio-monitor/discussions](https://github.com/yourusername/radio-monitor/discussions)

**Logs for Troubleshooting:**

```bash
# View logs
tail -f radio_monitor.log

# Search for errors
grep ERROR radio_monitor.log

# Search for specific feature
grep "LIDARR IMPORT" radio_monitor.log
grep "PLAYLIST" radio_monitor.log
```

---

**Installation Complete!** 🎉

Proceed to [User Guide](docs/USER_GUIDE.md) to learn how to use Radio Monitor.
