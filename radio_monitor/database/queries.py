"""
Database query methods for Radio Monitor 1.0

This module contains all SELECT query methods for retrieving data from the database.
All methods return data structures (dicts, lists, tuples) and do not modify the database.

Query Categories:
- Station queries: get_station_by_id, get_all_stations, get_all_stations_with_health
- Artist queries: get_artist_by_mbid, get_artist_by_name, get_pending_artists
- Song queries: get_top_songs, get_recent_songs, get_all_songs
- Statistics: get_statistics, get_dashboard_stats, get_plays_over_time, get_station_distribution
- Playlist queries: get_playlist, get_playlists, get_due_playlists
"""

import logging
from datetime import datetime
import re

logger = logging.getLogger(__name__)


def capitalize_name_properly(name):
    """Capitalize artist name properly (title case with exceptions)

    Handles common name patterns like:
    - "AC/DC" stays "AC/DC"
    - "fleetwood mac" becomes "Fleetwood Mac"
    - "the beatles" becomes "The Beatles"
    - "a-ha" becomes "A-ha" (starts with lowercase letter)
    - "blink-182" becomes "Blink-182"
    - "lovelytheband" stays "lovelytheband" (single word brand name)

    Args:
        name: Artist name string

    Returns:
        Properly capitalized artist name
    """
    if not name:
        return name

    # Known exceptions that should stay as-is or have specific capitalization
    exceptions = {
        'ac/dc': 'AC/DC',
        'abba': 'ABBA',
        'ok go': 'OK Go',
        'r.e.m.': 'R.E.M.',
        'tv on the radio': 'TV on the Radio',
        'a-ha': 'A-ha',
        'lovelytheband': 'lovelytheband',  # Single word brand name
    }

    # Check if name matches an exception (case-insensitive)
    lower_name = name.lower().strip()
    for exception, proper in exceptions.items():
        if lower_name == exception:
            return proper

    # Title case the name
    name = name.strip()

    # Handle special cases with parentheses
    if '(' in name and ')' in name:
        # Process main part and parenthetical part separately
        main_part = name[:name.index('(')].strip()
        paren_part = name[name.index('('):].strip()
        # Don't recurse on parenthetical part to avoid infinite loop
        return capitalize_name_properly(main_part) + ' ' + paren_part.title()

    # Handle hyphenated names (blink-182, a-ha, etc.)
    if '-' in name and ' ' not in name:
        # Capitalize each part of the hyphenated name
        parts = name.split('-')
        parts = [p.capitalize() for p in parts]
        return '-'.join(parts)

    # Split into words and capitalize each
    words = name.split()

    # Handle leading "the", "a", "an" (but only if more than one word)
    articles = ['the', 'a', 'an']
    if words and words[0].lower() in articles and len(words) > 1:
        # Capitalize article and rest
        words[0] = words[0].capitalize()
        for i in range(1, len(words)):
            words[i] = words[i].capitalize()
    else:
        # Just capitalize all words
        words = [w.capitalize() for w in words]

    return ' '.join(words)


# ==================== STATION QUERIES ====================

def get_station_by_id(cursor, station_id):
    """Get station information by ID

    Args:
        cursor: SQLite cursor object
        station_id: Station ID (e.g., 'wtmx')

    Returns:
        Station dict or None if not found
    """
    cursor.execute("""
        SELECT id, name, url, genre, market, has_mbid, scraper_type, wait_time, enabled
        FROM stations
        WHERE id = ?
    """, (station_id,))

    row = cursor.fetchone()
    if not row:
        return None

    columns = ['id', 'name', 'url', 'genre', 'market', 'has_mbid', 'scraper_type', 'wait_time', 'enabled']
    return dict(zip(columns, row))


def get_all_stations(cursor):
    """Get all stations with health status

    Args:
        cursor: SQLite cursor object

    Returns:
        List of tuples: (id, name, genre, enabled, consecutive_failures, last_failure_at)
    """
    cursor.execute("""
        SELECT id, name, genre, enabled, consecutive_failures, last_failure_at
        FROM stations
        ORDER BY id
    """)
    return cursor.fetchall()


def get_all_stations_with_health(cursor):
    """Get all stations with health status

    Args:
        cursor: SQLite cursor object

    Returns:
        List of dicts with station info and health status
    """
    cursor.execute("""
        SELECT
            id,
            name,
            url,
            genre,
            market,
            has_mbid,
            scraper_type,
            wait_time,
            enabled,
            consecutive_failures,
            last_failure_at,
            created_at
        FROM stations
        ORDER BY name
    """)

    columns = ['id', 'name', 'url', 'genre', 'market', 'has_mbid',
              'scraper_type', 'wait_time', 'enabled', 'consecutive_failures',
              'last_failure_at', 'created_at']

    stations = []
    for row in cursor.fetchall():
        station = dict(zip(columns, row))
        # Calculate human-readable status
        if station['enabled']:
            if station['consecutive_failures'] == 0:
                station['status'] = 'Enabled'
                station['status_class'] = 'success'
            else:
                station['status'] = f"Enabled ({station['consecutive_failures']} failures)"
                station['status_class'] = 'warning'
        else:
            if station['last_failure_at']:
                # Convert string to datetime if necessary
                if isinstance(station['last_failure_at'], str):
                    failure_time = datetime.fromisoformat(station['last_failure_at'])
                else:
                    failure_time = station['last_failure_at']
                days_ago = (datetime.now() - failure_time).days
                station['status'] = f"Disabled ({station['consecutive_failures']} failures since {days_ago} days ago)"
            else:
                station['status'] = f"Disabled ({station['consecutive_failures']} failures)"
            station['status_class'] = 'danger'
        stations.append(station)

    return stations


def get_station_health(cursor, station_id):
    """Get health status for a single station

    Args:
        cursor: SQLite cursor object
        station_id: Station ID (e.g., 'wtmx')

    Returns:
        Dict with station health info or None if not found
    """
    cursor.execute("""
        SELECT id, name, enabled, consecutive_failures, last_failure_at
        FROM stations
        WHERE id = ?
    """, (station_id,))

    row = cursor.fetchone()
    if not row:
        return None


def get_station_config(cursor, station_id):
    """Get station scraper configuration by ID

    Returns all fields needed for scraping: url, scraper_type, has_mbid, wait_time

    Args:
        cursor: SQLite cursor object
        station_id: Station ID (e.g., 'wtmx')

    Returns:
        Dict with station config or None if not found
        Keys: id, name, url, scraper_type, has_mbid, wait_time
    """
    cursor.execute("""
        SELECT id, name, url, scraper_type, has_mbid, wait_time
        FROM stations
        WHERE id = ?
    """, (station_id,))

    row = cursor.fetchone()
    if not row:
        return None

    columns = ['id', 'name', 'url', 'scraper_type', 'has_mbid', 'wait_time']
    return dict(zip(columns, row))


    columns = ['id', 'name', 'enabled', 'consecutive_failures', 'last_failure_at']
    station = dict(zip(columns, row))

    # Parse last_failure_at if it's a string (SQLite returns strings)
    if station['last_failure_at']:
        if isinstance(station['last_failure_at'], str):
            try:
                station['last_failure_at'] = datetime.fromisoformat(station['last_failure_at'])
            except:
                station['last_failure_at'] = None

    # Calculate human-readable status
    if station['enabled']:
        if station['consecutive_failures'] == 0:
            station['status'] = 'Healthy'
            station['status_class'] = 'success'
        else:
            station['status'] = f"Degraded ({station['consecutive_failures']} failures)"
            station['status_class'] = 'warning'
    else:
        if station['last_failure_at']:
            days_ago = (datetime.now() - station['last_failure_at']).days
            station['status'] = f"Disabled ({station['consecutive_failures']} failures since {days_ago} days ago)"
        else:
            station['status'] = f"Disabled ({station['consecutive_failures']} failures)"
        station['status_class'] = 'danger'

    return station


# ==================== ARTIST QUERIES ====================

def get_artist_by_mbid(cursor, mbid):
    """Get artist by MBID

    Args:
        cursor: SQLite cursor object
        mbid: MusicBrainz artist ID

    Returns:
        Artist dict or None
    """
    cursor.execute("SELECT * FROM artists WHERE mbid = ?", (mbid,))
    row = cursor.fetchone()

    if row:
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))
    return None


def get_artist_by_name(cursor, name):
    """Get artist by name

    Args:
        cursor: SQLite cursor object
        name: Artist name

    Returns:
        Artist dict or None
    """
    cursor.execute("SELECT * FROM artists WHERE name = ?", (name,))
    row = cursor.fetchone()

    if row:
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))
    return None


def get_all_artists(cursor):
    """Get all artists

    Args:
        cursor: SQLite cursor object

    Returns:
        List of artist dicts
    """
    cursor.execute("SELECT * FROM artists ORDER BY name")
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_pending_artists(cursor):
    """Get all artists with PENDING MBIDs

    Args:
        cursor: SQLite cursor object

    Returns:
        List of tuples: [(artist_name, pending_mbid), ...]
    """
    cursor.execute("""
        SELECT name, mbid
        FROM artists
        WHERE mbid LIKE 'PENDING-%'
        ORDER BY name
    """)

    return cursor.fetchall()


def get_artists_for_import(cursor, min_plays=5, station_id=None, sort='total_plays', direction='desc'):
    """Get artists that need Lidarr import

    Args:
        cursor: SQLite cursor object
        min_plays: Minimum total plays (default: 5)
        station_id: Optional station ID to filter by
        sort: Column to sort by (default: 'total_plays')
        direction: Sort direction 'asc' or 'desc' (default: 'desc')

    Returns:
        List of dicts with keys: mbid, name, total_plays
    """
    # Validate sort column
    valid_columns = ['name', 'total_plays']
    if sort not in valid_columns:
        sort = 'total_plays'

    # Validate direction
    if direction not in ['asc', 'desc']:
        direction = 'desc'

    # Map sort parameter to database column
    sort_column_mapping = {
        'name': 'a.name',
        'total_plays': 'total_plays'
    }
    sort_column = sort_column_mapping.get(sort, 'total_plays')

    # Build ORDER BY with direction
    if sort == 'name':
        order_by = "{} COLLATE NOCASE {}".format(sort_column, direction.upper())
    else:
        order_by = "{} {}".format(sort_column, direction.upper())

    # Build query with optional station filter
    if station_id and station_id != "all":
        query = """
            SELECT DISTINCT
                a.mbid,
                a.name,
                SUM(spd.play_count) as total_plays
            FROM artists a
            JOIN songs s ON a.mbid = s.artist_mbid
            JOIN song_plays_daily spd ON s.id = spd.song_id
            JOIN stations st ON spd.station_id = st.id
            WHERE a.mbid IS NOT NULL
              AND a.mbid NOT LIKE 'PENDING-%'
              AND a.lidarr_imported_at IS NULL
              AND st.id = ?
            GROUP BY a.mbid, a.name
            HAVING total_plays >= ?
            ORDER BY {}
        """.format(order_by)
        cursor.execute(query, (station_id, min_plays))
    else:
        query = """
            SELECT DISTINCT
                a.mbid,
                a.name,
                SUM(spd.play_count) as total_plays
            FROM artists a
            JOIN songs s ON a.mbid = s.artist_mbid
            JOIN song_plays_daily spd ON s.id = spd.song_id
            WHERE a.mbid IS NOT NULL
              AND a.mbid NOT LIKE 'PENDING-%'
              AND a.lidarr_imported_at IS NULL
            GROUP BY a.mbid, a.name
            HAVING total_plays >= ?
            ORDER BY {}
        """.format(order_by)
        cursor.execute(query, (min_plays,))

    columns = ['mbid', 'name', 'total_plays']
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_artists_paginated(cursor, page=1, limit=50, filters=None, sort='name', direction='asc'):
    """Get paginated list of artists with filtering and sorting

    Args:
        cursor: SQLite cursor object
        page: Page number (1-indexed)
        limit: Items per page
        filters: Dict with filter values (search, needs_import, station_id, first_seen_after, last_seen_after, total_plays_min, total_plays_max)
        sort: Sort field ('name', 'song_count', 'total_plays', 'last_seen', 'first_seen')
        direction: Sort direction ('asc' or 'desc')

    Returns:
        Dict with keys: items, total, page, pages, limit
    """
    offset = (page - 1) * limit

    # Build WHERE clause (non-aggregate filters only)
    conditions = []
    having_conditions = []  # For aggregate filters like total_plays
    params = []

    if filters:
        if filters.get('search'):
            conditions.append("a.name LIKE ?")
            params.append(f"%{filters['search']}%")

        if filters.get('needs_import') == 'only':
            conditions.append("a.needs_lidarr_import = 1")
        elif filters.get('needs_import') == 'imported':
            conditions.append("a.lidarr_imported_at IS NOT NULL")

        if filters.get('station_id'):
            conditions.append("a.first_seen_station = ?")
            params.append(filters['station_id'])

        # These are aggregate filters - need HAVING clause with full expression
        if filters.get('total_plays_min'):
            having_conditions.append("COALESCE(SUM(s.play_count), 0) >= ?")
            params.append(int(filters['total_plays_min']))

        if filters.get('total_plays_max'):
            having_conditions.append("COALESCE(SUM(s.play_count), 0) <= ?")
            params.append(int(filters['total_plays_max']))

        if filters.get('first_seen_after'):
            conditions.append("a.first_seen_at >= ?")
            params.append(filters['first_seen_after'])

        if filters.get('last_seen_after'):
            conditions.append("a.last_seen_at >= ?")
            params.append(filters['last_seen_after'])

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
    having_clause = "HAVING " + " AND ".join(having_conditions) if having_conditions else ""

    # Build ORDER BY clause dynamically based on sort and direction
    # Map sort parameter to database column
    sort_column_mapping = {
        'name': 'a.name',
        'song_count': 'song_count',
        'total_plays': 'total_plays',
        'last_seen': 'a.last_seen_at',
        'first_seen': 'a.first_seen_at'
    }

    # Get column name (default to name)
    sort_column = sort_column_mapping.get(sort, 'a.name')

    # Build ORDER BY clause with direction
    # Use COLLATE NOCASE for case-insensitive text sorting
    if sort in ['name']:
        order_by = f"{sort_column} COLLATE NOCASE {direction.upper()}"
    else:
        order_by = f"{sort_column} {direction.upper()}"

    # Check if we need to join songs table for filtering/aggregation
    needs_song_join = (
        filters and (
            filters.get('total_plays_min') or
            filters.get('total_plays_max') or
            sort == 'total_plays' or
            sort == 'song_count'
        )
    )

    # Get total count
    if needs_song_join:
        # Need JOIN for total_plays filter/sort - use subquery to count filtered results
        count_query = f"""
            SELECT COUNT(*) FROM (
                SELECT a.mbid
                FROM artists a
                LEFT JOIN songs s ON a.mbid = s.artist_mbid
                {where_clause}
                GROUP BY a.mbid
                {having_clause}
            )
        """
    else:
        # Simple count without JOIN
        count_query = f"""
            SELECT COUNT(DISTINCT a.mbid)
            FROM artists a
            {where_clause}
        """
    cursor.execute(count_query, params)
    total = cursor.fetchone()[0]

    # Get paginated results
    query = f"""
        SELECT
            a.mbid,
            a.name,
            a.first_seen_station,
            a.first_seen_at,
            a.last_seen_at,
            a.needs_lidarr_import,
            a.lidarr_imported_at,
            COALESCE(SUM(s.play_count), 0) as total_plays,
            COUNT(s.id) as song_count
        FROM artists a
        LEFT JOIN songs s ON a.mbid = s.artist_mbid
        {where_clause}
        GROUP BY a.mbid
        {having_clause}
        ORDER BY {order_by}
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])
    cursor.execute(query, params)

    columns = ['mbid', 'name', 'first_seen_station',
               'first_seen_at', 'last_seen_at', 'needs_lidarr_import',
               'lidarr_imported_at', 'total_plays', 'song_count']
    items = [dict(zip(columns, row)) for row in cursor.fetchall()]

    # Capitalize artist names properly
    for item in items:
        item['name'] = capitalize_name_properly(item['name'])

    # Get stations for each artist
    for item in items:
        # Get all stations where this artist's songs have been played
        cursor.execute("""
            SELECT DISTINCT st.id, st.name
            FROM song_plays_daily spd
            JOIN stations st ON spd.station_id = st.id
            JOIN songs s ON spd.song_id = s.id
            WHERE s.artist_mbid = ?
            ORDER BY st.name
        """, (item['mbid'],))

        stations = cursor.fetchall()
        item['stations'] = [{'id': s[0], 'name': s[1]} for s in stations]
        item['station_names'] = ', '.join([s[1] for s in stations])

    return {
        'items': items,
        'total': total,
        'page': page,
        'pages': (total + limit - 1) // limit,
        'limit': limit
    }


def get_artist_detail(cursor, mbid):
    """Get detailed artist information

    Args:
        cursor: SQLite cursor object
        mbid: Artist MusicBrainz ID

    Returns:
        Dict with artist details or None
    """
    cursor.execute("""
        SELECT
            a.mbid,
            a.name,
            a.first_seen_station,
            st.name as station_name,
            a.first_seen_at,
            a.last_seen_at,
            a.needs_lidarr_import,
            a.lidarr_imported_at,
            COALESCE(SUM(s.play_count), 0) as total_plays,
            COUNT(DISTINCT s.id) as song_count
        FROM artists a
        LEFT JOIN stations st ON a.first_seen_station = st.id
        LEFT JOIN songs s ON a.mbid = s.artist_mbid
        WHERE a.mbid = ?
        GROUP BY a.mbid
    """, (mbid,))

    row = cursor.fetchone()
    if not row:
        return None

    columns = ['mbid', 'name', 'first_seen_station', 'station_name',
               'first_seen_at', 'last_seen_at', 'needs_lidarr_import',
               'lidarr_imported_at', 'total_plays', 'song_count']
    return dict(zip(columns, row))


def get_artist_songs(cursor, mbid, limit=50):
    """Get songs by artist with play counts

    Args:
        cursor: SQLite cursor object
        mbid: Artist MusicBrainz ID
        limit: Maximum songs to return

    Returns:
        List of song dicts
    """
    cursor.execute("""
        SELECT
            s.id,
            s.song_title,
            s.play_count,
            s.first_seen_at,
            s.last_seen_at
        FROM songs s
        WHERE s.artist_mbid = ?
        ORDER BY s.play_count DESC
        LIMIT ?
    """, (mbid, limit))

    columns = ['id', 'song_title', 'play_count', 'first_seen_at', 'last_seen_at']
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_artist_play_history(cursor, mbid, days=30):
    """Get artist play history over time

    Args:
        cursor: SQLite cursor object
        mbid: Artist MusicBrainz ID
        days: Number of days to look back

    Returns:
        List of dicts with date, play_count, station_name
    """
    cursor.execute("""
        SELECT
            spd.date,
            SUM(spd.play_count) as play_count,
            st.name as station_name
        FROM song_plays_daily spd
        JOIN songs s ON spd.song_id = s.id
        LEFT JOIN stations st ON spd.station_id = st.id
        WHERE s.artist_mbid = ?
          AND spd.date >= date('now', '-' || ? || ' days')
        GROUP BY spd.date, st.id
        ORDER BY spd.date DESC
    """, (mbid, days))

    columns = ['date', 'play_count', 'station_name']
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


# ==================== SONG PAGINATION QUERIES ====================

def get_songs_paginated(cursor, page=1, limit=50, filters=None, sort='title', direction='asc'):
    """Get paginated list of songs with filtering and sorting

    Args:
        cursor: SQLite cursor object
        page: Page number (1-indexed)
        limit: Items per page
        filters: Dict with filter values (search, artist_name, station_id, last_seen_after, last_seen_before, plays_min, plays_max)
        sort: Sort field ('title', 'artist_name', 'play_count', 'last_seen')
        direction: Sort direction ('asc' or 'desc')

    Returns:
        Dict with keys: items, total, page, pages, limit
    """
    offset = (page - 1) * limit

    # Build WHERE clause
    conditions = []
    params = []

    if filters:
        if filters.get('search'):
            conditions.append("(s.song_title LIKE ? OR s.artist_name LIKE ?)")
            params.extend([f"%{filters['search']}%", f"%{filters['search']}%"])

        if filters.get('artist_name'):
            conditions.append("s.artist_name = ?")
            params.append(filters['artist_name'])

        if filters.get('station_id'):
            conditions.append("EXISTS (SELECT 1 FROM song_plays_daily spd WHERE spd.song_id = s.id AND spd.station_id = ?)")
            params.append(filters['station_id'])

        if filters.get('plays_min'):
            conditions.append("s.play_count >= ?")
            params.append(int(filters['plays_min']))

        if filters.get('plays_max'):
            conditions.append("s.play_count <= ?")
            params.append(int(filters['plays_max']))

        if filters.get('last_seen_after'):
            conditions.append("s.last_seen_at >= ?")
            params.append(filters['last_seen_after'])

        if filters.get('last_seen_before'):
            conditions.append("s.last_seen_at <= ?")
            params.append(filters['last_seen_before'])

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    # Build ORDER BY clause dynamically based on sort and direction
    # Map sort parameter to database column
    sort_column_mapping = {
        'title': 's.song_title',
        'artist_name': 's.artist_name',
        'play_count': 's.play_count',
        'last_seen': 's.last_seen_at'
    }

    # Get column name (default to song_title)
    sort_column = sort_column_mapping.get(sort, 's.song_title')

    # Build ORDER BY clause with direction
    # Use COLLATE NOCASE for case-insensitive text sorting
    if sort in ['title', 'artist_name']:
        order_by = f"{sort_column} COLLATE NOCASE {direction.upper()}"
    else:
        order_by = f"{sort_column} {direction.upper()}"

    # Get total count
    count_query = f"""
        SELECT COUNT(DISTINCT s.id)
        FROM songs s
        {where_clause}
    """
    cursor.execute(count_query, params)
    total = cursor.fetchone()[0]

    # Get paginated results
    query = f"""
        SELECT
            s.id,
            s.song_title,
            s.artist_name,
            a.mbid as artist_mbid,
            a.lidarr_imported_at,
            s.play_count,
            s.first_seen_at,
            s.last_seen_at
        FROM songs s
        LEFT JOIN artists a ON s.artist_mbid = a.mbid
        {where_clause}
        ORDER BY {order_by}
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])
    cursor.execute(query, params)

    columns = ['id', 'song_title', 'artist_name', 'artist_mbid', 'lidarr_imported_at',
               'play_count', 'first_seen_at', 'last_seen_at']
    items = [dict(zip(columns, row)) for row in cursor.fetchall()]

    # Capitalize artist names properly
    for item in items:
        item['artist_name'] = capitalize_name_properly(item['artist_name'])

    # Get stations for each song
    for item in items:
        # Get all stations where this song has been played
        cursor.execute("""
            SELECT DISTINCT st.id, st.name
            FROM song_plays_daily spd
            JOIN stations st ON spd.station_id = st.id
            WHERE spd.song_id = ?
            ORDER BY st.name
        """, (item['id'],))

        stations = cursor.fetchall()
        item['stations'] = [{'id': s[0], 'name': s[1]} for s in stations]
        item['station_names'] = ', '.join([s[1] for s in stations])

    return {
        'items': items,
        'total': total,
        'page': page,
        'pages': (total + limit - 1) // limit,
        'limit': limit
    }


def get_song_detail(cursor, song_id):
    """Get detailed song information

    Args:
        cursor: SQLite cursor object
        song_id: Song ID

    Returns:
        Dict with song details or None
    """
    # First, get the first station where this song was played
    cursor.execute("""
        SELECT sp.station_id, st.name as station_name
        FROM song_plays_daily sp
        LEFT JOIN stations st ON sp.station_id = st.id
        WHERE sp.song_id = ?
        ORDER BY sp.date ASC, sp.hour ASC, sp.minute ASC
        LIMIT 1
    """, (song_id,))

    first_play = cursor.fetchone()
    first_station_id = first_play[0] if first_play else None
    first_station_name = first_play[1] if first_play else None

    # Now get song details
    cursor.execute("""
        SELECT
            s.id,
            s.song_title,
            s.artist_name,
            a.mbid as artist_mbid,
            a.name as artist_name_canonical,
            s.play_count,
            s.first_seen_at,
            s.last_seen_at,
            a.lidarr_imported_at
        FROM songs s
        LEFT JOIN artists a ON s.artist_mbid = a.mbid
        WHERE s.id = ?
    """, (song_id,))

    row = cursor.fetchone()
    if not row:
        return None

    columns = ['id', 'song_title', 'artist_name', 'artist_mbid',
               'artist_name_canonical', 'play_count', 'first_seen_at',
               'last_seen_at', 'lidarr_imported_at']
    result = dict(zip(columns, row))

    # Add first station info separately
    result['first_seen_station'] = first_station_id
    result['station_name'] = first_station_name

    return result


def get_song_play_history(cursor, song_id, days=30):
    """Get song play history over time

    Args:
        cursor: SQLite cursor object
        song_id: Song ID
        days: Number of days to look back

    Returns:
        List of dicts with date, play_count, station_name
    """
    cursor.execute("""
        SELECT
            spd.date,
            SUM(spd.play_count) as play_count,
            st.name as station_name
        FROM song_plays_daily spd
        LEFT JOIN stations st ON spd.station_id = st.id
        WHERE spd.song_id = ?
          AND spd.date >= date('now', '-' || ? || ' days')
        GROUP BY spd.date, st.id
        ORDER BY spd.date DESC
    """, (song_id, days))

    columns = ['date', 'play_count', 'station_name']
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


# ==================== STATION DETAIL QUERIES ====================

def get_station_detail(cursor, station_id):
    """Get detailed station information with stats

    Args:
        cursor: SQLite cursor object
        station_id: Station ID

    Returns:
        Dict with station details and stats or None
    """
    cursor.execute("""
        SELECT
            s.id,
            s.name,
            s.url,
            s.genre,
            s.market,
            s.has_mbid,
            s.scraper_type,
            s.enabled,
            s.consecutive_failures,
            s.last_failure_at,
            s.created_at,
            COUNT(DISTINCT a.mbid) as artist_count,
            COUNT(DISTINCT sp.song_id) as song_count,
            COALESCE(SUM(sp.play_count), 0) as total_plays
        FROM stations s
        LEFT JOIN artists a ON a.first_seen_station = s.id
        LEFT JOIN song_plays_daily sp ON sp.station_id = s.id
        WHERE s.id = ?
        GROUP BY s.id
    """, (station_id,))

    row = cursor.fetchone()
    if not row:
        return None

    columns = ['id', 'name', 'url', 'genre', 'market', 'has_mbid',
               'scraper_type', 'enabled', 'consecutive_failures',
               'last_failure_at', 'created_at', 'artist_count',
               'song_count', 'total_plays']
    return dict(zip(columns, row))


def get_station_stats(cursor, station_id, days=30):
    """Get station statistics for a time period

    Args:
        cursor: SQLite cursor object
        station_id: Station ID
        days: Number of days to look back

    Returns:
        Dict with station statistics
    """
    cursor.execute("""
        SELECT
            COUNT(DISTINCT sp.song_id) as unique_songs,
            COUNT(DISTINCT s.artist_mbid) as unique_artists,
            SUM(sp.play_count) as total_plays
        FROM song_plays_daily sp
        JOIN songs s ON sp.song_id = s.id
        WHERE sp.station_id = ?
          AND sp.date >= date('now', '-' || ? || ' days')
    """, (station_id, days))

    row = cursor.fetchone()
    if not row:
        return {'unique_songs': 0, 'unique_artists': 0, 'total_plays': 0}

    return {
        'unique_songs': row[0] or 0,
        'unique_artists': row[1] or 0,
        'total_plays': row[2] or 0
    }


def get_station_top_songs(cursor, station_id, limit=50, days=30):
    """Get top songs for a station

    Args:
        cursor: SQLite cursor object
        station_id: Station ID
        limit: Maximum songs to return
        days: Number of days to look back

    Returns:
        List of song dicts
    """
    cursor.execute("""
        SELECT
            s.song_title,
            s.artist_name,
            SUM(sp.play_count) as play_count,
            MAX(sp.date) as last_seen
        FROM song_plays_daily sp
        JOIN songs s ON sp.song_id = s.id
        WHERE sp.station_id = ?
          AND sp.date >= date('now', '-' || ? || ' days')
        GROUP BY s.id
        ORDER BY play_count DESC
        LIMIT ?
    """, (station_id, days, limit))

    columns = ['song_title', 'artist_name', 'play_count', 'last_seen']
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


# ==================== SONG QUERIES ====================

def get_song_by_id(cursor, song_id):
    """Get song by ID

    Args:
        cursor: SQLite cursor object
        song_id: Song ID

    Returns:
        Song dict or None
    """
    cursor.execute("SELECT * FROM songs WHERE id = ?", (song_id,))
    row = cursor.fetchone()

    if row:
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))
    return None


def get_all_songs(cursor, station_id=None):
    """Get all songs for export (legacy compatibility)

    Args:
        cursor: SQLite cursor object
        station_id: Filter by station (None = all)

    Returns:
        List of tuples with song details
    """
    if station_id:
        cursor.execute("""
            SELECT s.artist_name, s.song_title, a.mbid as artist_mbid, s.play_count,
                   a.first_seen_at, a.last_seen_at, ?
            FROM songs s
            LEFT JOIN artists a ON s.artist_mbid = a.mbid
            WHERE s.artist_mbid IN (
                SELECT DISTINCT mbid FROM artists WHERE first_seen_station = ?
            )
            ORDER BY s.id DESC
        """, (station_id, station_id))
    else:
        cursor.execute("""
            SELECT s.artist_name, s.song_title, a.mbid as artist_mbid, s.play_count,
                   a.first_seen_at, a.last_seen_at, 'all'
            FROM songs s
            LEFT JOIN artists a ON s.artist_mbid = a.mbid
            ORDER BY s.id DESC
        """)

    return cursor.fetchall()


def get_top_songs(cursor, days=None, station_id=None, station_ids=None, limit=50):
    """Get top songs by play count

    Args:
        cursor: SQLite cursor object
        days: Only include plays from last N days (None = all time)
        station_id: Filter by single station (None = all stations)
        station_ids: Filter by multiple stations (None = all stations)
        limit: Maximum number of results

    Returns:
        List of tuples: (song_id, song_title, artist_name, play_count)
    """
    # Handle backward compatibility - if station_id is provided, convert to station_ids
    if station_id and not station_ids:
        station_ids = [station_id]

    if days and station_ids:
        # Build IN clause for multiple stations
        placeholders = ','.join(['?' for _ in station_ids])
        cursor.execute(f"""
            SELECT s.id, s.song_title, s.artist_name, SUM(d.play_count) as total_plays
            FROM song_plays_daily d
            JOIN songs s ON d.song_id = s.id
            WHERE d.station_id IN ({placeholders})
              AND d.date >= DATE('now', '-' || ? || ' days')
            GROUP BY s.id
            ORDER BY total_plays DESC
            LIMIT ?
        """, station_ids + [days, limit])
    elif days:
        cursor.execute("""
            SELECT s.id, s.song_title, s.artist_name, SUM(d.play_count) as total_plays
            FROM song_plays_daily d
            JOIN songs s ON d.song_id = s.id
            WHERE d.date >= DATE('now', '-' || ? || ' days')
            GROUP BY s.id
            ORDER BY total_plays DESC
            LIMIT ?
        """, (days, limit))
    elif station_ids:
        # For multiple stations without days filter
        # Aggregate plays from song_plays_daily for all selected stations
        placeholders = ','.join(['?' for _ in station_ids])
        cursor.execute(f"""
            SELECT s.id, s.song_title, s.artist_name, SUM(d.play_count) as total_plays
            FROM song_plays_daily d
            JOIN songs s ON d.song_id = s.id
            WHERE d.station_id IN ({placeholders})
            GROUP BY s.id
            ORDER BY total_plays DESC
            LIMIT ?
        """, station_ids + [limit])
    elif station_id:
        # Backward compatibility - single station without days
        cursor.execute("""
            SELECT id, song_title, artist_name, play_count
            FROM songs
            WHERE artist_mbid IN (
                SELECT DISTINCT mbid FROM artists WHERE first_seen_station = ?
            )
            ORDER BY play_count DESC
            LIMIT ?
        """, (station_id, limit))
    else:
        cursor.execute("""
            SELECT id, song_title, artist_name, play_count
            FROM songs
            ORDER BY play_count DESC
            LIMIT ?
        """, (limit,))

    return cursor.fetchall()


def get_recent_songs(cursor, days=None, station_ids=None, limit=50):
    """Get most recently played songs (ordered by last_seen_at)

    Args:
        cursor: SQLite cursor object
        days: Only include plays from last N days (None = all time)
        station_ids: Filter by multiple stations (None = all stations)
        limit: Maximum number of results

    Returns:
        List of tuples: (song_id, song_title, artist_name, play_count)
    """
    if days and station_ids:
        # Build IN clause for multiple stations
        placeholders = ','.join(['?' for _ in station_ids])
        cursor.execute(f"""
            SELECT s.id, s.song_title, s.artist_name, s.play_count
            FROM songs s
            JOIN song_plays_daily d ON d.song_id = s.id
            WHERE d.station_id IN ({placeholders})
              AND s.last_seen_at >= datetime('now', '-' || ? || ' days')
            GROUP BY s.id
            ORDER BY s.last_seen_at DESC
            LIMIT ?
        """, station_ids + [days, limit])
    elif days:
        cursor.execute("""
            SELECT s.id, s.song_title, s.artist_name, s.play_count
            FROM songs s
            WHERE s.last_seen_at >= datetime('now', '-' || ? || ' days')
            ORDER BY s.last_seen_at DESC
            LIMIT ?
        """, (days, limit))
    elif station_ids:
        # Build IN clause for multiple stations
        placeholders = ','.join(['?' for _ in station_ids])
        cursor.execute(f"""
            SELECT s.id, s.song_title, s.artist_name, s.play_count
            FROM songs s
            JOIN song_plays_daily d ON d.song_id = s.id
            WHERE d.station_id IN ({placeholders})
            GROUP BY s.id
            ORDER BY s.last_seen_at DESC
            LIMIT ?
        """, station_ids + [limit])
    else:
        cursor.execute("""
            SELECT id, song_title, artist_name, play_count
            FROM songs
            ORDER BY last_seen_at DESC
            LIMIT ?
        """, (limit,))

    return cursor.fetchall()


def get_top_artists(cursor, days=None, station_ids=None, limit=50):
    """Get top artists by play count

    Args:
        cursor: SQLite cursor object
        days: Only include plays from last N days (None = all time)
        station_ids: Filter by multiple stations (None = all stations)
        limit: Maximum number of results

    Returns:
        List of tuples: (artist_name, play_count)
    """
    if days and station_ids:
        # Build IN clause for multiple stations
        placeholders = ','.join(['?' for _ in station_ids])
        cursor.execute(f"""
            SELECT s.artist_name, SUM(d.play_count) as total_plays
            FROM song_plays_daily d
            JOIN songs s ON d.song_id = s.id
            WHERE d.station_id IN ({placeholders})
              AND d.date >= DATE('now', '-' || ? || ' days')
            GROUP BY s.artist_name
            ORDER BY total_plays DESC
            LIMIT ?
        """, station_ids + [days, limit])
    elif days:
        cursor.execute("""
            SELECT s.artist_name, SUM(d.play_count) as total_plays
            FROM song_plays_daily d
            JOIN songs s ON d.song_id = s.id
            WHERE d.date >= DATE('now', '-' || ? || ' days')
            GROUP BY s.artist_name
            ORDER BY total_plays DESC
            LIMIT ?
        """, (days, limit))
    elif station_ids:
        # For multiple stations without days filter
        placeholders = ','.join(['?' for _ in station_ids])
        cursor.execute(f"""
            SELECT s.artist_name, SUM(d.play_count) as total_plays
            FROM song_plays_daily d
            JOIN songs s ON d.song_id = s.id
            WHERE d.station_id IN ({placeholders})
            GROUP BY s.artist_name
            ORDER BY total_plays DESC
            LIMIT ?
        """, station_ids + [limit])
    else:
        # All time, all stations
        cursor.execute("""
            SELECT artist_name, play_count
            FROM songs
            GROUP BY artist_name
            ORDER BY play_count DESC
            LIMIT ?
        """, (limit,))

    return cursor.fetchall()


def get_trending_songs(cursor, days=90):
    """Get trending songs (recent plays vs older plays)

    Args:
        cursor: SQLite cursor object
        days: Number of recent days to compare

    Returns:
        List of tuples: (song_title, artist_name, recent_plays, older_plays, growth)
    """
    cursor.execute(f"""
        SELECT s.song_title, s.artist_name,
               SUM(CASE WHEN d.date >= DATE('now', '-{days} days')
                   THEN d.play_count ELSE 0 END) as recent,
               SUM(CASE WHEN d.date >= DATE('now', '-{days*2} days')
                      AND d.date < DATE('now', '-{days} days')
                   THEN d.play_count ELSE 0 END) as older
        FROM song_plays_daily d
        JOIN songs s ON d.song_id = s.id
        WHERE d.date >= DATE('now', '-{days*2} days')
        GROUP BY s.id
        HAVING recent > older
        ORDER BY (recent - older) DESC
    """)

    results = []
    for row in cursor.fetchall():
        song_title, artist_name, recent, older = row
        growth = recent - older
        results.append((song_title, artist_name, recent, older, growth))

    return results


def get_recent_plays(cursor, limit=10, station_id=None):
    """Get recent plays for dashboard live feed

    Joins: song_plays_daily → songs → artists → stations
    Orders by most recent

    Args:
        cursor: SQLite cursor object
        limit: Maximum number of plays to return (default: 10)
        station_id: Filter by specific station ID (default: None = all stations)

    Returns:
        List of dicts with keys: timestamp, artist_name, song_title, station_name, station_id
    """
    # Build query with optional station filter
    if station_id:
        query = """
            SELECT
                datetime(sp.date || ' ' ||
                       printf('%02d:%02d:00', sp.hour, COALESCE(sp.minute, 0))) as timestamp,
                a.name as artist_name,
                s.song_title,
                st.name as station_name,
                st.id as station_id
            FROM song_plays_daily sp
            JOIN songs s ON sp.song_id = s.id
            JOIN artists a ON s.artist_mbid = a.mbid
            LEFT JOIN stations st ON sp.station_id = st.id
            WHERE sp.station_id = ?
            ORDER BY sp.date DESC, sp.hour DESC
            LIMIT ?
        """
        params = (station_id, limit)
    else:
        query = """
            SELECT
                datetime(sp.date || ' ' ||
                       printf('%02d:%02d:00', sp.hour, COALESCE(sp.minute, 0))) as timestamp,
                a.name as artist_name,
                s.song_title,
                st.name as station_name,
                st.id as station_id
            FROM song_plays_daily sp
            JOIN songs s ON sp.song_id = s.id
            JOIN artists a ON s.artist_mbid = a.mbid
            LEFT JOIN stations st ON sp.station_id = st.id
            ORDER BY sp.date DESC, sp.hour DESC
            LIMIT ?
        """
        params = (limit,)

    cursor.execute(query, params)

    columns = ['timestamp', 'artist_name', 'song_title', 'station_name', 'station_id']
    results = [dict(zip(columns, row)) for row in cursor.fetchall()]
    return results


# ==================== STATISTICS QUERIES ====================

def get_statistics(cursor):
    """Get database statistics

    Args:
        cursor: SQLite cursor object

    Returns:
        Dict with: total_artists, total_songs, total_plays, plays_today
    """
    cursor.execute("SELECT COUNT(*) FROM artists")
    total_artists = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM songs")
    total_songs = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(play_count) FROM songs")
    total_plays = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT COALESCE(SUM(play_count), 0)
        FROM song_plays_daily
        WHERE date = DATE('now', 'localtime')
    """)
    plays_today = cursor.fetchone()[0]

    return {
        'total_artists': total_artists,
        'total_songs': total_songs,
        'total_plays': total_plays,
        'plays_today': plays_today
    }


def get_dashboard_stats(cursor):
    """Alias for get_statistics (for GUI compatibility)

    Args:
        cursor: SQLite cursor object

    Returns:
        Dict with database statistics
    """
    return get_statistics(cursor)


def get_daily_plays_chart_data(cursor, days=30, station_id=None):
    """Get play counts over time for line chart

    Args:
        cursor: SQLite cursor object
        days: Number of days to look back (default: 30)
        station_id: Filter by specific station (optional)

    Returns:
        List of dicts with date and total_plays
    """
    if station_id:
        cursor.execute("""
            SELECT date, SUM(play_count) as total_plays
            FROM song_plays_daily
            WHERE station_id = ?
              AND date >= date('now', '-' || ? || ' days')
            GROUP BY date
            ORDER BY date ASC
        """, (station_id, days))
    else:
        cursor.execute("""
            SELECT date, SUM(play_count) as total_plays
            FROM song_plays_daily
            WHERE date >= date('now', '-' || ? || ' days')
            GROUP BY date
            ORDER BY date ASC
        """, (days,))

    columns = ['date', 'total_plays']
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_hourly_plays_chart_data(cursor):
    """Get hourly play distribution for heat map

    Args:
        cursor: SQLite cursor object

    Returns:
        List of dicts with hour, day, and play_count
    """
    cursor.execute("""
        SELECT
            strftime('%w', date) as day_of_week,
            hour,
            SUM(play_count) as total_plays
        FROM song_plays_daily
        WHERE date >= date('now', '-7 days')
        GROUP BY day_of_week, hour
        ORDER BY day_of_week, hour
    """)

    columns = ['day_of_week', 'hour', 'total_plays']
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_plays_over_time(cursor, days=30, station_id=None):
    """Alias for get_daily_plays_chart_data

    Args:
        cursor: SQLite cursor object
        days: Number of days to look back (default: 30)
        station_id: Filter by specific station (optional)

    Returns:
        List of dicts with date and total_plays
    """
    return get_daily_plays_chart_data(cursor, days, station_id)


def get_station_distribution(cursor, days=None):
    """Get play distribution by station for pie chart

    Args:
        cursor: SQLite cursor object
        days: Number of days to look back (None = all time)

    Returns:
        List of dicts with station_name and play_count
    """
    if days:
        cursor.execute("""
            SELECT st.name, SUM(spd.play_count) as play_count
            FROM song_plays_daily spd
            JOIN songs s ON spd.song_id = s.id
            JOIN stations st ON spd.station_id = st.id
            WHERE spd.date >= DATE('now', '-' || ? || ' days')
            GROUP BY st.id, st.name
            ORDER BY play_count DESC
        """, (days,))
    else:
        cursor.execute("""
            SELECT st.name, SUM(spd.play_count) as play_count
            FROM song_plays_daily spd
            JOIN songs s ON spd.song_id = s.id
            JOIN stations st ON spd.station_id = st.id
            GROUP BY st.id, st.name
            ORDER BY play_count DESC
        """)

    columns = ['station_name', 'play_count']
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


# ==================== PLAYLIST QUERIES ====================

def get_playlist(cursor, playlist_id):
    """Get single playlist by ID (manual or auto)

    Args:
        cursor: SQLite cursor object
        playlist_id: Playlist ID

    Returns:
        Dict with playlist details or None
    """
    import json

    cursor.execute("""
        SELECT
            id, name, is_auto, interval_minutes, station_ids, max_songs, mode,
            min_plays, max_plays, days, enabled, last_updated, next_update,
            plex_playlist_name, consecutive_failures, created_at
        FROM playlists
        WHERE id = ?
    """, (playlist_id,))

    row = cursor.fetchone()
    if not row:
        return None

    return {
        'id': row[0],
        'name': row[1],
        'is_auto': bool(row[2]),
        'interval_minutes': row[3],
        'station_ids': json.loads(row[4]),
        'max_songs': row[5],
        'mode': row[6],
        'min_plays': row[7],
        'max_plays': row[8],
        'days': row[9],
        'enabled': bool(row[10]),
        'last_updated': row[11],
        'next_update': row[12],
        'plex_playlist_name': row[13],
        'consecutive_failures': row[14],
        'created_at': row[15]
    }


def get_playlists(cursor):
    """Get all playlists (manual and auto)

    Args:
        cursor: SQLite cursor object

    Returns:
        List of dicts with playlist details
    """
    import json

    cursor.execute("""
        SELECT
            id, name, is_auto, interval_minutes, station_ids, max_songs, mode,
            min_plays, max_plays, days, enabled, last_updated, next_update,
            plex_playlist_name, consecutive_failures, created_at
        FROM playlists
        ORDER BY created_at DESC
    """)

    playlists = []
    for row in cursor.fetchall():
        playlist = {
            'id': row[0],
            'name': row[1],
            'is_auto': bool(row[2]),
            'interval_minutes': row[3],
            'station_ids': json.loads(row[4]),
            'max_songs': row[5],
            'mode': row[6],
            'min_plays': row[7],
            'max_plays': row[8],
            'days': row[9],
            'enabled': bool(row[10]),
            'last_updated': row[11],
            'next_update': row[12],
            'plex_playlist_name': row[13],
            'consecutive_failures': row[14],
            'created_at': row[15]
        }
        playlists.append(playlist)

    return playlists


def get_due_playlists(cursor):
    """Get auto playlists that need updating

    Args:
        cursor: SQLite cursor object

    Returns:
        List of auto playlist dicts that are due for update
    """
    import json

    cursor.execute("""
        SELECT
            id, name, interval_minutes, station_ids, max_songs, mode,
            min_plays, max_plays, days, plex_playlist_name
        FROM playlists
        WHERE enabled = 1
          AND is_auto = 1
          AND next_update <= ?
        ORDER BY next_update ASC
    """, (datetime.now(),))

    playlists = []
    for row in cursor.fetchall():
        playlists.append({
            'id': row[0],
            'name': row[1],
            'interval_minutes': row[2],
            'station_ids': json.loads(row[3]),
            'max_songs': row[4],
            'mode': row[5],
            'min_plays': row[6],
            'max_plays': row[7],
            'days': row[8],
            'plex_playlist_name': row[9]
        })

    return playlists


def get_random_songs(cursor, station_ids=None, min_plays=1, max_plays=None, days=None, limit=50):
    """Get random songs from filtered results

    Args:
        cursor: SQLite cursor object
        station_ids: Filter by stations (None = all)
        min_plays: Minimum play count (default: 1)
        max_plays: Maximum play count (NULL = no maximum)
        days: Only include songs from last N days (NULL = all time)
        limit: Maximum songs to return

    Returns:
        List of tuples: (song_id, song_title, artist_name, play_count)
    """
    # Build query components
    conditions = []
    params = []

    # Station filter
    if station_ids:
        placeholders = ','.join(['?' for _ in station_ids])
        conditions.append(f"d.station_id IN ({placeholders})")
        params.extend(station_ids)

    # Days filter
    if days:
        conditions.append("s.last_seen_at >= datetime('now', '-' || ? || ' days')")
        params.append(days)

    # Build WHERE clause
    where_clause = " AND ".join(conditions) if conditions else "1=1"

    # Build HAVING clause for play count range
    having_clause = "HAVING total_plays >= ?"
    params.append(min_plays)

    if max_plays is not None:
        having_clause += " AND total_plays <= ?"
        params.append(max_plays)

    # Build complete query
    query = f"""
        SELECT s.id, s.song_title, s.artist_name, SUM(d.play_count) as total_plays
        FROM song_plays_daily d
        JOIN songs s ON d.song_id = s.id
        WHERE {where_clause}
        GROUP BY s.id
        {having_clause}
        ORDER BY RANDOM()
        LIMIT ?
    """
    params.append(limit)

    cursor.execute(query, params)
    return cursor.fetchall()


def get_ai_playlist_songs(cursor, station_ids=None, min_plays=1, first_seen=None, last_seen=None):
    """Get songs for AI playlist generation

    Args:
        cursor: SQLite cursor object
        station_ids: Filter by stations (None or empty list = all stations)
        min_plays: Minimum play count (default: 1)
        first_seen: First seen date filter (ISO format string, e.g., "2026-01-01")
        last_seen: Last seen date filter (ISO format string, e.g., "2026-02-16")

    Returns:
        List of tuples: (artist_name, song_title) - suitable for AI consumption
    """
    # Build query components
    conditions = []
    params = []

    # Station filter (empty list or None = all stations)
    if station_ids:
        placeholders = ','.join(['?' for _ in station_ids])
        conditions.append(f"d.station_id IN ({placeholders})")
        params.extend(station_ids)

    # First seen filter
    if first_seen:
        conditions.append("DATE(s.first_seen_at) >= ?")
        params.append(first_seen)

    # Last seen filter
    if last_seen:
        conditions.append("DATE(s.last_seen_at) <= ?")
        params.append(last_seen)

    # Build WHERE clause
    where_clause = " AND ".join(conditions) if conditions else "1=1"

    # Build query with play count filter
    query = f"""
        SELECT DISTINCT
            s.artist_name,
            s.song_title
        FROM song_plays_daily d
        JOIN songs s ON d.song_id = s.id
        WHERE {where_clause}
        GROUP BY s.id
        HAVING SUM(d.play_count) >= ?
        ORDER BY s.artist_name COLLATE NOCASE, s.song_title COLLATE NOCASE
    """
    params.append(min_plays)

    cursor.execute(query, params)
    results = cursor.fetchall()

    logger.info(f"AI playlist query returned {len(results)} songs "
                f"(stations={station_ids or 'all'}, min_plays={min_plays}, "
                f"first_seen={first_seen or 'none'}, last_seen={last_seen or 'none'})")

    return results


def format_songs_for_ai(songs):
    """Format song list for AI consumption

    Args:
        songs: List of (artist, song) tuples

    Returns:
        List of strings in "1. Artist: Song" format
    """
    return [f"{i + 1}. {artist}: {song}" for i, (artist, song) in enumerate(songs)]
