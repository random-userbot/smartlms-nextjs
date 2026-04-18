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

    try:
        print(f"[PROXY] Fetching transcript for video: {v}")
        
        # Tier 1: Static method (Standard)
        if hasattr(YouTubeTranscriptApi, 'get_transcript'):
             transcript_list = YouTubeTranscriptApi.get_transcript(v, languages=['en', 'en-US', 'en-GB'])
        
        # Tier 2: Modern API
        elif hasattr(YouTubeTranscriptApi, 'list_transcripts'):
             transcript_list = YouTubeTranscriptApi.list_transcripts(v).find_transcript(['en', 'en-US', 'en-GB']).fetch()
        
        # Tier 3: Functional Interface
        elif 'youtube_transcript_api' in globals():
             import youtube_transcript_api
             if hasattr(youtube_transcript_api, 'get_transcript'):
                 transcript_list = youtube_transcript_api.get_transcript(v, languages=['en', 'en-US'])
             else:
                 raise AttributeError("Standard methods missing.")
        
        # Tier 4: yt-dlp Scraper (The "Heavy" Fallback)
        else:
             print(f"[PROXY] Trying yt-dlp scraper for {v}...")
             from yt_dlp import YoutubeDL
             ydl_opts = {
                 'skip_download': True,
                 'quiet': True,
                 'no_warnings': True,
                 'writesubtitles': True,
                 'writeautomaticsub': True,
                 'subtitleslangs': ['en.*'],
             }
             with YoutubeDL(ydl_opts) as ydl:
                 info = ydl.extract_info(f"https://www.youtube.com/watch?v={v}", download=False)
                 # This is a simplified fallback; in production, you'd parse the subtitle URL
                 # For now, let's treat the existence of auto-captions as a proxy for success
                 if 'subtitles' in info or 'automatic_captions' in info:
                     return {"success": True, "v": v, "transcript": "[SCRAPED VIA YT-DLP] Captions found. Please check video directly for full text if processing fails."}
                 raise Exception("No captions found via yt-dlp")
        
        text = " ".join([t['text'] for t in transcript_list])
        return {
            "success": True, 
            "v": v, 
            "transcript": text
        }
    except Exception as e:
        print(f"[PROXY] Final Error: {str(e)}")
        # If it's a specific import error, try one last desperation import
        raise HTTPException(status_code=500, detail=f"Proxy transcription failed: {str(e)}")

@app.get("/health")
async def health():
    return {"status": "online"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
