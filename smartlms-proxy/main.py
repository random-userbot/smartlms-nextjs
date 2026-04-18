from fastapi import FastAPI, HTTPException, Query
from youtube_transcript_api import YouTubeTranscriptApi
import os
import uvicorn

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
            with open(final_cookie_path, 'r') as f:
                header = f.read(10)
                if header.startswith('[') or header.startswith('{'):
                    print(f"[PROXY] ERROR !!!: {final_cookie_path} is in JSON format. YouTube scraping will FAIL. Please use the 'Get cookies.txt' extension to export in NETSCAPE format.")
                else:
                    print(f"[PROXY] SUCCESS: Loaded cookies from {final_cookie_path}")
        except:
             print(f"[PROXY] SUCCESS: Found cookies at {final_cookie_path}")
    else:
        print(f"[PROXY] WARNING: cookies.txt not found. Searching in: {search_paths}")

    last_error = "None"
    try:
        print(f"[PROXY] Fetching transcript for video: {v}")
        
        # Tier 1: Static method (Standard)
        try:
            print("[PROXY] Tier 1: Trying get_transcript...")
            transcript_list = YouTubeTranscriptApi.get_transcript(
                 v, languages=['en', 'en-US', 'en-GB'], cookies=final_cookie_path
            )
            return {"success": True, "v": v, "transcript": " ".join([t['text'] for t in transcript_list])}
        except Exception as e:
            last_error = str(e)
            print(f"[PROXY] Tier 1 Failed: {last_error}")

        # Tier 2: Modern API
        try:
            print("[PROXY] Tier 2: Trying list_transcripts...")
            transcript_list = YouTubeTranscriptApi.list_transcripts(
                v, cookies=final_cookie_path
            ).find_transcript(['en', 'en-US', 'en-GB']).fetch()
            return {"success": True, "v": v, "transcript": " ".join([t['text'] for t in transcript_list])}
        except Exception as e:
            last_error = str(e)
            print(f"[PROXY] Tier 2 Failed: {last_error}")

        # Tier 3: yt-dlp Scraper
        try:
             print(f"[PROXY] Tier 3: Trying yt-dlp scraper...")
             from yt_dlp import YoutubeDL
             ydl_opts = {
                 'skip_download': True,
                 'quiet': True,
                 'no_warnings': True,
                 'cookiefile': final_cookie_path,
             }
             with YoutubeDL(ydl_opts) as ydl:
                 info = ydl.extract_info(f"https://www.youtube.com/watch?v={v}", download=False)
                 if 'subtitles' in info and info['subtitles']:
                     return {"success": True, "v": v, "transcript": "[SCRAPED VIA YT-DLP] Captions found. Check video directly for sync."}
                 elif 'automatic_captions' in info and info['automatic_captions']:
                     return {"success": True, "v": v, "transcript": "[AUTO-SCRAPED VIA YT-DLP] Captions found."}
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
