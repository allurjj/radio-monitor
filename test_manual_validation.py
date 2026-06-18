"""
Manual testing script for song validation helper functions.

This script tests the helper functions that enhance song validation:
- strip_song_suffixes(): Removes version suffixes for better matching
- calculate_similarity(): Calculates string similarity for near matches

Usage:
    python test_manual_validation.py
"""

from radio_monitor.normalization import strip_song_suffixes, calculate_similarity


def test_suffix_stripping():
    """Test suffix stripping functionality"""
    print("\nSuffix Stripping Tests")
    print("=" * 80)

    test_cases = [
        # (input, expected_output, description)
        ("Neon Moon (Remix)", "Neon Moon", "Basic remix suffix"),
        ("Neon Moon (Live)", "Neon Moon", "Live version suffix"),
        ("Austin - Live", "Austin", "Dash-separated live"),
        ("Test Song (Radio Edit)", "Test Song", "Radio edit suffix"),
        ("Test Song (Remastered)", "Test Song", "Remastered suffix"),
        ("Neon Moon", "Neon Moon", "Clean title - no change"),
        ("Bad (Remix)", "Bad", "Short title with remix"),
        ("Up (Live)", "Up", "Short title with live"),
    ]

    passed = 0
    failed = 0

    for input_title, expected_output, description in test_cases:
        actual_output = strip_song_suffixes(input_title)
        result = "PASS" if actual_output == expected_output else "FAIL"

        if actual_output == expected_output:
            passed += 1
        else:
            failed += 1

        print(f"{result}: {description}")
        print(f"       '{input_title}' -> '{actual_output}' (expected: '{expected_output}')")

    print("=" * 80)
    print(f"Results: {passed} passed, {failed} failed")

    return passed, failed


def test_similarity_calculation():
    """Test similarity calculation functionality"""
    print("\nSimilarity Calculation Tests")
    print("=" * 80)

    test_cases = [
        # (str1, str2, min_expected, max_expected, description)
        ("Neon Moon", "Neon Moon", 1.0, 1.0, "Exact match"),
        ("Neon Moon", "neon moon", 1.0, 1.0, "Case insensitive"),
        ("Neon Moon", "Neon Moo", 0.85, 1.0, "One character difference"),
        ("Test Song", "Completely Different", 0.0, 0.3, "Completely different"),
        ("Neon Moon", "Boot Scootin' Boogy", 0.0, 0.3, "Completely different song"),
    ]

    passed = 0
    failed = 0

    for str1, str2, min_expected, max_expected, description in test_cases:
        similarity = calculate_similarity(str1, str2)
        result = "PASS" if min_expected <= similarity <= max_expected else "FAIL"

        if min_expected <= similarity <= max_expected:
            passed += 1
        else:
            failed += 1

        print(f"{result}: {description}")
        print(f"       '{str1}' vs '{str2}' = {similarity:.2f} (expected: {min_expected:.2f}-{max_expected:.2f})")

    print("=" * 80)
    print(f"Results: {passed} passed, {failed} failed")

    return passed, failed


if __name__ == '__main__':
    import sys

    print("Song Validation Helper Functions - Manual Testing")
    print("=" * 80)
    print()

    # Run suffix stripping tests
    passed1, failed1 = test_suffix_stripping()

    print()

    # Run similarity calculation tests
    passed2, failed2 = test_similarity_calculation()

    print()
    print("=" * 80)
    print(f"Total Results: {passed1 + passed2} passed, {failed1 + failed2} failed")

    if failed1 + failed2 == 0:
        print("[PASS] All tests passed!")
    else:
        print(f"[FAIL] {failed1 + failed2} test(s) failed")

    sys.exit(0 if (failed1 + failed2) == 0 else 1)
