import base64
import json
import os
import re
import subprocess
import time
from typing import Callable, Dict
from urllib.parse import quote
import requests
from mutagen.flac import FLAC, Picture
from mutagen.id3 import PictureType
from mutagen.mp4 import MP4, MP4Cover
from pathlib import Path

# Rate limiting protection (shared with Tidal)
_last_api_call_time = 0
_min_delay_between_calls = 2.0  # Minimum seconds between API calls

def _respect_rate_limit():
    """Ensure minimum delay between API calls to avoid rate limiting"""
    global _last_api_call_time
    current_time = time.time()
    time_since_last_call = current_time - _last_api_call_time

    if time_since_last_call < _min_delay_between_calls:
        sleep_time = _min_delay_between_calls - time_since_last_call
        print(f"Rate limit protection: waiting {sleep_time:.1f}s before API call")
        time.sleep(sleep_time)

    _last_api_call_time = time.time()

# Share the same cache as Tidal (use the same file)
_songlink_cache = {}
_cache_file = Path.home() / '.spotiflac' / 'songlink_cache.json'

def _load_songlink_cache():
    """Load song.link cache from disk"""
    global _songlink_cache
    try:
        if _cache_file.exists():
            with open(_cache_file, 'r') as f:
                _songlink_cache = json.load(f)
    except Exception:
        _songlink_cache = {}

def _save_songlink_cache():
    """Save song.link cache to disk"""
    try:
        _cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(_cache_file, 'w') as f:
            json.dump(_songlink_cache, f)
    except Exception:
        pass

# Load cache on module import
_load_songlink_cache()

class ProgressCallback:
    def __call__(self, current: int, total: int) -> None:
        if total > 0:
            percent = (current / total) * 100
            print(f"\r{percent:.2f}% ({current}/{total})", end="")
        else:
            print(f"\r{current / (1024 * 1024):.2f} MB", end="")

def sanitize_filename(value: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", value).strip()

def get_first_artist(artist_str: str) -> str:
    if not artist_str:
        return "Unknown"
    return artist_str.split(",")[0].strip()

def get_ffmpeg_path() -> str:
    return "ffmpeg"

def get_ffprobe_path() -> str:
    return "ffprobe"

def safe_int(value) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0

class AmazonDownloader:
    def __init__(self, timeout: float = 120.0):
        self.session = requests.Session()
        self.session.timeout = timeout
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
        })
        self.progress_callback: Callable[[int, int], None] = ProgressCallback()

    def set_progress_callback(self, callback: Callable[[int, int], None]) -> None:
        self.progress_callback = callback

    def get_amazon_url_from_spotify(self, spotify_track_id: str) -> str:
        print("Getting Amazon URL via Songlink API...")

        # Check cache first
        if spotify_track_id in _songlink_cache:
            cached_data = _songlink_cache[spotify_track_id]
            if 'amazon' in cached_data and cached_data['amazon']:
                print(f"Found cached Amazon URL: {cached_data['amazon']}")
                return cached_data['amazon']

        spotify_url = f"https://open.spotify.com/track/{spotify_track_id}"
        api_url = f"https://api.song.link/v1-alpha.1/links?url={spotify_url}"

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json"
        }

        # Retry logic with exponential backoff for rate limiting
        max_retries = 3
        base_delay = 5  # seconds

        for attempt in range(max_retries):
            try:
                # Respect rate limits between calls
                _respect_rate_limit()

                resp = self.session.get(api_url, headers=headers, timeout=10)
                resp.raise_for_status()

                data = resp.json()

                # Check if Amazon link exists in response
                if 'linksByPlatform' in data and 'amazonMusic' in data['linksByPlatform']:
                    amazon_url = data['linksByPlatform']['amazonMusic']['url']
                    print(f"Found Amazon URL: {amazon_url}")

                    # Cache the result
                    if spotify_track_id not in _songlink_cache:
                        _songlink_cache[spotify_track_id] = {}
                    _songlink_cache[spotify_track_id]['amazon'] = amazon_url
                    _save_songlink_cache()

                    return amazon_url
                else:
                    # Cache negative result too
                    if spotify_track_id not in _songlink_cache:
                        _songlink_cache[spotify_track_id] = {}
                    _songlink_cache[spotify_track_id]['amazon'] = None
                    _save_songlink_cache()

                    raise Exception("Amazon link not found in song.link API response")

            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:
                    if attempt < max_retries - 1:
                        # Exponential backoff: 5s, 10s, 20s
                        delay = base_delay * (2 ** attempt)
                        print(f"Rate limited by song.link API. Waiting {delay}s before retry {attempt + 1}/{max_retries}...")
                        time.sleep(delay)
                        continue
                    else:
                        raise Exception(f"song.link API rate limit exceeded. Please wait a few minutes and try again.")
                else:
                    raise Exception(f"song.link API returned status {e.response.status_code}")
            except Exception as e:
                if attempt < max_retries - 1 and "rate limit" in str(e).lower():
                    delay = base_delay * (2 ** attempt)
                    print(f"Error: {e}. Waiting {delay}s before retry {attempt + 1}/{max_retries}...")
                    time.sleep(delay)
                    continue
                else:
                    raise Exception(f"Error resolving Amazon URL via API: {e}")

        raise Exception("Failed to get Amazon URL after multiple retries")

    def _get_codec(self, filepath: str) -> str:
        try:
            cmd = [
                get_ffprobe_path(), "-v", "quiet", "-select_streams", "a:0",
                "-show_entries", "stream=codec_name", "-of", "default=noprint_wrappers=1:nokey=1",
                filepath
            ]
            si = None
            if os.name == 'nt':
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            codec = subprocess.check_output(cmd, text=True, startupinfo=si).strip()
            return codec
        except:
            return "m4a"

    def download_from_afkar_xyz(self, amazon_url: str, output_dir: str) -> str:
        asin_match = re.search(r'(B[0-9A-Z]{9})', amazon_url)
        if not asin_match:
            raise Exception(f"Failed to extract ASIN from: {amazon_url}")
        asin = asin_match.group(1)

        api_url = f"https://amzn.afkarxyz.fun/api/track/{asin}"
        print(f"Fetching from Amazon API (ASIN: {asin})...")
        
        resp = self.session.get(api_url)
        if resp.status_code != 200:
             raise Exception(f"Amazon API returned status {resp.status_code}")

        data = resp.json()
        stream_url = data.get("streamUrl")
        decryption_key = data.get("decryptionKey")

        if not stream_url:
            raise Exception("No stream URL found in API response")

        temp_file = os.path.join(output_dir, f"{asin}.enc")
        print(f"Downloading track...")
        
        with self.session.get(stream_url, stream=True) as r:
            r.raise_for_status()
            total = int(r.headers.get("Content-Length") or 0)
            downloaded = 0
            with open(temp_file, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if self.progress_callback:
                            self.progress_callback(downloaded, total)
        print()

        if decryption_key:
            print("Decrypting file...")
            codec = self._get_codec(temp_file)
            ext = ".flac" if codec == "flac" else ".m4a"
            decrypted_path = os.path.join(output_dir, f"{asin}{ext}")

            cmd = [
                get_ffmpeg_path(), "-y",
                "-decryption_key", decryption_key.strip(),
                "-i", temp_file,
                "-c", "copy",
                decrypted_path
            ]
            
            si = None
            if os.name == 'nt':
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            result = subprocess.run(cmd, capture_output=True, startupinfo=si)
            if result.returncode != 0:
                os.remove(temp_file)
                raise Exception(f"Decryption failed: {result.stderr.decode()}")
            
            os.remove(temp_file)
            return decrypted_path
        
        final_path = os.path.join(output_dir, f"{asin}.m4a")
        if os.path.exists(final_path):
             os.remove(final_path)
        os.rename(temp_file, final_path)
        return final_path

    def download_by_url(self, amazon_url: str, output_dir: str, quality: str, filename_format: str, 
                        playlist_name: str, playlist_owner: str, include_track_number: bool, position: int, 
                        spotify_track_name: str, spotify_artist_name: str, spotify_album_name: str, 
                        spotify_album_artist: str, spotify_release_date: str, spotify_cover_url: str, 
                        spotify_track_number: int, spotify_disc_number: int, spotify_total_tracks: int, 
                        embed_max_quality_cover: bool, spotify_total_discs: int, spotify_copyright: str, 
                        spotify_publisher: str, spotify_url: str, use_album_track_number: bool = False,
                        use_first_artist_only: bool = False):
        
        os.makedirs(output_dir, exist_ok=True)
        print(f"Using Amazon URL: {amazon_url}")

        # 1. Prepara os nomes otimizados
        artist_to_use = get_first_artist(spotify_artist_name) if use_first_artist_only else spotify_artist_name
        album_artist_to_use = get_first_artist(spotify_album_artist) if use_first_artist_only else spotify_album_artist

        safe_title = sanitize_filename(spotify_track_name)
        safe_artist = sanitize_filename(artist_to_use)
        safe_album = sanitize_filename(spotify_album_name)
        safe_album_artist = sanitize_filename(album_artist_to_use)
        year = spotify_release_date[:4] if len(spotify_release_date) >= 4 else ""

        track_num_for_filename = position
        if use_album_track_number and safe_int(spotify_track_number) > 0:
            track_num_for_filename = safe_int(spotify_track_number)

        if "{" in filename_format:
            new_name = (filename_format.replace("{title}", safe_title)
                        .replace("{artist}", safe_artist)
                        .replace("{album}", safe_album)
                        .replace("{album_artist}", safe_album_artist)
                        .replace("{year}", year))
            
            new_name = new_name.replace("{disc}", str(spotify_disc_number) if safe_int(spotify_disc_number) > 0 else "")
            
            if track_num_for_filename > 0:
                new_name = new_name.replace("{track}", f"{track_num_for_filename:02d}")
            else:
                new_name = re.sub(r'\{track\}[\.\s-]*', "", new_name)
        else:
            if filename_format == "artist-title":
                new_name = f"{safe_artist} - {safe_title}"
            elif filename_format == "title":
                new_name = safe_title
            else:
                new_name = f"{safe_title} - {safe_artist}"
            
            if include_track_number and track_num_for_filename > 0:
                new_name = f"{track_num_for_filename:02d}. {new_name}"

        new_name = sanitize_filename(new_name)
        
        # Checa se o arquivo FLAC ou M4A já existe no disco antes de acionar a API
        expected_path_flac = os.path.join(output_dir, new_name + ".flac")
        expected_path_m4a = os.path.join(output_dir, new_name + ".m4a")

        if os.path.exists(expected_path_flac) and os.path.getsize(expected_path_flac) > 0:
            size_mb = os.path.getsize(expected_path_flac) / (1024 * 1024)
            print(f"File already exists: {expected_path_flac} ({size_mb:.2f} MB)")
            return expected_path_flac
        
        if os.path.exists(expected_path_m4a) and os.path.getsize(expected_path_m4a) > 0:
            size_mb = os.path.getsize(expected_path_m4a) / (1024 * 1024)
            print(f"File already exists: {expected_path_m4a} ({size_mb:.2f} MB)")
            return expected_path_m4a

        # 3. Baixa o arquivo apenas se não existir
        file_path = self.download_from_afkar_xyz(amazon_url, output_dir)
        ext = os.path.splitext(file_path)[1] or ".flac"
        new_path = os.path.join(output_dir, new_name + ext)
        
        if os.path.exists(new_path):
             try: os.remove(new_path)
             except: pass
             
        os.replace(file_path, new_path)
        print(f"Renamed to: {new_name + ext}")

        self.embed_metadata(new_path, spotify_track_name, spotify_artist_name, spotify_album_name, 
                            spotify_album_artist, spotify_release_date, spotify_track_number, 
                            spotify_total_tracks, spotify_disc_number, spotify_total_discs, 
                            spotify_cover_url, spotify_copyright, spotify_publisher, spotify_url)

        print("Done\n✓ Downloaded successfully from Amazon Music")
        return new_path

    def embed_metadata(self, filepath, title, artist, album, album_artist, date, track_num, total_tracks, 
                       disc_num, total_discs, cover_url, copyright, publisher, url):
        print("Embedding metadata and cover art...")
        try:
            cover_data = None
            if cover_url:
                try: 
                    resp = self.session.get(cover_url, timeout=15)
                    if resp.status_code == 200:
                        cover_data = resp.content
                except Exception as e:
                    print(f"Warning: Could not download cover: {e}")

            t_num = safe_int(track_num)
            t_total = safe_int(total_tracks)
            d_num = safe_int(disc_num)
            d_total = safe_int(total_discs)
            
            if t_num == 0: t_num = 1
            if d_num == 0: d_num = 1

            if filepath.endswith(".flac"):
                audio = FLAC(filepath)
                audio.delete()
                
                audio["TITLE"] = title
                audio["ARTIST"] = artist
                audio["ALBUM"] = album
                audio["ALBUMARTIST"] = album_artist
                audio["DATE"] = date
                audio["TRACKNUMBER"] = str(t_num)
                audio["TRACKTOTAL"] = str(t_total)
                audio["DISCNUMBER"] = str(d_num)
                audio["DISCTOTAL"] = str(d_total)
                if copyright: audio["COPYRIGHT"] = copyright
                if publisher: audio["ORGANIZATION"] = publisher
                if url: audio["URL"] = url
                audio["DESCRIPTION"] = "https://github.com/ShuShuzinhuu/SpotiFLAC-Module-Version"

                if cover_data:
                    pic = Picture()
                    pic.data = cover_data
                    pic.type = PictureType.COVER_FRONT
                    pic.mime = "image/jpeg"
                    audio.add_picture(pic)
                audio.save()

            elif filepath.endswith(".m4a"):
                try:
                    audio = MP4(filepath)
                except:
                    audio = MP4(filepath)
                
                audio.delete()
                
                audio["\xa9nam"] = title
                audio["\xa9ART"] = artist
                audio["\xa9alb"] = album
                audio["aART"] = album_artist
                audio["\xa9day"] = date
                audio["trkn"] = [(t_num, t_total)]
                audio["disk"] = [(d_num, d_total)]
                if copyright: audio["cprt"] = copyright
                
                if cover_data:
                    audio["covr"] = [MP4Cover(cover_data, imageformat=MP4Cover.FORMAT_JPEG)]
                audio.save()
                
            print("Metadata embedded successfully")

        except Exception as e:
            print(f"Warning: Failed to embed metadata: {e}")

    def download_by_spotify_id(self, spotify_track_id, **kwargs):
        amazon_url = self.get_amazon_url_from_spotify(spotify_track_id)
        
        default_kwargs = {
            "output_dir": ".", "quality": "LOSSLESS", "filename_format": "{title} - {artist}",
            "playlist_name": "", "playlist_owner": "", "include_track_number": False, "position": 1,
            "spotify_track_name": "Unknown", "spotify_artist_name": "Unknown", 
            "spotify_album_name": "Unknown", "spotify_album_artist": "Unknown",
            "spotify_release_date": "", "spotify_cover_url": "", "spotify_track_number": 1,
            "spotify_disc_number": 1, "spotify_total_tracks": 1, "embed_max_quality_cover": True,
            "spotify_total_discs": 1, "spotify_copyright": "", "spotify_publisher": "", "spotify_url": "",
            "use_album_track_number": False, "use_first_artist_only": False
        }

        for key in kwargs:
            if key in default_kwargs:
                default_kwargs[key] = kwargs[key]

        return self.download_by_url(amazon_url, **default_kwargs)