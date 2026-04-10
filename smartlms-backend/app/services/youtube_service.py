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
from typing import List, Dict, Optional
import yt_dlp
import base64
from youtube_transcript_api import YouTubeTranscriptApi
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
        }
        self._groq_cooldown_until = 0.0
        self._cookie_path = None
        self._setup_resilience()

    def _setup_resilience(self):
        """Configure cookies and proxies from settings."""
        if settings.YOUTUBE_PROXY:
            self.ydl_opts["proxy"] = settings.YOUTUBE_PROXY
            print(f"[YOUTUBE] Using proxy: {settings.YOUTUBE_PROXY[:20]}...", flush=True)

        if settings.YOUTUBE_COOKIES:
            try:
                # Try to write cookies to a temp file
                self._cookie_path = self._get_cookie_file(settings.YOUTUBE_COOKIES)
                if self._cookie_path:
                    self.ydl_opts["cookiefile"] = self._cookie_path
                    print(f"[YOUTUBE] Authentication cookies loaded from environment.", flush=True)
            except Exception as e:
                print(f"[YOUTUBE] Failed to setup cookies: {e}", flush=True)

    def _get_cookie_file(self, cookie_str: str) -> Optional[str]:
        """Decode and write cookies to a temporary file for yt-dlp."""
        try:
            # 1. Check if it's base64 encoded
            try:
                decoded = base64.b64decode(cookie_str).decode('utf-8')
                content = decoded
            except Exception:
                # Fallback to raw string
                content = cookie_str

            # 2. Check and normalize format
            # If it's a raw header string (key=val; key2=val2), convert to Netscape format
            if ";" in content and "=" in content and "Netscape" not in content and "# HTTP Cookie File" not in content:
                print("[YOUTUBE] Detected raw cookie header format. Converting...", flush=True)
                netscape_lines = ["# Netscape HTTP Cookie File", "# http://curl.haxx.se/rfc/cookie_spec.html", "# This is a generated file! Do not edit.", ""]
                for part in content.split(";"):
                    if "=" in part:
                        k, v = part.strip().split("=", 1)
                        # Format: domain, flag, path, secure, expiration, name, value
                        # Using .youtube.com for global applicability
                        netscape_lines.append(f".youtube.com\tTRUE\t/\tTRUE\t0\t{k}\t{v}")
                content = "\n".join(netscape_lines)

            if not content or ("Netscape" not in content and "# HTTP Cookie File" not in content):
                print("[YOUTUBE] Invalid cookie format. Expected Netscape or Header format.", flush=True)
                return None

            temp_dir = tempfile.gettempdir()
            path = os.path.join(temp_dir, f"yt_cookies_{int(time.time())}.txt")
            with open(path, "w", encoding='utf-8') as f:
                f.write(content)
            return path
        except Exception as e:
            print(f"[YOUTUBE] Error creating temp cookie file: {e}", flush=True)
            return None

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
        video_id = self.extract_video_id(video_url)
        
        # Scenario A: YouTube Video
        if video_id:
            # Tier 1: YouTube Transcript API
            try:
                transcript_text = await self._fetch_api_transcript(video_id)
                if transcript_text:
                    return transcript_text
            except Exception as e:
                print(f"Transcript API failed: {e}")

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

    async def _fetch_api_transcript(self, video_id: str) -> Optional[str]:
        """Internal helper for Tier 1 transcript fetching."""
        def _ytt():
            try:
                # Prepare proxies for YouTubeTranscriptApi
                proxies = None
                if settings.YOUTUBE_PROXY:
                    proxies = {
                        "http": settings.YOUTUBE_PROXY,
                        "https": settings.YOUTUBE_PROXY
                    }

                t_list = YouTubeTranscriptApi.list_transcripts(video_id, proxies=proxies)
                langs = ['en', 'ja', 'hi', 'es', 'fr', 'de', 'pt', 'ru', 'ko', 'zh-Hans', 'zh-Hant', 'ar', 'id', 'tr']
                try:
                    transcript = t_list.find_transcript(langs)
                except:
                    try:
                        transcript = t_list.find_generated_transcript(langs)
                    except:
                        transcript = next(iter(t_list))
                if transcript:
                    return " ".join([p['text'] for p in transcript.fetch()])
            except:
                return None
            return None
        return await asyncio.get_event_loop().run_in_executor(None, _ytt)

    async def _download_media_audio(self, url: str, is_youtube: bool = True) -> Optional[str]:
        """Download audio from YouTube or a direct URL to a temp file."""
        identifier = self.extract_video_id(url) or str(int(time.time()))
        temp_dir = tempfile.mkdtemp(prefix=f"audio_proc_{identifier}_")
        output_path = os.path.join(temp_dir, f'{identifier}.%(ext)s')

        if is_youtube:
            ydl_opts = self._get_ydl_opts({
                'format': '139/249/bestaudio[abr<=64]/bestaudio/best',
                'outtmpl': output_path,
                'quiet': True,
                'no_warnings': True,
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

