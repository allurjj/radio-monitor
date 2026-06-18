"""
Phase 5: Data Quality Validation Script

Validate data quality after implementation of new scrape & match logic.
This checks:
- Total songs and validation status distribution
- Invalid combinations (PENDING MBID with valid status)
- Validation percentage
- Database health metrics
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from radio_monitor.database import RadioDatabase
from radio_monitor.data_quality import run_health_check, get_validated_count, get_invalid_count


def check_data_quality():
    """Validate data quality after implementation"""
    print("=" * 70)
    print("Phase 5: Data Quality Validation Test")
    print("=" * 70)

    # Initialize database
    db_path = os.path.join(os.path.dirname(__file__), "radio_songs.db")
    db = RadioDatabase(db_path)
    db.connect()

    cursor = db.get_cursor()

    try:
        # Get basic stats
        cursor.execute("SELECT COUNT(*) FROM songs")
        total_songs = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM artists")
        total_artists = cursor.fetchone()[0]

        print(f"\n--- Database Overview ---")
        print(f"  Total songs: {total_songs}")
        print(f"  Total artists: {total_artists}")

        # Check if validation_status column exists
        cursor.execute("PRAGMA table_info(songs)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'validation_status' not in columns:
            print("\n  ⚠️  validation_status column not found (schema not migrated)")
            print("=" * 70)
            return

        # Get validation status distribution
        cursor.execute("""
            SELECT validation_status, COUNT(*) as count
            FROM songs
            GROUP BY validation_status
        """)
        validation_results = cursor.fetchall()

        print(f"\n--- Validation Status Distribution ---")

        status_counts = {}
        total_counted = 0
        for status, count in validation_results:
            status_key = status or 'NULL'
            status_counts[status_key] = count
            total_counted += count
            print(f"  {status_key}: {count}")

        if total_counted > 0:
            valid = status_counts.get('valid', 0)
            pending = status_counts.get('pending', 0)
            invalid = status_counts.get('invalid', 0)
            unvalidated = status_counts.get('unvalidated', 0) + status_counts.get('NULL', 0)

            print(f"\n--- Validation Percentages ---")
            print(f"  Valid: {valid} ({valid/total_counted*100:.1f}%)")
            print(f"  Pending: {pending} ({pending/total_counted*100:.1f}%)")
            print(f"  Invalid: {invalid} ({invalid/total_counted*100:.1f}%)")
            print(f"  Unvalidated: {unvalidated} ({unvalidated/total_counted*100:.1f}%)")

            # Check for PENDING MBIDs with valid status (shouldn't happen)
            print(f"\n--- Data Consistency Checks ---")
            cursor.execute("""
                SELECT COUNT(*)
                FROM songs
                WHERE artist_mbid LIKE 'PENDING-%'
                  AND validation_status = 'valid'
            """)
            invalid_combos = cursor.fetchone()[0]

            if invalid_combos > 0:
                print(f"  ⚠️  WARNING: {invalid_combos} songs have PENDING MBID but valid status")
            else:
                print(f"  ✓ No invalid combinations (PENDING MBID with valid status)")

            # Check for NULL MBIDs with valid status
            cursor.execute("""
                SELECT COUNT(*)
                FROM songs
                WHERE (artist_mbid IS NULL OR artist_mbid = '')
                  AND validation_status = 'valid'
            """)
            null_mbid_valid = cursor.fetchone()[0]

            if null_mbid_valid > 0:
                print(f"  ⚠️  WARNING: {null_mbid_valid} songs have NULL MBID but valid status")
            else:
                print(f"  ✓ No NULL MBID with valid status")

        # Run comprehensive health check
        print(f"\n--- Health Check Results ---")
        health_issues = run_health_check(db)

        for issue_type in ['critical', 'warning', 'info']:
            issues = health_issues.get(issue_type, [])
            if issues:
                for issue in issues:
                    print(f"  [{issue_type.upper()}] {issue.get('message', 'Unknown issue')}")

        # Health score
        health_score = health_issues.get('summary', {}).get('health_score', 0)
        print(f"\n  Health Score: {health_score}/100")

        # Validation expectations from plan:
        # - Validation accuracy: 95%+ valid
        # - Pending rate: <10%
        # - Bad data prevented: 0 incorrect artist-song combinations

        print(f"\n--- Validation Expectations (from plan) ---")
        print(f"  Validation accuracy: 95%+ valid")
        print(f"  Pending rate: <10%")
        print(f"  Bad data prevented: 0 incorrect artist-song combinations")

        # Check if we meet expectations
        if total_counted > 0:
            valid_pct = valid / total_counted * 100
            pending_pct = pending / total_counted * 100

            print(f"\n--- Meeting Expectations ---")
            if valid_pct >= 95:
                print(f"  ✓ Validation accuracy: {valid_pct:.1f}% >= 95%")
            else:
                print(f"  ✗ Validation accuracy: {valid_pct:.1f}% < 95% (BELOW EXPECTATION)")

            if pending_pct < 10:
                print(f"  ✓ Pending rate: {pending_pct:.1f}% < 10%")
            else:
                print(f"  ✗ Pending rate: {pending_pct:.1f}% >= 10% (ABOVE EXPECTATION)")

        print("=" * 70)

        return {
            'total_songs': total_songs,
            'total_artists': total_artists,
            'status_counts': status_counts,
            'health_score': health_score
        }

    finally:
        cursor.close()


if __name__ == '__main__':
    check_data_quality()
