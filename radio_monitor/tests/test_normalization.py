"""
Unit Tests for Text Normalization Module

Tests for radio_monitor.normalization module

Run with:
    python -m pytest radio_monitor/tests/test_normalization.py -v
    OR
    python -m pytest radio_monitor/tests/test_normalization.py -v --tb=short
"""

import pytest
from radio_monitor.normalization import (
    normalize_text,
    normalize_text_aggressive,
    normalize_artist_name,
    normalize_song_title,
    handle_special_hyphens,
    handle_special_apostrophes,
    normalize_with_edge_cases,
    should_preserve_caps,
    CAPS_EXCEPTIONS,
    detect_collaboration,
    split_collaboration_artists,
    handle_collaboration
)


class TestNormalizeText:
    """Tests for normalize_text() function"""

    def test_empty_string(self):
        """Test empty string handling"""
        assert normalize_text("") == ""
        assert normalize_text(None) == ""

    def test_whitespace_trimming(self):
        """Test leading/trailing whitespace removal"""
        assert normalize_text("  Perfect  ") == "Perfect"
        assert normalize_text("\tDon't\n") == "Don't"
        assert normalize_text("  My Love  ") == "My Love"

    def test_whitespace_normalization(self):
        """Test multiple whitespace → single space"""
        assert normalize_text("Don't   Stop") == "Don't Stop"
        assert normalize_text("My    Love") == "My Love"
        assert normalize_text("It's  My  Life") == "It's My Life"

    def test_apostrophe_unification(self):
        """Test apostrophe variant unification"""
        # Note: In Python, curly quotes may not render correctly in tests
        # Test double apostrophes
        assert normalize_text("Don''t") == "Don't"
        assert normalize_text("Fallin''") == "Fallin'"

    def test_all_caps_conversion(self):
        """Test ALL CAPS → Title Case"""
        assert normalize_text("PERFECT") == "Perfect"
        assert normalize_text("AIN'T IT FUN") == "Ain't It Fun"
        assert normalize_text("IT'S MY LIFE") == "It's My Life"
        assert normalize_text("HOMEWRECKER") == "Homewrecker"
        assert normalize_text("NICE TO MEET YOU") == "Nice To Meet You"

    def test_preserve_title_case(self):
        """Test already Title Case text is unchanged"""
        assert normalize_text("Perfect") == "Perfect"
        assert normalize_text("My Love") == "My Love"
        assert normalize_text("Don't Stop Believin'") == "Don't Stop Believin'"

    def test_preserve_known_acronyms(self):
        """Test known acronyms stay ALL CAPS"""
        assert normalize_text("ABBA") == "ABBA"
        assert normalize_text("ACDC") == "ACDC"
        assert normalize_text("KISS") == "KISS"
        assert normalize_text("NSYNC") == "NSYNC"
        assert normalize_text("TLC") == "TLC"
        assert normalize_text("BTS") == "BTS"
        assert normalize_text("R.E.M.") == "R.E.M."
        assert normalize_text("O.A.R.") == "O.A.R."

    def test_short_all_caps_not_preserved(self):
        """Test short ALL CAPS words (not in exceptions) are converted"""
        assert normalize_text("MY") == "My"
        assert normalize_text("THE") == "The"
        assert normalize_text("AND") == "And"

    def test_mixed_case_unchanged(self):
        """Test mixed case text is unchanged"""
        assert normalize_text("Ne-Yo") == "Ne-Yo"
        assert normalize_text("McCartney") == "McCartney"
        assert normalize_text("DeBarge") == "DeBarge"

    def test_real_radio_examples(self):
        """Test real examples from radio data"""
        assert normalize_text("5 Foot 9") == "5 Foot 9"
        assert normalize_text("I DON'T WANT TO BE") == "I Don't Want To Be"
        assert normalize_text("IRREPLACEABLE") == "Irreplaceable"
        assert normalize_text("CLOSER") == "Closer"


class TestApostropheHandling:
    """Tests for apostrophe handling"""

    def test_double_apostrophes(self):
        """Test double apostrophes unified to single"""
        assert normalize_text("Don''t") == "Don't"
        assert normalize_text("Fallin''") == "Fallin'"
        assert normalize_text("I''m") == "I'm"

    def test_apostrophes_in_various_positions(self):
        """Test apostrophes in different positions"""
        assert normalize_text("Don't") == "Don't"  # Middle
        assert normalize_text("Fallin'") == "Fallin'"  # End
        assert normalize_text("'Cause") == "'Cause"  # Beginning


class TestWhitespaceHandling:
    """Tests for whitespace normalization"""

    def test_tabs_to_spaces(self):
        """Test tabs converted to spaces"""
        assert normalize_text("Don't\tStop") == "Don't Stop"
        assert normalize_text("My\t\tLove") == "My Love"

    def test_newlines_to_spaces(self):
        """Test newlines converted to spaces"""
        assert normalize_text("Don't\nStop") == "Don't Stop"
        assert normalize_text("My\r\nLove") == "My Love"

    def test_mixed_whitespace(self):
        """Test mixed whitespace characters"""
        assert normalize_text("Don't \t\n Stop") == "Don't Stop"


class TestSpecialCharacters:
    """Tests for special character handling"""

    def test_punctuation_preserved(self):
        """Test that regular punctuation is preserved"""
        assert normalize_text("Don't Stop!") == "Don't Stop!"
        assert normalize_text("Rock & Roll") == "Rock & Roll"
        assert normalize_text("Doin' It") == "Doin' It"


class TestNormalizeTextAggressive:
    """Tests for aggressive normalization (Plex matching only)"""

    def test_aggressive_removes_punctuation(self):
        """Test aggressive mode removes punctuation"""
        assert normalize_text_aggressive("Don't Stop!") == "dont stop"
        assert normalize_text_aggressive("Rock & Roll") == "rock roll"

    def test_aggressive_lowercases(self):
        """Test aggressive mode converts to lowercase"""
        assert normalize_text_aggressive("PERFECT") == "perfect"
        assert normalize_text_aggressive("My Love") == "my love"

    def test_aggressive_removes_apostrophes(self):
        """Test aggressive mode removes apostrophes"""
        assert normalize_text_aggressive("Don't Stop") == "dont stop"
        assert normalize_text_aggressive("Fallin'") == "fallin"


class TestNormalizeArtistName:
    """Tests for normalize_artist_name() function"""

    def test_artist_normalization(self):
        """Test artist name normalization"""
        assert normalize_artist_name("PINK") == "P!NK"  # Exception
        assert normalize_artist_name("GUNS N' ROSES") == "Guns N' Roses"
        assert normalize_artist_name("Ne-Yo") == "Ne-Yo"

    def test_known_artists_preserved(self):
        """Test known artists are preserved correctly"""
        assert normalize_artist_name("ABBA") == "ABBA"
        assert normalize_artist_name("KISS") == "KISS"
        assert normalize_artist_name("R.E.M.") == "R.E.M."


class TestNormalizeSongTitle:
    """Tests for normalize_song_title() function"""

    def test_song_normalization(self):
        """Test song title normalization"""
        assert normalize_song_title("AIN'T IT FUN") == "Ain't It Fun"
        assert normalize_song_title("PERFECT") == "Perfect"
        assert normalize_song_title("  Don't Stop  ") == "Don't Stop"

    def test_songs_with_roman_numerals(self):
        """Test songs with Roman numerals"""
        # Note: Roman numerals are preserved if they're the entire text
        # But in titles like "Part II", they'll be title-cased
        assert normalize_song_title("PART I") == "Part I"
        assert normalize_song_title("PART II") == "Part II"


class TestHandleSpecialHyphens:
    """Tests for handle_special_hyphens() function"""

    def test_special_hyphen_conversion(self):
        """Test unicode hyphens converted to ASCII"""
        # Note: Testing with actual unicode characters
        assert handle_special_hyphens("Ne‐Yo") == "Ne-Yo"  # U+2010
        # En dash
        assert handle_special_hyphens("The All–American Rejects") == "The All-American Rejects"

    def test_regular_hyphen_unchanged(self):
        """Test regular ASCII hyphen unchanged"""
        assert handle_special_hyphens("Ne-Yo") == "Ne-Yo"
        assert handle_special_hyphens("The All-American Rejects") == "The All-American Rejects"


class TestHandleSpecialApostrophes:
    """Tests for handle_special_apostrophes() function"""

    def test_special_apostrophe_conversion(self):
        """Test unicode apostrophes converted to ASCII"""
        # Right single quotation mark
        assert handle_special_apostrophes("Don't") == "Don't"

    def test_double_apostrophe_removal(self):
        """Test double apostrophes reduced to single"""
        assert handle_special_apostrophes("Don''t") == "Don't"

    def test_backtick_conversion(self):
        """Test backtick converted to apostrophe"""
        assert handle_special_apostrophes("Don`t") == "Don't"


class TestNormalizeWithEdgeCases:
    """Tests for normalize_with_edge_cases() function"""

    def test_combined_normalization(self):
        """Test all edge cases handled together"""
        result = normalize_with_edge_cases("Ne‐Yo")
        assert result == "Ne-Yo"  # Hyphen fixed

        result = normalize_with_edge_cases("AIN'T IT FUN")
        assert result == "Ain't It Fun"  # ALL CAPS + apostrophe

    def test_whitespace_and_special_chars(self):
        """Test whitespace + special characters"""
        result = normalize_with_edge_cases("  Don''t  Stop  ")
        assert result == "Don't Stop"


class TestShouldPreserveCaps:
    """Tests for should_preserve_caps() function"""

    def test_known_exceptions_preserved(self):
        """Test known exceptions return True"""
        assert should_preserve_caps("ABBA") == True
        assert should_preserve_caps("KISS") == True
        assert should_preserve_caps("R.E.M.") == True
        assert should_preserve_caps("NSYNC") == True

    def test_regular_all_caps_not_preserved(self):
        """Test regular ALL CAPS returns False"""
        assert should_preserve_caps("PERFECT") == False
        assert should_preserve_caps("MY LOVE") == False
        assert should_preserve_caps("HOMEWRECKER") == False

    def test_short_all_caps_preserved(self):
        """Test short ALL CAPS (likely acronyms) preserved"""
        assert should_preserve_caps("BTS") == True  # In exceptions
        assert should_preserve_caps("TLC") == True  # In exceptions

    def test_roman_numerals_preserved(self):
        """Test Roman numerals preserved"""
        assert should_preserve_caps("I") == True
        assert should_preserve_caps("II") == True
        assert should_preserve_caps("III") == True
        assert should_preserve_caps("IV") == True
        assert should_preserve_caps("V") == True

    def test_mixed_case_returns_false(self):
        """Test mixed case returns False"""
        assert should_preserve_caps("Perfect") == False
        assert should_preserve_caps("Ne-Yo") == False


class TestRealWorldExamples:
    """Tests with real-world examples from database"""

    def test_radio_station_all_caps(self):
        """Test actual ALL CAPS from radio stations"""
        examples = {
            "PERFECT": "Perfect",
            "AIN'T IT FUN": "Ain't It Fun",
            "IT'S MY LIFE": "It's My Life",
            "HOMEWRECKER": "Homewrecker",
            "I JUST MIGHT": "I Just Might",
            "NICE TO MEET YOU": "Nice To Meet You",
            "IRREPLACEABLE": "Irreplaceable",
            "CLOSER": "Closer",
            "BIG GIRLS DON'T CRY": "Big Girls Don't Cry",
            "SK8ER BOI": "Sk8er Boi",  # Stylized spelling preserved
        }

        for input_text, expected in examples.items():
            result = normalize_text(input_text)
            assert result == expected, f"Failed: {input_text} → {result} (expected {expected})"

    def test_collaborations(self):
        """Test artist collaborations"""
        examples = {
            "MIRANDA LAMBERT & CHRIS STAPLETON": "Miranda Lambert & Chris Stapleton",
            "DHT FEAT. EDMEE": "DHT Feat. Edmee",
            "POST MALONE & MORGAN WALLEN": "Post Malone & Morgan Wallen",
        }

        for input_text, expected in examples.items():
            result = normalize_text(input_text)
            assert result == expected, f"Failed: {input_text} → {result} (expected {expected})"

    def test_plex_library_titles(self):
        """Test actual Plex library titles (should be unchanged)"""
        examples = [
            "Back At One",
            "Marry You",
            "Live and Let Die",
            "John Deere Green",
            "Don't Stop Believin'",
        ]

        for title in examples:
            result = normalize_text(title)
            assert result == title, f"Plex title changed: {title} → {result}"


class TestPreserveCapsParameter:
    """Tests for preserve_caps parameter"""

    def test_preserve_caps_true(self):
        """Test preserve_caps=True keeps ALL CAPS"""
        assert normalize_text("PERFECT", preserve_caps=True) == "PERFECT"
        assert normalize_text("MY LOVE", preserve_caps=True) == "MY LOVE"

    def test_preserve_caps_false(self):
        """Test preserve_caps=False converts ALL CAPS"""
        assert normalize_text("PERFECT", preserve_caps=False) == "Perfect"
        assert normalize_text("MY LOVE", preserve_caps=False) == "My Love"


class TestEmptyAndNone:
    """Tests for empty and None inputs"""

    def test_none_input(self):
        """Test None input returns empty string"""
        assert normalize_text(None) == ""
        assert normalize_artist_name(None) == ""
        assert normalize_song_title(None) == ""

    def test_empty_string_input(self):
        """Test empty string input"""
        assert normalize_text("") == ""
        assert normalize_artist_name("") == ""
        assert normalize_song_title("") == ""


if __name__ == '__main__':
    # Run tests with pytest
    pytest.main([__file__, '-v', '--tb=short'])
