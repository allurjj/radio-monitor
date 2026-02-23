# Troubleshooting Guide

Quick fixes for common Radio Monitor 1.0.0 issues.

---

## Quick Start

**Run diagnostics:**
```bash
python -m radio_monitor.cli --test
```

Checks database, MusicBrainz, Lidarr, and Plex connectivity.

---

## GUI Issues

### Can't Access GUI

**Problem:** Browser won't connect to http://localhost:5000

**Solutions:**
- **Windows:** Use `http://127.0.0.1:5000` instead
- **Linux:** Use `http://localhost:5000`
- **Check if running:** Terminal should show "Running on http://..."
- **Kill old process:** `taskkill /F /IM python.exe` (Windows) or `killall python` (Linux)
- **Try different port:** Settings → GUI → Port (change from 5000)

### GUI Shows "Checking..." Forever

**Problem:** Status items stuck on "Checking..."

**Solutions:**
- Refresh page (F5)
- Check Flask terminal for errors
- Restart Flask app
- Clear browser cache

### Settings Page Blank / Dropdowns Empty

**Problem:** Settings page doesn't load or dropdowns empty

**Solutions:**
- Click "Refresh" button next to dropdown
- Check Flask terminal for API errors
- Verify Lidarr/Plex are running
- Restart Flask app (clears template cache)

### Backup Button Shows Error

**Problem:** Clicking "Create Backup" shows "'NoneType' object has no attribute 'get'" error

**Cause:** Settings not loaded properly in backup routes

**Status:** ✅ **FIXED in v3.0.0**

**If you see this error:**
1. Restart the Flask app
2. Try the backup button again
3. If still failing, run smoke test: `python -m radio_monitor.cli --test`
4. Check that `radio_monitor_settings.json` exists and is valid JSON

**Workaround (manual backup):**
```bash
# Manual backup from command line
python -m radio_monitor.cli --backup-db
```

---

## Lidarr Issues

### "Lidarr connection failed"

**Problem:** Can't connect to Lidarr

**Solutions:**
1. **Check Lidarr is running**
   - Open http://localhost:8686
   - Should show Lidarr web interface

2. **Verify URL**
   - Correct: `http://localhost:8686`
   - Wrong: `localhost:8686` (missing http://)

3. **Check API key**
   - Lidarr → Settings → General → API Key
   - Copy and paste (no extra spaces)

4. **Test manually**
   ```bash
   curl -H "X-Api-Key: YOUR_KEY" http://localhost:8686/api/v1/system/status
   ```

### "No artists found for import"

**Problem:** Lidarr page shows no artists

**Solutions:**
1. **Run monitoring first**
   - Monitor → Start Monitoring
   - Wait 10-15 minutes
   - Or click "Scrape Now"

2. **Lower minimum plays**
   - Change filter from "5+" to "1+"

3. **Check database**
   ```bash
   ls -lh radio_songs.db
   ```

### "Artist already exists" for all artists

**Problem:** All imports show "Already exists"

**Solution:**
- **This is normal** - Radio Monitor checks before adding
- No duplicates created
- Only new artists added

---

## Plex Issues

### "Plex connection failed"

**Problem:** Can't connect to Plex

**Solutions:**
1. **Check Plex is running**
   - Open http://localhost:32400/web
   - Should show Plex web interface

2. **Verify URL**
   - Correct: `http://localhost:32400`
   - Wrong: `localhost:32400` (missing http://)

3. **Get token**
   - Visit https://plex.tv/api/v2/user
   - Log in
   - Copy the long token string

4. **Test manually**
   ```bash
   curl -H "X-Plex-Token: YOUR_TOKEN" http://localhost:32400/
   ```

### "Music library not found"

**Problem:** Can't find music library

**Solutions:**
1. **Get library name**
   - Plex → Libraries
   - Find your music library name
   - Common names: "Music", "Audio", "Music Library"

2. **Refresh dropdown**
   - Settings → Plex → Click "Refresh" button
   - Select library from dropdown

### "undefined - undefined" in not found list

**Problem:** Songs not found show as "undefined"

**Solution:**
- Restart Flask app
- Fixed in latest version

---

## Monitoring Issues

### "No songs scraped"

**Problem:** Scrapes complete but find 0 songs

**Solutions:**
1. **Check stations are enabled**
   - Settings → Stations
   - Make sure stations have checkmarks

2. **Check station status**
   - Monitor → Stations
   - Look for red "Disabled" badges
   - Re-enable if needed

3. **Test station manually**
   - Open station website in browser
   - Verify "Now Playing" section exists

4. **Check logs**
   - Flask terminal shows scrape errors
   - Look for "Failed to scrape" messages

### "Station disabled"

**Problem:** Station auto-disabled after failures

**Solutions:**
1. **Check station website**
   - Station might be down
   - HTML structure might have changed

2. **Re-enable station**
   - Settings → Stations
   - Click station
   - Set "Enabled" to ON
   - Save

3. **Monitor health**
   - Station will disable again if failures continue
   - ~24 hours of failures = auto-disable

### Dashboard shows 0 plays today

**Problem:** "Plays Today" shows 0 when there should be plays

**Solutions:**
1. **Check timezone**
   - Fixed in latest version (uses local time)

2. **Run scrape first**
   - Monitor → Scrape Now
   - Wait for scrape to complete
   - Refresh dashboard

3. **Check database**
   ```bash
   sqlite3 radio_songs.db "SELECT date, SUM(play_count) FROM song_plays_daily GROUP BY date ORDER BY date DESC LIMIT 3"
   ```

---

## Database Issues

### "Database locked"

**Problem:** Can't access database

**Solutions:**
1. **Stop Flask**
   - Kill Flask process
   - Only one app can access SQLite at a time

2. **Check for other processes**
   ```bash
   # Linux
   lsof | grep radio_songs.db

   # Windows
   Task Manager → Find python.exe
   ```

3. **Create backup**
   ```bash
   python -m radio_monitor.cli --backup-db
   ```

### Database corrupted

**Problem:** Database errors, crashes

**Solutions:**
1. **Restore from backup**
   ```bash
   python -m radio_monitor.cli --list-backups
   python -m radio_monitor.cli --restore-db backups/radio_songs_YYYY-MM-DD_HHMMSS.db
   ```

2. **Start fresh**
   - Rename `radio_songs.db` to `radio_songs.db.old`
   - Run setup wizard again
   - Import from old DB if needed

### Export Database for Sharing

**Problem:** Want to share your discovered artists/songs with a friend

**Solution:** Use the Export Database feature on Settings page

**What gets exported:**
- ✅ All discovery data (artists, songs, play counts, stations)
- ✅ All discovery metadata (first_seen, last_seen dates)

**What gets removed (user-specific):**
- ❌ Playlists (your custom playlists)
- ❌ Activity logs (your activity history)
- ❌ Plex failures (your Plex matching errors)
- ❌ Notifications (your notification configs)
- ❌ Notification history (your notification history)
- ❌ Lidarr import status (reset - friends need to do their own import)

**How to export:**
1. Go to Settings page
2. Scroll to "Export Database for Sharing" section
3. Enter a filename (or use default: `radio_monitor_shared_YYYY-MM-DD.db`)
4. Click "Export Database"
5. File is saved to your backup directory (default: `backups/`)
6. Share the file with friends via cloud storage, email, etc.

**Note:** Export shows full path when complete (e.g., "Database exported to backups/radio_monitor_shared_2026-02-10.db")

---

## Performance Issues

### Scraping too slow

**Problem:** Scrapes take 5+ minutes

**Solutions:**
1. **Reduce stations**
   - Disable stations you don't need
   - Settings → Stations

2. **Check station health**
   - Slow stations drag down performance
   - Disable problematic stations

3. **Increase interval**
   - Settings → Monitor → Scrape Interval
   - Set to 15-30 minutes

### Plex playlist creation slow

**Problem:** Creating playlist takes 2+ minutes

**Solutions:**
1. **Reduce song limit**
   - Lower from 50 to 25 or 10
   - Fewer songs = faster matching

2. **Reduce days**
   - Use 7 days instead of 30
   - Fewer plays to process

3. **Fewer stations**
   - Select fewer stations
   - Reduces total songs

---

## Auto Playlists Issues

### "Auto playlist created 0 songs"

**Problem:** Auto playlist runs but finds no songs

**Solutions:**
1. **Check database has data**
   ```bash
   python -m radio_monitor.cli --stats
   ```
   Should show total_songs > 0

2. **Verify filters aren't too restrictive**
   - Try with: No days filter, all stations, min_plays = 1
   - Click "Update Now" to test immediately

3. **Check station selection**
   - At least one station must be selected
   - Stations must have plays in database

4. **Check monitoring is running**
   - Auto playlists only update when monitoring is active
   - Monitor → Start Monitoring

### "Auto playlist not updating"

**Problem:** Next update time passes but playlist doesn't update

**Solutions:**
1. **Check monitoring is running**
   - Auto playlists skip updates if monitoring stopped
   - Monitor → Check "Monitoring Status"

2. **Verify playlist is enabled**
   - Look for green "Active" badge on playlist card
   - If "Paused", click play button to resume

3. **Check Flask is running**
   - Auto playlists require Flask app to be running
   - Restart Flask if it crashed

4. **Check for errors**
   - View Flask terminal for error messages
   - Look for "Error executing auto playlist"

### "Found 0/X songs in Plex"

**Problem:** Database has songs but Plex can't find them

**Solutions:**
1. **This is normal** - 40-60% match rate is typical
   - Fuzzy matching isn't perfect
   - Metadata quality varies
   - Some songs may not be in your library

2. **Check if songs are actually missing**
   - Search for a "missing" song in Plex manually
   - Might be different spelling/version

3. **Improve matching later**
   - Ensure Plex music library is complete
   - Clean up song metadata in Plex
   - Accept current match rate

### "Auto playlist disabled automatically"

**Problem:** Playlist shows as "Paused" with error badge

**Solutions:**
1. **Check consecutive failures**
   - Auto playlists disable after 10 consecutive failures
   - Prevents endless error loops

2. **Fix the root cause**
   - Check Plex connection (Settings → Plex → Test)
   - Verify filters aren't impossible
   - Check Flask terminal for specific error

3. **Re-enable after fixing**
   - Click play button on playlist card
   - Monitor next update

### "Update interval not working"

**Problem:** Playlist updates at wrong time

**Solutions:**
1. **Check interval is in minutes**
   - 360 = 6 hours (not 360 minutes!)
   - 60 = 1 hour
   - 1440 = 24 hours

2. **Countdown timer counts down**
   - Updates occur when countdown reaches "Due now"
   - Timer updates every 10 seconds

3. **Test with "Update Now"**
   - Don't wait for scheduled update
   - Click ↻ button to trigger immediately

---

## Error Messages

### "Module not found" errors

**Error:** `ModuleNotFoundError: No module named 'xxx'`

**Solution:**
```bash
pip install -r requirements.txt
```

### "Permission denied" errors

**Error:** Can't write to database or log file

**Solutions:**
- Check file permissions
- Run as user with write access
- On Linux: `chmod u+w radio_songs.db`

### "MusicBrainz rate limit exceeded"

**Error:** Too many MBID lookups

**Solutions:**
- Wait 1 hour (rate limit resets)
- Increase rate limit delay
- Settings → MusicBrainz → Rate Limit Delay

---

## MBID & Artist Issues

### PENDING Artists Won't Resolve

**Problem:** Artists showing as "PENDING-xxxxx" and can't import to Lidarr

**Solutions:**

1. **Retry PENDING artists:**
   ```bash
   python -m radio_monitor.cli --retry-pending
   ```

2. **Check MusicBrainz connectivity:**
   ```bash
   python -m radio_monitor.cli --test
   ```

3. **Network errors:** Wait and retry (MusicBrainz API has transient failures)

4. **No match found:** Artist might not exist in MusicBrainz database

### Wrong Artist Imported

**Problem:** Imported "Elliott Smith" instead of "Sam Smith"

**Solutions:**

1. **System automatically uses fuzzy matching** (80% threshold)
   - Prevents most mismatches

2. **If wrong import happens:**
   - Delete from Lidarr manually
   - Delete from database: `DELETE FROM artists WHERE mbid = 'wrong-mbid';`
   - Run scrape again to re-import

3. **Prevention:** System logs borderline matches for review

### Artist Names Showing MBIDs

**Problem:** Database shows MBID instead of artist name

**Solutions:**
- **FIXED in v3:** Corrupted data automatically repaired
- If you see this, run: `python -m radio_monitor.cli --retry-pending`

### Collaboration Artists Not Found

**Problem:** "Dylan Scott" or "Elle King" not found

**Solutions:**

1. **System automatically handles collaborations:**
   - "feat." → Extracts primary artist (left side)
   - "&" → Tries each artist separately

2. **Manual retry:**
   ```bash
   python -m radio_monitor.cli --retry-pending --force
   ```

3. **Verify on MusicBrainz website:**
   - Go to musicbrainz.org
   - Search for artist name
   - Check if they exist

### Checking PENDING Artist Count

**Command:**
```bash
python -c "import sqlite3; conn = sqlite3.connect('radio_songs.db'); cur = conn.cursor(); cur.execute('SELECT COUNT(*) FROM artists WHERE mbid LIKE \"PENDING-%\"'); print(f'PENDING artists: {cur.fetchone()[0]}')"
```

**Expected:** Should be 0 after running --retry-pending

---

## Export CSV Issues

### CSV Export Button Missing

**Problem:** Export CSV button not visible on list pages

**Solutions:**
1. **Check page type** - Export is available on:
   - Songs page (`/songs`)
   - Artists page (`/artists`)
   - Activity page (`/activity`)
   - Logs page (`/logs`)
   - Dashboard (recent plays table)

2. **Refresh page** - Sometimes UI elements don't load
   - Press F5 to refresh
   - Clear browser cache

3. **Check JavaScript errors** - Open browser console (F12)
   - Look for red error messages
   - Report bugs if errors appear

### CSV File Contains Wrong Data

**Problem:** Exported CSV doesn't match filtered results

**Solutions:**
1. **Clear filters first** - Click "Reset Filters" or "Clear" buttons
2. **Re-apply filters** - Set filters again and wait for data to load
3. **Export again** - Click "Export CSV" after filters are applied

**Note:** CSV exports currently filtered/displayed data, not entire database

### CSV File Won't Open in Excel

**Problem:** Excel shows garbled text or wrong encoding

**Solutions:**
1. **Import correctly** - Don't double-click the CSV file
   - Open Excel first
   - Data → From Text/CSV
   - Select file and set UTF-8 encoding

2. **Use Google Sheets** - Better UTF-8 support
   - Upload CSV to Google Drive
   - Open with Sheets

3. **Use text editor** - Notepad++, VSCode, etc.
   - Always open correctly with UTF-8

### CSV Filename Wrong

**Problem:** Filename has wrong date or page name

**Explanation:**
- Filename format: `radio-monitor-{page}-{YYYY-MM-DD}.csv`
- Date is when file was created (not data date)
- Page name is lowercase (songs, artists, activity, logs, dashboard)

**Example:** `radio-monitor-songs-2026-02-12.csv`

This is expected behavior, not a bug.

---

## Advanced Search Issues

### Advanced Filters Not Working

**Problem:** Date range or play count filters return no results

**Solutions:**
1. **Check date format** - Must be YYYY-MM-DD format
   - Correct: `2026-02-12`
   - Wrong: `02/12/2026` or `12-Feb-2026`

2. **Verify filter logic** - Understand what filters do:
   - **Last Seen After** - Songs/artists seen *after* this date
   - **Last Seen Before** - Songs/artists seen *before* this date
   - **First Seen After** - Artists discovered *after* this date
   - **Plays Min/Max** - Play count range (inclusive)

3. **Try broader filters** - Start with:
   - Remove date filters entirely
   - Set plays_min to 0 or 1
   - Use "Last 30 Days" preset if available

4. **Check database has data** - Run smoke test:
   ```bash
   python -m radio_monitor.cli --test
   ```

### Filters Applied But No Change

**Problem:** Set filters but results don't change

**Solutions:**
1. **Click "Apply Filters"** - Some filters need manual apply
   - Not all filters are instant (auto-apply)

2. **Check filter is active** - Look for:
   - Blue highlight on active filter section
   - Filter values displayed in applied section
   - "Reset Filters" button becomes enabled

3. **Clear and re-apply**:
   - Click "Reset Filters"
   - Set filters again
   - Apply or wait for auto-refresh

### Advanced Filters Section Won't Expand

**Problem:** Can't access date range or play count inputs

**Solutions:**
1. **Click toggle button** - Look for:
   - "Advanced Filters" button (Songs page)
   - "More Filters" button (Artists page)
   - Section should expand when clicked

2. **Check JavaScript** - Open browser console (F12)
   - Look for JavaScript errors
   - Refresh page if errors present

3. **Mobile users** - Advanced filters may be collapsed by default
   - Tap toggle button to expand
   - May need to scroll to see all filters

### Search + Advanced Filters Conflict

**Problem:** Using search bar ignores advanced filters (or vice versa)

**Explanation:**
- Search bar and advanced filters work **together**
- Both are applied (AND logic)
- Results must match **all** active filters

**Example:**
- Search: "Taylor Swift"
- Last Seen After: 2026-02-01
- Result: Songs by Taylor Swift seen after Feb 1, 2026

This is expected behavior, not a bug.

---

## Getting Help

Still stuck?

1. **Check logs**
   - Flask terminal output
   - `radio_monitor.log` file

2. **Run diagnostics**
   ```bash
   python -m radio_monitor.cli --test
   ```

3. **Create backup before changes**
   ```bash
   python -m radio_monitor.cli --backup-db
   ```

4. **Report issues**
   - Include error messages
   - Include log output
   - Describe what you were doing

---

**Last updated:** 2026-02-12 (Phase 8: Export CSV & Advanced Search)
