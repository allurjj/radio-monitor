"""Test SSL fix for iHeartRadio scraping"""
import sys
sys.path.insert(0, r'C:\Users\allurjj\Documents\Radio_Monitor')
from radio_monitor.scrapers import scrape_all_stations
from radio_monitor.database import RadioDatabase
import logging

logging.basicConfig(level=logging.INFO)

print('Testing SSL fix with one station scrape...')
db = RadioDatabase('radio_songs.db')
db.connect()

# Test just one station
results = scrape_all_stations(db, station_ids=['wlite'])

print(f'\nTest scrape found {len(results)} songs')
for artist, song, mbid in results[:10]:
    print(f'  {artist}: {song}')
