# New Scrape & Match Logic - Implementation Guide

**Version:** 1.0.0
**Created:** 2026-06-13
**Implemented:** 2026-06-14
**Status:** ✅ COMPLETE

---

## Overview

This document describes the new scraping and matching logic that improves data quality by:
1. Checking local database FIRST before MusicBrainz queries
2. Validating artist-song relationships during scrape (not later)
3. Using pending status for failed validations (retryable)
4. Increasing MusicBrainz results limit for better matching

---

## Current State (Before This Change)

### Problems

1. **Unnecessary MusicBrainz traffic:** Queries MusicBrainz for every artist, even if already in database
2. **Bad data enters database:** Scraped data stored immediately, validated later
3. **Low MusicBrainz limit:** `limit=5` may miss legitimate matches
4. **No song validation:** Doesn't verify artist actually recorded the song

### Current Flow

```
SCRAPE → Normalize → Split Collaboration → Store → Later Validate → Fix Errors
```

---

## New State (After This Change)

### Improvements

1. **Database-first:** Check local DB before MusicBrainz (95%+ cache hit)
2. **Immediate validation:** Validate artist-song during scrape
3. **Higher MusicBrainz limit:** `limit=20` for better matching
4. **Pending status:** Store failed validations as 'pending' for retry

### New Flow

```
SCRAPE → Normalize → Split Collaboration → Check DB → MusicBrainz (if needed) → Validate → Store with Status
```

---

## Detailed Implementation Flow

### Step 1: Scrape from Radio Station

**Input:** Raw HTML from radio station website

**Output:** List of `(artist_name, song_title)` tuples

**Example:**
```python
# Raw scraped data
songs = [
    ("Brooks & Dunn", "Neon Moon"),
    ("George Birge & Luke Bryan", "Cowboy Song"),
    ("Justin Moore feat. Dierks Bentley", "Time's Ticking"),
]
```

---

### Step 2: Normalize Text

**Function:** `normalize_with_edge_cases(text)` in `radio_monitor/normalization.py`

**Purpose:** Fix encoding, unify apostrophes, title case, known corrections

**Transformations:**
1. Fix encoding corruption (â€™ → ')
2. Unify apostrophes (smart quotes → straight quotes)
3. Trim whitespace
4. Normalize internal whitespace (multiple spaces → single space)
5. Apply known corrections (PINK → P!NK, ABBA → ABBA)
6. Title case with smart exceptions (WE'RE → We're, not We'Re)

**Example:**
```python
# Input
"BROOKS & DUNN - NEON MOON"

# Output
"Brooks & Dunn - Neon Moon"
```

---

### Step 3: Handle Collaborations

**Function:** `handle_collaboration(artist_name, song_title, mbid)` in `radio_monitor/normalization.py`

**Purpose:** Split temporary collaborations, preserve legitimate duos

**Detection Flow (in order):**

1. **Check whitelist** (`duo_whitelist.json`):
   - If artist in whitelist → Don't split, treat as single artist
   - Example: "Brooks & Dunn" is in whitelist → Keep as-is

2. **Check MusicBrainz** (if not in whitelist):
   - Query MusicBrainz for exact artist name match
   - If found as single artist → Don't split (legitimate duo)
   - Example: "Dan + Shay" found in MusicBrainz → Keep as-is

3. **Check collaboration markers** (if MusicBrainz doesn't recognize):
   - Markers: `feat`, `ft`, `featuring`, `with`, `;`
   - If found → Split, keep primary artist only
   - Example: "Justin Moore feat. Dierks Bentley" → "Justin Moore"

4. **Check ambiguous markers** (last resort):
   - Markers: `&`, `+`, `x`, `and`
   - If found → Split (might incorrectly split some duos, whitelist can fix)
   - Example: "George Birge & Luke Bryan" → "George Birge"

**Output:** List of `[(primary_artist, song_title, mbid)]`

**Examples:**
```python
# Legitimate duo (whitelisted)
handle_collaboration("Brooks & Dunn", "Neon Moon", None)
# Returns: [("Brooks & Dunn", "Neon Moon", None)]

# Temporary collaboration (split)
handle_collaboration("George Birge & Luke Bryan", "Cowboy Song", None)
# Returns: [("George Birge", "Cowboy Song", None)]

# Feature (split)
handle_collaboration("Justin Moore feat. Dierks Bentley", "Time's Ticking", None)
# Returns: [("Justin Moore", "Time's Ticking", None)]
```

---

### Step 4: Check Database First

**Purpose:** Avoid unnecessary MusicBrainz queries by checking local database first

**Database Query:**
```sql
SELECT mbid, validation_status
FROM artists
WHERE match_key = ?
```

**match_key Generation:**
```python
# Use same normalization as MusicBrainz queries
match_key = generate_match_key_for_db(artist_name)
# Example: "Brooks & Dunn" → "brooksdunn"
```

**Decision Logic:**

| DB State | Action |
|----------|--------|
| Not found | Query MusicBrainz for artist lookup |
| Found with valid MBID | Use existing MBID, skip MusicBrainz |
| Found with PENDING MBID | Query MusicBrainz to get real MBID |
| Found with NULL MBID | Query MusicBrainz to get MBID |

**Examples:**
```python
# Case 1: Artist exists with valid MBID
# DB has: Brooks & Dunn (MBID: f30118c5-...)
match_key = generate_match_key_for_db("Brooks & Dunn")  # "brooksdunn"
# Query DB → Found with MBID f30118c5-...
# Action: Use existing MBID, skip MusicBrainz

# Case 2: Artist doesn't exist
match_key = generate_match_key_for_db("New Artist")
# Query DB → Not found
# Action: Query MusicBrainz for artist lookup

# Case 3: Artist exists with PENDING MBID
# DB has: Some Artist (MBID: PENDING-uuid)
match_key = generate_match_key_for_db("Some Artist")
# Query DB → Found with PENDING MBID
# Action: Query MusicBrainz to get real MBID
```

---

### Step 5: Query MusicBrainz (if needed)

**When to query:**
- Artist not in database
- Artist in database but has PENDING MBID

**API Endpoint:**
```
GET https://musicbrainz.org/ws2/artist?query=artist:"{artist_name}"&fmt=json&limit=20
```

**Parameters:**
- `artist_name`: Normalized artist name from Step 2
- `limit`: 20 (increased from 5)
- `fmt`: json

**Response Processing:**
```python
response = requests.get(url, verify=False, timeout=10, headers={'User-Agent': 'radio-monitor/1.0'})

if response.status_code == 200:
    data = response.json()
    artists = data.get('artists', [])
    
    # Check for exact name match (case-insensitive)
    for artist in artists:
        mb_name = artist.get('name', '')
        if mb_name.lower() == artist_name.lower():
            mbid = artist.get('id')
            return mbid  # Found exact match
    
    # Check for alias matches
    for artist in artists:
        aliases = artist.get('aliases', [])
        for alias in aliases:
            if alias.lower() == artist_name.lower():
                mbid = artist.get('id')
                return mbid  # Found alias match
    
    # No match found
    return None

else:
    # API error
    return None
```

**Error Handling:**
- Timeout → Return None (will be handled as PENDING)
- HTTP error → Return None (will be handled as PENDING)
- Not found → Return None (will be handled as PENDING)

---

### Step 6: Validate Song (Artist → Song Relationship)

**Purpose:** Verify that the artist actually recorded this song

**Two-Step Process:**

#### Step 6a: Look up artist (already done in Step 5)

**We have:** Artist MBID from either database or MusicBrainz

#### Step 6b: Check if song belongs to this artist

**API Endpoint:**
```
GET https://musicbrainz.org/ws2/recording?query=artist:{mbid}+recording:"{song_title}"&fmt=json&limit=20
```

**Parameters:**
- `mbid`: Artist MBID from Step 5
- `song_title`: Normalized song title from Step 2
- `limit`: 20

**Response Processing:**
```python
response = requests.get(url, verify=False, timeout=10, headers={'User-Agent': 'radio-monitor/1.0'})

if response.status_code == 200:
    data = response.json()
    recordings = data.get('recordings', [])
    
    for recording in recordings:
        recording_title = recording.get('title', '')
        
        # Check for exact match (case-insensitive)
        if recording_title.lower() == song_title.lower():
            return True, 'valid'  # Exact match found
        
        # Check for similarity match (85%+ threshold)
        similarity = calculate_similarity(song_title, recording_title)
        if similarity >= 0.85:
            return True, 'valid'  # Similar match found (remixes, etc.)
    
    # No match found
    return False, 'pending'

else:
    # API error
    return False, 'pending'
```

**Validation Rules:**

| Scenario | Result | Reason |
|----------|--------|--------|
| Exact match | valid | "Neon Moon" = "Neon Moon" |
| Remix/Live version | valid | "Neon Moon (Remix)" ≈ "Neon Moon" (85%+ similarity) |
| Different song | pending | "Different Song" ≠ "Neon Moon" (below threshold) |
| API error | pending | Retry later |

**Edge Cases:**

1. **Remixes = Same Song**
   - "Neon Moon (Remix)" ≈ "Neon Moon" ✅
   - "Neon Moon - Live" ≈ "Neon Moon" ✅
   - Uses 85%+ similarity threshold

2. **Features = Primary Artist Only**
   - "Justin Moore feat. Dierks Bentley - Time's Ticking"
   - After split: "Justin Moore" + "Time's Ticking"
   - Validate: Does "Justin Moore" have "Time's Ticking"?
   - Check: Primary artist only, ignore featured artist

3. **Multiple Artists**
   - Rare case where song has multiple valid artist combinations
   - Use first match found (highest similarity)

**Examples:**
```python
# Case 1: Valid match
validate_song(mbid="f30118c5-...", song="Neon Moon")
# MusicBrainz has: "Brooks & Dunn - Neon Moon"
# Returns: True, 'valid'

# Case 2: Remix match
validate_song(mbid="f30118c5-...", song="Neon Moon")
# MusicBrainz has: "Brooks & Dunn - Neon Moon (Remix)"
# Similarity: 92%
# Returns: True, 'valid'

# Case 3: No match
validate_song(mbid="f30118c5-...", song="Fake Song")
# MusicBrainz doesn't have this song for this artist
# Returns: False, 'pending'

# Case 4: API error
validate_song(mbid="f30118c5-...", song="Neon Moon")
# API times out
# Returns: False, 'pending'
```

---

### Step 7: Store with Validation Status

**Database Schema (songs table):**
```sql
CREATE TABLE songs (
    id INTEGER PRIMARY KEY,
    song_title TEXT NOT NULL,
    artist_name TEXT NOT NULL,
    artist_mbid TEXT,
    validation_status TEXT DEFAULT 'unvalidated',  -- 'valid', 'pending', 'unvalidated'
    first_seen_at TIMESTAMP,
    last_seen_at TIMESTAMP,
    first_seen_station TEXT,
    UNIQUE(artist_mbid, song_title)
);
```

**Storage Logic:**

| Scenario | validation_status | Action |
|----------|------------------|--------|
| Song validated successfully | 'valid' | Store/update song with valid status |
| Validation failed (API error) | 'pending' | Store with pending status, retry later |
| Validation failed (no match) | 'pending' | Store with pending status, manual review |

**Error Handling:**

```python
try:
    # Validate song
    is_valid, status = validate_song(artist_mbid, song_title)
    
    if is_valid:
        # Store with valid status
        store_song(artist_name, song_title, artist_mbid, validation_status='valid')
    else:
        # Store with pending status
        store_song(artist_name, song_title, artist_mbid, validation_status='pending')
        
except Exception as e:
    # Store with pending status on any error
    logger.error(f"Validation error for {artist_name} - {song_title}: {e}")
    store_song(artist_name, song_title, artist_mbid, validation_status='pending')
```

**Handling Existing Invalid Entries:**

If we scrape a song that already exists with `validation_status='invalid'`:

- **Don't** update to 'pending' (user manually marked as invalid for a reason)
- **Don't** store the play (avoid reinforcing bad data)
- Skip this song entry

---

## Performance Considerations

### Current Performance

- **Without validation:** ~30 seconds for 27 stations (~300 songs)
- **Rate:** ~10 songs/second

### Expected Performance with New Logic

- **With validation:** ~5 minutes for 27 stations (~300 songs)
- **Rate:** ~1 song/second (MusicBrainz rate limit)
- **Cache benefit:** 95%+ cache hit over time → faster

### Optimization

1. **Database cache:** First scrape will be slow (~5 min), subsequent scrapes faster
2. **Batch validation:** Future enhancement to validate multiple songs at once
3. **Parallel processing:** Future enhancement to parallelize independent queries

---

## Database Changes Required

### None Required

The current schema already supports the new logic:

**Artists table:**
- `mbid` (TEXT) - Already supports NULL and PENDING values
- `match_key` (TEXT) - Already used for matching

**Songs table:**
- `validation_status` (TEXT) - Already supports 'valid', 'pending', 'unvalidated', 'invalid'

---

## Code Changes Required

### Files Modified (Actual Implementation)

1. **`radio_monitor/normalization.py`**
   - ✅ Updated `check_musicbrainz_exists()` - Increased limit to 50
   - ✅ Added `calculate_similarity()` - String similarity matching
   - ✅ Added `strip_song_suffixes()` - Removes Remix, Live, etc.
   - ✅ Added `clean_song_title_for_query()` - Cleans titles for queries

2. **`radio_monitor/recording_validation.py`** (NEW FILE)
   - ✅ Created `validate_recording_with_fallback()` - Main validation function
   - ✅ Created `validate_recording_by_mbid()` - MBID-based validation
   - ✅ Created `validate_recording_by_text()` - Text-based fallback
   - ✅ Created `is_recording_match()` - Three-tier matching (exact → suffix → similarity)

3. **`radio_monitor/scrapers.py`**
   - ✅ Updated scrape loop (lines 901-924) to call validation
   - ✅ Added settings-based toggle for validation
   - ✅ Handles validation status in storage logic

4. **`radio_monitor/database/queries.py`**
   - ✅ Added `get_artist_by_match_key()` - Database-first artist lookup

5. **`radio_monitor/data_quality.py`**
   - ✅ Added `validate_batch_scheduled()` - Batch validation for scheduler

6. **`radio_monitor/scheduler.py`**
   - ✅ Added `add_validation_job()` - Scheduled validation support

7. **`radio_monitor_settings.json`**
   - ✅ Added `validate_recordings` setting
   - ✅ Added `skip_unvalidated_recordings` setting

---

## Implementation Checklist

- [x] Update `check_musicbrainz_exists()` to use `limit=50` (exceeded plan of 20)
- [x] Add `validate_recording_with_fallback()` function in `recording_validation.py`
- [x] Add database-first check with `generate_match_key_for_db()` and `get_artist_by_match_key()`
- [x] Update scrape loop to call validation (lines 901-924 in `scrapers.py`)
- [x] Add validation settings: `validate_recordings` and `skip_unvalidated_recordings`
- [x] Test with fresh scrape (30 unit tests passing)
- [x] Verify database integrity
- [x] Update documentation

---

## Testing Plan

1. **Unit Tests:**
   - Test `validate_song_recordings()` with known valid/invalid songs
   - Test database-first check with existing/new artists
   - Test collaboration handling with edge cases

2. **Integration Tests:**
   - Full scrape with 27 stations
   - Verify all songs have validation_status set
   - Verify no bad data enters database

3. **Performance Tests:**
   - Time first scrape (empty database)
   - Time subsequent scrape (cached database)
   - Verify ~5 minute target met

---

## Rollback Plan

If issues arise:

1. **Revert code changes** to previous version
2. **Database remains intact** (no schema changes)
3. **Re-validate pending entries** using existing validation system
4. **Document issues** for future fixes

---

## Future Enhancements

1. **Batch validation** - Validate multiple songs in single API call
2. **Async validation** - Validate in background after scrape
3. **Local cache** - Cache MusicBrainz results locally
4. **Smart retry** - Only retry failed validations with backoff
5. **GUI integration** - Show validation status in UI

---

## References

- [COLLABORATION_DETECTION.md](COLLABORATION_DETECTION.md) - Collaboration detection logic
- [MusicBrainz API](https://musicbrainz.org/doc/API) - API documentation
- [Normalization module](../radio_monitor/normalization.py) - Text normalization functions

---

**Version:** 1.0.0
**Created:** 2026-06-13
**Implemented:** 2026-06-14
**Status:** ✅ COMPLETE
