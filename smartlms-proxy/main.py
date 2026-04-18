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
        transcript_list = YouTubeTranscriptApi.get_transcript(v, languages=['en', 'en-US'])
        text = " ".join([t['text'] for t in transcript_list])
        return {
            "success": True, 
            "v": v, 
            "transcript": text
        }
    except Exception as e:
        print(f"[PROXY] Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "online"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
