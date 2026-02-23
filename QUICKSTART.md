# Quick Start Guide (5 minutes)

Get Radio Monitor 1.1.3 running in 5 minutes.

---

## Step 1: Install (1 minute)

```bash
pip install -r requirements.txt
```

**Need help?** See [INSTALL.md](INSTALL.md)

---

## Step 2: Setup Wizard (2 minutes)

**Start the GUI:**
```bash
python -m radio_monitor.cli --gui
```

**Open:** http://127.0.0.1:5000

Follow the 5-step wizard:

### 1. Welcome
Click "Next"

### 2. Lidarr (Optional)
- URL: `http://localhost:8686`
- API Key: Lidarr → Settings → General → API Key
- Click "Test Connection"
- Click "Next"

**Skip if you don't use Lidarr**

### 3. Plex (Optional)
- URL: `http://localhost:32400`
- Token: Get from https://plex.tv/api/v2/user
- Library Name: `Music` (or your library name)
- Click "Test Connection"
- Click "Next"

**Skip if you don't use Plex**

### 4. Monitor Settings
- Scrape Interval: `10` (minutes)
- Stations: All 8 Chicago stations pre-selected
- Click "Next"

### 5. Summary
- Review settings
- Click "Save & Start Monitoring"

---

## Step 3: First Scrape (30 seconds)

After setup:
1. Click **"Start Monitoring"** (if not running)
2. Wait for first scrape (10 minutes with default interval)
3. Or click **"Scrape Now"** for immediate results

**Status:** Monitor page shows progress

---

## Step 4: Import to Lidarr (1 minute)

1. Go to **"Lidarr"** tab
2. Browse artists (filtered by 5+ plays)
3. Select artists:
   - **"Select All"** for bulk import
   - Or click individual checkboxes
4. Click **"Import Selected"**
5. Watch results:
   - ✓ Imported
   - ⊘ Already exists
   - ✗ Failed

---

## Step 5: Create Plex Playlist (30 seconds)

1. Go to **"Plex"** tab
2. Configure playlist:
   - **Playlist Name:** "Radio Hits"
   - **Mode:** "merge" (updates existing playlist)
   - **Stations:** Select stations to include
   - **Days:** Last 7 days
   - **Limit:** Top 50 songs
3. Click **"Preview"** to see songs
4. Click **"Create Playlist"**
5. Results:
   - Added: Songs found in Plex
   - Not Found: Songs missing from your library

---

## What's Next?

### Monitor Continuously
- Monitoring runs automatically (every 6 minutes)
- Dashboard shows live play feed
- Charts visualize trends over time

### Import More Artists
- Go to Lidarr tab regularly
- New artists appear as they're discovered on radio

### Update Playlists
- Run Plex playlist creation anytime
- Merge mode updates existing playlists
- Create mode makes new snapshots

### Set Up Auto Playlists
- Go to Plex tab → Auto Playlists section
- Click "Add Auto Playlist"
- Configure schedule (default: every 6 hours)
- Select stations, filters, and song limit
- Playlist updates automatically forever
- Use "Update Now" to test immediately

### Settings
- Change scrape interval (Monitor page)
- Enable/disable stations (Settings → Stations)
- Configure backups (Settings → Database)

---

## Troubleshooting

**"Can't connect to GUI"**
→ Windows: Use `http://127.0.0.1:5000` (not `localhost`)
→ Linux: Use `http://localhost:5000`

**"Lidarr/Plex connection failed"**
→ Check URL and API key/token
→ Click "Test Connection" button

**"No artists showing"**
→ Run a scrape first (Monitor → Scrape Now)
→ Wait for songs to be discovered

**"Station disabled"**
→ Re-enable in Settings → Stations
→ Check station website for issues

**More help:** [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

---

## Tips

- **Start with fewer stations** - Enable 2-3 to test
- **Lower interval for testing** - Set to 3-5 minutes
- **Check Dashboard** - Verify scrapes are working
- **Use Preview** - See songs before creating playlists
- **Backup before changes** - Settings → Database → Create Backup

---

**Done!** You're now monitoring radio stations. 🎵
