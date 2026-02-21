#!/usr/bin/env python
"""
Test suite for Phase 2 Collaboration Detection

Tests:
1. Collaboration pattern detection
2. Artist splitting logic
3. Integration with scraper

Run with: python test_collaborations.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from radio_monitor.normalization import (
    detect_collaboration,
    split_artist_list,
    handle_collaboration,
    COLLABORATION_WHITELIST
)

# Windows console encoding fix
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def test_feat_pattern():
    """Test Feat/Featuring pattern detection"""
    print("\n" + "="*60)
    print("TEST 1: Feat/Featuring Pattern Detection")
    print("="*60)

    test_cases = [
        ("Shaboozey Feat Jelly Roll", True, ["Shaboozey", "Jelly Roll"]),
        ("Artist Featuring Artist2", True, ["Artist", "Artist2"]),
        ("Artist Ft Artist2", True, ["Artist", "Artist2"]),
        ("Taylor Swift", False, None),
    ]

    for artist_name, expected_is_collab, expected_artists in test_cases:
        is_collab, artists = detect_collaboration(artist_name)

        if is_collab == expected_is_collab:
            if expected_artists is None or artists == expected_artists:
                print(f"OK PASS: '{artist_name}' -> {artists}")
            else:
                print(f"X FAIL: '{artist_name}' -> {artists} (expected {expected_artists})")
                return False
        else:
            print(f"X FAIL: '{artist_name}' detected as collab={is_collab} (expected {expected_is_collab})")
            return False

    print("\nOK ALL FEAT TESTS PASSED")
    return True


def test_ampersand_pattern():
    """Test & pattern detection"""
    print("\n" + "="*60)
    print("TEST 2: Ampersand Pattern Detection")
    print("="*60)

    test_cases = [
        ("DJ Khaled & Drake", True, ["DJ Khaled", "Drake"]),
        ("Artist & Artist2", True, ["Artist", "Artist2"]),
        ("Simon And Garfunkel", False, None),  # In whitelist, should NOT split
        ("Taylor Swift", False, None),
    ]

    for artist_name, expected_is_collab, expected_artists in test_cases:
        is_collab, artists = detect_collaboration(artist_name)

        if is_collab == expected_is_collab:
            if expected_artists is None or artists == expected_artists:
                print(f"OK PASS: '{artist_name}' -> {artists}")
            else:
                print(f"X FAIL: '{artist_name}' -> {artists} (expected {expected_artists})")
                return False
        else:
            print(f"X FAIL: '{artist_name}' detected as collab={is_collab} (expected {expected_is_collab})")
            return False

    print("\nOK ALL AMPERSAND TESTS PASSED")
    return True


def test_concatenated_names():
    """Test concatenated artist names (heuristic)"""
    print("\n" + "="*60)
    print("TEST 3: Concatenated Artist Names (Heuristic)")
    print("="*60)

    test_cases = [
        ("Rascal Flatts Jonas Brothers", True),  # Should detect as collab
        ("Taylor Swift", False),
        ("Madonna", False),
    ]

    for artist_name, expected_is_collab in test_cases:
        is_collab, artists = detect_collaboration(artist_name)

        if is_collab == expected_is_collab:
            print(f"OK PASS: '{artist_name}' -> is_collab={is_collab}, artists={artists}")
        else:
            print(f"X FAIL: '{artist_name}' detected as collab={is_collab} (expected {expected_is_collab})")
            return False

    print("\nOK ALL CONCATENATED NAME TESTS PASSED")
    return True


def test_split_artist_list():
    """Test splitting artist lists by separators"""
    print("\n" + "="*60)
    print("TEST 4: Split Artist List")
    print("="*60)

    test_cases = [
        ("DJ Khaled, Drake, Lil Wayne", ["DJ Khaled", "Drake", "Lil Wayne"]),
        ("Artist1 & Artist2", ["Artist1", "Artist2"]),
        ("Artist + Artist", ["Artist", "Artist"]),
    ]

    for artist_string, expected in test_cases:
        result = split_artist_list(artist_string)

        if result == expected:
            print(f"OK PASS: '{artist_string}' -> {result}")
        else:
            print(f"X FAIL: '{artist_string}' -> {result} (expected {expected})")
            return False

    print("\nOK ALL SPLIT TESTS PASSED")
    return True


def test_handle_collaboration():
    """Test full collaboration handling"""
    print("\n" + "="*60)
    print("TEST 5: Handle Collaboration (Full Integration)")
    print("="*60)

    test_cases = [
        {
            "input": ("Shaboozey Feat Jelly Roll", "A Bar Song", None),
            "expected_count": 2,
            "expected_artists": ["Shaboozey", "Jelly Roll"],
        },
        {
            "input": ("Taylor Swift", "Love Story", "mbid123"),
            "expected_count": 1,
            "expected_artists": ["Taylor Swift"],
        },
    ]

    for test_case in test_cases:
        artist_name, song_title, mbid = test_case["input"]
        results = handle_collaboration(artist_name, song_title, mbid)

        if len(results) == test_case["expected_count"]:
            artists = [r[0] for r in results]
            if artists == test_case["expected_artists"]:
                print(f"OK PASS: '{artist_name}' -> {len(results)} artists: {artists}")
            else:
                print(f"X FAIL: '{artist_name}' -> artists={artists} (expected {test_case['expected_artists']})")
                return False
        else:
            print(f"X FAIL: '{artist_name}' -> count={len(results)} (expected {test_case['expected_count']})")
            return False

    print("\nOK ALL HANDLE COLLABORATION TESTS PASSED")
    return True


def test_whitelist():
    """Test collaboration whitelist"""
    print("\n" + "="*60)
    print("TEST 6: Collaboration Whitelist")
    print("="*60)

    # Test that whitelisted artists are not split
    whitelisted = "Hall And Oates"
    is_collab, artists = detect_collaboration(whitelisted)

    if not is_collab:
        print(f"OK PASS: Whitelisted '{whitelisted}' not split")
    else:
        print(f"X FAIL: Whitelisted '{whitelisted}' was split into {artists}")
        return False

    # Test that similar non-whitelisted artists are split
    not_whitelisted = "Artist And Artist2"
    is_collab, artists = detect_collaboration(not_whitelisted)

    if is_collab and len(artists) > 1:
        print(f"OK PASS: Non-whitelisted '{not_whitelisted}' split into {artists}")
    else:
        print(f"X FAIL: Non-whitelisted '{not_whitelisted}' not split")
        return False

    print("\nOK ALL WHITELIST TESTS PASSED")
    return True


def main():
    """Run all collaboration detection tests"""
    print("\n" + "="*60)
    print("PHASE 2 COLLABORATION DETECTION - TEST SUITE")
    print("="*60)
    print("\nTesting collaboration detection and splitting:")

    results = []

    # Run all tests
    results.append(("Feat Pattern", test_feat_pattern()))
    results.append(("Ampersand Pattern", test_ampersand_pattern()))
    results.append(("Concatenated Names", test_concatenated_names()))
    results.append(("Split Artist List", test_split_artist_list()))
    results.append(("Handle Collaboration", test_handle_collaboration()))
    results.append(("Whitelist", test_whitelist()))

    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    for test_name, passed in results:
        status = "OK PASS" if passed else "X FAIL"
        print(f"{status}: {test_name}")

    all_passed = all(result[1] for result in results)

    print("\n" + "="*60)
    if all_passed:
        print("SUCCESS ALL TESTS PASSED - Collaboration detection verified!")
    else:
        print("WARNING SOME TESTS FAILED - Please review errors above")
    print("="*60 + "\n")

    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
