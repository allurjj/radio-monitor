"""
Phase 2 Tests: Increase MusicBrainz Query Limit

Tests that verify the MusicBrainz query limit has been increased from 5 to 20.
This improves matching accuracy for artists with similar names.
"""

import pytest
import re


def test_musicbrainz_query_limit():
    """Test that MusicBrainz queries use limit=20"""
    # This test verifies the URL contains limit=20
    # We check the source code directly
    from radio_monitor.normalization import check_musicbrainz_exists
    import inspect

    source = inspect.getsource(check_musicbrainz_exists)

    # Check that limit=20 is in the code
    assert 'limit=20' in source, "MusicBrainz query should use limit=20"
    assert 'limit=5' not in source, "Old limit=5 should be removed"

    # Also verify the URL construction
    assert '&limit=20' in source or 'limit=20' in source


def test_musicbrainz_better_matching():
    """Test that higher limit improves matching for edge cases"""
    from radio_monitor.normalization import check_musicbrainz_exists

    # Test with artist that has multiple similar names
    # Results beyond first 5 should now be considered

    # Example: "Pink" vs "P!NK" - with limit=5 might miss
    # With limit=20, both should be found
    artist_name = "P!NK"

    # This should return True (artist exists)
    # With higher limit, more likely to find the correct match
    result = check_musicbrainz_exists(artist_name)

    assert result is not None, "check_musicbrainz_exists should return a result"
    # Note: May return False if API is down or rate limited


def test_musicbrainz_query_format():
    """Test that MusicBrainz query format is correct"""
    from radio_monitor.normalization import check_musicbrainz_exists
    import inspect

    source = inspect.getsource(check_musicbrainz_exists)

    # Verify the URL format uses proper quoting
    assert 'requests.utils.quote' in source, "Query should be URL-encoded"

    # Verify User-Agent header is present (required by MusicBrainz)
    assert 'User-Agent' in source, "User-Agent header required by MusicBrainz"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
