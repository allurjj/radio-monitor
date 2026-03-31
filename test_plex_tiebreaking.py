#!/usr/bin/env python3
"""
Test Plex date-based tiebreaking

This script tests the new date-based tiebreaking feature against your actual Plex library.
"""

import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from radio_monitor.auth import get_plex_server
from radio_monitor.plex import find_song_in_library
from radio_monitor.database import RadioDatabase


def test_song_matching(song_title, artist_name, debug=True):
    """Test matching a single song"""
    print(f"\n{'='*60}")
    print(f"Testing: {song_title} - {artist_name}")
    print(f"{'='*60}")

    try:
        # Get Plex server
        plex = get_plex_server()
        music_library = plex.library.section()

        # Find the song
        track = find_song_in_library(music_library, song_title, artist_name, debug=debug)

        if track:
            # Get track details
            track_title = track.title
            artist = track.artist().title if track.artist() else "Unknown"
            album = track.parent().title if hasattr(track, 'parent') and track.parent else "Unknown"
            year = track.parent().year if hasattr(track, 'parent') and track.parent and hasattr(track.parent, 'year') else "Unknown"

            print(f"\n✅ FOUND: {track_title}")
            print(f"   Artist: {artist}")
            print(f"   Album:  {album}")
            print(f"   Year:   {year}")

            # Get version preference
            from radio_monitor.plex import get_track_version_preference
            version_pref = get_track_version_preference(track_title)
            version_labels = ['studio', 'radio edit', 'remix', 'acoustic', 'live']
            version_label = version_labels[version_pref] if version_pref < 5 else 'unknown'
            print(f"   Type:   {version_label} (score: {version_pref})")

            return True
        else:
            print(f"\n❌ NOT FOUND: {song_title} - {artist_name}")
            return False

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test function"""
    print("\n" + "="*60)
    print("Plex Date-Based Tiebreaking Test")
    print("="*60)

    # Test cases - add more songs here to test
    test_cases = [
        # Known problematic case
        ("Hero", "Mariah Carey"),

        # Add more test cases here, for example:
        # ("Your Song", "Elton John"),
        # ("Sweet Child O' Mine", "Guns N' Roses"),
    ]

    results = []
    for song_title, artist_name in test_cases:
        success = test_song_matching(song_title, artist_name, debug=True)
        results.append((song_title, artist_name, success))

    # Print summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for song_title, artist_name, success in results:
        status = "✅ FOUND" if success else "❌ NOT FOUND"
        print(f"{status}: {song_title} - {artist_name}")

    print(f"\nTotal: {len(results)} tested")
    print(f"Found: {sum(1 for _, _, s in results if s)}")
    print(f"Not Found: {sum(1 for _, _, s in results if not s)}")


if __name__ == "__main__":
    main()
