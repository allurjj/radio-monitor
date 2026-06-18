"""Analyze current database state"""
import sqlite3
import os

db_path = 'C:/Users/allurjj/Documents/Radio_Monitor/radio_songs.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check database stats
    cursor.execute('SELECT COUNT(*) FROM artists')
    print(f'Artists: {cursor.fetchone()[0]}')

    cursor.execute('SELECT COUNT(*) FROM songs')
    print(f'Songs: {cursor.fetchone()[0]}')

    # Check for PENDING MBIDs
    cursor.execute('SELECT COUNT(*) FROM artists WHERE mbid LIKE "PENDING%"')
    pending_count = cursor.fetchone()[0]
    print(f'Pending MBIDs: {pending_count}')

    # Check for corrupted multi-artist names (no separators)
    cursor.execute('''
        SELECT COUNT(*)
        FROM artists
        WHERE name LIKE '% %'
        AND name NOT GLOB '*[;&+]*'
        AND name NOT LIKE '% feat%'
        AND name NOT LIKE '% ft.%'
        AND name NOT LIKE '% featuring%'
        AND mbid LIKE 'PENDING%'
    ''')
    corrupted = cursor.fetchone()[0]
    print(f'Corrupted multi-artist (no separators): {corrupted}')

    # Check for (feat.) in artist names
    cursor.execute('''
        SELECT COUNT(*)
        FROM songs
        WHERE artist_name LIKE '%(feat.%'
        AND artist_mbid IS NULL
    ''')
    feat_null_mbid = cursor.fetchone()[0]
    print(f'Songs with (feat.) and NULL MBID: {feat_null_mbid}')

    # Show sample of recent songs
    cursor.execute('''
        SELECT artist_name, song_title
        FROM songs
        WHERE artist_name LIKE '%Shaboozey%'
        LIMIT 5
    ''')
    print('\nSample Shaboozey songs:')
    for row in cursor.fetchall():
        print(f'  {row[1][:30]:30} | {row[0][:40]:40}')

    # Show PENDING artists
    cursor.execute('''
        SELECT name, mbid
        FROM artists
        WHERE mbid LIKE 'PENDING%'
        LIMIT 10
    ''')
    print('\nSample PENDING artists:')
    for row in cursor.fetchall():
        print(f'  {row[0][:40]:40} | {row[1][:40]}')

    conn.close()
else:
    print('Database not found yet')
