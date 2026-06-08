"""
Data Quality Health Check Module

This module provides local-only health checks for the Radio Monitor database.
All checks are performed without API calls to MusicBrainz.

Key Functions:
- run_health_check(): Comprehensive health check
- get_pending_mbid_count(): Count songs with PENDING MBIDs
- get_known_bad_artists(): Find artists needing correction
- get_messy_titles(): Find songs with messy titles
- detect_potential_duplicates(): Find possible duplicate songs

Usage:
    from radio_monitor.data_quality import run_health_check

    issues = run_health_check(db)
    print(f"Found {len(issues)} data quality issues")
"""

import logging
import re
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


def run_health_check(db) -> Dict[str, Any]:
    """Run comprehensive health check on database

    Args:
        db: RadioDatabase instance

    Returns:
        Dict with health check results
    """
    issues = {
        'critical': [],
        'warning': [],
        'info': [],
        'summary': {}
    }

    # Check 1: PENDING MBIDs
    pending = get_pending_mbid_count(db)
    if pending > 0:
        issues['warning'].append({
            'type': 'pending_mbid',
            'count': pending,
            'message': f'{pending} songs with PENDING MBIDs'
        })

    # Check 2: Known bad artist names
    bad_artists = get_known_bad_artists(db)
    if bad_artists:
        issues['critical'].append({
            'type': 'artist_names',
            'count': len(bad_artists),
            'artists': bad_artists,
            'message': f'{len(bad_artists)} songs with known artist name issues'
        })

    # Check 3: Messy song titles
    messy = get_messy_titles(db)
    if messy:
        issues['info'].append({
            'type': 'song_titles',
            'count': len(messy),
            'message': f'{len(messy)} songs with messy titles (parentheticals, etc.)'
        })

    # Check 4: Potential duplicates
    dupes = detect_potential_duplicates(db)
    if dupes:
        issues['warning'].append({
            'type': 'duplicates',
            'count': len(dupes),
            'message': f'{len(dupes)} potential duplicate songs'
        })

    # Summary
    stats = db.get_stats()
    total_songs = stats.get('total_songs', 0)
    issues['summary'] = {
        'total_songs': total_songs,
        'total_issues': sum(len(issues[k]) for k in ['critical', 'warning', 'info']),
        'health_score': calculate_health_score(total_songs, issues)
    }

    return issues


def get_pending_mbid_count(db) -> int:
    """Count songs with PENDING MBIDs

    Args:
        db: RadioDatabase instance

    Returns:
        Number of songs with PENDING MBIDs
    """
    cursor = db.get_cursor()
    try:
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM songs s
            WHERE s.artist_mbid LIKE 'PENDING-%'
        """)
        result = cursor.fetchone()
        return result[0] if result else 0
    finally:
        cursor.close()


def get_known_bad_artists(db) -> List[Dict]:
    """Find songs with known bad artist names

    Args:
        db: RadioDatabase instance

    Returns:
        List of dicts with song info
    """
    from radio_monitor.normalization import ARTIST_NAME_CORRECTIONS

    bad_songs = []
    cursor = db.get_cursor()

    try:
        # Check for each known bad artist
        for bad_name, correct_name in ARTIST_NAME_CORRECTIONS.items():
            cursor.execute("""
                SELECT id, artist_name, song_title, play_count
                FROM songs
                WHERE LOWER(artist_name) = ?
            """, (bad_name,))

            results = cursor.fetchall()
            for row in results:
                bad_songs.append({
                    'song_id': row[0],
                    'current_artist': row[1],
                    'correct_artist': correct_name,
                    'song_title': row[2],
                    'play_count': row[3]
                })
    finally:
        cursor.close()

    return bad_songs


def get_messy_titles(db, limit: int = 100) -> List[Dict]:
    """Find songs with messy titles (parentheticals, features, etc.)

    Args:
        db: RadioDatabase instance
        limit: Maximum number of results (default: 100)

    Returns:
        List of dicts with song info
    """
    from radio_monitor.normalization import clean_song_title_for_query

    messy_songs = []
    cursor = db.get_cursor()

    try:
        # Find titles with parentheticals, brackets, etc.
        cursor.execute("""
            SELECT id, artist_name, song_title, play_count
            FROM songs
            WHERE song_title LIKE '%(%'
               OR song_title LIKE '%[%'
               OR song_title LIKE '%feat%'
               OR song_title LIKE '%ft.%'
               OR song_title LIKE '%featuring%'
            LIMIT ?
        """, (limit,))

        results = cursor.fetchall()
        for row in results:
            original = row[2]  # song_title
            cleaned = clean_song_title_for_query(original)

            messy_songs.append({
                'song_id': row[0],
                'artist_name': row[1],
                'original_title': original,
                'cleaned_title': cleaned,
                'play_count': row[3]
            })
    finally:
        cursor.close()

    return messy_songs


def detect_potential_duplicates(db, limit: int = 50) -> List[Dict]:
    """Detect potential duplicate songs

    Args:
        db: RadioDatabase instance
        limit: Maximum number of results (default: 50)

    Returns:
        List of potential duplicate groups
    """
    duplicates = []
    cursor = db.get_cursor()

    try:
        # Find songs with same artist but very similar titles
        cursor.execute("""
            SELECT s1.id as id1, s1.song_title as title1,
                   s2.id as id2, s2.song_title as title2,
                   s1.artist_name
            FROM songs s1
            JOIN songs s2 ON s1.artist_name = s2.artist_name AND s1.id < s2.id
            WHERE s1.artist_name = s2.artist_name
              AND LENGTH(s1.song_title) > 3
              AND LENGTH(s2.song_title) > 3
            LIMIT ?
        """, (limit,))

        results = cursor.fetchall()
        for row in results:
            # Calculate similarity (indices: id1=0, title1=1, id2=2, title2=3, artist=4)
            title1 = row[1].lower()
            title2 = row[3].lower()

            # Simple similarity check
            if title1 in title2 or title2 in title1 or title1.startswith(title2[:5]):
                duplicates.append({
                    'song_id1': row[0],
                    'song_id2': row[2],
                    'title1': row[1],
                    'title2': row[3],
                    'artist': row[4]
                })
    finally:
        cursor.close()

    return duplicates


def calculate_health_score(total_songs: int, issues: Dict) -> float:
    """Calculate overall health score (0-100)

    Args:
        total_songs: Total number of songs
        issues: Health check issues dict

    Returns:
        Health score (0-100)
    """
    if total_songs == 0:
        return 100.0

    # Count total issues from issue dicts with 'count' field
    critical_count = sum(issue.get('count', 0) for issue in issues.get('critical', []))
    warning_count = sum(issue.get('count', 0) for issue in issues.get('warning', []))
    info_count = sum(issue.get('count', 0) for issue in issues.get('info', []))

    # Calculate weighted score
    total_issues = (critical_count * 10) + (warning_count * 3) + (info_count * 1)

    # Calculate score
    # Start at 100, subtract points for issues
    # But don't go below 0
    score = max(0, 100 - (total_issues / total_songs * 100))

    return round(score, 1)
