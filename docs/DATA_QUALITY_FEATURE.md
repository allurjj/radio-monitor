# Data Quality Feature

**Version:** 1.4.10+
**Last Updated:** 2026-06-08

---

## Overview

The Data Quality feature helps you monitor and maintain the health of your Radio Monitor song database. It provides tools for:

1. **Health Checks** - Comprehensive analysis of data quality issues
2. **Artist Name Corrections** - Fix known artist name issues automatically
3. **Recording Validation** - Verify songs against MusicBrainz recording database
4. **Issue Tracking** - Visual indicators on Songs and Artists pages

---

## Accessing Data Quality

### Web Interface
Navigate to **Data Quality** in the sidebar, or visit:
```
http://localhost:5000/data-quality
```

### CLI Commands
```bash
# Run health check
python -m radio_monitor.cli --health-check

# Fix artist names (with backup)
python -m radio_monitor.cli --fix-artist-names --backup

# Validate library
python -m radio_monitor.cli --validate-library --limit 50
```

---

## Health Score

The Health Score is a percentage (0-100) that represents the overall quality of your database:

| Score Range | Color | Description |
|-------------|-------|-------------|
| 90-100% | Green | Excellent - No critical issues |
| 75-89% | Blue | Good - Minor issues only |
| 60-74% | Yellow | Fair - Some issues need attention |
| 0-59% | Red | Poor - Critical issues present |

### Score Calculation
- Critical issues: -10 points per issue
- Warning issues: -3 points per issue
- Info issues: -1 point per issue

---

## Issue Types

### Critical Issues

#### 1. Known Artist Name Issues
Songs with artist names that are known to be incorrect (e.g., "P!NK" → "P!NK (missing letter)").

**Impact:** High - Can cause duplicate artists and matching issues

**Fix:** Click "Fix Artist Names" button to apply corrections automatically

#### 2. Database Corruption
Missing indexes, incorrect schema version, or other structural issues.

**Impact:** High - Can cause application errors

**Fix:** Requires database repair or migration

### Warning Issues

#### 1. PENDING MBIDs
Songs where the artist MBID couldn't be found in MusicBrainz.

**Impact:** Medium - Artist can't be imported to Lidarr

**Fix:** Manually set MBID via Artists page or wait for MusicBrainz update

#### 2. Potential Duplicates
Songs that appear to be duplicates based on similar titles.

**Impact:** Medium - Inflated play counts

**Fix:** Manual review and merging

### Info Issues

#### 1. Messy Song Titles
Songs with parentheticals, features, or extra text (e.g., "Song (feat. Artist)").

**Impact:** Low - Cosmetic only

**Fix:** None needed - informational only

---

## Recording Validation

### What is Recording Validation?

Recording validation verifies that a song (artist + title) exists in the MusicBrainz recording database. This is different from artist-level verification.

**Validation Status:**
- **Valid** - Recording found in MusicBrainz
- **Invalid** - Recording not found in MusicBrainz
- **Unvalidated** - Not yet checked (default)

### How to Validate

#### Web Interface
1. Navigate to **Data Quality** page
2. Click **"Validate 50 Songs"** button
3. System checks 50 unvalidated songs against MusicBrainz
4. Progress updates in real-time

#### CLI
```bash
# Validate 50 songs
python -m radio_monitor.cli --validate-library --limit 50

# Validate 100 songs by top play count
python -m radio_monitor.cli --validate-library --limit 100 --priority top-plays
```

### Viewing Validation Status

#### Songs Page
Each song shows its recording validation status in the **Recording** column:

| Badge | Status | Description |
|-------|--------|-------------|
| <span class="badge bg-success">Validated</span> | Valid | Recording verified against MusicBrainz |
| <span class="badge bg-danger">Not Found</span> | Invalid | Recording not found in MusicBrainz |
| <span class="badge bg-secondary">Unvalidated</span> | Unvalidated | Not yet checked |

#### Artists Page
Each artist shows the percentage of songs validated in the **Recording** column:

| Badge | Description |
|-------|-------------|
| 🟢 80%+ | Most songs validated |
| 🟡 50-79% | Partially validated |
| 🔴 1-49% | Few songs validated |
| ⚪ 0% | No songs validated |

---

## Artist Name Corrections

### Automatic Corrections

The system includes a list of known artist name corrections. When you click **"Fix Artist Names"**, it:

1. Creates a backup of your database
2. Merges duplicate artists (if correct artist already exists)
3. Updates all songs to use correct artist name
4. Preserves all play counts and history
5. Cleans up blocklist entries

### What Gets Fixed

Common corrections include:
- Typos: "Pinnk" → "P!NK"
- Encoding issues: "Thatâ's So True" → "That's So True"
- Capitalization: "THE WEEKND" → "The Weeknd"

### Safety Features

- **Automatic Backup** - Database backed up before any changes
- **Merge Play Counts** - Preserves all play data when merging duplicates
- **Foreign Key Safety** - Handles all FK constraints automatically
- **Rollback** - Can restore from backup if needed

---

## Technical Details

### Database Schema (v22)

Recording validation adds three columns to the `songs` table:

```sql
validation_status TEXT DEFAULT 'unvalidated'  -- 'valid', 'invalid', 'pending'
validated_at TIMESTAMP                        -- When validation occurred
validation_method TEXT                        -- How validation was performed
```

### API Endpoints

#### Health Check
```http
GET /api/data-quality/health
```

#### Fix Artist Names
```http
POST /api/data-quality/fix-artist-names
Content-Type: application/json

{
  "backup": true
}
```

#### Validate Batch
```http
POST /api/data-quality/validate-batch
Content-Type: application/json

{
  "count": 50
}
```

---

## Troubleshooting

### Validated Count Not Updating

**Problem:** Clicking "Validate 50 Songs" doesn't increase the validated count.

**Cause:** Database schema v22 migration hasn't run (adds validation columns).

**Solution:** The system now auto-creates the columns if missing. Update to v1.4.10+.

### FOREIGN KEY Constraint Errors

**Problem:** "Fix Artist Names" fails with FOREIGN KEY constraint error.

**Cause:** Song play records or blocklist entries reference the artist being deleted.

**Solution:** Fixed in v1.4.9+. Update to the latest version.

### Validation Takes Too Long

**Problem:** Batch validation is slow.

**Cause:** MusicBrainz API rate limits (0.2s delay between requests).

**Solution:** This is expected behavior. 50 songs takes approximately 10 seconds.

---

## Best Practices

1. **Run Health Checks Regularly** - Check data quality weekly
2. **Validate High-Play Songs First** - Prioritize popular songs
3. **Review Critical Issues Promptly** - Address artist name issues quickly
4. **Keep Backups** - The system auto-backups before fixes
5. **Monitor Validation Progress** - Check validation coverage percentage

---

## Future Enhancements

Planned improvements for future versions:

- [ ] Automatic validation during idle time
- [ ] Bulk invalid song review interface
- [ ] Export validation report
- [ ] Integration with Plex to mark validated songs
- [ ] Validation retry for previously invalid songs
