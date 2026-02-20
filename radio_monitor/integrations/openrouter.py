"""
OpenRouter AI Integration for Radio Monitor

This module provides functions to communicate with OpenRouter.ai API
for AI-powered playlist generation.
"""

import json
import logging
import time
import requests
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_TIMEOUT = 120  # Increased to handle large playlists (5000+ songs)
DEFAULT_MAX_RETRIES = 3
DEFAULT_MODEL = "qwen/qwen3-next-80b-a3b-instruct:free"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


def load_system_prompt() -> str:
    """
    Load the system prompt from the prompts directory.

    Returns:
        System prompt string

    Raises:
        FileNotFoundError: If prompt file doesn't exist
    """
    prompt_path = Path(__file__).parent.parent / "prompts" / "ai_playlist_system_prompt.txt"

    if not prompt_path.exists():
        logger.warning(f"System prompt file not found at {prompt_path}, using default prompt")
        return get_default_system_prompt()

    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt = f.read().strip()
            logger.debug(f"Loaded system prompt from {prompt_path} ({len(prompt)} chars)")
            return prompt
    except Exception as e:
        logger.error(f"Error loading system prompt: {e}")
        return get_default_system_prompt()


def get_default_system_prompt() -> str:
    """
    Returns the default system prompt.

    This is used as a fallback if the prompt file is missing.
    """
    return """You are a playlist curator. You will receive:
1. A numbered list of songs in "1. Artist Name: Song Title" format
2. A user's theme description

Your task: Select songs that best match the user's theme from the provided list.

Return ONLY a JSON object in this exact format:
{"songs": ["1. Artist Name: Song Title", "2. Artist Name: Song Title", ...]}

Guidelines:
- Select 20-50 songs unless the user specifies otherwise
- Return ONLY songs from the provided list
- Do not include songs not in the list
- Return nothing else - no explanations, no markdown, no commentary
- Just the JSON object"""


def send_to_openrouter(
    song_list: List[str],
    instructions: str,
    api_key: str,
    model: Optional[str] = None,
    timeout: int = DEFAULT_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
    max_tokens: int = 100000,
    max_songs: Optional[int] = None
) -> Dict[str, Any]:
    """
    Send a playlist generation request to OpenRouter AI.

    Args:
        song_list: List of songs in format "1. Artist: Song"
        instructions: User's theme/mood instructions
        api_key: OpenRouter API key
        model: Model name (default: from settings)
        timeout: Request timeout in seconds (default: 120 from settings)
        max_retries: Number of retries on failure (default: 3 from settings)
        max_tokens: Maximum output tokens (default: 100000 from settings)
        max_songs: Maximum number of songs to return (optional, for AI guidance)

    Returns:
        API response as dictionary

    Raises:
        ValueError: If API key is missing or invalid
        requests.RequestException: If API call fails after retries
        TimeoutError: If request times out
    """
    if not api_key or not api_key.strip():
        raise ValueError("OpenRouter API key is missing or empty")

    if not model:
        model = DEFAULT_MODEL

    # Load system prompt
    system_prompt = load_system_prompt()

    # Construct user message with song list and instructions
    max_songs_instruction = f"\n\nIMPORTANT: Return exactly {max_songs} songs" if max_songs else ""

    user_message = f"""You have {len(song_list)} songs to choose from:

{chr(10).join(song_list)}

User Instructions: "{instructions}"{max_songs_instruction}

Select songs that match this theme and return ONLY JSON in format:
{{"songs": ["1. Artist: Song", "2. Artist: Song", ...]}}"""

    # Construct API request
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/allurjj/radio-monitor",
        "X-Title": "Radio Monitor AI Playlists"
    }

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_message
            }
        ],
        "temperature": 0.7,
        "max_tokens": max_tokens
    }

    # Debug: Save request to file
    try:
        debug_dir = Path(__file__).parent.parent.parent
        request_file = debug_dir / "ai_request.txt"
        with open(request_file, 'w', encoding='utf-8') as f:
            f.write(f"Model: {model}\n")
            f.write(f"Max Tokens: {payload['max_tokens']}\n")
            f.write(f"Temperature: {payload['temperature']}\n")
            f.write(f"\n{'='*80}\n")
            f.write(f"SYSTEM PROMPT:\n{'='*80}\n")
            f.write(system_prompt)
            f.write(f"\n\n{'='*80}\n")
            f.write(f"USER MESSAGE:\n{'='*80}\n")
            f.write(user_message)
        logger.info(f"Saved AI request to {request_file}")
    except Exception as e:
        logger.warning(f"Failed to save AI request to file: {e}")

    # Send request with retries
    last_exception = None
    for attempt in range(max_retries):
        try:
            logger.info(f"Sending request to OpenRouter (attempt {attempt + 1}/{max_retries})")

            response = requests.post(
                OPENROUTER_API_URL,
                headers=headers,
                json=payload,
                timeout=timeout
            )

            response.raise_for_status()

            result = response.json()

            # Log token usage (if available)
            usage = result.get('usage', {})
            if usage:
                logger.info(f"OpenRouter API call successful - "
                          f"Prompt tokens: {usage.get('prompt_tokens', 0)}, "
                          f"Completion tokens: {usage.get('completion_tokens', 0)}, "
                          f"Total tokens: {usage.get('total_tokens', 0)}")

            # Debug: Save response to file
            try:
                debug_dir = Path(__file__).parent.parent.parent
                response_file = debug_dir / "ai_response.txt"
                with open(response_file, 'w', encoding='utf-8') as f:
                    f.write(f"Status: {response.status_code}\n")
                    f.write(f"Model: {result.get('model', 'unknown')}\n")
                    if usage:
                        f.write(f"Prompt Tokens: {usage.get('prompt_tokens', 0)}\n")
                        f.write(f"Completion Tokens: {usage.get('completion_tokens', 0)}\n")
                        f.write(f"Total Tokens: {usage.get('total_tokens', 0)}\n")
                    f.write(f"\n{'='*80}\n")
                    f.write(f"RAW JSON RESPONSE:\n{'='*80}\n")
                    f.write(json.dumps(result, indent=2))
                    f.write(f"\n\n{'='*80}\n")
                    f.write(f"EXTRACTED CONTENT:\n{'='*80}\n")
                    if 'choices' in result and result['choices']:
                        content = result['choices'][0]['message']['content']
                        f.write(content)
                    else:
                        f.write("(No content found in response)")
                logger.info(f"Saved AI response to {response_file}")
            except Exception as e:
                logger.warning(f"Failed to save AI response to file: {e}")

            return result

        except requests.Timeout as e:
            last_exception = e
            logger.warning(f"OpenRouter API timeout (attempt {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                logger.info(f"Waiting {wait_time}s before retry...")
                time.sleep(wait_time)

        except requests.HTTPError as e:
            last_exception = e
            status_code = e.response.status_code

            # Don't retry authentication errors
            if status_code == 401:
                raise ValueError(f"OpenRouter API authentication failed. Check your API key.") from e

            # Don't retry rate limit errors (429)
            if status_code == 429:
                logger.error("OpenRouter API rate limit exceeded. Please wait before trying again.")
                raise requests.RequestException("Rate limit exceeded. Please try again later.") from e

            # Retry other server errors (5xx)
            if status_code >= 500:
                logger.warning(f"OpenRouter API server error (attempt {attempt + 1}/{max_retries}): {status_code}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.info(f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
            else:
                # Client errors (4xx except 401/429) - don't retry
                raise

        except requests.RequestException as e:
            last_exception = e
            logger.warning(f"OpenRouter API request failed (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                logger.info(f"Waiting {wait_time}s before retry...")
                time.sleep(wait_time)

    # All retries exhausted
    logger.error(f"OpenRouter API failed after {max_retries} attempts")
    raise requests.RequestException(f"Failed to communicate with OpenRouter API after {max_retries} retries") from last_exception


def parse_ai_response(
    response: Dict[str, Any],
    original_songs: List[Tuple[str, str]],
    max_tokens: int = 100000
) -> Tuple[List[Tuple[str, str]], int]:
    """
    Parse AI response and extract song list.

    Args:
        response: OpenRouter API response dictionary
        original_songs: Original list of songs for hallucination checking
                       Format: [(artist, song), ...]
        max_tokens: Maximum tokens for truncation check (default: 100000)

    Returns:
        Tuple of:
        - List of (artist, song) tuples
        - Count of hallucinated songs (removed)

    Raises:
        ValueError: If response format is invalid
    """
    try:
        # Extract content from response
        if 'choices' not in response or not response['choices']:
            raise ValueError("Invalid response: No choices in API response")

        content = response['choices'][0]['message']['content'].strip()

        # Check if response was truncated (hit max_tokens)
        usage = response.get('usage', {})
        completion_tokens = usage.get('completion_tokens', 0)
        if completion_tokens >= max_tokens:
            logger.warning(f"AI response may be truncated - hit max_tokens limit ({max_tokens} tokens). "
                         f"Increase max_tokens or reduce the number of songs sent to the AI.")

        logger.debug(f"AI Response content: {content[:200]}...")

        # Try to parse as JSON first
        try:
            data = json.loads(content)

            if 'songs' not in data:
                raise ValueError("Invalid JSON response: Missing 'songs' key")

            ai_songs = data['songs']

            if not isinstance(ai_songs, list):
                raise ValueError("Invalid JSON response: 'songs' is not a list")

            logger.info(f"Parsed JSON response with {len(ai_songs)} songs")

        except json.JSONDecodeError:
            # Fallback to plain text parsing
            logger.info("JSON parse failed, attempting plain text fallback")
            ai_songs = parse_plain_text_response(content)
            logger.info(f"Parsed plain text response with {len(ai_songs)} songs")

        # Parse numbered format "1. Artist: Song"
        parsed_songs = []
        hallucinations = []

        for entry in ai_songs:
            try:
                artist, song = parse_song_entry(entry)
                parsed_songs.append((artist, song))
            except ValueError as e:
                logger.warning(f"Failed to parse song entry '{entry}': {e}")
                continue

        logger.info(f"Parsed {len(parsed_songs)} valid songs from AI response")

        # De-duplicate
        unique_songs = list(dict.fromkeys(parsed_songs))  # Preserve order, remove duplicates
        duplicates_removed = len(parsed_songs) - len(unique_songs)

        if duplicates_removed > 0:
            logger.info(f"Removed {duplicates_removed} duplicate songs from AI response")

        # Hallucination check - remove songs not in original list
        original_set = set((a.lower(), s.lower()) for a, s in original_songs)
        valid_songs = []
        hallucinated_count = 0

        for artist, song in unique_songs:
            if (artist.lower(), song.lower()) in original_set:
                valid_songs.append((artist, song))
            else:
                hallucinated_count += 1
                hallucinations.append(f"{artist}: {song}")
                logger.warning(f"AI hallucinated song not in original list: {artist}: {song}")

        if hallucinated_count > 0:
            logger.warning(f"Removed {hallucinated_count} hallucinated songs: {hallucinations[:5]}")

        return valid_songs, hallucinated_count

    except Exception as e:
        logger.error(f"Error parsing AI response: {e}")
        raise ValueError(f"Failed to parse AI response: {e}") from e


def parse_plain_text_response(content: str) -> List[str]:
    """
    Parse plain text response (fallback when JSON parsing fails).

    Args:
        content: Plain text response from AI

    Returns:
        List of song strings in "Artist: Song" or "1. Artist: Song" format

    Raises:
        ValueError: If no valid songs found
    """
    songs = []
    lines = content.strip().split('\n')

    for line in lines:
        line = line.strip()

        # Skip empty lines and common non-song lines
        if not line or line.lower().startswith(('here', 'the songs', 'selected', 'playlist', '```', '{', '}')):
            continue

        # Remove markdown formatting, bullet points, etc.
        line = line.lstrip('-*•0123456789.) ')
        line = line.lstrip('0123456789.')
        line = line.strip()

        if line and ':' in line:
            songs.append(line)

    if not songs:
        raise ValueError("No valid songs found in plain text response")

    return songs


def parse_song_entry(entry: str) -> Tuple[str, str]:
    """
    Parse a single song entry in "1. Artist: Song" or "Artist: Song" format.

    Args:
        entry: Song entry string

    Returns:
        Tuple of (artist, song)

    Raises:
        ValueError: If entry format is invalid
    """
    entry = entry.strip()

    # Remove leading number if present
    if entry and entry[0].isdigit():
        parts = entry.split('.', 1)
        if len(parts) == 2:
            entry = parts[1].strip()

    # Split on first colon
    if ':' not in entry:
        raise ValueError(f"Invalid song format (missing ':'): {entry}")

    parts = entry.split(':', 1)
    artist = parts[0].strip()
    song = parts[1].strip()

    if not artist or not song:
        raise ValueError(f"Invalid song format (empty artist or song): {entry}")

    return artist, song
