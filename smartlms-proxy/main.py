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
        
        # Tier 3: Functional Interface (Last Resort)
        else:
             import youtube_transcript_api
             if hasattr(youtube_transcript_api, 'get_transcript'):
                 transcript_list = youtube_transcript_api.get_transcript(v, languages=['en', 'en-US'])
             else:
                 available = [m for m in dir(YouTubeTranscriptApi) if not m.startswith('_')]
                 raise AttributeError(f"Could not find fetch method. Available: {available}")
        
        text = " ".join([t['text'] for t in transcript_list])
        return {
            "success": True, 
            "v": v, 
            "transcript": text
        }
    except Exception as e:
        print(f"[PROXY] Final Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Proxy transcription failed: {str(e)}")

@app.get("/health")
async def health():
    return {"status": "online"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
