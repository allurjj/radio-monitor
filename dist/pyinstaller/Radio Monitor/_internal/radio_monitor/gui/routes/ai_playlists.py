"""
AI Playlists Routes for Radio Monitor 1.0

Experimental AI-powered playlist generation using OpenRouter.ai.
"""

import json
import logging
import sys
from datetime import datetime
from flask import Blueprint, render_template, jsonify, request, current_app
from radio_monitor.auth import requires_auth

logger = logging.getLogger(__name__)

ai_playlists_bp = Blueprint('ai_playlists', __name__)

# Rate limiting tracking (in-memory for simplicity)
_last_request_time = None
_rate_limit_seconds = 60  # 1 request per minute


def get_db():
    """Get database instance from Flask app config"""
    return current_app.config.get('db')


def get_settings():
    """Get settings from Flask app config"""
    # Try to reload from file first to get latest changes
    from radio_monitor.gui import load_settings
    fresh_settings = load_settings()
    if fresh_settings:
        return fresh_settings

    # Fallback to cached settings in app config
    return current_app.config.get('settings', {})


@ai_playlists_bp.route('/ai-playlists')
@requires_auth
def ai_playlists():
    """AI Playlists page (experimental feature)"""
    from radio_monitor.gui import is_first_run
    from flask import redirect, url_for

    if is_first_run():
        return redirect(url_for('wizard'))

    return render_template('ai_playlists.html')


@ai_playlists_bp.route('/api/ai-playlists/generate', methods=['POST'])
@requires_auth
def api_generate_ai_playlist():
    """Generate AI-powered playlist

    Expects JSON:
        {
            "playlist_name": "Party Mix",
            "instructions": "Upbeat party songs with high energy",
            "stations": ["us99", "wlit"],  // optional, empty = all stations
            "min_plays": 10,
            "first_seen": "2026-01-01",
            "last_seen": "2026-02-16",
            "max_songs": 50
        }

    Returns JSON:
        Success:
        {
            "status": "success",
            "message": "Created playlist 'Party Mix' with 42 songs",
            "playlist_name": "Party Mix",
            "songs_requested": 50,
            "songs_returned": 47,
            "songs_added": 42,
            "songs_skipped": 5,
            "songs_hallucinated": 2,
            "plex_url": "https://plex.tv/..."
        }

        Error:
        {
            "status": "error",
            "message": "Error description",
            "error_code": "ERROR_CODE"
        }
    """
    global _last_request_time

    db = get_db()
    if not db:
        return jsonify({
            'status': 'error',
            'message': 'Database not initialized',
            'error_code': 'DATABASE_ERROR'
        }), 500

    settings = get_settings()
    if not settings:
        return jsonify({
            'status': 'error',
            'message': 'Settings not loaded',
            'error_code': 'SETTINGS_ERROR'
        }), 500

    # Parse request data
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'Request body is required',
                'error_code': 'INVALID_REQUEST'
            }), 400

        playlist_name = data.get('playlist_name', '').strip()
        instructions = data.get('instructions', '').strip()
        stations = data.get('stations', [])
        min_plays = data.get('min_plays', 1)
        first_seen = data.get('first_seen')
        last_seen = data.get('last_seen')
        max_songs = data.get('max_songs', 50)
        exclude_blocklist = data.get('exclude_blocklist', True)  # Default: True

    except Exception as e:
        logger.error(f"Error parsing request data: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Invalid request format',
            'error_code': 'INVALID_REQUEST'
        }), 400

    # Validation
    if not playlist_name:
        return jsonify({
            'status': 'error',
            'message': 'Playlist name is required',
            'error_code': 'INVALID_INPUT'
        }), 400

    if not instructions:
        return jsonify({
            'status': 'error',
            'message': 'Instructions are required',
            'error_code': 'INVALID_INPUT'
        }), 400

    # Validate max_songs range (1-1500)
    try:
        max_songs = int(max_songs)
        if max_songs < 1 or max_songs > 1500:
            return jsonify({
                'status': 'error',
                'message': 'max_songs must be between 1 and 1500',
                'error_code': 'INVALID_INPUT'
            }), 400
    except (ValueError, TypeError):
        return jsonify({
            'status': 'error',
            'message': 'max_songs must be a number',
            'error_code': 'INVALID_INPUT'
        }), 400

    # Validate min_plays
    try:
        min_plays = int(min_plays)
        if min_plays < 0:
            return jsonify({
                'status': 'error',
                'message': 'min_plays must be 0 or greater',
                'error_code': 'INVALID_INPUT'
            }), 400
    except (ValueError, TypeError):
        return jsonify({
            'status': 'error',
            'message': 'min_plays must be a number',
            'error_code': 'INVALID_INPUT'
        }), 400

    # Check OpenRouter settings
    openrouter_config = settings.get('openrouter', {})
    api_key = openrouter_config.get('api_key', '').strip()

    if not api_key:
        return jsonify({
            'status': 'error',
            'message': 'OpenRouter API key not configured. Please add it in Settings.',
            'error_code': 'API_KEY_MISSING'
        }), 400

    # Rate limiting check
    current_time = datetime.now()
    if _last_request_time:
        time_diff = (current_time - _last_request_time).total_seconds()
        if time_diff < _rate_limit_seconds:
            retry_after = int(_rate_limit_seconds - time_diff)
            return jsonify({
                'status': 'error',
                'message': f'Please wait {retry_after} seconds before generating another playlist',
                'error_code': 'RATE_LIMITED',
                'retry_after': retry_after
            }), 429

    # Update last request time
    _last_request_time = current_time

    cursor = None
    try:
        cursor = db.get_cursor()

        # Query songs from database
        from radio_monitor.database.queries import get_ai_playlist_songs, format_songs_for_ai

        # Treat empty stations list as "all stations"
        station_ids = stations if stations else None

        songs = get_ai_playlist_songs(
            cursor,
            station_ids=station_ids,
            min_plays=min_plays,
            first_seen=first_seen,
            last_seen=last_seen
        )

        # Filter out blocklisted songs if requested
        if exclude_blocklist:
            from radio_monitor.database.queries import filter_blocklist_songs
            original_count = len(songs)
            songs = filter_blocklist_songs(cursor, songs)
            excluded = original_count - len(songs)
            logger.info(f"Excluded {excluded} songs by blocklist, {len(songs)} remaining")
        else:
            excluded = 0

        if not songs:
            return jsonify({
                'status': 'error',
                'message': 'No songs found matching the specified filters',
                'error_code': 'NO_SONGS'
            }), 400

        logger.info(f"Found {len(songs)} songs matching filters for AI playlist generation")

        # Safety: Limit the number of songs sent to AI to prevent token limit issues
        # Read from settings (default: 5000 for models with 1M+ token context windows)
        max_songs_input = openrouter_config.get('max_songs_input', 5000)
        if len(songs) > max_songs_input:
            logger.warning(f"Too many songs ({len(songs)}) for AI - limiting to {max_songs_input} most recent")
            # Keep most recent songs (by last_seen_at)
            songs = songs[:max_songs_input]

        # Format songs for AI (numbered list: "1. Artist: Song")
        formatted_songs = format_songs_for_ai(songs)
        logger.info(f"Sending {len(formatted_songs)} songs to AI for playlist generation")

        # Call OpenRouter API
        from radio_monitor.integrations.openrouter import send_to_openrouter, parse_ai_response

        model = openrouter_config.get('model', 'qwen/qwen3-next-80b-a3b-instruct:free')
        timeout = openrouter_config.get('timeout_seconds', 120)
        max_retries = openrouter_config.get('max_retries', 3)
        max_tokens = openrouter_config.get('max_tokens', 100000)

        logger.info(f"Using AI model: {model}")

        try:
            ai_response = send_to_openrouter(
                song_list=formatted_songs,
                instructions=instructions,
                api_key=api_key,
                model=model,
                timeout=timeout,
                max_retries=max_retries,
                max_tokens=max_tokens,
                max_songs=max_songs  # Pass user's max_songs preference to AI
            )
        except ValueError as e:
            # API key or validation error
            return jsonify({
                'status': 'error',
                'message': str(e),
                'error_code': 'API_ERROR'
            }), 400
        except Exception as e:
            logger.error(f"OpenRouter API error: {e}")
            return jsonify({
                'status': 'error',
                'message': f'Failed to communicate with OpenRouter API: {str(e)}',
                'error_code': 'API_ERROR'
            }), 500

        # Parse AI response
        try:
            # songs is list of (artist, song) tuples
            ai_songs, hallucinated_count = parse_ai_response(
                ai_response,
                songs,
                max_tokens=max_tokens
            )
        except ValueError as e:
            logger.error(f"Failed to parse AI response: {e}")
            return jsonify({
                'status': 'error',
                'message': f'Failed to parse AI response: {str(e)}',
                'error_code': 'PARSE_ERROR'
            }), 500

        songs_returned = len(ai_songs)

        if not ai_songs:
            return jsonify({
                'status': 'error',
                'message': 'AI did not return any valid songs',
                'error_code': 'NO_SONGS_RETURNED'
            }), 500

        # Check playlist name collision in Plex
        try:
            from plexapi.server import PlexServer

            plex_config = settings.get('plex', {})
            plex_url = plex_config.get('url')
            plex_token = plex_config.get('token')

            if plex_url and plex_token:
                plex = PlexServer(plex_url, plex_token, timeout=30)

                # Try to get the playlist - this will raise exception if it doesn't exist
                try:
                    existing_playlist = plex.playlist(playlist_name)
                    # If we get here, playlist exists
                    return jsonify({
                        'status': 'error',
                        'message': f"Playlist '{playlist_name}' already exists in Plex. Please choose a different name.",
                        'error_code': 'PLAYLIST_EXISTS'
                    }), 400
                except:
                    # Playlist doesn't exist - this is good, we can create it
                    pass

        except Exception as e:
            logger.warning(f"Could not check for playlist collision in Plex: {e}")
            # Continue anyway - Plex will handle duplicates

        # Match songs to Plex and create playlist
        try:
            from plexapi.server import PlexServer
            from radio_monitor.plex import find_song_in_library

            plex_config = settings.get('plex', {})
            plex_url = plex_config.get('url')
            plex_token = plex_config.get('token')

            if not plex_url or not plex_token:
                return jsonify({
                    'status': 'error',
                    'message': 'Plex configuration missing. Please check your Plex settings.',
                    'error_code': 'PLEX_ERROR'
                }), 500

            logger.info(f"Connecting to Plex at {plex_url}...")
            sys.stdout.flush()
            plex = PlexServer(plex_url, plex_token, timeout=30)
            logger.info(f"Connected to Plex successfully")
            sys.stdout.flush()

            # Get music library
            music_library_name = plex_config.get('library_name', 'Music')
            logger.info(f"Accessing Plex music library '{music_library_name}'...")
            sys.stdout.flush()
            music_library = plex.library.section(music_library_name)
            logger.info(f"Accessed music library successfully")
            sys.stdout.flush()

            # Match songs to Plex
            songs_to_add = []
            songs_skipped = []

            logger.info(f"Starting Plex matching for {len(ai_songs)} songs...")
            sys.stdout.flush()

            for idx, (artist, song) in enumerate(ai_songs, 1):
                # Log more frequently and flush immediately to avoid buffering
                if idx % 5 == 0 or idx == len(ai_songs):
                    logger.info(f"Matching song {idx}/{len(ai_songs)}: {song} - {artist}")
                    sys.stdout.flush()

                track = find_song_in_library(music_library, song, artist)

                if track:
                    songs_to_add.append(track)
                else:
                    songs_skipped.append((artist, song))
                    logger.warning(f"Song not found in Plex: {song} - {artist}")
                    sys.stdout.flush()

            songs_added_count = len(songs_to_add)
            songs_skipped_count = len(songs_skipped)

            # Check if any songs matched
            if songs_added_count == 0:
                # Create empty playlist with warning
                try:
                    playlist = plex.createPlaylist(playlist_name, items=[])
                    plex_url = playlist.url if hasattr(playlist, 'url') else None

                    # Log generation with warning status
                    _log_ai_generation(
                        cursor=cursor,
                        playlist_name=playlist_name,
                        model=model,
                        instructions=instructions,
                        filters=data,
                        status='warning',
                        songs_requested=max_songs,
                        songs_returned=songs_returned,
                        songs_added_to_plex=0,
                        songs_skipped=songs_skipped_count,
                        songs_hallucinated=hallucinated_count,
                        error_message="None of the selected songs were found in your Plex library",
                        plex_url=plex_url
                    )

                    return jsonify({
                        'status': 'warning',
                        'message': f"Created empty playlist '{playlist_name}' - none of the selected songs were found in your Plex library",
                        'playlist_name': playlist_name,
                        'songs_added': 0,
                        'songs_requested': max_songs,
                        'songs_returned': songs_returned,
                        'songs_skipped': songs_skipped_count,
                        'songs_hallucinated': hallucinated_count,
                        'plex_url': plex_url
                    })

                except Exception as e:
                    logger.error(f"Failed to create empty Plex playlist: {e}")
                    return jsonify({
                        'status': 'error',
                        'message': f'Failed to create Plex playlist: {str(e)}',
                        'error_code': 'PLEX_ERROR'
                    }), 500

            # Create playlist with matched songs
            playlist = plex.createPlaylist(playlist_name, items=songs_to_add)
            plex_url = playlist.url if hasattr(playlist, 'url') else None

            logger.info(f"Created Plex playlist '{playlist_name}' with {songs_added_count} songs")

            # Log successful generation
            _log_ai_generation(
                cursor=cursor,
                playlist_name=playlist_name,
                model=model,
                instructions=instructions,
                filters=data,
                status='success',
                songs_requested=max_songs,
                songs_returned=songs_returned,
                songs_added_to_plex=songs_added_count,
                songs_skipped=songs_skipped_count,
                songs_hallucinated=hallucinated_count,
                error_message=None,
                plex_url=plex_url
            )

            # Determine status based on how many songs were skipped
            status = 'success'
            message = f"Created playlist '{playlist_name}' with {songs_added_count} songs"

            if songs_skipped_count > 0:
                if songs_skipped_count <= 5:
                    message += f" ({songs_skipped_count} songs not found in Plex)"
                else:
                    message += f" ({songs_skipped_count} songs not found in Plex - check Plex Failures page)"
                    status = 'partial'

            return jsonify({
                'status': status,
                'message': message,
                'playlist_name': playlist_name,
                'songs_requested': max_songs,
                'songs_returned': songs_returned,
                'songs_added': songs_added_count,
                'songs_skipped': songs_skipped_count,
                'songs_hallucinated': hallucinated_count,
                'plex_url': plex_url
            })

        except Exception as e:
            logger.error(f"Error creating Plex playlist: {e}")
            return jsonify({
                'status': 'error',
                'message': f'Failed to create Plex playlist: {str(e)}',
                'error_code': 'PLEX_ERROR'
            }), 500

    except Exception as e:
        logger.error(f"Error generating AI playlist: {e}")
        return jsonify({
            'status': 'error',
            'message': f'An unexpected error occurred: {str(e)}',
            'error_code': 'INTERNAL_ERROR'
        }), 500

    finally:
        if cursor:
            cursor.close()


@ai_playlists_bp.route('/api/ai-playlists/history', methods=['GET'])
@requires_auth
def api_ai_playlist_history():
    """Get AI playlist generation history

    Query parameters:
        page: Page number (default: 1)
        limit: Items per page (default: 20)
        status: Filter by status (optional: success, failed, warning, partial)

    Returns JSON:
        {
            "items": [
                {
                    "id": 1,
                    "timestamp": "2026-02-16T14:30:00",
                    "playlist_name": "Party Mix",
                    "model": "qwen/qwen3-next-80b-a3b-instruct:free",
                    "instructions": "Upbeat party songs",
                    "status": "success",
                    "songs_requested": 50,
                    "songs_returned": 47,
                    "songs_added_to_plex": 42,
                    "songs_skipped": 5,
                    "songs_hallucinated": 2,
                    "error_message": null,
                    "plex_url": "https://plex.tv/..."
                }
            ],
            "total": 15,
            "page": 1,
            "limit": 20
        }
    """
    db = get_db()
    if not db:
        return jsonify({
            'error': 'Database not initialized'
        }), 500

    cursor = None
    try:
        cursor = db.get_cursor()

        # Get query parameters
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 20, type=int)
        status_filter = request.args.get('status', None)

        # Validate parameters
        if page < 1:
            page = 1
        if limit < 1 or limit > 100:
            limit = 20

        offset = (page - 1) * limit

        # Build query
        where_clause = ""
        params = []

        if status_filter:
            where_clause = "WHERE status = ?"
            params.append(status_filter)

        # Get total count
        count_query = f"SELECT COUNT(*) FROM ai_playlist_generations {where_clause}"
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]

        # Get items
        query = f"""
            SELECT
                id, timestamp, playlist_name, model, instructions,
                filters_json, status, songs_requested, songs_returned,
                songs_added_to_plex, songs_skipped, songs_hallucinated,
                error_message, plex_url, created_at
            FROM ai_playlist_generations
            {where_clause}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()

        items = []
        for row in rows:
            items.append({
                'id': row[0],
                'timestamp': row[1],
                'playlist_name': row[2],
                'model': row[3],
                'instructions': row[4],
                'filters_json': row[5],
                'status': row[6],
                'songs_requested': row[7],
                'songs_returned': row[8],
                'songs_added_to_plex': row[9],
                'songs_skipped': row[10],
                'songs_hallucinated': row[11],
                'error_message': row[12],
                'plex_url': row[13],
                'created_at': row[14]
            })

        return jsonify({
            'items': items,
            'total': total,
            'page': page,
            'limit': limit
        })

    except Exception as e:
        logger.error(f"Error fetching AI playlist history: {e}")
        return jsonify({
            'error': str(e)
        }), 500

    finally:
        if cursor:
            cursor.close()


def _log_ai_generation(cursor, playlist_name, model, instructions, filters,
                       status, songs_requested, songs_returned, songs_added_to_plex,
                       songs_skipped, songs_hallucinated, error_message=None,
                       plex_url=None):
    """Log AI playlist generation to database

    Args:
        cursor: Database cursor
        playlist_name: Name of playlist
        model: AI model used
        instructions: User instructions
        filters: Filter criteria dict
        status: Generation status (success, failed, warning, partial)
        songs_requested: Number of songs requested
        songs_returned: Number of songs returned by AI
        songs_added_to_plex: Number of songs added to Plex
        songs_skipped: Number of songs skipped (not in Plex)
        songs_hallucinated: Number of hallucinated songs
        error_message: Error message (if any)
        plex_url: URL to Plex playlist (if successful)
    """
    try:
        filters_json = json.dumps(filters) if filters else None

        cursor.execute("""
            INSERT INTO ai_playlist_generations (
                timestamp, playlist_name, model, instructions, filters_json,
                status, songs_requested, songs_returned, songs_added_to_plex,
                songs_skipped, songs_hallucinated, error_message, plex_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now(),
            playlist_name,
            model,
            instructions,
            filters_json,
            status,
            songs_requested,
            songs_returned,
            songs_added_to_plex,
            songs_skipped,
            songs_hallucinated,
            error_message,
            plex_url
        ))

        logger.info(f"Logged AI playlist generation: {playlist_name} ({status})")

    except Exception as e:
        logger.error(f"Failed to log AI playlist generation: {e}")


@ai_playlists_bp.route('/api/ai-playlists/delete/<int:generation_id>', methods=['DELETE'])
@requires_auth
def api_delete_ai_playlist(generation_id):
    """Delete AI-generated playlist from Plex and history

    Args:
        generation_id: ID of the generation record

    Returns JSON:
        Success:
        {
            "status": "success",
            "message": "Deleted playlist 'Party Mix' from Plex and history"
        }

        Error:
        {
            "status": "error",
            "message": "Error description",
            "error_code": "ERROR_CODE"
        }
    """
    db = get_db()
    if not db:
        return jsonify({
            'status': 'error',
            'message': 'Database not initialized',
            'error_code': 'DATABASE_ERROR'
        }), 500

    settings = get_settings()
    if not settings:
        return jsonify({
            'status': 'error',
            'message': 'Settings not loaded',
            'error_code': 'SETTINGS_ERROR'
        }), 500

    cursor = None
    try:
        cursor = db.get_cursor()

        # Get the generation record
        cursor.execute("""
            SELECT id, playlist_name, plex_url
            FROM ai_playlist_generations
            WHERE id = ?
        """, (generation_id,))

        row = cursor.fetchone()
        if not row:
            return jsonify({
                'status': 'error',
                'message': 'Generation record not found',
                'error_code': 'NOT_FOUND'
            }), 404

        generation_id, playlist_name, plex_url = row

        # Delete from Plex if URL exists
        if plex_url:
            try:
                from plexapi.server import PlexServer

                plex_config = settings.get('plex', {})
                plex_url_setting = plex_config.get('url')
                plex_token = plex_config.get('token')

                if plex_url_setting and plex_token:
                    plex = PlexServer(plex_url_setting, plex_token, timeout=30)

                    # Try to get the playlist
                    try:
                        playlist = plex.playlist(playlist_name)
                        playlist.delete()
                        logger.info(f"Deleted Plex playlist '{playlist_name}'")
                    except:
                        logger.warning(f"Plex playlist '{playlist_name}' not found or already deleted")

            except Exception as e:
                logger.error(f"Error deleting Plex playlist: {e}")
                # Continue anyway - we'll still delete the history record

        # Delete the generation record
        cursor.execute("""
            DELETE FROM ai_playlist_generations
            WHERE id = ?
        """, (generation_id,))

        logger.info(f"Deleted AI playlist generation record: {playlist_name} (ID: {generation_id})")

        return jsonify({
            'status': 'success',
            'message': f"Deleted playlist '{playlist_name}'"
        })

    except Exception as e:
        logger.error(f"Error deleting AI playlist: {e}")
        return jsonify({
            'status': 'error',
            'message': f'An unexpected error occurred: {str(e)}',
            'error_code': 'INTERNAL_ERROR'
        }), 500

    finally:
        if cursor:
            cursor.close()
