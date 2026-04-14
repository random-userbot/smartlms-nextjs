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

        self._groq_cooldown_until = 0.0
        self._cookie_path = None
        # Lazy resilience setup happens on first use to ensure environment is loaded

    def _get_ydl_opts(self, extra_opts: Optional[Dict] = None, use_cookies: bool = True) -> Dict:
        """Centralized yt-dlp configuration with dynamic safety injection."""
        # Base options optimized for AWS Fargate stability
        opts = {
            "format": "bestaudio/best",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "extract_audio": True,
            "audio_format": "mp3",
            "outtmpl": os.path.join(tempfile.gettempdir(), "%(id)s.%(ext)s"),
            "nocheckcertificate": True,
            "ignoreerrors": False,
            "logtostderr": False,
        }

        # 1. User-Agent and Headers
        ua = settings.YOUTUBE_USER_AGENT
        if ua:
            opts["user_agent"] = ua
            opts["http_headers"] = {
                "User-Agent": ua,
                "Referer": "https://www.youtube.com/",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }

        # 2. Proxy support
        if settings.YOUTUBE_PROXY:
            opts["proxy"] = settings.YOUTUBE_PROXY

        # Merge with extra_opts if provided
        if extra_opts:
            opts.update(extra_opts)

        # 3. Inject Cookies if available and requested
        if use_cookies and self._cookie_path:
            opts["cookiefile"] = self._cookie_path
        elif not use_cookies:
            # Explicitly remove cookiefile if we are trying a fallback
            opts.pop("cookiefile", None)

        # 4. Inject PO Token & Visitor Data for bot bypassing
        if settings.YOUTUBE_PO_TOKEN and settings.YOUTUBE_VISITOR_DATA:
            token_str = f"{settings.YOUTUBE_PO_TOKEN}:{settings.YOUTUBE_VISITOR_DATA}"
            # Ensure postprocessor_args doesn't clash
            if "postprocessor_args" not in opts:
                opts["postprocessor_args"] = []
            opts["postprocessor_args"].extend(["--param", f"youtube:token={token_str}"])

        return opts

    def _setup_resilience(self):
        """Configure cookies and file paths from settings."""
        if self._cookie_path: # Already setup
            return

        print(f"[YOUTUBE] CONFIG CHECK: Cookies present: {bool(settings.YOUTUBE_COOKIES)} | API Key present: {bool(settings.YOUTUBE_API_KEY)} | UA present: {bool(settings.YOUTUBE_USER_AGENT)}", flush=True)

        if settings.YOUTUBE_COOKIES:
            try:
                # Try to write cookies to a temp file
                self._cookie_path = self._get_cookie_file(settings.YOUTUBE_COOKIES)
                if self._cookie_path:
                    print(f"[YOUTUBE] Authentication cookies loaded from environment.", flush=True)
                else:
                    print(f"[YOUTUBE] [WARNING] Cookies provided but failed to write to temp file.", flush=True)
            except Exception as e:
                print(f"[YOUTUBE] [ERROR] Failed to setup cookies: {e}", flush=True)

    def _get_cookie_file(self, cookie_str: str) -> Optional[str]:
        """Verify or create temporary Netscape cookie file for yt-dlp."""
        if not cookie_str:
            return None

        # Clean input: strip quotes and whitespace that might be added by cloud envs
        cookie_str = cookie_str.strip().strip('"').strip("'").strip()

        # Detect if it's already a full file path
        if os.path.isfile(cookie_str):
            print(f"[YOUTUBE] Loading cookies from file path: {cookie_str}", flush=True)
            return cookie_str

        try:
            content = ""
            # Support base64 prefix
            if cookie_str.startswith('base64:'):
                try:
                    # Strip prefix and any internal whitespace
                    b64_data = cookie_str[7:].replace(" ", "").replace("\n", "").replace("\r", "")
                    raw_bytes = base64.b64decode(b64_data)
                    try:
                        content = raw_bytes.decode('utf-8')
                    except UnicodeDecodeError:
                        content = raw_bytes.decode('latin-1')
                    print("[YOUTUBE] Successfully decoded Base64 cookie string.", flush=True)
                except Exception as b64e:
                    print(f"[YOUTUBE] [ERROR] Base64 decoding failed: {b64e}", flush=True)
                    content = cookie_str
            else:
                # Direct check for Netscape header or standard cookie string
                try:
                    # Clean potential base64 if no prefix
                    clean_str = cookie_str.replace('\n', '').replace('\r', '').replace(' ', '')
                    if re.match(r'^[A-Za-z0-9+/=]+$', clean_str):
                        content = base64.b64decode(clean_str).decode('utf-8')
                        print("[YOUTUBE] Decoded probable Base64 string (no prefix).", flush=True)
                    else:
                        content = cookie_str
                except:
                    content = cookie_str

            # Validation: If it doesn't look like a cookie file, try to wrap it
            if content and "# Netscape" not in content and "# HTTP Cookie File" not in content:
                print("[YOUTUBE] Content detected as raw key=value string. Wrapping in Netscape header.", flush=True)
                if ";" in content and "=" in content:
                    netscape_lines = ["# Netscape HTTP Cookie File", "# This was auto-generated by SmartLMS", ""]
                    for part in content.split(";"):
                        if "=" in part:
                            try:
                                k_v = part.strip().split("=", 1)
                                if len(k_v) == 2:
                                    k, v = k_v
                                    netscape_lines.append(f".youtube.com\tTRUE\t/\tTRUE\t0\t{k}\t{v}")
                            except:
                                continue
                    content = "\n".join(netscape_lines)

            if not content or ("# Netscape" not in content and "youtube.com" not in content):
                print(f"[YOUTUBE] [ERROR] Cookie string does not contain valid Netscape headers or youtube domain. (Length: {len(content) if content else 0})", flush=True)
                return None

            # Persistent temp file in the scratch or temp directory
            path = os.path.join(tempfile.gettempdir(), f"yt_active_session.txt")
            with open(path, "w", encoding='utf-8') as f:
                f.write(content)
            
            print(f"[YOUTUBE] Successfully wrote cookie file to: {path} ({len(content)} bytes)", flush=True)
            return path
        except Exception as e:
            print(f"[YOUTUBE] [ERROR] Critical error creating temp cookie file: {e}", flush=True)
            return None
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
        self._setup_resilience()
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
        self._setup_resilience()
        def _extract():
            opts = self._get_ydl_opts()
            opts["extract_flat"] = True # Tell yt-dlp to just list playlist contents, not download
            opts["noplaylist"] = False  # Overwrite base opts to allow playlist extraction
            
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
        
        Pipeline:
          Tier 0: Official YouTube Data API (metadata only)
          Tier 1: youtube-transcript-api scraper (BLOCKED on cloud IPs)
          Tier 2: Download audio via yt-dlp + Groq Whisper transcription
          Tier 3: Local faster-whisper (if available)
        """
        self._setup_resilience() # Ensure cookies/UA are loaded
        video_id = self.extract_video_id(video_url)
        
        # Scenario A: YouTube Video
        if video_id:
            # Tier 0: Official YouTube Data API (metadata verification)
            if settings.YOUTUBE_API_KEY and GOOGLE_API_CLIENT_AVAILABLE:
                try:
                    print(f"[YOUTUBE] [Tier 0] Official API metadata check for {video_id}...", flush=True)
                    await self._fetch_official_api_info(video_id)
                except Exception as e:
                    print(f"[YOUTUBE] [Tier 0] Metadata check skipped: {e}", flush=True)

            # Tier 1: YouTube Transcript API (scraper - often blocked on cloud IPs)
            try:
                print(f"[YOUTUBE] [Tier 1] Trying caption scraper for {video_id}...", flush=True)
                transcript_text = await self._fetch_api_transcript(video_id)
                if transcript_text:
                    print(f"[YOUTUBE] [Tier 1] Success! Got {len(transcript_text)} chars via scraper.", flush=True)
                    return transcript_text
                print(f"[YOUTUBE] [Tier 1] Scraper returned empty. Falling through to audio transcription.", flush=True)
            except Exception as e:
                # This is expected on AWS/cloud — YouTube blocks cloud IPs
                print(f"[YOUTUBE] [Tier 1] Scraper blocked (expected on cloud): {str(e)[:120]}", flush=True)

            # Tier 1.5: yt-dlp Subtitle Extraction (Resilient to cloud IP blocks)
            try:
                print(f"[YOUTUBE] [Tier 1.5] Trying yt-dlp subtitle extraction for {video_id}...", flush=True)
                transcript_text = await self._fetch_ytdlp_subtitles(video_url)
                if transcript_text:
                    print(f"[YOUTUBE] [Tier 1.5] Success! Got {len(transcript_text)} chars via yt-dlp subs.", flush=True)
                    return transcript_text
                print(f"[YOUTUBE] [Tier 1.5] No subtitles found via yt-dlp.", flush=True)
            except Exception as e:
                print(f"[YOUTUBE] [Tier 1.5] yt-dlp sub extraction failed: {e}", flush=True)

            # Tier 2: Download audio + Groq Whisper (primary cloud path)
            print(f"[YOUTUBE] [Tier 2] Downloading audio for Whisper transcription...", flush=True)
            try:
                result = await self._fetch_media_transcription(video_url, is_youtube=True, use_groq=True)
                if result:
                    print(f"[YOUTUBE] [Tier 2] Success! Got {len(result)} chars via Groq Whisper.", flush=True)
                    return result
                print(f"[YOUTUBE] [Tier 2] Groq Whisper returned empty.", flush=True)
            except Exception as e:
                print(f"[YOUTUBE] [Tier 2] Groq Whisper failed: {e}", flush=True)

            # Tier 3: Local faster-whisper fallback
            if self.local_whisper_available:
                print(f"[YOUTUBE] [Tier 3] Trying local Whisper fallback...", flush=True)
                try:
                    result = await self._fetch_media_transcription(video_url, is_youtube=True, use_groq=False)
                    if result:
                        print(f"[YOUTUBE] [Tier 3] Success! Got {len(result)} chars via local Whisper.", flush=True)
                        return result
                except Exception as e:
                    print(f"[YOUTUBE] [Tier 3] Local Whisper failed: {e}", flush=True)

            print(f"[YOUTUBE] All transcript tiers exhausted for {video_id}. Returning empty.", flush=True)

        # Scenario B: Direct Media URL (Cloudinary, etc.)
        else:
            try:
                return await self._fetch_media_transcription(video_url, is_youtube=False, use_groq=not prefer_local)
            except Exception as e:
                print(f"[YOUTUBE] Direct media transcription failed: {e}", flush=True)
        
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
                print(f"[YOUTUBE] [Tier 1] Fetching via youtube-transcript-api...", flush=True)
                
                # 3. Fetch transcript list
                try:
                    import requests
                    import http.cookiejar
                    from youtube_transcript_api import YouTubeTranscriptApi
                    
                    session = None
                    if self._cookie_path and os.path.exists(self._cookie_path):
                        session = requests.Session()
                        cookie_jar = http.cookiejar.MozillaCookieJar(self._cookie_path)
                        cookie_jar.load(ignore_discard=True, ignore_expires=True)
                        session.cookies = cookie_jar
                        print(f"[YOUTUBE] Using cookies for transcript api: {self._cookie_path}", flush=True)
                        
                    api_instance = YouTubeTranscriptApi(http_client=session)
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
                'ignoreerrors': True,
            })
        else:
            # For direct URLs, we just download the file
            ydl_opts = self._get_ydl_opts({
                'format': 'bestaudio/best',
                'outtmpl': output_path,
                'quiet': True,
                'no_warnings': True,
            })

        def _download(current_opts):
            with yt_dlp.YoutubeDL(current_opts) as ydl:
                ydl.download([url])

        try:
            # Attempt 1: Standard (with cookies if available)
            await asyncio.get_event_loop().run_in_executor(None, _download, ydl_opts)
        except Exception as e:
            if self._cookie_path:
                print(f"[YOUTUBE] Authenticated download failed, trying WITHOUT cookies as fallback: {e}")
                # Attempt 2: Fallback (explicitly without cookies)
                try:
                    fallback_opts = self._get_ydl_opts({
                        'format': '139/249/bestaudio[abr<=64]/bestaudio/best',
                        'outtmpl': output_path,
                        'quiet': True,
                    }, use_cookies=False)
                    await asyncio.get_event_loop().run_in_executor(None, _download, fallback_opts)
                except Exception as e2:
                    print(f"[YOUTUBE] Final download fallback failed: {e2}")
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    return None
            else:
                print(f"Download failed: {e}")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return None

        # Check for results
        files = glob.glob(os.path.join(temp_dir, f"{identifier}.*"))
        if not files:
            shutil.rmtree(temp_dir, ignore_errors=True)
            return None
        return files[0]

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

    async def _fetch_ytdlp_subtitles(self, video_url: str) -> Optional[str]:
        """Fetch subtitles directly using yt-dlp's authenticated session."""
        identifier = self.extract_video_id(video_url) or "subs"
        temp_dir = tempfile.mkdtemp(prefix=f"ytdlp_subs_{identifier}_")
        
        # Configure for subtitle extraction only
        ydl_opts = self._get_ydl_opts({
            'skip_download': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en.*', 'en'], # Match any English variant
            'outtmpl': os.path.join(temp_dir, 'subs.%(ext)s'),
        })

        def _download(current_opts):
            try:
                with yt_dlp.YoutubeDL(current_opts) as ydl:
                    ydl.download([video_url])
                return True
            except Exception as e:
                print(f"[YOUTUBE] yt-dlp subtitle download attempt failed: {e}")
                return False

        try:
            # Attempt 1: Authenticated
            success = await asyncio.get_event_loop().run_in_executor(None, _download, ydl_opts)
            
            # Attempt 2: Fallback (unauthenticated) if attempt 1 failed and cookies were present
            if not success and self._cookie_path:
                print("[YOUTUBE] Retrying subtitle fetch WITHOUT cookies...")
                fallback_opts = self._get_ydl_opts({
                    'skip_download': True,
                    'writesubtitles': True,
                    'writeautomaticsub': True,
                    'subtitleslangs': ['en.*', 'en'],
                    'outtmpl': os.path.join(temp_dir, 'subs.%(ext)s'),
                    'quiet': True,
                }, use_cookies=False)
                success = await asyncio.get_event_loop().run_in_executor(None, _download, fallback_opts)

            if not success:
                return None

            # Find the downloaded subtitle file (usually .vtt or .srt)
            sub_files = glob.glob(os.path.join(temp_dir, "subs.*"))
            if not sub_files:
                return None

            # Prefer English vtt
            vtt_file = next((f for f in sub_files if f.endswith('.vtt')), sub_files[0])
            
            with open(vtt_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return self._parse_vtt(content)
        except Exception as e:
            print(f"[YOUTUBE] Error processing yt-dlp subtitles: {e}")
            return None
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _parse_vtt(self, vtt_content: str) -> str:
        """Parse VTT content to extract clean text."""
        # 1. Remove WEBVTT header
        content = re.sub(r'^WEBVTT.*?\n', '', vtt_content, flags=re.DOTALL)
        
        # 2. Remove timestamps (00:00:00.000 --> 00:00:00.000)
        content = re.sub(r'\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}', '', content)
        
        # 3. Remove metadata/position tags like <c.colorE8E8E8> or alignments
        content = re.sub(r'<[^>]+>', '', content)
        content = re.sub(r' align:.*?\n', '\n', content)
        
        # 4. Remove empty lines and duplicates (VTT often overlaps lines)
        lines = []
        last_line = ""
        for line in content.split('\n'):
            line = line.strip()
            if line and line != last_line:
                lines.append(line)
                last_line = line
        
        return " ".join(lines)

    async def _fetch_local_whisper_transcript(self, video_url: str) -> str:
        """
        Tier 3: Local faster-whisper fallback for multilingual transcription.
        """
        if not self.local_whisper_available:
            return ""

        video_id = self.extract_video_id(video_url)
        if not video_id:
            return ""

        temp_audio = await self._download_media_audio(video_url, is_youtube=True)
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

