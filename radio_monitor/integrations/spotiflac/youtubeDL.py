"""
Working YouTube Downloader using yt-dlp directly.

This replaces the broken SpotubeDL and Cobalt APIs with yt-dlp.
"""

import os
import re
import yt_dlp
from typing import Callable
from mutagen.id3 import ID3, ID3NoHeaderError, TIT2, TPE1, TALB, TPE2, TDRC, TRCK, TPOS, APIC, TPUB, WXXX, COMM
from mutagen.mp3 import MP3

def sanitize_filename(value: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", value).strip()

def safe_int(value) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0

class YouTubeDownloader:
    """
    YouTube downloader using yt-dlp library.

    This replaces the old SpotubeDL/Cobalt approach which no longer works.
    """

    def __init__(self, timeout: float = 120.0):
        self.timeout = timeout
        self.progress_callback: Callable[[int, int], None] = None

    def set_progress_callback(self, callback: Callable[[int, int], None]) -> None:
        self.progress_callback = callback

    def get_youtube_url_from_spotify(self, spotify_track_id: str, track_name: str = None, artist_name: str = None) -> str:
        """
        Get YouTube URL via Songlink (the working method from earlier tests).
        """
        import requests
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        url = f"https://song.link/s/{spotify_track_id}"
        headers = {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"}

        try:
            # Try to extract from Songlink
            session = requests.Session()
            session.verify = False
            resp = session.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            html = resp.text

            match = re.search(r'https://(?:music\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})', html)
            if not match:
                match = re.search(r'https://youtu\.be/([a-zA-Z0-9_-]{11})', html)

            if match:
                video_id = match.group(1)
                yt_url = f"https://music.youtube.com/watch?v={video_id}"
                print(f"[OK] Found on Songlink: {yt_url}")
                return yt_url
            else:
                print("[!] Songlink does not have a YouTube link for this track.")

        except Exception as e:
            print(f"[!] Error accessing Songlink: {e}")

        # Fallback: direct YouTube search (scrape YouTube search results page)
        if track_name and artist_name:
            from urllib.parse import quote
            query = quote(f"{track_name} {artist_name}")
            search_url = f"https://www.youtube.com/results?search_query={query}"

            try:
                session = requests.Session()
                session.verify = False
                resp = session.get(search_url, timeout=10)
                resp.raise_for_status()

                # YouTube stores search data inside a JS variable called ytInitialData
                match = re.search(r'"videoId":"([a-zA-Z0-9_-]{11})"', resp.text)
                if match:
                    video_id = match.group(1)
                    yt_url = f"https://music.youtube.com/watch?v={video_id}"
                    print(f"[OK] Video found via YouTube Search: {yt_url}")
                    return yt_url
            except Exception as e:
                print(f"Error in direct YouTube search: {e}")

        raise Exception("Failed to resolve YouTube URL")

    def download_by_spotify_id(self, spotify_track_id, **kwargs):
        """
        Download track using yt-dlp.

        Process:
        1. Get YouTube URL via Songlink/scraping
        2. Download the audio using yt-dlp
        3. Convert to MP3 and embed metadata
        """
        output_dir = kwargs.get("output_dir", ".")
        os.makedirs(output_dir, exist_ok=True)

        track_name = kwargs.get("spotify_track_name", "Unknown")
        artist_name = kwargs.get("spotify_artist_name", "Unknown").split(",")[0]

        safe_title = sanitize_filename(track_name)
        safe_artist = sanitize_filename(artist_name)

        expected_filename = f"{safe_artist} - {safe_title}.mp3"
        expected_path = os.path.join(output_dir, expected_filename)

        if os.path.exists(expected_path) and os.path.getsize(expected_path) > 0:
            print(f"File already exists: {expected_path}")
            return expected_path

        # Get YouTube URL using Songlink (works!) or direct search (fallback)
        yt_url = self.get_youtube_url_from_spotify(
            spotify_track_id,
            track_name=track_name,
            artist_name=artist_name
        )

        print(f"Using YouTube URL: {yt_url}")

        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }],
            'outtmpl': os.path.join(output_dir, f"{safe_artist} - {safe_title}.%(ext)s"),
            'quiet': False,
            'no_warnings': False,
            'nocheckcertificate': True,
            # Enhanced YouTube options to bypass restrictions
            'extractor_args': {
                'youtube': [
                    'player_client=android,androidembed',
                    'player_skip=configs,js,webpage,age_gate',
                ]
            },
            # Use mobile user agent
            'http_headers': {
                'User-Agent': 'com.google.android.youtube/17.36.4 (Linux; U; Android 12) gzip',
            },
            # Additional options
            'ignoreerrors': True,
            'retries': 10,
            'fragment_retries': 10,
            # Progress hook
            'progress_hooks': [self._yt_dlp_progress_hook] if self.progress_callback else [],
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Download the video using the direct URL
                info = ydl.extract_info(yt_url, download=True)

                # Find the downloaded file - yt-dlp may have named it differently
                from glob import glob
                potential_files = list(glob(os.path.join(output_dir, "*.mp3")))

                # Try to find the most recent file matching our pattern
                downloaded_path = None
                for f in sorted(potential_files, key=os.path.getmtime, reverse=True):
                    if safe_artist in f and safe_title in f:
                        downloaded_path = f
                        break

                # Fallback to expected path
                if not downloaded_path and os.path.exists(expected_path):
                    downloaded_path = expected_path

                # Last resort: use the most recently modified MP3
                if not downloaded_path and potential_files:
                    downloaded_path = sorted(potential_files, key=os.path.getmtime, reverse=True)[0]

                if not downloaded_path or not os.path.exists(downloaded_path):
                    raise Exception(f"Downloaded file not found. Expected: {expected_path}. Available: {potential_files}")

                # Rename to expected filename if needed
                if downloaded_path != expected_path:
                    try:
                        os.rename(downloaded_path, expected_path)
                        downloaded_path = expected_path
                        print(f"Renamed to: {downloaded_path}")
                    except:
                        pass  # Keep the original name if rename fails

                print(f"Downloaded to: {downloaded_path}")

                # Embed metadata
                self.embed_metadata(
                    downloaded_path,
                    kwargs.get("spotify_track_name"),
                    kwargs.get("spotify_artist_name"),
                    kwargs.get("spotify_album_name"),
                    kwargs.get("spotify_album_artist"),
                    kwargs.get("spotify_release_date"),
                    kwargs.get("spotify_track_number", 1),
                    kwargs.get("spotify_total_tracks", 1),
                    kwargs.get("spotify_disc_number", 1),
                    kwargs.get("spotify_total_discs", 1),
                    kwargs.get("spotify_cover_url"),
                    kwargs.get("spotify_publisher"),
                    kwargs.get("spotify_url")
                )

                return downloaded_path

        except Exception as e:
            raise Exception(f"yt-dlp download failed: {e}")

    def _yt_dlp_progress_hook(self, d):
        """Progress hook for yt-dlp."""
        if self.progress_callback and d['status'] == 'downloading':
            total = d.get('total', 0) or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            self.progress_callback(downloaded, total)

    def embed_metadata(self, filepath, title, artist, album, album_artist, date, track_num, total_tracks, disc_num, total_discs, cover_url, publisher=None, url=None):
        print("Embedding metadata and cover art...")
        try:
            try:
                audio = ID3(filepath)
                audio.delete()
            except ID3NoHeaderError:
                audio = ID3()

            if title: audio.add(TIT2(encoding=3, text=str(title)))
            if artist: audio.add(TPE1(encoding=3, text=str(artist)))
            if album: audio.add(TALB(encoding=3, text=str(album)))
            if album_artist: audio.add(TPE2(encoding=3, text=str(album_artist)))
            if date: audio.add(TDRC(encoding=3, text=str(date)))

            audio.add(TRCK(encoding=3, text=f"{safe_int(track_num)}/{safe_int(total_tracks)}"))
            audio.add(TPOS(encoding=3, text=f"{safe_int(disc_num)}/{safe_int(total_discs)}"))

            if publisher:
                audio.add(TPUB(encoding=3, text=[str(publisher)]))
            if url:
                audio.add(WXXX(encoding=3, desc=u'', url=str(url)))

            audio.add(COMM(
                encoding=3,
                lang='eng',
                desc=u'',
                text=[u"Downloaded by Radio Monitor SpotiFLAC integration"]
            ))

            if cover_url:
                try:
                    import requests
                    # Use SSL-disabled session
                    session = requests.Session()
                    session.verify = False
                    import urllib3
                    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

                    resp = session.get(cover_url, timeout=10)
                    if resp.status_code == 200:
                        audio.add(APIC(
                            encoding=3,
                            mime='image/jpeg',
                            type=3,
                            desc='Cover',
                            data=resp.content
                        ))
                except Exception as e:
                    print(f"Warning: Could not download cover: {e}")

            audio.save(filepath, v2_version=3)
            print("Metadata embedded successfully")

        except Exception as e:
            print(f"Warning: Failed to embed metadata: {e}")
