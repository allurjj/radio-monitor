"""
Scrapers module for Radio Monitor 1.1

This module handles web scraping of radio station websites to capture
currently playing songs. Supports iHeartRadio stations only.

Key Features:
- Fast scraping system using requests+BeautifulSoup
  * 0.43s average scraping time
- Multiple retry attempts with exponential backoff (7 attempts, ~112 seconds max)
- Artist/song validation to prevent swap bugs and data corruption
- Smart duplicate detection (compares with previous scrape)
- Station health tracking (auto-disable after failures)
- MusicBrainz MBID lookup (via API)
- Extensive filtering for taglines, ads, news
- Graceful cancellation support
"""

import os
import re
import time
import logging
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import uuid

logger = logging.getLogger(__name__)

# Global flag for cancellation
_scraping_cancelled = False


def cancel_scraping():
    """Signal scraping to cancel gracefully"""
    global _scraping_cancelled
    _scraping_cancelled = True
    logger.info("Scraping cancellation requested")


def is_scraping_cancelled():
    """Check if scraping has been cancelled"""
    global _scraping_cancelled
    return _scraping_cancelled


def reset_cancellation_flag():
    """Reset the cancellation flag for next scrape"""
    global _scraping_cancelled
    _scraping_cancelled = False


# ==================== MANUAL MBID OVERRIDE SUPPORT ====================

def get_artist_mbid_with_override(cursor, artist_name, mbid_from_station=None):
    """Get artist MBID with manual override support

    Priority order:
    1. MBID from station website (highest priority - station knows best)
    2. Manual override table (user's explicit choice)
    3. MusicBrainz API lookup (automatic discovery)
    4. PENDING-xxx (fallback)

    Args:
        cursor: Database cursor
        artist_name: Artist name from scraper
        mbid_from_station: MBID provided by station (if any)

    Returns:
        tuple: (mbid_to_use, source)
            - mbid_to_use: The MBID to use
            - source: 'station', 'override', 'musicbrainz', or 'pending'
    """
    # Priority 1: Station MBID (highest priority)
    if mbid_from_station and mbid_from_station != 'PENDING':
        return mbid_from_station, 'station'

    # Priority 2: Manual override (user's explicit choice)
    from radio_monitor.database.crud import get_manual_mbid_override
    override_mbid = get_manual_mbid_override(cursor, artist_name)
    if override_mbid:
        logger.info(f"Using manual MBID override for '{artist_name}': {override_mbid}")
        return override_mbid, 'override'

    # Priority 3: MusicBrainz API lookup (automatic)
    # Note: This will be called later by the main scraper loop
    # We return None here to signal that lookup is needed
    return None, 'musicbrainz_needed'


# ==================== FILTERING LISTS ====================

# Taglines and unwanted phrases to filter out
TAGLINE_PHRASES = [
    'if you like', 'hits', 'commercial-free', 'see all', 'drive',
    'cool oldies', 'real oldies', 'big classic hits', 'variety hits',
    'pop hits', 'rock hits', 'country hits', 'oldies',
    'live for', ' listen', 'station', 'contests', 'promotions',
    'ticket tuesday', 'free ticket', 'melissa forman',
    'your home for', 'your number one hit music station'
]

# News phrases to filter out
NEWS_PHRASES = [
    'family', 'issues', 'message', 'kidnapp', 'ransom',
    'identified', 'postpones', 'residency', 'surgery',
    'doctor', 'global', 'recall', 'toxin', 'expansion'
]

# Stop phrases indicating end of song list or non-music content
STOP_PHRASES = [
    'Most Played', 'Advertise With Us', 'Advertise', 'CONNECT',
    'EXCLUSIVES', 'INFORMATION', 'GET THE APP',
    'iHeart', 'Live Radio', 'Podcasts', 'News', 'News Feed',
    'For You', 'Your Library', 'Artist Radio', 'Playlists',
    'Follow Us', 'Social', 'Facebook', 'Twitter', 'Instagram',
    'Download', 'App Store', 'Google Play', 'Amazon Alexa',
    'Sign Up', 'Log In', 'Newsletter', 'Terms', 'Privacy', 'Privacy Policy',
    'Do Not Sell', 'Settings', 'Contact', 'Help', 'Support',
    '©', 'Copyright', 'LLC', 'iHeartMedia', 'iHeartRadio',
    'The Latest', 'Trending', 'Latest News', 'Trending Now',
    'Subscribe', 'Subscription', 'Donate', 'Sponsor', 'Sponsored',
    'Advertisement', 'Ad', 'Banner', 'Click Here', 'Learn More',
    'Join Now', 'Register', 'Create Account', 'Sign In',
    'Mobile App', 'iOS', 'Android', 'Download Now',
    'Contest Rules', 'Terms of Use', 'Cookie Policy'
]

# Phrases that indicate a line is definitely an advertisement or website element
ADVERTISEMENT_PHRASES = [
    'advertise', 'sponsor', 'promotion', 'banner', 'subscribe',
    'newsletter', 'privacy policy', 'terms of service', 'cookie',
    'download the app', 'get the app', 'app store', 'google play',
    'sign up', 'log in', 'register', 'create account', 'join now',
    'follow us', 'social media', 'facebook', 'twitter', 'instagram',
    'contact us', 'help center', 'customer service', 'support',
    'copyright', 'all rights reserved', 'llc', 'incorporated', 'corp',
    'click here', 'learn more', 'read more', 'find out more',
    'don\'t miss', 'limited time', 'act now', 'special offer',
    'contest', 'sweepstakes', 'giveaway', 'win', 'free'
]

def is_advertisement_or_website_content(text):
    """Check if text appears to be an advertisement, website UI element, or non-music content

    Args:
        text: String to check

    Returns:
        bool: True if text looks like advertisement/website content
    """
    if not text:
        return False

    text_lower = text.lower().strip()

    # Check against advertisement phrases
    if any(phrase in text_lower for phrase in ADVERTISEMENT_PHRASES):
        return True

    # Check against stop phrases
    if any(phrase in text for phrase in STOP_PHRASES):
        return True

    # Check for URLs
    if 'http://' in text_lower or 'https://' in text_lower or 'www.' in text_lower:
        return True

    # Check for email addresses
    if '@' in text and '.' in text:
        return True

    # Check for phone numbers (patterns like 1-800, 800-, etc.)
    if '1-800' in text or '1-888' in text or '1-877' in text or '1-866' in text:
        return True

    # Check for copyright symbol
    if '©' in text or '(c)' in text.lower():
        return True

    return False


def is_valid_artist_name(artist_name):
    """Validate artist name to prevent corrupted data

    Checks for:
    - Multiple commas (likely a list of artists, not a single artist)
    - Excessive length (likely advertisement or website content)
    - Suspicious patterns (feat., ft., featuring, &, +, etc.)
    - Only numbers or special characters

    Args:
        artist_name: Artist name string to validate

    Returns:
        bool: True if artist name appears valid, False if it looks corrupted
    """
    if not artist_name:
        return False

    artist_name = artist_name.strip()

    # Check length (excessive length indicates corrupted data)
    if len(artist_name) > 100:
        logger.debug(f"Rejecting artist name (too long, {len(artist_name)} chars): {artist_name[:50]}...")
        return False

    # Check for multiple commas (indicates list, not single artist)
    comma_count = artist_name.count(',')
    if comma_count >= 2:
        logger.debug(f"Rejecting artist name (too many commas): {artist_name}")
        return False

    # Check for suspicious patterns that indicate multiple artists
    # These are legitimate in some cases (e.g., "Post Malone Feat Blake Shelton")
    # but we'll allow them - they'll be filtered by MBID lookup later
    # Just reject obviously bad patterns like "Artist1, Artist2, Artist3"
    if comma_count == 1:
        # Check if it looks like "Last, First" (legitimate) or "Artist1, Artist2" (suspicious)
        parts = [p.strip() for p in artist_name.split(',')]
        if len(parts) == 2:
            # If both parts have spaces, might be "Artist One, Artist Two"
            if ' ' in parts[0] and ' ' in parts[1]:
                logger.debug(f"Rejecting artist name (looks like list): {artist_name}")
                return False

    # Check for only special characters or numbers
    if not re.search(r'[a-zA-Z]', artist_name):
        logger.debug(f"Rejecting artist name (no letters): {artist_name}")
        return False

    return True


# Station configurations (fallback for backward compatibility)
# NOTE: This is kept as fallback but database configs take precedence
STATION_CONFIGS = {
    'us99': {
        'url': 'https://www.iheart.com/live/us-99-10819/',
        'type': 'iheart',
        'has_mbid': False,
        'wait_time': 15
    },
    'wls': {
        'url': 'https://www.iheart.com/live/947-wls-5367/',
        'type': 'iheart',
        'has_mbid': False,
        'wait_time': 15
    },
    'rock955': {
        'url': 'https://www.iheart.com/live/rock-955-857/',
        'type': 'iheart',
        'has_mbid': False,
        'wait_time': 15
    },
    'q101': {
        'url': 'https://www.iheart.com/live/q101-6468/',
        'type': 'iheart',
        'has_mbid': False,
        'wait_time': 15
    },
    'b96': {
        'url': 'https://www.iheart.com/live/b96-353/',
        'type': 'iheart',
        'has_mbid': False,
        'wait_time': 15
    },
    'wlite': {
        'url': 'https://www.iheart.com/live/939-lite-fm-853/',
        'type': 'iheart',
        'has_mbid': False,
        'wait_time': 15
    },
    'wiil': {
        'url': 'https://www.iheart.com/live/95-wiil-rock-7716/',
        'type': 'iheart',
        'has_mbid': False,
        'wait_time': 15
    }
}

# Cache for database-loaded station configs (refreshed each scrape run)
_db_station_configs = None


def load_station_configs_from_db(db):
    """Load all station configurations from database

    Args:
        db: RadioDatabase instance

    Returns:
        dict: Station configs keyed by station_id
    """
    global _db_station_configs

    if not db:
        logger.warning("No database provided, using fallback STATION_CONFIGS")
        return STATION_CONFIGS.copy()

    try:
        # Check if database is connected
        if db.conn is None:
            logger.warning("Database not connected, using fallback STATION_CONFIGS")
            return STATION_CONFIGS.copy()

        cursor = db.get_cursor()
        cursor.execute("""
            SELECT id, url, scraper_type, has_mbid, wait_time, enabled
            FROM stations
            WHERE enabled = 1
        """)

        configs = {}
        for row in cursor.fetchall():
            station_id, url, scraper_type, has_mbid, wait_time, enabled = row

            # Map database columns to config format
            configs[station_id] = {
                'url': url,
                'type': scraper_type if scraper_type else 'iheart',  # Default to iheart
                'has_mbid': bool(has_mbid) if has_mbid is not None else False,
                'wait_time': wait_time if wait_time else 15
            }

        _db_station_configs = configs
        logger.info(f"Loaded {len(configs)} station configs from database")

        return configs

    except Exception as e:
        logger.error(f"Error loading station configs from database: {e}")
        logger.warning("Falling back to hardcoded STATION_CONFIGS")
        return STATION_CONFIGS.copy()


def get_station_config(db, station_id):
    """Get configuration for a specific station

    Args:
        db: RadioDatabase instance
        station_id: Station identifier

    Returns:
        dict: Station configuration

    Raises:
        ValueError: If station not found in database or fallback configs
    """
    global _db_station_configs

    # Load from database if not cached
    if _db_station_configs is None and db:
        _db_station_configs = load_station_configs_from_db(db)

    # Try database configs first
    if _db_station_configs and station_id in _db_station_configs:
        return _db_station_configs[station_id]

    # Fallback to hardcoded configs
    if station_id in STATION_CONFIGS:
        logger.warning(f"Station {station_id} not in database, using hardcoded config")
        return STATION_CONFIGS[station_id]

    # Station not found anywhere
    available_stations = list(_db_station_configs.keys()) if _db_station_configs else list(STATION_CONFIGS.keys())
    raise ValueError(
        f"Unknown station: {station_id}. "
        f"Available stations: {', '.join(sorted(available_stations))}"
    )

def scrape_station_iheart_fast(config, max_retries=7, initial_wait=4):
    """Scrape iHeartRadio station using requests+BeautifulSoup

    This is the iHeart scraper that:
    - Uses requests+BeautifulSoup (0.43s average scraping time)
    - Parses HTML structure directly (immune to text-based swap bugs)
    - Gets all 12 songs at once
    - Has retry mechanism with exponential backoff (7 attempts, ~112 seconds max)
    - Validates artist/song pairs to prevent data corruption

    Args:
        config: Station configuration dict
        max_retries: Maximum number of retry attempts (default: 7)
        initial_wait: Initial wait time in seconds before first retry (default: 4)

    Returns:
        List of (artist, song, None) tuples (iHeart doesn't provide MBIDs)
    """
    for attempt in range(1, max_retries + 1):
        songs = []

        try:
            # Setup headers
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            }

            # Fetch page
            logger.debug(f"Fast scraper attempt {attempt}/{max_retries}: {config['url']}")
            response = requests.get(config['url'], headers=headers, timeout=15)
            response.raise_for_status()

            # Parse HTML
            soup = BeautifulSoup(response.text, "html.parser")

            # Find all anchor tags that point to a song URL (contain '/songs/')
            song_links = soup.find_all("a", href=lambda h: h and "/songs/" in h)
            logger.debug(f"Found {len(song_links)} song links")

            # Track seen songs for deduplication
            seen = set()

            for link in song_links:
                try:
                    song_title = link.get_text(strip=True)
                    href = link.get("href", "")

                    # Validate song title
                    if not song_title or len(song_title) < 3 or len(song_title) > 60:
                        continue

                    # Skip advertisements/website content
                    if is_advertisement_or_website_content(song_title):
                        logger.debug(f"Skipping song that looks like ad: {song_title}")
                        continue

                    # Try to find artist link inside same parent container
                    parent = link.parent
                    artist_link = parent.find(
                        "a", href=lambda h: h and "/artist/" in h and "/songs/" not in h
                    ) if parent else None

                    if artist_link:
                        artist_name = artist_link.get_text(strip=True)
                    else:
                        # Fallback: derive artist name from the song URL slug
                        # e.g., '/artist/megan-moroney-35764910/songs/...' -> 'Megan Moroney'
                        parts = href.strip("/").split("/")
                        if len(parts) > 1:
                            artist_slug = parts[1]
                            # Strip trailing numeric ID (e.g. '-35764910')
                            artist_slug = re.sub(r"-\d+$", "", artist_slug)
                            # Convert slug to title case
                            artist_name = artist_slug.replace("-", " ").title()
                        else:
                            logger.debug(f"Cannot extract artist from URL: {href}")
                            continue

                    # Validate artist name
                    if not artist_name or len(artist_name) < 3 or len(artist_name) > 60:
                        continue

                    # Skip advertisements/website content (artist names too)
                    if is_advertisement_or_website_content(artist_name):
                        logger.debug(f"Skipping artist that looks like ad: {artist_name}")
                        continue

                    # Validate artist name to prevent corrupted data
                    if not is_valid_artist_name(artist_name):
                        logger.debug(f"Skipping artist with invalid name: {artist_name}")
                        continue

                    # CRITICAL VALIDATION: Prevent artist/song swap bugs
                    # Artist names shouldn't contain digits (except collaborations)
                    # Song titles shouldn't look like artist names
                    if _validate_artist_song_pair(artist_name, song_title):
                        # Deduplicate by (song, artist) pair
                        key = (song_title, artist_name)
                        if key not in seen:
                            seen.add(key)
                            songs.append((artist_name, song_title, None))
                            logger.debug(f"Found: {song_title} by {artist_name}")
                    else:
                        logger.warning(f"Validation failed - possible swap: '{song_title}' by '{artist_name}'")

                except Exception as e:
                    logger.debug(f"Error parsing song link: {e}")
                    continue

            logger.info(f"Fast scraper found {len(songs)} songs (attempt {attempt}/{max_retries})")

            # Success: If we found enough songs, return immediately
            if len(songs) >= 2:  # Need at least 2 songs to consider it successful
                logger.info(f"Fast scraper successful with {len(songs)} songs in {attempt} attempt(s)")
                return songs

            # Not enough songs - retry with exponential backoff (capped at 20s)
            if attempt < max_retries:
                wait_time = min(initial_wait * (2 ** (attempt - 1)), 20)  # 4s, 8s, 16s, 20s, 20s, 20s...
                logger.info(f"Only {len(songs)} songs (need >=2), waiting {wait_time}s before retry...")
                time.sleep(wait_time)
            else:
                logger.warning(f"Fast scraper: All {max_retries} attempts completed, returning {len(songs)} songs")
                return songs

        except requests.exceptions.RequestException as e:
            logger.warning(f"Request error on attempt {attempt}/{max_retries}: {e}")
            if attempt < max_retries:
                wait_time = min(initial_wait * (2 ** (attempt - 1)), 20)  # Capped at 20s
                logger.info(f"Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
            else:
                logger.error(f"All {max_retries} attempts failed for fast scraper")
                return []
        except Exception as e:
            logger.warning(f"Unexpected error on attempt {attempt}/{max_retries}: {e}")
            if attempt < max_retries:
                wait_time = min(initial_wait * (2 ** (attempt - 1)), 20)  # Capped at 20s
                logger.info(f"Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
            else:
                logger.error(f"All {max_retries} attempts failed for fast scraper")
                return []

    return []


def _validate_artist_song_pair(artist_name, song_title):
    """Validate artist/song pair to prevent swap bugs and data corruption

    This function performs sanity checks to ensure the artist and song
    are not swapped and both appear to be valid.

    Args:
        artist_name: Artist name string
        song_title: Song title string

    Returns:
        bool: True if pair appears valid, False if suspicious
    """
    # Collaboration markers that indicate long artist names are legitimate
    collaboration_markers = ['feat', 'featuring', 'ft', 'with', '&', 'and', '+', 'x']
    artist_lower = artist_name.lower()
    has_collaboration_marker = any(marker in artist_lower for marker in collaboration_markers)

    # Rule 1: Artist name that is ONLY digits and looks like a year (likely a swap)
    # Example: "2024" as artist would mean swapped (year is usually song/album)
    # Allow all-digit artists like "311", "UB40", "50 Cent", "21 Savage"
    # Only reject if it's a 4-digit year (1000-2999 covers reasonable song years)
    if artist_name.isdigit() and len(artist_name) == 4:
        year = int(artist_name)
        if 1000 <= year <= 2999:
            logger.debug(f"Validation failed: Artist '{artist_name}' looks like a year")
            return False

    # Rule 2: Song title shouldn't be ALL UPPERCASE with lots of spaces
    # (unless it's stylized, which is rare)
    if song_title.isupper() and len(song_title) > 15:
        # This might be an artist name
        logger.debug(f"Validation failed: Song '{song_title}' is all uppercase and long")
        return False

    # Rule 3: Artist name shouldn't be extremely long (EXCEPT for collaborations)
    # Collaboration artists can have very long names like "Marky Mark And The Funky Bunch Feat Loleatta Holloway"
    if len(artist_name) > 40 and not has_collaboration_marker:
        logger.debug(f"Validation failed: Artist '{artist_name}' is too long")
        return False

    # Rule 4: Both should have reasonable character lengths
    if len(artist_name) < 3 or len(song_title) < 3:
        logger.debug(f"Validation failed: Artist or song too short")
        return False

    # Rule 5: Check for common website/content indicators
    skip_phrases = ['listen live', 'now playing', 'up next', 'advertisement', 'sponsor']
    combined = f"{artist_name} {song_title}".lower()
    if any(phrase in combined for phrase in skip_phrases):
        logger.debug(f"Validation failed: Contains skip phrase")
        return False

    # Rule 6: Check for obvious swap - short title looks like artist name, long artist looks like song
    # Example: song="Taylor Swift", artist="Love Story" (SWAPPED)
    # BUT: Allow collaborations with long artist names
    if len(song_title.split()) <= 2 and len(artist_name.split()) >= 4 and not has_collaboration_marker:
        # Title is short, artist is long - might be swapped
        # But only flag if title looks like artist name (capitalized words)
        if song_title and all(word[0].isupper() for word in song_title.split() if word):
            logger.debug(f"Validation failed: Possible swap - short title '{song_title}' with long artist '{artist_name}'")
            return False

    # All checks passed
    return True


def scrape_single_station(db, station_id):
    """Scrape a single station and return current songs

    Note: This function only supports iHeartRadio stations using the fast scraper.

    Args:
        db: RadioDatabase instance (for loading station configs)
        station_id: Station identifier (e.g., 'us99', 'wls')

    Returns:
        List of (artist, song, artist_mbid) tuples

    Raises:
        ValueError: If station_id not found or station type is not supported
        Exception: If scraping fails
    """
    # Check for cancellation
    if is_scraping_cancelled():
        logger.info(f"Scraping cancelled before scraping {station_id}")
        return []

    # Get station config from database (with fallback to hardcoded)
    config = get_station_config(db, station_id)

    try:
        logger.info(f"Scraping {station_id}: {config['url']}")

        # Only iHeartRadio stations are supported
        if config['type'] != 'iheart':
            raise ValueError(
                f"Unsupported station type: '{config['type']}'. "
                f"Only 'iheart' type is supported. "
                f"Station '{station_id}' has type '{config['type']}'."
            )

        # Use fast scraper (requests + BeautifulSoup)
        logger.info(f"Using fast scraper for {station_id}...")
        songs = scrape_station_iheart_fast(config, max_retries=7, initial_wait=4)

        if len(songs) == 0:
            logger.warning(f"Fast scraper found 0 songs for {station_id} after all retries")
        else:
            logger.info(f"Fast scraper successful for {station_id}: {len(songs)} songs")

        logger.info(f"Scraped {len(songs)} songs from {station_id}")
        return songs

    except Exception as e:
        logger.error(f"Failed to scrape {station_id}: {e}")
        raise


def scrape_all_stations(db=None, station_ids=None):
    """Scrape all enabled stations and update database

    This is the main scraping function called by the scheduler.
    It scrapes all enabled stations, looks up MBIDs for new artists,
    adds songs to the database, and tracks station health.

    Args:
        db: RadioDatabase instance (required)
        station_ids: List of station IDs to scrape (optional, default: all enabled)

    Returns:
        dict: Results of scraping operation
    """
    # Reset cancellation flag at start
    reset_cancellation_flag()

    if not db:
        logger.error("Database not provided to scrape_all_stations")
        return {
            "success": False,
            "stations_scraped": 0,
            "songs_found": 0,
            "artists_added": 0,
            "songs_added": 0,
            "message": "Database not initialized"
        }

    # Load station configurations from database
    load_station_configs_from_db(db)

    # Import MusicBrainz lookup
    from radio_monitor.mbid import lookup_artist_mbid

    # Load settings for auto-import
    from radio_monitor.gui import load_settings
    settings = load_settings()
    auto_import_enabled = settings.get('lidarr', {}).get('auto_import', False) if settings else False
    min_plays_for_import = settings.get('lidarr', {}).get('min_plays_for_import', 5) if settings else 5
    min_songs_for_import = settings.get('lidarr', {}).get('min_songs_for_import', 1) if settings else 1

    if auto_import_enabled:
        logger.info(f"Lidarr auto-import is ENABLED (min_plays={min_plays_for_import}, min_songs={min_songs_for_import})")

    # Get stations to scrape
    if station_ids:
        stations_to_scrape = station_ids
    else:
        # Get all enabled stations from database
        stations = db.get_all_stations_with_health()
        stations_to_scrape = [s['id'] for s in stations if s['enabled']]

    if not stations_to_scrape:
        logger.warning("No enabled stations to scrape")
        return {
            "success": True,
            "stations_scraped": 0,
            "songs_found": 0,
            "artists_added": 0,
            "songs_added": 0,
            "message": "No enabled stations"
        }

    logger.info(f"Scraping {len(stations_to_scrape)} stations: {', '.join(stations_to_scrape)}")

    total_songs_found = 0
    total_artists_added = 0
    total_songs_added = 0
    total_plays_recorded = 0
    skipped_no_mbid = 0
    stations_scraped = 0
    failed_stations = []

    for station_id in stations_to_scrape:
        # Check for cancellation before each station
        if is_scraping_cancelled():
            logger.info("Scraping cancelled by user. Stopping.")
            break

        try:
            # Scrape the station
            songs_data = scrape_single_station(db, station_id)

            if not songs_data:
                logger.warning(f"No songs found for {station_id}")
                db.record_scrape_failure(station_id)
                failed_stations.append(station_id)
                continue

            # Record success and reset failure counter
            db.record_scrape_success(station_id)
            total_songs_found += len(songs_data)

            # Process each song
            for artist_name, song_title, artist_mbid in songs_data:
                try:
                    # Clean up the data with proper normalization
                    from radio_monitor.normalization import normalize_artist_name, normalize_song_title
                    artist_name = normalize_artist_name(artist_name.strip())
                    song_title = normalize_song_title(song_title.strip())

                    # Skip if too short (probably not a real song)
                    if len(artist_name) < 3 or len(song_title) < 3:
                        continue

                    # SAFETY NET: Final check for advertisements/website content before database insertion
                    if is_advertisement_or_website_content(artist_name):
                        logger.warning(f"BLOCKED: Artist name appears to be advertisement/website content: '{artist_name}' (skipping)")
                        continue

                    if is_advertisement_or_website_content(song_title):
                        logger.warning(f"BLOCKED: Song title appears to be advertisement/website content: '{song_title}' (skipping)")
                        continue

                    # Handle collaborations: Use comprehensive collaboration detection
                    from radio_monitor.normalization import handle_collaboration

                    # Split collaboration into individual artists
                    # Returns list of (artist, song, mbid) tuples
                    collaboration_results = handle_collaboration(artist_name, song_title, artist_mbid)

                    # Extract just the artist names for processing
                    artists_to_process = [result[0] for result in collaboration_results]

                    # Log collaboration splits
                    if len(artists_to_process) > 1:
                        logger.info(f"Collaboration detected: '{artist_name}' split into {len(artists_to_process)} artists: {artists_to_process}")

                    # Process each primary artist from the collaboration
                    for primary_artist in artists_to_process:
                        # Get MBID with manual override support
                        # Priority: Station MBID > Manual override > MusicBrainz API > PENDING
                        primary_artist_mbid = artist_mbid if len(artists_to_process) == 1 else None

                        if not primary_artist_mbid:
                            # Check for manual override first
                            cursor = db.get_cursor()
                            try:
                                mbid_with_source, source = get_artist_mbid_with_override(
                                    cursor,
                                    primary_artist,
                                    None  # No station MBID at this point
                                )

                                # Log source for debugging
                                logger.debug(f"MBID for '{primary_artist}': source={source}, mbid={mbid_with_source}")

                                if mbid_with_source:
                                    primary_artist_mbid = mbid_with_source
                                elif source == 'musicbrainz_needed':
                                    # No override found, try MusicBrainz lookup
                                    try:
                                        from radio_monitor.mbid import lookup_artist_mbid
                                        # Get user_agent from settings for MusicBrainz API
                                        user_agent = settings.get('musicbrainz', {}).get('user_agent') if settings else None
                                        primary_artist_mbid = lookup_artist_mbid(primary_artist, db, user_agent=user_agent)
                                        if primary_artist_mbid:
                                            logger.debug(f"MBID from MusicBrainz for '{primary_artist}': {primary_artist_mbid}")
                                    except Exception as e:
                                        logger.warning(f"MBID lookup failed for '{primary_artist}': {e}")
                            finally:
                                cursor.close()

                        # If still no MBID, try multi-artist resolution (ONE-TIME attempt)
                        # Note: This only returns the MBID - no database updates during scraping
                        # Database updates happen only during manual CLI command to avoid transaction conflicts
                        if not primary_artist_mbid:
                            try:
                                from radio_monitor.multi_artist_resolver import try_split_and_validate

                                # Try to resolve as multi-artist collaboration
                                logger.info(f"No MBID found for '{primary_artist}', trying multi-artist resolution...")

                                # Use the smart grouping resolver to find the primary MBID
                                validated_artists = try_split_and_validate(primary_artist, db, user_agent)

                                if validated_artists:
                                    # Get the MBID of the first (primary) artist
                                    from radio_monitor.mbid import lookup_artist_mbid
                                    primary_name = validated_artists[0]
                                    primary_artist_mbid = lookup_artist_mbid(
                                        artist_name=primary_name,
                                        db=db,
                                        user_agent=user_agent
                                    )

                                if primary_artist_mbid and not primary_artist_mbid.startswith('PENDING'):
                                    logger.info(f"Multi-artist resolution successful for '{primary_artist}' -> '{primary_name}': {primary_artist_mbid}")
                                else:
                                    logger.debug(f"Multi-artist resolution failed for '{primary_artist}'")
                            except Exception as e:
                                logger.warning(f"Multi-artist resolution error for '{primary_artist}': {e}")

                        # If still no MBID, use a placeholder (PENDING)
                        if not primary_artist_mbid:
                            # Create temporary MBID placeholder
                            import hashlib
                            artist_hash = hashlib.md5(primary_artist.encode()).hexdigest()[:32]
                            primary_artist_mbid = f"PENDING-{artist_hash}"
                            logger.debug(f"Using placeholder MBID for {primary_artist}: {primary_artist_mbid}")

                        # Add artist to database (if new)
                        artist_added = db.add_artist_if_new(primary_artist_mbid, primary_artist)
                        if artist_added:
                            total_artists_added += 1
                            logger.info(f"New artist: {primary_artist} ({primary_artist_mbid})")

                        # Auto-import to Lidarr if enabled and artist meets threshold
                        if auto_import_enabled:
                            # Get artist's current play count and song count
                            cursor = db.get_cursor()
                            try:
                                cursor.execute("""
                                    SELECT
                                        COALESCE(SUM(s.play_count), 0) as total_plays,
                                        COUNT(DISTINCT s.id) as song_count
                                    FROM artists a
                                    LEFT JOIN songs s ON a.mbid = s.artist_mbid
                                    WHERE a.mbid = ?
                                    GROUP BY a.mbid
                                """, (primary_artist_mbid,))

                                result = cursor.fetchone()
                                if result:
                                    total_plays = result[0]
                                    song_count = result[1]

                                    # Check if artist meets threshold
                                    if total_plays >= min_plays_for_import and song_count >= min_songs_for_import:
                                        try:
                                            from radio_monitor.lidarr import import_artist_to_lidarr
                                            success, message = import_artist_to_lidarr(
                                                primary_artist_mbid, primary_artist, settings
                                            )
                                            if success:
                                                logger.info(f"Auto-imported {primary_artist} to Lidarr ({total_plays} plays, {song_count} songs)")
                                                db.mark_artist_imported_to_lidarr(primary_artist_mbid)
                                            else:
                                                # Mark for manual import later
                                                logger.warning(f"Auto-import failed for {primary_artist}: {message}")
                                        except Exception as e:
                                            logger.warning(f"Auto-import error for {primary_artist}: {e}")
                                            # Continue scraping even if auto-import fails
                                    else:
                                        logger.debug(f"Artist {primary_artist} doesn't meet threshold yet ({total_plays}/{min_plays_for_import} plays, {song_count}/{min_songs_for_import} songs)")
                            finally:
                                cursor.close()

                    # Add song to database (if new)
                    song_added, play_id = db.add_song_if_new(primary_artist_mbid, song_title)
                    if song_added:
                        total_songs_added += 1
                        logger.info(f"New song: {song_title} by {primary_artist}")

                    # Record play for this station (may be skipped as duplicate)
                    station = db.get_station_by_id(station_id)
                    if station and play_id:
                        recorded = db.record_play(
                            song_id=play_id,
                            station_id=station['id'],
                            play_count=1
                        )
                        if recorded:
                            total_plays_recorded += 1
                        # Silently skip duplicates (no logging, no counter)

                except Exception as e:
                    logger.warning(f"Error processing song '{song_title}' by '{artist_name}': {e}")
                    continue

            stations_scraped += 1
            logger.info(f"Completed scraping {station_id}: {len(songs_data)} songs found")

        except Exception as e:
            logger.error(f"Failed to scrape {station_id}: {e}")
            db.record_scrape_failure(station_id)
            failed_stations.append(station_id)
            continue

    # Compile results
    result = {
        "success": True,
        "stations_scraped": stations_scraped,
        "songs_found": total_songs_found,
        "artists_added": total_artists_added,
        "songs_added": total_songs_added,
        "plays_recorded": total_plays_recorded,
        "skipped_no_mbid": skipped_no_mbid,
        "failed_stations": failed_stations,
        "message": f"Scraped {stations_scraped} stations, found {total_songs_found} songs, {total_plays_recorded} plays recorded"
    }

    if failed_stations:
        result["message"] += f", {len(failed_stations)} failed: {', '.join(failed_stations)}"

    logger.info(f"Scraping complete: {result}")

    # Log activity
    try:
        from radio_monitor.database.activity import log_activity
        severity = 'success' if len(failed_stations) == 0 else 'warning' if len(failed_stations) < len(stations_to_scrape) else 'error'
        log_activity(
            db.get_cursor(),
            event_type='scrape',
            title=f"Scraping complete: {stations_scraped} stations",
            description=result["message"],
            metadata={
                'stations_scraped': stations_scraped,
                'songs_found': total_songs_found,
                'artists_added': total_artists_added,
                'songs_added': total_songs_added,
                'plays_recorded': total_plays_recorded,
                'failed_stations': failed_stations
            },
            severity=severity,
            source='scheduler'
        )
    except Exception as e:
        logger.error(f"Failed to log scrape activity: {e}")

    # Send notifications
    try:
        from radio_monitor.notifications import send_notifications
        if result['success']:
            send_notifications(
                db,
                'on_scrape_complete',
                'Scraping Complete',
                f"Scraped {result['stations_scraped']} stations, found {result['songs_found']} songs",
                'info' if result['failed_stations'] == 0 else 'warning',
                {
                    'stations_scraped': result['stations_scraped'],
                    'songs_found': result['songs_found'],
                    'artists_added': result['artists_added'],
                    'songs_added': result['songs_added'],
                    'failed_stations': result['failed_stations']
                }
            )
        else:
            send_notifications(
                db,
                'on_scrape_error',
                'Scraping Failed',
                result.get('message', 'Scraping operation failed'),
                'error',
                {'stations_scraped': result.get('stations_scraped', 0)}
            )
    except Exception as e:
        logger.error(f"Failed to send scrape notifications: {e}")

    return result
