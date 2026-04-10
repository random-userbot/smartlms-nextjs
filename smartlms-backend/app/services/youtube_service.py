"""
Smart LMS - YouTube Service
Professional rewrite for robust video processing and transcription.
"""

import asyncio
import re
import os
import json
import glob
import time
import tempfile
import shutil
import requests
import http.cookiejar
from typing import List, Dict, Optional
import yt_dlp
import base64
from youtube_transcript_api import YouTubeTranscriptApi
try:
    from googleapiclient.discovery import build
    GOOGLE_API_CLIENT_AVAILABLE = True
except ImportError:
    GOOGLE_API_CLIENT_AVAILABLE = False
from groq import Groq
from app.config import settings
from app.services.groq_fallback import AllModelsRateLimitedError, transcription_with_fallback
# from app.database import SessionLocal # For caching if needed later

class YouTubeService:
    def __init__(self):
        api_key = settings.GROQ_API_KEY
        self.groq_client = Groq(api_key=api_key) if api_key else None
        if not api_key:
            print("Warning: GROQ_API_KEY not found. Groq Whisper fallback will be disabled.")

        try:
            from faster_whisper import WhisperModel  # type: ignore
            self._WhisperModel = WhisperModel
            self.local_whisper_available = True
        except Exception:
            self._WhisperModel = None
            self.local_whisper_available = False

        self.ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "skip_download": True,
            "nocheckcertificate": True,
            "ignoreerrors": True,
            "no_color": True,
            "geo_bypass": True,
        }
        self._groq_cooldown_until = 0.0
        self._cookie_path = None
        # Lazy resilience setup happens on first use to ensure environment is loaded

    def _setup_resilience(self):
        """Configure cookies and proxies from settings."""
        if self._cookie_path: # Already setup
            return

        print(f"[YOUTUBE] CONFIG CHECK: Cookies present: {bool(settings.YOUTUBE_COOKIES)} | API Key present: {bool(settings.YOUTUBE_API_KEY)} | UA present: {bool(settings.YOUTUBE_USER_AGENT)}", flush=True)

        if settings.YOUTUBE_PROXY:
            self.ydl_opts["proxy"] = settings.YOUTUBE_PROXY

        if settings.YOUTUBE_USER_AGENT:
            self.ydl_opts["user_agent"] = settings.YOUTUBE_USER_AGENT
            self.ydl_opts["http_headers"] = {
                "User-Agent": settings.YOUTUBE_USER_AGENT,
                "Referer": "https://www.youtube.com/",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
            print(f"[YOUTUBE] Matching User-Agent and Headers applied.", flush=True)

        if settings.YOUTUBE_COOKIES:
            try:
                # Try to write cookies to a temp file
                self._cookie_path = self._get_cookie_file(settings.YOUTUBE_COOKIES)
                if self._cookie_path:
                    self.ydl_opts["cookiefile"] = self._cookie_path
                    print(f"[YOUTUBE] Authentication cookies loaded from environment.", flush=True)
                else:
                    print(f"[YOUTUBE] [WARNING] Cookies provided but failed to write to temp file.", flush=True)
            except Exception as e:
                print(f"[YOUTUBE] [ERROR] Failed to setup cookies: {e}", flush=True)

    def _get_cookie_file(self, cookie_str: str) -> Optional[str]:
        """Decode and write cookies to a temporary file for yt-dlp."""
        try:
            if not cookie_str:
                return None

            content = ""
            # Detection and normalization logic preserved...
            is_probably_base64 = re.match(r'^[A-Za-z0-9+/=]+$', cookie_str.strip().replace('\n', '').replace('\r', ''))
            
            if is_probably_base64:
                try:
                    decoded = base64.b64decode(cookie_str).decode('utf-8')
                    if "# Netscape" in decoded or "youtube.com" in decoded or "domain" in decoded:
                        content = decoded
                    else:
                        content = cookie_str
                except Exception:
                    content = cookie_str
            else:
                content = cookie_str

            if ";" in content and "=" in content and "# Netscape" not in content and "# HTTP Cookie File" not in content:
                netscape_lines = ["# Netscape HTTP Cookie File", "# http://curl.haxx.se/rfc/cookie_spec.html", "# This is a generated file! Do not edit.", ""]
                for part in content.split(";"):
                    if "=" in part:
                        k, v = part.strip().split("=", 1)
                        netscape_lines.append(f".youtube.com\tTRUE\t/\tTRUE\t0\t{k}\t{v}")
                content = "\n".join(netscape_lines)

            if not content or ("# Netscape" not in content and "# HTTP Cookie File" not in content):
                return None

            temp_dir = tempfile.gettempdir()
            path = os.path.join(temp_dir, f"yt_cookies_{int(time.time())}.txt")
            with open(path, "w", encoding='utf-8') as f:
                f.write(content)
            
            return path
        except Exception as e:
            print(f"[YOUTUBE] [ERROR] Error creating temp cookie file: {e}", flush=True)
            return None

    def _create_authenticated_session(self) -> requests.Session:
        """Create a requests session with manually loaded cookies."""
        session = requests.Session()
        session.headers.update({
            "User-Agent": settings.YOUTUBE_USER_AGENT or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        })
        
        if self._cookie_path and os.path.exists(self._cookie_path):
            try:
                cj = http.cookiejar.MozillaCookieJar(self._cookie_path)
                cj.load(ignore_discard=True, ignore_expires=True)
                session.cookies.update(cj)
                print("[YOUTUBE] Injected cookies into requests session.", flush=True)
            except Exception as e:
                print(f"[YOUTUBE] [WARNING] Failed to load cookies into session: {e}", flush=True)
        
        return session

    def _get_ydl_opts(self, extra_opts: Optional[Dict] = None) -> Dict:
        """Get consolidated yt-dlp options."""
        opts = self.ydl_opts.copy()
        if extra_opts:
            opts.update(extra_opts)
        return opts

    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        """Extract the 11-character YouTube video ID using robust regex."""
        patterns = [
            r"(?:v=|\/v\/|youtu\.be\/|embed\/|shorts\/|watch\?v=)([a-zA-Z0-9_-]{11})",
            r"^([a-zA-Z0-9_-]{11})$" # In case just the ID is passed
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    @staticmethod
    def normalize_watch_url(url: Optional[str]) -> Optional[str]:
        """Normalize YouTube URLs/IDs to canonical watch URLs for consistent playback."""
        if not url:
            return url

        video_id = YouTubeService.extract_video_id(url)
        if video_id:
            return f"https://www.youtube.com/watch?v={video_id}"
        return url

    async def get_video_info(self, video_url: str) -> Dict:
        """Fetch video metadata using yt-dlp."""
        def _extract():
            opts = self._get_ydl_opts()
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                return {
                    "id": info.get("id"),
                    "title": info.get("title", "Untitled"),
                    "duration": info.get("duration", 0),
                    "thumbnail": info.get("thumbnails", [{}])[-1].get("url") if info.get("thumbnails") else None,
                    "description": info.get("description", ""),
                    "view_count": info.get("view_count", 0),
                    "uploader": info.get("uploader", "Unknown"),
                }
        
        return await asyncio.get_event_loop().run_in_executor(None, _extract)

    async def get_playlist_videos(self, playlist_url: str) -> List[Dict]:
        """Extract all videos from a playlist or a single video URL."""
        def _extract():
            opts = self._get_ydl_opts()
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(playlist_url, download=False)
                videos = []
                
                if "entries" in info:
                    for entry in info["entries"]:
                        if entry:
                            raw_url = entry.get("url") or entry.get("webpage_url") or entry.get("id")
                            videos.append({
                                "id": entry.get("id"),
                                "title": entry.get("title", "Untitled"),
                                "url": self.normalize_watch_url(raw_url),
                                "thumbnail": entry.get("thumbnails", [{}])[-1].get("url") if entry.get("thumbnails") else None,
                                "duration": entry.get("duration", 0),
                            })
                else:
                    raw_url = info.get("webpage_url") or playlist_url
                    videos.append({
                        "id": info.get("id"),
                        "title": info.get("title", "Untitled"),
                        "url": self.normalize_watch_url(raw_url),
                        "thumbnail": info.get("thumbnails", [{}])[-1].get("url") if info.get("thumbnails") else None,
                        "duration": info.get("duration", 0),
                    })
                return videos

        return await asyncio.get_event_loop().run_in_executor(None, _extract)

    async def get_transcript(self, video_url: str, prefer_local: bool = False) -> str:
        """
        Get transcript with a multi-layered fallback strategy.
        Supports YouTube URLs and direct media URLs (e.g., Cloudinary).
        """
        self._setup_resilience() # Ensure cookies/UA are loaded
        video_id = self.extract_video_id(video_url)
        
        # Scenario A: YouTube Video
        if video_id:
            # Tier 0: Official YouTube Data API
            if settings.YOUTUBE_API_KEY and GOOGLE_API_CLIENT_AVAILABLE:
                try:
                    print(f"[YOUTUBE] [Tier 0] Trying Official API for {video_id}...", flush=True)
                    transcript_text = await self._fetch_official_api_info(video_id)
                    # Note: captions().download() usually needs OAuth, so we mostly use this for metadata
                    # and then fallback to the scraper which now has the API key info if needed.
                except Exception as e:
                    print(f"Official API metadata check failed: {e}")

            # Tier 1: YouTube Transcript API (The Scraper)
            try:
                print(f"[YOUTUBE] [Tier 1] Fetching scraper transcript for {video_id}...", flush=True)
                transcript_text = await self._fetch_api_transcript(video_id)
                if transcript_text:
                    print(f"[YOUTUBE] Success via scraper transcript.", flush=True)
                    return transcript_text
            except Exception as e:
                print(f"Scraper transcript fetch failed: {e}")

            # Fallback to Media Transcription (Local or Groq)
            try:
                return await self._fetch_media_transcription(video_url, is_youtube=True, use_groq=not prefer_local)
            except Exception as e:
                print(f"YouTube media transcription failed: {e}")

        # Scenario B: Direct Media URL (Cloudinary, etc.)
        else:
            try:
                return await self._fetch_media_transcription(video_url, is_youtube=False, use_groq=not prefer_local)
            except Exception as e:
                print(f"Direct media transcription failed: {e}")
        
        return ""

    async def _fetch_official_api_info(self, video_id: str) -> Optional[str]:
        """Fetch metadata via Official API to see if we can get better context."""
        def _api():
            try:
                youtube = build("youtube", "v3", developerKey=settings.YOUTUBE_API_KEY)
                request = youtube.videos().list(part="snippet,contentDetails", id=video_id)
                response = request.execute()
                if response['items']:
                    snippet = response['items'][0]['snippet']
                    print(f"[YOUTUBE] Official API verified video: {snippet['title']}", flush=True)
                return None # Usually doesn't return transcript text directly without OAuth
            except Exception as e:
                print(f"Official API error: {e}")
                return None
        return await asyncio.get_event_loop().run_in_executor(None, _api)

    async def _fetch_api_transcript(self, video_id: str) -> Optional[str]:
        """Internal helper for Tier 1 transcript fetching with safety timeout."""
        def _ytt():
            try:
                # 1. Create authenticated session
                session = self._create_authenticated_session()
                
                # 2. Instantiate API with custom session (bypass library restrictions)
                api_instance = YouTubeTranscriptApi(http_client=session)
                
                print(f"[YOUTUBE] [Tier 1] Fetching via authenticated session...", flush=True)
                
                # 3. Fetch transcript list
                try:
                    transcript_list = api_instance.list(video_id)
                    
                    # 4. English Selection Strategy
                    # Tier 1: Manual or Generated English
                    try:
                        transcript = transcript_list.find_transcript(['en'])
                        print(f"[YOUTUBE] SELECTED LANGUAGE: {transcript.language_code} ({transcript.language})", flush=True)
                    except:
                        try:
                            # Tier 2: Any English (Generated)
                            transcript = transcript_list.find_generated_transcript(['en'])
                            print(f"[YOUTUBE] SELECTED GENERATED: {transcript.language_code}", flush=True)
                        except:
                            # Tier 3: Translate whatever is first to English
                            first_available = next(iter(transcript_list))
                            transcript = first_available.translate('en')
                            print(f"[YOUTUBE] FALLBACK TRANSLATION: {first_available.language_code} -> en", flush=True)
                    
                    data = transcript.fetch()
                    result = " ".join([p['text'] if isinstance(p, dict) else p.text for p in data])
                    print(f"[YOUTUBE] CONTENT PREVIEW: {result[:100]}...", flush=True)
                    return result
                except Exception as ex:
                    print(f"[YOUTUBE] Scraper Fetch Failed: {ex}", flush=True)
                    return None
            except Exception as e:
                print(f"[YOUTUBE] Scraper Setup Failed: {e}", flush=True)
                return None

        try:
            # Enforce a 45-second timeout to prevent background task hangs
            return await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, _ytt),
                timeout=45.0
            )
        except asyncio.TimeoutError:
            print("[YOUTUBE] [Tier 1] Scraper timed out after 45s. pivoting to fallback.", flush=True)
            return None
        except Exception as e:
            print(f"[YOUTUBE] Scraper execution error: {e}", flush=True)
            return None

    async def _download_media_audio(self, url: str, is_youtube: bool = True) -> Optional[str]:
        """Download audio from YouTube or a direct URL to a temp file."""
        identifier = self.extract_video_id(url) or str(int(time.time()))
        temp_dir = tempfile.mkdtemp(prefix=f"audio_proc_{identifier}_")
        output_path = os.path.join(temp_dir, f'{identifier}.%(ext)s')

        self._setup_resilience()
        if is_youtube:
            ydl_opts = self._get_ydl_opts({
                'format': '139/249/bestaudio[abr<=64]/bestaudio/best',
                'outtmpl': output_path,
                'quiet': True,
                'no_warnings': True,
                'nocheckcertificate': True,
                'ignoreerrors': True,
                'user_agent': settings.YOUTUBE_USER_AGENT or self.ydl_opts.get('user_agent'),
                'cookiefile': self._cookie_path
            })
        else:
            # For direct URLs, we just download the file
            ydl_opts = self._get_ydl_opts({
                'format': 'bestaudio/best',
                'outtmpl': output_path,
                'quiet': True,
                'no_warnings': True,
            })

        def _download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

        try:
            await asyncio.get_event_loop().run_in_executor(None, _download)
            files = glob.glob(os.path.join(temp_dir, f"{identifier}.*"))
            if not files:
                shutil.rmtree(temp_dir, ignore_errors=True)
                return None
            return files[0]
        except Exception as e:
            print(f"Download failed: {e}")
            shutil.rmtree(temp_dir, ignore_errors=True)
            return None

    async def _fetch_media_transcription(self, url: str, is_youtube: bool = True, use_groq: bool = True) -> str:
        """Consolidated handler for both Groq and Local Whisper transcription."""
        temp_audio = await self._download_media_audio(url, is_youtube=is_youtube)
        if not temp_audio:
            return ""

        try:
            if use_groq and self.groq_client and time.time() >= self._groq_cooldown_until:
                try:
                    with open(temp_audio, "rb") as file:
                        model_chain = settings.groq_audio_models_for_task(primary_model="whisper-large-v3")
                        transcription, _ = transcription_with_fallback(
                            self.groq_client,
                            file_tuple=(os.path.basename(temp_audio), file.read()),
                            primary_model=model_chain[0],
                            fallback_models=model_chain[1:],
                            response_format="text"
                        )
                        return transcription
                except AllModelsRateLimitedError as e:
                    self._groq_cooldown_until = time.time() + max(90, e.retry_after_seconds)
                except Exception as e:
                    print(f"Groq transcription error: {e}")

            # Fallback to Local Whisper
            if self.local_whisper_available:
                model = self._WhisperModel("tiny", device="cpu", compute_type="int8")
                segments, _ = model.transcribe(temp_audio)
                return " ".join([seg.text.strip() for seg in segments])
            
            return ""
        finally:
            shutil.rmtree(os.path.dirname(temp_audio), ignore_errors=True)

    async def _fetch_local_whisper_transcript(self, video_url: str) -> str:
        """
        Tier 3: Local faster-whisper fallback for multilingual transcription.
        """
        if not self.local_whisper_available:
            return ""

        video_id = self.extract_video_id(video_url)
        if not video_id:
            return ""

        temp_audio = await self._download_audio_for_transcription(video_url, video_id)
        if not temp_audio:
            return ""

        try:
            model = self._WhisperModel("tiny", device="cpu", compute_type="int8")
            segments, _ = model.transcribe(temp_audio, task="transcribe", beam_size=1, best_of=1, vad_filter=False)
            text_chunks = [seg.text.strip() for seg in segments if seg.text and seg.text.strip()]
            return " ".join(text_chunks)
        except BaseException as e:
            print(f"Local whisper transcription error: {e}")
            return ""
        finally:
            temp_dir = os.path.dirname(temp_audio)
            shutil.rmtree(temp_dir, ignore_errors=True)

# Singleton instance
youtube_service = YouTubeService()

# Maintain backward compatibility for existing routes
async def extract_playlist_videos(url: str):
    return await youtube_service.get_playlist_videos(url)

async def get_video_transcript(url: str, prefer_local: bool = False):
    return await youtube_service.get_transcript(url, prefer_local=prefer_local)

def normalize_youtube_watch_url(url: Optional[str]) -> Optional[str]:
    return YouTubeService.normalize_watch_url(url)

