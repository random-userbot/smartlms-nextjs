from fastapi import FastAPI, HTTPException, Query
from youtube_transcript_api import YouTubeTranscriptApi
import os
import uvicorn
import re
import tempfile
import glob

app = FastAPI(title="SmartLMS Transcript Proxy")

# Security: Add a simple secret key check if desired
PROXY_SECRET = os.getenv("PROXY_SECRET")

@app.get("/transcript")
async def get_transcript(
    v: str = Query(..., description="YouTube Video ID"),
    key: str = Query(None, description="Secret key for access")
):
    # Optional Security Check
    if PROXY_SECRET and key != PROXY_SECRET:
        raise HTTPException(status_code=403, detail="Invalid access key")

    # Robust Cookie Search
    search_paths = ["cookies.txt", "/app/cookies.txt", "/etc/secrets/cookies.txt"]
    final_cookie_path = None
    for p in search_paths:
        if os.path.exists(p):
            final_cookie_path = p
            break

    if final_cookie_path:
        try:
            size = os.path.getsize(final_cookie_path)
            with open(final_cookie_path, 'r') as f:
                content = f.read(100)
                # Masked preview for security (replaces letters/numbers with *)
                masked = re.sub(r'[a-zA-Z0-9]', '*', content[:50])
                print(f"[PROXY] COOKIE INSPECTOR: Size={size} bytes, Preview='{masked}...'")
                
                if content.startswith('[') or content.startswith('{'):
                    print(f"[PROXY] ERROR !!!: {final_cookie_path} is in JSON format. YouTube scraping will FAIL.")
                elif size < 100:
                    print(f"[PROXY] WARNING: Cookie file is very small ({size} bytes). It might be empty or invalid.")
                else:
                    print(f"[PROXY] SUCCESS: Loaded cookies from {final_cookie_path}")
        except Exception as file_err:
             print(f"[PROXY] ERROR reading cookie file: {str(file_err)}")
    else:
        print(f"[PROXY] WARNING: cookies.txt not found. Searching in: {search_paths}")

    last_error = "None"
    try:
        print(f"[PROXY] Fetching transcript for video: {v}")
        
        # Tier 1: Flexible API with Auto-Translation
        try:
            print("[PROXY] Tier 1: Trying get_transcript (with translation fallback)...")
            try:
                # Try preferred languages first
                transcript_list = YouTubeTranscriptApi.get_transcript(
                     v, languages=['en', 'en-US', 'en-GB'], cookies=final_cookie_path
                )
            except:
                # Fallback: Get the list and translate the first available language to English
                print("[PROXY] Native English missing. Attempting translation...")
                transcript_list_obj = YouTubeTranscriptApi.list_transcripts(v, cookies=final_cookie_path)
                # Try to find any transcript and translate it to English
                transcript_list = transcript_list_obj.find_transcript(['en', 'en-US', 'en-GB', 'hi', 'es', 'fr', 'de']).translate('en').fetch()
            
            return {"success": True, "v": v, "transcript": " ".join([t['text'] for t in transcript_list])}
        except Exception as e:
            last_error = str(e)
            print(f"[PROXY] Tier 1 Failed: {last_error}")

        # Tier 2: Modern API Fallback
        try:
            print("[PROXY] Tier 2: Trying list_transcripts (Manual translation)...")
            t_obj = YouTubeTranscriptApi.list_transcripts(v, cookies=final_cookie_path)
            # Desperation: find the first available transcript and translate it
            first_available = list(t_obj._manually_created_transcripts.values()) + list(t_obj._generated_transcripts.values())
            if first_available:
                transcript_list = first_available[0].translate('en').fetch()
                return {"success": True, "v": v, "transcript": " ".join([t['text'] for t in transcript_list])}
        except Exception as e:
            last_error = str(e)
            print(f"[PROXY] Tier 2 Failed: {last_error}")

        # Tier 3: yt-dlp Scraper
        try:
             print(f"[PROXY] Tier 3: Trying yt-dlp scraper...")
             from yt_dlp import YoutubeDL
             
             with tempfile.TemporaryDirectory() as tmpdir:
                 ydl_opts = {
                     'skip_download': True,
                     'quiet': True,
                     'cookiefile': final_cookie_path,
                     'writesubtitles': True,
                     'writeautomaticsub': True,
                     'subtitleslangs': ['en.*'],
                     'outtmpl': f'{tmpdir}/%(id)s.%(ext)s',
                 }
                 with YoutubeDL(ydl_opts) as ydl:
                     ydl.download([f"https://www.youtube.com/watch?v={v}"])
                     
                     # Look for the .vtt or .srt file
                     files = glob.glob(f"{tmpdir}/{v}.en*")
                     if files:
                         with open(files[0], 'r', encoding='utf-8') as sf:
                             raw_text = sf.read()
                             # Simple VTT/SRT cleanup (removes timestamps/headers/formatting)
                             clean_text = raw_text
                             clean_text = re.sub(r'WEBVTT|Kind:.*|Language:.*|ID:.*', '', clean_text)
                             clean_text = re.sub(r'\d{2}:\d{2}:\d{2}.\d{3} --> \d{2}:\d{2}:\d{2}.\d{3}', '', clean_text)
                             clean_text = re.sub(r'<.*?>', '', clean_text)
                             clean_text = re.sub(r'align:.*?position:.*?\d+%', '', clean_text) # Remove VTT alignment tags
                             clean_text = " ".join(clean_text.split())
                             return {"success": True, "v": v, "transcript": clean_text}
                     
                 raise Exception("No caption files generated by yt-dlp")
        except Exception as e:
            last_error = str(e)
            print(f"[PROXY] Tier 3 Failed: {last_error}")

        raise Exception(f"All tiers failed. Last error: {last_error}")

    except Exception as e:
        print(f"[PROXY] Final Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Proxy transcription failed: {str(e)}")

@app.get("/health")
async def health():
    return {"status": "online"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
