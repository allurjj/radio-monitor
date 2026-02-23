# Manual Playlist Builder - User Guide

**Version:** 1.1.7
**Last Updated:** 2026-02-23
**Feature Status:** ✅ Stable

---

## Table of Contents

1. [Feature Overview](#feature-overview)
2. [Getting Started](#getting-started)
3. [Creating a Playlist](#creating-a-playlist)
4. [Editing Playlists](#editing-playlists)
5. [Deleting Playlists](#deleting-playlists)
6. [View Modes](#view-modes)
7. [Filtering and Search](#filtering-and-search)
8. [Selection Management](#selection-management)
9. [Plex Integration](#plex-integration)
10. [Troubleshooting](#troubleshooting)
11. [FAQ](#faq)

---

## Feature Overview

The Manual Playlist Builder allows you to create custom playlists by manually selecting songs from your radio monitoring database. Unlike the automated playlist system that uses algorithms and filters, the Manual Playlist Builder gives you complete control over which songs appear in your playlists.

### Key Features

- **Browse Entire Catalog**: Access all songs discovered by the radio monitor
- **Powerful Filters**: Filter by station, date range, play counts, and search
- **Two View Modes**: View songs grouped by artist or as a flat list
- **Multi-Select**: Select multiple songs across different pages and filters
- **Persistent Selections**: Your selections are saved even if you navigate away
- **Plex Integration**: One-click playlist creation in Plex
- **Full CRUD Operations**: Create, read, update, and delete playlists

### Use Cases

- **Theme Playlists**: Create playlists for specific moods, events, or genres
- **Favorites Collection**: Save your most-loved discoveries
- **Curated Lists**: Build hand-picked song collections
- **Backup Selections**: Save songs before database cleanup
- **Testing Collections**: Create test playlists for Plex matching

---

## Getting Started

### Prerequisites

1. **Radio Monitor Running**: Ensure Radio Monitor is running and has discovered songs
2. **Plex Configured** (optional): For creating playlists in Plex, configure your Plex server in Settings
3. **Database Access**: The feature requires the database to be initialized

### Access the Playlist Builder

1. Navigate to **Playlist Builder** in the sidebar
2. The page loads with all available songs in your database
3. Use filters to narrow down your selection
4. Click songs to select them for your playlist

### Page Layout

```
┌─────────────────────────────────────────────────────────────┐
│  [🏠 Home] [Playlist Builder]              [Search: ______] │
├─────────────────────────────────────────────────────────────┤
│  Filters:                                                   │
│  [Stations ▼] [From Date] [To Date] [Min Plays] [Apply]    │
├─────────────────────────────────────────────────────────────┤
│  View: [By Artist] [By Song]  Selected: 0 songs  [Clear]    │
├─────────────────────────────────────────────────────────────┤
│  ┌─ Song List ────────────────────────────────────────────┐ │
│  │ ☐ Song Title - Artist (Plays: 5)  [Add]               │ │
│  │ ☐ Song Title - Artist (Plays: 3)  [Add]               │ │
│  │ ...                                                  │ │
│  └───────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│  My Playlists                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Playlist Name              Songs  Actions            │   │
│  │ My Favorites               12     [Edit] [Delete]    │   │
│  │ Road Trip Mix              25     [Edit] [Delete]    │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Creating a Playlist

### Step-by-Step Guide

1. **Browse Songs**
   - Use filters to find songs you want to include
   - Switch between view modes (By Artist / By Song) as needed
   - Use search to find specific songs or artists

2. **Select Songs**
   - Click the checkbox next to each song to select it
   - Selected songs are highlighted and saved to your session
   - You can navigate between pages - selections persist

3. **Create Playlist**
   - Click the **"Create Playlist"** button (appears when you have selections)
   - Enter a name for your playlist
   - Optionally select a Plex server (if configured)
   - Click **"Save"**

4. **Verify**
   - Your playlist appears in the "My Playlists" section
   - If Plex is configured, the playlist is created in Plex
   - You can edit or delete the playlist at any time

### Tips for Better Playlists

- **Use Filters**: Narrow down by station to find songs from specific radio stations
- **Date Range**: Select songs from a specific time period
- **Min Plays**: Filter out songs that haven't been played much
- **By Artist View**: Great for selecting multiple songs from the same artist
- **By Song View**: Better for browsing songs alphabetically

---

## Editing Playlists

### How to Edit

1. **Open Playlist**
   - Find the playlist in "My Playlists" section
   - Click the **"Edit"** button
   - The edit modal opens showing all songs in the playlist

2. **Add Songs**
   - Browse the song catalog (same filters as creating)
   - Select additional songs
   - Click **"Add to Playlist"**

3. **Remove Songs**
   - In the edit modal, click the **"Remove"** button next to any song
   - Click **"Save Changes"** to confirm

4. **Update Plex** (if configured)
   - Changes are automatically synced to Plex
   - The playlist is updated with the new song list

### Editing Scenarios

- **Add More Songs**: Use the catalog browser to select and add new songs
- **Remove Songs**: Use the edit modal to remove individual songs
- **Complete Overhaul**: Remove all songs and start fresh
- **Fine-tuning**: Add a few songs or remove ones you don't want

---

## Deleting Playlists

### How to Delete

1. **Find Playlist**
   - Locate the playlist in "My Playlists" section

2. **Click Delete**
   - Click the **"Delete"** button
   - Confirm the deletion in the modal

3. **What Happens**
   - Playlist is removed from the database
   - Playlist is removed from Plex (if configured)
   - **This action cannot be undone**

### Safety Tips

- **Double-check**: Review the playlist contents before deleting
- **Plex Sync**: Deleting also removes from Plex
- **No Undo**: Make sure you really want to delete

---

## View Modes

### By Artist (Grouped View)

**Best for**: Selecting multiple songs from the same artist

**Layout**:
- Songs grouped by artist name
- Artist sections expand/collapse
- Shows song count per artist
- Easier to see all songs by an artist at once

**Example**:
```
▼ The Weeknd (3 songs)
  ☐ Blinding Lights (Plays: 15)
  ☐ Starboy (Plays: 8)
  ☐ Save Your Tears (Plays: 12)

▼ Taylor Swift (2 songs)
  ☐ Anti-Hero (Plays: 20)
  ☐ Shake It Off (Plays: 18)
```

### By Song (Flat View)

**Best for**: Browsing all songs alphabetically

**Layout**:
- Flat list of all songs
- Sorted alphabetically by song title
- Shows artist name and play count
- Pagination for large datasets

**Example**:
```
☐ Blinding Lights - The Weeknd (Plays: 15)
☐ Bohemian Rhapsody - Queen (Plays: 25)
☐ Don't Stop Believin' - Journey (Plays: 10)
```

### Switching Views

- Click the **"By Artist"** or **"By Song"** button
- Your selections are preserved when switching views
- Current view is highlighted

---

## Filtering and Search

### Station Filter

**What it does**: Show only songs from selected radio stations

**How to use**:
1. Click the **"Stations"** dropdown
2. Select one or more stations
3. Click **"Apply Filters"**

**Example**: Select "B96" and "US99" to see songs from only those stations

### Date Range Filter

**What it does**: Show only songs first seen within a date range

**How to use**:
1. Select **"From Date"** (optional)
2. Select **"To Date"** (optional)
3. Click **"Apply Filters"**

**Example**: Select songs from January 2026 only

### Minimum Plays Filter

**What it does**: Show only songs with at least X plays

**How to use**:
1. Enter a number in **"Min Plays"**
2. Click **"Apply Filters"**

**Example**: Enter "5" to see songs played 5+ times

### Search

**What it does**: Find songs by title or artist name

**How to use**:
1. Type in the **"Search"** box
2. Results update as you type
3. Clears when you click the "X"

**Example**: Type "Blinding" to find "Blinding Lights"

### Combining Filters

**You can combine multiple filters**:
- Station + Date Range + Min Plays + Search
- All filters work together
- Click **"Clear Filters"** to reset everything

**Example**:
```
Show me songs from B96 station,
from January 2026,
with at least 5 plays,
that have "Love" in the title
```

---

## Selection Management

### How Selections Work

- **Persistent**: Selected songs stay selected when you change pages or filters
- **Session-based**: Selections are saved to the database (playlist_builder_state table)
- **Cross-session**: If you close and reopen the browser, selections are restored
- **Multi-page**: Select songs on page 1, go to page 2, select more - all are saved

### Clearing Selections

**Two ways to clear**:

1. **Soft Clear**: Click **"Clear Selections"** in the song list
   - Clears current selections
   - You can start selecting new songs

2. **Hard Reset**: Click **"Reset All"** in the page header
   - Clears selections AND resets all filters
   - Returns you to the default view

### Selection Count

- The page shows **"Selected: X songs"**
- Updates in real-time as you select/deselect
- Helps you track how many songs you've chosen

### Selecting All

- **By Artist View**: Click the artist checkbox to select all songs by that artist
- **By Song View**: No "Select All" button (to prevent accidental bulk selection)

---

## Plex Integration

### How It Works

When you create or edit a playlist:

1. **Playlist is saved** to the Radio Monitor database
2. **If Plex is configured**, the playlist is also created in Plex
3. **Songs are matched** using the same fuzzy matching as automated playlists
4. **Updates are synced** when you edit playlists

### Configuring Plex

1. Go to **Settings** → **Plex**
2. Enter your Plex server details:
   - URL (e.g., `http://localhost:32400`)
   - Token (from Plex settings)
3. Click **"Test Connection"**
4. Click **"Save"**

### What Gets Created in Plex

- **Playlist Name**: Same name you entered
- **Playlist Type**: Audio
- **Songs**: Matched using fuzzy matching (artist + title)
- **Unmatched Songs**: Logged in the Plex Failures page

### Troubleshooting Plex Issues

**Playlist not created in Plex?**
- Check Plex settings are configured
- Verify connection test passes
- Check Plex Failures page for matching errors

**Songs missing from Plex playlist?**
- Some songs may not match in Plex
- Check Plex Failures page for details
- Verify songs exist in your Plex library

---

## Troubleshooting

### Common Issues

#### "No songs found" message

**Cause**: Your filters are too restrictive or no songs match

**Solutions**:
- Click **"Clear Filters"** to reset
- Check your date range (is it too narrow?)
- Lower the "Min Plays" value
- Try the search without filters

#### Selections disappeared

**Cause**: Database connection issue or session timeout

**Solutions**:
- Refresh the page (selections should restore)
- Check browser console for errors
- Verify database is accessible

#### Playlist creation fails

**Cause**: Invalid playlist name or database error

**Solutions**:
- Use alphanumeric characters in playlist name
- Avoid special characters
- Check radio_monitor.log for errors
- Verify database is writable

#### Plex playlist not created

**Cause**: Plex not configured or connection failed

**Solutions**:
- Check Plex settings
- Test connection
- Verify songs exist in Plex library
- Check Plex Failures page

#### Songs not matching in Plex

**Cause**: Artist or title differences between databases

**Solutions**:
- Check Plex Failures page for specific errors
- Verify song titles match exactly (case-insensitive)
- Try using the Plex Failures "Retry" button
- Consider editing song titles in Plex

### Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| "Database error" | Database connection lost | Restart Radio Monitor |
| "Invalid playlist name" | Name contains invalid characters | Use letters, numbers, spaces only |
| "No songs selected" | Tried to create empty playlist | Select at least one song |
| "Plex connection failed" | Plex server unreachable | Check URL and token |
| "Song not found in Plex" | Fuzzy matching failed | Check Plex Failures page |

---

## FAQ

### General Questions

**Q: Can I create playlists without Plex?**
A: Yes! Playlists are saved in the Radio Monitor database. Plex integration is optional.

**Q: Is there a limit to how many songs I can add?**
A: No technical limit, but very large playlists (1000+ songs) may be slow to load.

**Q: Can I share playlists with other users?**
A: Not directly. Playlists are stored in your local database. Export/import is a future enhancement.

**Q: What happens if I delete a song from the database?**
A: It's also removed from any manual playlists that contain it.

**Q: Can I rename a playlist?**
A: Not directly. Delete and recreate with the new name, or this feature may be added in the future.

### Selections and State

**Q: How long are selections saved?**
A: Selections persist until you manually clear them or create a playlist.

**Q: If I close my browser, are selections saved?**
A: Yes! Selections are restored when you return to the page.

**Q: Can I select songs across multiple sessions?**
A: Yes. Select songs today, come back tomorrow, and add more.

### Plex Integration

**Q: Does this create smart playlists in Plex?**
A: No, it creates static playlists. Changes in Radio Monitor require manual updates.

**Q: What if a song doesn't exist in my Plex library?**
A: It's logged in the Plex Failures page. The playlist is created without that song.

**Q: Can I edit Plex playlists created manually?**
A: Yes, but changes in Plex won't sync back to Radio Monitor.

### Performance

**Q: Why is the page slow to load?**
A: Large databases (10,000+ songs) may take time. Use filters to narrow down.

**Q: Can I speed up filtering?**
A: Use more specific filters (station + date) to reduce results.

**Q: Does this feature slow down scraping?**
A: No. The playlist builder is independent of the scraping loop.

---

## Getting Help

### Documentation

- **Main README**: [README.md](../README.md)
- **API Documentation**: [API.md](../API.md)
- **Troubleshooting**: [TROUBLESHOOTING.md](../TROUBLESHOOTING.md)

### Support

- **GitHub Issues**: https://github.com/allurjj/radio-monitor/issues
- **Documentation**: https://github.com/allurjj/radio-monitor

### Feature Requests

Have an idea for improving the Manual Playlist Builder? Please:

1. Check [FUTURE_ENHANCEMENTS.md](../FUTURE_ENHANCEMENTS.md)
2. Create a GitHub issue with the "enhancement" label
3. Describe your use case and suggested implementation

---

**Version:** 1.1.7
**Database Schema:** v12
**Last Updated:** 2026-02-23
