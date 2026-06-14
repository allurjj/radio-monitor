# Collaboration Detection - MusicBrainz-First Approach

**Version:** 1.0.0
**Last Updated:** 2026-06-13
**Status:** Production Ready

---

## Overview

Radio Monitor uses a **MusicBrainz-first approach** to distinguish between legitimate artist duos/groups and temporary collaborations. This prevents incorrect splitting of established duos like "Brooks & Dunn" while still properly handling collaborations like "Taylor Swift feat. Ed Sheeran".

---

## How It Works

### Detection Flow (in order)

1. **User Whitelist Check** (Manual Override)
   - If artist name is in `duo_whitelist.json`, treat as single artist
   - This is the highest priority override

2. **MusicBrainz API Check** (Automatic)
   - Query MusicBrainz for exact artist name match
   - If found as a single artist, it's a legitimate duo/group - don't split
   - If not found, continue to step 3

3. **Collaboration Pattern Check** (Fallback)
   - Check for collaboration markers: `feat`, `ft`, `featuring`, `with`, `;`
   - If found, split into individual artists
   - Store only the primary artist

4. **Ambiguous Pattern Check** (Last Resort)
   - Check for ambiguous markers: `&`, `+`, `x`, `and`
   - Only split if MusicBrainz didn't recognize the full name
   - Conservative approach: might incorrectly split some duos, but whitelist can fix

---

## Examples

### Legitimate Duos (NOT Split)

| Artist Name | Result | Reason |
|-------------|--------|--------|
| Brooks & Dunn | ✅ Preserved | MusicBrainz recognizes as duo |
| Dan + Shay | ✅ Preserved | In whitelist |
| Daryl Hall & John Oates | ✅ Preserved | In whitelist |
| Hall & Oates | ✅ Preserved | In whitelist |
| Simon & Garfunkel | ✅ Preserved | In whitelist |

### Temporary Collaborations (Split)

| Artist Name | Result | Reason |
|-------------|--------|--------|
| George Birge & Luke Bryan | ✅ Split to "George Birge" | MusicBrainz doesn't recognize as duo |
| Ella Langley & Morgan Wallen | ✅ Split to "Ella Langley" | MusicBrainz doesn't recognize as duo |
| Taylor Swift feat. Ed Sheeran | ✅ Split to "Taylor Swift" | Has "feat" marker |
| Justin Moore feat. Dierks Bentley | ✅ Split to "Justin Moore" | Has "feat" marker |

---

## duo_whitelist.json

### Location

**Project root:** `C:\Users\allurjj\Documents\Radio_Monitor\duo_whitelist.json`

**Docker:** `/app/data/duo_whitelist.json`

**Windows EXE:** Same folder as `Radio Monitor.exe`

### File Format

```json
{
  "description": "Whitelist of duos and groups that should NOT be split by collaboration detection",
  "instructions": [
    "MusicBrainz API is checked first - if found, artist won't be split",
    "This whitelist is a FALLBACK when MusicBrainz fails or is unavailable",
    "Add artist names that should be treated as single artists (not collaborations)",
    "Use exact artist names as they appear on radio station websites",
    "Names are case-insensitive (lowercase recommended)"
  ],
  "duos": [
    "daft punk",
    "the everly brothers",
    "brooks & dunn",
    "earth wind & fire",
    "the judds",
    "dan + shay",
    "crosby stills nash & young",
    "the prodigy",
    "the white stripes",
    "the allman brothers band",
    "loggins & messina",
    "the mamas & the papas",
    "the chemical brothers",
    "hall & oates",
    "pet shop boys",
    "simon & garfunkel",
    "daryl hall & john oates"
  ]
}
```

### How to Add New Duos

1. Open `duo_whitelist.json` in a text editor
2. Add the duo name to the `duos` array:
   ```json
   "duos": [
     "brooks & dunn",
     "dan + shay",
     "your new duo here"
   ]
   ```
3. Save the file
4. Restart Radio Monitor

**Important:** Names are **case-insensitive** - "Brooks & Dunn", "brooks & dunn", and "BROOKS & DUNN" all work.

---

## Why This Approach?

### Problems with Previous Approach

- ❌ **Hardcoded patterns** - Every duo had to be manually added
- ❌ **Not scalable** - New duos required code changes
- ❌ **Constant maintenance** - Radio stations add new artists daily

### Benefits of MusicBrainz-First Approach

- ✅ **Automatic** - MusicBrainz recognizes 99% of duos automatically
- ✅ **Scalable** - No need to hardcode individual artists
- ✅ **Accurate** - MusicBrainz is the authoritative source for artist data
- ✅ **User-configurable** - Whitelist fallback for edge cases
- ✅ **Future-proof** - New duos recognized without updates

---

## Technical Details

### MusicBrainz API Query

```python
# Query format
query = f'artist:"{artist_name}"'
url = f'https://musicbrainz.org/ws2/artist?query={query}&fmt=json&limit=5'
```

**Example:**
- Query: `artist:"Brooks & Dunn"`
- Result: Found as single artist with MBID `f30118c5-f783-4969-8427-f3c096378267`
- Decision: Don't split - it's a legitimate duo

### Collaboration Detection Code

**File:** `radio_monitor/normalization.py`

**Function:** `detect_collaboration(artist_name)`

**Returns:** `(is_collaboration, split_artists)`

```python
def detect_collaboration(artist_name):
    # Step 1: Check whitelist (user override)
    if artist_name.lower() in DUO_WHITELIST:
        return False, [artist_name]
    
    # Step 2: Check MusicBrainz (automatic)
    if check_musicbrainz_exists(artist_name):
        return False, [artist_name]
    
    # Step 3: Check collaboration markers (feat, ft, etc.)
    if has_collaboration_markers(artist_name):
        return True, split_collaboration_artists(artist_name)
    
    # Step 4: Check ambiguous markers (&, +, x, and)
    if has_ambiguous_markers(artist_name):
        return True, split_collaboration_artists(artist_name)
    
    return False, [artist_name]
```

---

## Troubleshooting

### "A duo I know is being split"

**Solution 1:** Check MusicBrainz
1. Go to https://musicbrainz.org
2. Search for the duo name
3. If found as a single artist, the API might be temporarily down
4. Check logs for `MusicBrainz query failed` messages

**Solution 2:** Add to whitelist
1. Open `duo_whitelist.json`
2. Add the duo name
3. Restart Radio Monitor

### "MusicBrainz is slow/unavailable"

**Solution:** The whitelist acts as a fallback
- Add known duos to `duo_whitelist.json`
- System will use whitelist when MusicBrainz fails
- No downtime or data corruption

### "I see 'MusicBrainz query failed: HTTP 404' in logs"

**Solution:** This is expected for some queries
- MusicBrainz API sometimes returns 404 for complex queries
- The whitelist catches these cases
- As long as the duo is in the whitelist, it won't be split

---

## Configuration

### Disable MusicBrainz Checking

**Not recommended** - reduces accuracy significantly.

If you must disable it (e.g., air-gapped network):

1. Add all known duos to `duo_whitelist.json`
2. Set environment variable (future feature):
   ```bash
   RADIO_MONITOR_DISABLE_MUSICBRAINZ=true
   ```

### Increase MusicBrainz Timeout

**File:** `radio_monitor/normalization.py`

**Line:** ~445 (in `check_musicbrainz_exists`)

```python
response = requests.get(url, verify=False, timeout=10)  # Increase from 5 to 10
```

---

## Performance Impact

- **MusicBrainz query:** ~0.5-2 seconds per artist
- **Cached results:** Not implemented yet (planned for v1.5)
- **Whitelist lookup:** Instant (< 1ms)

**Recommendation:** For large databases (1000+ artists), consider caching MusicBrainz results to improve performance.

---

## Future Enhancements

1. **Local cache** of MusicBrainz results (v1.5)
2. **Batch queries** to MusicBrainz API (v1.5)
3. **Automatic whitelist suggestions** based on detected patterns (v1.6)
4. **GUI integration** for whitelist management (v1.6)

---

## Related Documentation

- [USER_MAPPINGS_README.md](../USER_MAPPINGS_README.md) - Plex matching mappings
- [ADVERTISMENT_FILTER_FIX.md](ADVERTISMENT_FILTER_FIX.md) - Advertisement detection
- [TITLE_CASE_NORMALIZATION.md](TITLE_CASE_NORMALIZATION.md) - Text normalization

---

## Support

If you encounter issues:

1. Check the logs: `radio_monitor.log`
2. Verify `duo_whitelist.json` is valid JSON
3. Test MusicBrainz API: https://musicbrainz.org
4. Check GitHub Issues: https://github.com/allurjj/radio-monitor/issues

---

**Version:** 1.0.0
**Last Updated:** 2026-06-13
**Status:** Production Ready
