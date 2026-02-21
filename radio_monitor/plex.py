"""
Plex Integration module for Radio Monitor 1.0

This module handles Plex playlist creation with multi-strategy fuzzy matching:
- Multi-strategy fuzzy matching (exact → normalized → fuzzy → partial)
- All playlist modes (merge, replace, append, create, snapshot)
- Test-matching command
- Playlist config file support

Multi-Strategy Matching:
1. Exact match - title and artist must match exactly (case-insensitive)
2. Normalized match - Title Case, apostrophes unified, special chars handled
3. Fuzzy match - Levenshtein distance (>= 90% similarity)
4. Partial match - substring matching (fallback)

Normalization (Strategy 2):
- Converts ALL CAPS to Title Case (AIN'T IT FUN → Ain't It Fun)
- Unifies apostrophe variants (''´` → ')
- Preserves known acronyms (ABBA, KISS, TLC)
- Handles Roman numerals, contractions, collaborations

Key Principle: Radio songs might not match Plex library exactly due to
different formatting, spelling variations, or remix versions.
"""

import re
import logging
from datetime import datetime
from rapidfuzz import fuzz
from radio_monitor.normalization import normalize_artist_name, normalize_song_title

logger = logging.getLogger(__name__)


def fuzzy_ratio(str1, str2):
    """Calculate Levenshtein similarity ratio (0-100)

    Args:
        str1: First string
        str2: Second string

    Returns:
        Similarity percentage (0-100)
    """
    if not str1 or not str2:
        return 0

    return int(fuzz.ratio(str1.lower(), str2.lower()))


def get_title_variations(title):
    """Generate multiple title variations for Plex searching

    Handles common punctuation and formatting differences:
    - Removes parentheses with (feat., remix, extended, etc.)
    - Removes apostrophes (tries both with and without)
    - Removes periods from abbreviations (MR., DR.)
    - Replaces hyphens with spaces
    - Removes diacritics/accents (ROSÉ → ROSE)
    - Normalizes whitespace

    Args:
        title: Original song title

    Returns:
        List of title variations to try (original first, then cleaned versions)
    """
    import re
    import unicodedata
    variations = [title]  # Always try original first

    # Variation 1: Remove parenthetical content (feat., remix, extended, etc.)
    # This helps: "TOO Sweet (extended Intro)" -> "TOO Sweet"
    no_paren = re.sub(r'\s*[(\[].*?[)\]]', '', title).strip()
    if no_paren != title:
        variations.append(no_paren)

    # Variation 2a: Convert regular apostrophes (U+0027) to Plex apostrophe (U+2019)
    # This helps when database has U+0027 but Plex has U+2019
    plex_apos = title.replace("\u0027", "\u2019")  # ' → '
    if plex_apos != title:
        variations.append(plex_apos)

    # Variation 2b: Remove apostrophes entirely
    # This helps: "Summer Of '69" -> "Summer Of 69"
    # But can hurt: "It's Time" -> "Its Time"
    no_apostrophe = re.sub(r"[''''`´]", '', title)  # Includes U+2019 right single quote
    if no_apostrophe != title:
        variations.append(no_apostrophe)

    # Variation 3: Remove periods from abbreviations
    # This helps: "MR. Electric Blue" -> "MR Electric Blue"
    no_period = title.replace('.', '')
    if no_period != title:
        variations.append(no_period)

    # Variation 4: Replace hyphens with spaces
    # This helps: "Undone - The Sweater Song" -> "Undone  The Sweater Song"
    with_spaces = title.replace('-', ' ')
    with_spaces = ' '.join(with_spaces.split())  # Normalize multiple spaces
    if with_spaces != title:
        variations.append(with_spaces)

    # Variation 5: Remove diacritics/accents
    # This helps: "ROSÉ" -> "ROSE", "Beyoncé" -> "Beyonce"
    # Normalize unicode to ASCII form, remove combining diacritics
    normalized = unicodedata.normalize('NFKD', title)
    no_diacritics = ''.join([c for c in normalized if not unicodedata.combining(c)])
    if no_diacritics != title:
        variations.append(no_diacritics)

    # Variation 6: Combined aggressive cleaning (no paren + no apostrophe + no period + no hyphen + no diacritics)
    aggressive = no_paren
    aggressive = re.sub(r"['''`´]", '', aggressive)  # Includes U+2019
    aggressive = aggressive.replace('.', '')
    aggressive = aggressive.replace('-', ' ')
    aggressive = ' '.join(aggressive.split())
    # Also remove diacritics from aggressive version
    aggressive_norm = unicodedata.normalize('NFKD', aggressive)
    aggressive = ''.join([c for c in aggressive_norm if not unicodedata.combining(c)])
    if aggressive != title and aggressive not in variations:
        variations.append(aggressive)

    return variations


def find_song_in_library(music_library, song_title, artist_name, debug=False):
    """Find song in Plex library using multi-strategy fuzzy matching

    Args:
        music_library: Plex music library section
        song_title: Song title to find
        artist_name: Artist name to find
        debug: Enable debug logging

    Returns:
        Plex Track object or None
    """
    if debug:
        logger.debug(f"Searching for: {song_title} - {artist_name}")

    # STRATEGY 0: Artist-first search (bypasses Plex search limitations)
    # For common song titles, Plex search doesn't return all tracks
    # So we search by artist first, then within their catalog
    if debug:
        logger.debug(f"  Trying Strategy 0: Artist-first search")

    try:
        # Search for artist
        artists = music_library.search(artist_name, libtype='artist')

        if artists:
            # Check each artist match
            for artist in artists:
                artist_title = artist.title if hasattr(artist, 'title') else str(artist)

                # Check if artist name matches (case-insensitive)
                if artist_title.lower() == artist_name.lower():
                    if debug:
                        logger.debug(f"  Found artist: {artist_title}")

                    # Get ALL tracks from this artist
                    all_tracks = []
                    for album in artist.albums():
                        all_tracks.extend(album.tracks())

                    if debug:
                        logger.debug(f"  Artist has {len(all_tracks)} tracks")

                    # Search for matching title within artist's catalog
                    # Try all title variations
                    for search_title in get_title_variations(song_title):
                        # Match using all strategies (exact, normalized, fuzzy)
                        for track in all_tracks:
                            try:
                                # Strategy 0a: Exact match (case-insensitive)
                                if track.title.lower() == search_title.lower():
                                    if debug:
                                        logger.debug(f"  ✓ Artist-first exact match: {track.title}")
                                    return track

                                # Strategy 0b: Normalized match
                                track_norm = normalize_song_title(track.title)
                                search_norm = normalize_song_title(search_title)

                                if (track_norm.lower() == search_norm.lower() or
                                    track_norm.lower() in search_norm.lower() or
                                    search_norm.lower() in track_norm.lower()):
                                    if debug:
                                        logger.debug(f"  ✓ Artist-first normalized match: {track.title}")
                                    return track

                                # Strategy 0c: Fuzzy match
                                fuzzy = fuzzy_ratio(track.title, search_title)
                                if fuzzy >= 90:
                                    if debug:
                                        logger.debug(f"  ✓ Artist-first fuzzy match: {track.title} ({fuzzy}%)")
                                    return track
                            except Exception:
                                continue
                    break
    except Exception as e:
        if debug:
            logger.debug(f"  Artist-first search failed: {e}")

    # Get title variations to try for traditional search
    title_variations = get_title_variations(song_title)

    if debug and len(title_variations) > 1:
        logger.debug(f"  Will try {len(title_variations)} title variations")

    # Try each title variation
    for variation_idx, search_title in enumerate(title_variations):
        if variation_idx > 0 and debug:
            logger.debug(f"  Trying variation {variation_idx}: \"{search_title}\"")

        # Search for tracks with matching title
        try:
            # Limit search results to avoid timeout on common song titles
            tracks = music_library.search(title=search_title, libtype='track', maxresults=100)
        except Exception as e:
            logger.error(f"Error searching Plex library: {e}")
            continue

        if not tracks:
            if debug:
                logger.debug(f"  No tracks found with title: {search_title}")
            continue

        if debug:
            logger.debug(f"  Found {len(tracks)} tracks with title: {search_title}")

        # Strategy 1: Exact match
        for track in tracks:
            try:
                track_artist = track.artist().title if track.artist() else ""
                if track_artist.lower() == artist_name.lower() and track.title.lower() == song_title.lower():
                    if debug:
                        logger.debug(f"  ✓ Exact match: {track.title} - {track_artist}")
                    return track
            except Exception as e:
                if debug:
                    logger.debug(f"  Error accessing track: {e}")
                continue

        # Strategy 2: Normalized match (using proper normalization)
        song_norm = normalize_song_title(song_title)
        artist_norm = normalize_artist_name(artist_name)

        for track in tracks:
            try:
                track_artist = track.artist().title if track.artist() else ""
                track_artist_norm = normalize_artist_name(track_artist)
                track_song_norm = normalize_song_title(track.title)

                # Check if normalized artist and song match
                # Use substring matching to handle remixes, features, etc.
                artist_match = (artist_norm.lower() in track_artist_norm.lower() or
                               track_artist_norm.lower() in artist_norm.lower())
                song_match = (song_norm.lower() in track_song_norm.lower() or
                             track_song_norm.lower() in song_norm.lower())

                if artist_match and song_match:
                    if debug:
                        logger.debug(f"  ✓ Normalized match: {track.title} - {track_artist}")
                        logger.debug(f"    DB norm: {song_norm} - {artist_norm}")
                        logger.debug(f"    Plex norm: {track_song_norm} - {track_artist_norm}")
                    return track
            except Exception as e:
                continue

        # Strategy 3: Fuzzy match (Levenshtein >= 90%)
        best_match = None
        best_score = 0

        for track in tracks[:20]:  # Check top 20 for fuzzy
            try:
                track_artist = track.artist().title if track.artist() else ""
                artist_ratio = fuzzy_ratio(artist_name, track_artist)
                song_ratio = fuzzy_ratio(song_title, track.title)

                if artist_ratio > best_score and song_ratio > best_score:
                    best_score = min(artist_ratio, song_ratio)
                    best_match = (track, artist_ratio, song_ratio)

                if artist_ratio >= 90 and song_ratio >= 90:
                    if debug:
                        logger.debug(f"  ✓ Fuzzy match: {track.title} - {track_artist} (artist: {artist_ratio}%, song: {song_ratio}%)")
                    return track
            except Exception as e:
                continue

        # Strategy 4: Partial match (substring)
        for track in tracks:
            try:
                track_artist = track.artist().title if track.artist() else ""
                if artist_name.lower() in track_artist.lower() and song_title.lower() in track.title.lower():
                    if debug:
                        logger.debug(f"  ✓ Partial match: {track.title} - {track_artist}")
                    return track
            except Exception as e:
                continue

    # If we get here, no match found with any title variation
    if debug:
        logger.debug(f"  ✗ No match found for: {song_title} - {artist_name}")

    return None

def create_playlist(db, plex, playlist_name, mode='merge', filters=None):
    """Create or update Plex playlist

    Args:
        db: RadioDatabase instance
        plex: PlexServer instance
        playlist_name: Name of playlist
        mode: Playlist mode ('merge', 'replace', 'append', 'create', 'snapshot', 'recent', 'random')
        filters: Dict with filter criteria:
            - days: Only include songs from last N days
            - limit: Maximum number of songs
            - station_ids: Array of station IDs to filter by (optional)
            - min_plays: Minimum play count (default: 1)
            - max_plays: Maximum play count (optional, NULL = no maximum)

    Returns:
        dict with:
        - added: Number of songs added to playlist
        - not_found: Number of songs not found in Plex
        - not_found_list: List of dicts with song_title and artist_name
    """
    if filters is None:
        filters = {'days': 7, 'limit': 50, 'min_plays': 1}

    days = filters.get('days', 7)
    limit = filters.get('limit', 50)
    station_ids = filters.get('station_ids', None)
    min_plays = filters.get('min_plays', 1)
    max_plays = filters.get('max_plays', None)

    # Calculate over-query limit (35% more to account for Plex matching failures)
    # Cap at 2500 for database queries (Plex playlist itself will be capped at 1500)
    over_query_limit = min(int(limit * 1.35), 2500)
    logger.info(f"Querying for {over_query_limit} songs (target: {limit}, 35% buffer for Plex matching)")

    # Get music library

    # Get music library
    music_library_name = filters.get('music_library_name', 'Music')
    try:
        music_library = plex.library.section(music_library_name)
    except Exception as e:
        logger.error(f"Error accessing Plex music library '{music_library_name}': {e}")
        return {
            'added': 0,
            'not_found': 0,
            'not_found_list': [],
            'error': f"Music library '{music_library_name}' not found"
        }

    # Query database for songs based on mode
    if mode == 'random':
        # NEW: Random mode
        if station_ids:
            songs = db.get_random_songs(
                station_ids=station_ids,
                min_plays=min_plays,
                max_plays=max_plays,
                days=days,
                limit=over_query_limit
            )
        else:
            songs = db.get_random_songs(
                min_plays=min_plays,
                max_plays=max_plays,
                days=days,
                limit=over_query_limit
            )
    elif mode == 'recent':
        if station_ids:
            songs = db.get_recent_songs(days=days, station_ids=station_ids, limit=over_query_limit)
        else:
            songs = db.get_recent_songs(days=days, limit=over_query_limit)
    else:
        # Top songs mode (merge, replace, append, create, snapshot)
        if station_ids:
            songs = db.get_top_songs(days=days, station_ids=station_ids, limit=over_query_limit)
        else:
            songs = db.get_top_songs(days=days, limit=over_query_limit)

    logger.info(f"Found {len(songs)} songs in database matching criteria")

    # Find songs in Plex library
    songs_to_add = []
    not_found = []

    for idx, (song_id, song_title, artist_name, play_count) in enumerate(songs, 1):
        if idx % 10 == 0 or idx == len(songs):
            logger.info(f"Processing song {idx}/{len(songs)}: {song_title} - {artist_name}")

        track = find_song_in_library(music_library, song_title, artist_name)

        if track:
            songs_to_add.append(track)
        else:
            not_found.append((song_id, song_title, artist_name))
            # Log Plex failure to database
            try:
                from radio_monitor.database import plex_failures
                cursor = db.get_cursor()
                plex_failures.log_plex_failure(
                    cursor,
                    song_id=song_id,
                    playlist_id=None,  # We don't have playlist_id yet
                    failure_reason='no_match',
                    search_attempts=4,  # We try 4 strategies
                    search_terms={'title': song_title, 'artist': artist_name}
                )
                db.conn.commit()
                cursor.close()
            except Exception as e:
                logger.error(f"Failed to log Plex failure: {e}")

    logger.info(f"Finished searching Plex: found {len(songs_to_add)}/{len(songs)} songs")

    # Trim to requested limit if we have too many matches
    if len(songs_to_add) > limit:
        logger.info(f"Trimming playlist from {len(songs_to_add)} to requested limit of {limit}")
        songs_to_add = songs_to_add[:limit]

    # Create or update playlist based on mode
    try:
        if mode == 'create':
            # Create new playlist (error if exists)
            playlist = plex.createPlaylist(playlist_name, items=songs_to_add)
            logger.info(f"Created playlist '{playlist_name}' with {len(songs_to_add)} songs")

        elif mode == 'replace':
            # Replace existing playlist (or create if doesn't exist)
            try:
                playlist = plex.playlist(playlist_name)
                playlist.removeItems(playlist.items())
                playlist.addItems(songs_to_add)
                logger.info(f"Replaced playlist '{playlist_name}' with {len(songs_to_add)} songs")
            except:
                # Playlist doesn't exist, create it
                playlist = plex.createPlaylist(playlist_name, items=songs_to_add)
                logger.info(f"Created playlist '{playlist_name}' with {len(songs_to_add)} songs")

        elif mode == 'append':
            # Append to existing playlist (or create if doesn't exist)
            try:
                playlist = plex.playlist(playlist_name)
                existing_keys = {item.ratingKey for item in playlist.items()}
                new_songs = [s for s in songs_to_add if s.ratingKey not in existing_keys]
                if new_songs:
                    playlist.addItems(new_songs)
                logger.info(f"Appended {len(new_songs)} songs to '{playlist_name}'")
            except:
                # Playlist doesn't exist, create it
                playlist = plex.createPlaylist(playlist_name, items=songs_to_add)
                logger.info(f"Created playlist '{playlist_name}' with {len(songs_to_add)} songs")

        elif mode == 'merge':
            # Smart merge: remove stale, add new
            try:
                playlist = plex.playlist(playlist_name)
                existing_items = playlist.items()
                existing_keys = {item.ratingKey for item in existing_items}

                # Remove stale items (no longer in database)
                to_remove = [item for item in existing_items if item.ratingKey not in [s.ratingKey for s in songs_to_add]]
                if to_remove:
                    playlist.removeItems(to_remove)

                # Add new items
                to_add = [s for s in songs_to_add if s.ratingKey not in existing_keys]
                if to_add:
                    playlist.addItems(to_add)

                logger.info(f"Merged '{playlist_name}': -{len(to_remove)}, +{len(to_add)}")
            except:
                # Playlist doesn't exist, create it
                playlist = plex.createPlaylist(playlist_name, items=songs_to_add)
                logger.info(f"Created playlist '{playlist_name}' with {len(songs_to_add)} songs")

        elif mode == 'snapshot':
            # Create timestamped snapshot
            timestamp = datetime.now().strftime('%Y-%m-%d')
            snapshot_name = f"{playlist_name} {timestamp}"
            playlist = plex.createPlaylist(snapshot_name, items=songs_to_add)
            logger.info(f"Created snapshot '{snapshot_name}' with {len(songs_to_add)} songs")

        elif mode == 'recent':
            # Recent mode: replace with most recently played songs
            # Works like replace - clear old list, add new recent songs
            try:
                playlist = plex.playlist(playlist_name)
                playlist.removeItems(playlist.items())
                playlist.addItems(songs_to_add)
                logger.info(f"Updated recent playlist '{playlist_name}' with {len(songs_to_add)} songs")
            except:
                # Playlist doesn't exist, create it
                playlist = plex.createPlaylist(playlist_name, items=songs_to_add)
                logger.info(f"Created recent playlist '{playlist_name}' with {len(songs_to_add)} songs")

        elif mode == 'random':
            # Random mode: replace with random songs
            # Works like replace - clear old list, add new random songs
            try:
                playlist = plex.playlist(playlist_name)
                playlist.removeItems(playlist.items())
                playlist.addItems(songs_to_add)
                logger.info(f"Updated random playlist '{playlist_name}' with {len(songs_to_add)} songs")
            except:
                # Playlist doesn't exist, create it
                playlist = plex.createPlaylist(playlist_name, items=songs_to_add)
                logger.info(f"Created random playlist '{playlist_name}' with {len(songs_to_add)} songs")

        else:
            logger.error(f"Unknown playlist mode: {mode}")
            return {
                'added': 0,
                'not_found': len(not_found),
                'not_found_list': not_found,
                'error': f"Unknown mode: {mode}"
            }

    except Exception as e:
        logger.error(f"Error creating/updating playlist: {e}")
        return {
            'added': 0,
            'not_found': len(not_found),
            'not_found_list': not_found,
            'error': str(e)
        }

    # Report not found songs
    if not_found:
        logger.warning(f"{len(not_found)} songs not found in Plex library")
        for song_id, song_title, artist_name in not_found[:10]:
            logger.warning(f"  - {song_title} - {artist_name}")
        if len(not_found) > 10:
            logger.warning(f"  ... and {len(not_found) - 10} more")

    # Convert not_found tuples to dicts for JSON response
    not_found_list = [
        {'song_id': song_id, 'song_title': song_title, 'artist_name': artist_name}
        for song_id, song_title, artist_name in not_found
    ]

    result = {
        'added': len(songs_to_add),
        'not_found': len(not_found),
        'not_found_list': not_found_list
    }

    # Log activity
    try:
        from radio_monitor.database.activity import log_activity
        severity = 'success' if len(not_found) == 0 else 'warning' if len(not_found) < len(songs) else 'error'
        log_activity(
            db.get_cursor(),
            event_type='playlist_update',
            title=f"Playlist updated: {playlist_name} ({mode})",
            description=f"Added {len(songs_to_add)} songs to '{playlist_name}' ({len(not_found)} not found)",
            metadata={
                'playlist_name': playlist_name,
                'mode': mode,
                'added': len(songs_to_add),
                'not_found': len(not_found),
                'days': days,
                'limit': limit
            },
            severity=severity,
            source='user'
        )
    except Exception as e:
        logger.error(f"Failed to log playlist activity: {e}")

    # Send notifications
    try:
        from radio_monitor.notifications import send_notifications
        logger.info(f"Sending playlist notifications: error={bool(result.get('error'))}, added={result.get('added', 0)}, not_found={result.get('not_found', 0)}")

        if not result.get('error'):
            logger.info(f"Sending on_playlist_update notification for '{playlist_name}'")
            sent = send_notifications(
                db,
                'on_playlist_update',
                f'Playlist Updated: {playlist_name}',
                f"Added {result['added']} songs to '{playlist_name}' ({result['not_found']} not found in Plex)",
                'success' if result['not_found'] == 0 else 'warning',
                {
                    'playlist_name': playlist_name,
                    'mode': mode,
                    'added': result['added'],
                    'not_found': result['not_found']
                }
            )
            logger.info(f"on_playlist_update notification sent to {sent} provider(s)")
        else:
            logger.info(f"Sending on_playlist_error notification for '{playlist_name}': {result.get('error')}")
            sent = send_notifications(
                db,
                'on_playlist_error',
                f'Playlist Error: {playlist_name}',
                result.get('error', 'Failed to create/update playlist'),
                'error',
                {'playlist_name': playlist_name, 'mode': mode}
            )
            logger.info(f"on_playlist_error notification sent to {sent} provider(s)")
    except Exception as e:
        logger.error(f"Failed to send playlist notifications: {e}", exc_info=True)

    return result


def test_matching(db, plex, test_songs_file=None, songs=None):
    """Test Plex fuzzy matching

    Args:
        db: RadioDatabase instance
        plex: PlexServer instance
        test_songs_file: Path to file with test songs (one per line: "artist - song")
        songs: List of (artist, song) tuples (alternative to test_songs_file)

    Returns:
        dict with:
        - total: Total songs tested
        - found: Number found in Plex
        - not_found: Number not found
        - match_rate: Percentage found
        - not_found_list: List of (song_title, artist_name) tuples
    """
    if test_songs_file:
        # Load test songs from file
        test_songs = []
        with open(test_songs_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and '-' in line:
                    parts = line.split('-', 1)
                    if len(parts) == 2:
                        artist = parts[0].strip()
                        song = parts[1].strip()
                        test_songs.append((artist, song))
    elif songs:
        test_songs = songs
    else:
        # Use top songs from database
        top_songs = db.get_top_songs(limit=20)
        test_songs = [(artist, song) for song, artist, _ in top_songs]

    # Get music library
    music_library_name = 'Music'
    try:
        music_library = plex.library.section(music_library_name)
    except Exception as e:
        logger.error(f"Error accessing Plex music library: {e}")
        return {
            'total': 0,
            'found': 0,
            'not_found': 0,
            'match_rate': 0,
            'not_found_list': [],
            'error': str(e)
        }

    # Test matching
    found = 0
    not_found_list = []

    for artist_name, song_title in test_songs:
        track = find_song_in_library(music_library, song_title, artist_name, debug=True)

        if track:
            found += 1
            print(f"[OK] {song_title} - {artist_name}")
        else:
            not_found_list.append((song_title, artist_name))
            print(f"[NOT FOUND] {song_title} - {artist_name}")

    total = len(test_songs)
    match_rate = (found / total * 100) if total > 0 else 0

    print(f"\nMatch rate: {found}/{total} ({match_rate:.1f}%)")

    return {
        'total': total,
        'found': found,
        'not_found': total - found,
        'match_rate': match_rate,
        'not_found_list': not_found_list
    }


def update_playlists_from_config(db, plex, config_file, settings):
    """Update multiple playlists from config file

    Args:
        db: RadioDatabase instance
        plex: PlexServer instance
        config_file: Path to JSON config file
        settings: Settings dict with default music_library_name

    Returns:
        List of result dicts from create_playlist()
    """
    import json

    with open(config_file, 'r', encoding='utf-8') as f:
        playlists = json.load(f)

    results = []

    for playlist_config in playlists:
        name = playlist_config.get('name', 'Playlist')
        mode = playlist_config.get('mode', 'merge')
        days = playlist_config.get('days', 7)
        limit = playlist_config.get('limit', 50)
        station_id = playlist_config.get('station', None)

        filters = {
            'days': days,
            'limit': limit,
            'station_id': station_id,
            'music_library_name': settings.get('plex', {}).get('music_library_name', 'Music')
        }

        print(f"\nProcessing playlist: {name} (mode: {mode})")
        result = create_playlist(db, plex, name, mode, filters)
        results.append(result)

        if result.get('error'):
            print(f"  Error: {result['error']}")
        else:
            print(f"  Added: {result['added']}, Not found: {result['not_found']}")

    return results


def get_plex_libraries(settings):
    """Get available music libraries from Plex

    Args:
        settings: Settings dict with plex configuration

    Returns:
        List of library dicts with 'name' and 'key', or None
    """
    try:
        from plexapi.server import PlexServer

        plex_url = settings.get('plex', {}).get('url', 'http://localhost:32400')
        token = settings.get('plex', {}).get('token', '')

        if not token:
            logger.error("No Plex token configured")
            return None

        plex = PlexServer(plex_url, token, timeout=10)

        # Get all libraries
        libraries = []
        for lib in plex.library.sections():
            # Only include music libraries
            if lib.type == 'artist':
                libraries.append({
                    'name': lib.title,
                    'key': str(lib.key)
                })

        logger.info(f"Found {len(libraries)} music libraries in Plex")
        return libraries

    except Exception as e:
        logger.error(f"Error getting Plex libraries: {e}")
        return None


def test_plex_connection(settings):
    """Test connection to Plex

    Args:
        settings: Settings dict with plex configuration

    Returns:
        (success, message) tuple
    """
    try:
        from plexapi.server import PlexServer

        plex_url = settings.get('plex', {}).get('url', 'http://localhost:32400')
        token = settings.get('plex', {}).get('token', '')

        if not token:
            return False, "No Plex token configured"

        # Add explicit timeout
        plex = PlexServer(plex_url, token, timeout=(5, 10))

        # Get server info
        server_name = plex.friendlyName
        version = plex.version

        return True, f"Connected to {server_name} (Plex {version})"

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Plex connection error: {e}")

        # Provide helpful error messages
        if "Connection refused" in error_msg or "Errno 111" in error_msg or "Errno 61" in error_msg:
            return False, "Connection refused - Is Plex running?"
        elif "401" in error_msg or "Unauthorized" in error_msg:
            return False, "Authentication failed - Check your token"
        elif "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            return False, "Connection timeout - Is Plex responding?"
        else:
            return False, f"Connection failed: {error_msg}"
