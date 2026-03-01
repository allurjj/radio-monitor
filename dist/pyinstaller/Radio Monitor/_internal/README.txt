RADIO MONITOR v1.1.0 - Windows Edition
=======================================

Thank you for using Radio Monitor!

QUICK START
-----------

1. Double-click "Start Radio Monitor.bat" to launch the application
2. Your browser will open to http://127.0.0.1:5000
3. Follow the setup wizard to configure your settings

WHAT'S NEW
-----------

Version 1.1.0 (February 19, 2026)
- Removed Selenium dependency (reduced EXE size by 20-30 MB)
- WTMX station no longer supported (requires Vue.js rendering)
- All scraping now uses requests + BeautifulSoup (faster, more reliable)
- 7 iHeartRadio stations supported (Chicago area)
- Updated to database schema v11

Version 1.0 (February 19, 2026)
- Initial Windows release
- AI-powered playlist generation (experimental)
- Complete database schema (12 tables)
- All 18 GUI pages working
- Lidarr, Plex, and notification integrations
- NO console window - all logs go to radio_monitor.log file

FEATURES
--------

* Radio Scraping: Monitor 7 Chicago radio stations (iHeartRadio)
* Music Discovery: Identify artists and songs using MusicBrainz
* Lidarr Integration: One-click import of discovered artists
* Plex Integration: Create dynamic playlists (7 modes)
* AI Playlists: Generate themed playlists using AI (experimental)
* Analytics: Track plays, view charts, export to CSV
* Automation: Schedule scraping, importing, and playlist creation
* Notifications: 17 providers (Discord, Slack, Email, etc.)

TROUBLESHOOTING
---------------

Application won't start?
- Check that port 5000 is not in use
- Verify Windows 10/11 (64-bit)
- Check radio_monitor.log file for error messages

Need to see what's happening?
- Open radio_monitor.log with any text editor
- All Flask logs and application output are written here
- Application runs silently (no console window)

Database not saving?
- Look for radio_songs.db in this folder
- If missing, the application will create it on first run

Need help?
- Documentation: https://github.com/allurjj/radio-monitor
- Issues: https://github.com/allurjj/radio-monitor/issues

DATA LOCATION
-------------

All data is stored in this folder:
- radio_songs.db - Database (all artists, songs, play history)
- radio_monitor_settings.json - Your settings
- radio_monitor.log - Application logs (all Flask output here!)
- auto-backups/daily/ - Automatic database backups

SYSTEM REQUIREMENTS
-------------------

- Windows 10 or 11 (64-bit)
- 2GB RAM minimum (4GB recommended)
- 500MB free disk space
- Internet connection

UPGRADING
---------

To upgrade to a new version:
1. Download the new ZIP file
2. Extract to a NEW folder
3. Copy radio_songs.db and radio_monitor_settings.json from old folder
4. Delete old folder

Enjoy discovering new music!

Radio Monitor Project
https://github.com/allurjj/radio-monitor
