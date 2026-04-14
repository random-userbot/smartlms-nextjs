from app.services.youtube_service import YouTubeService
import asyncio

async def test():
    yt = YouTubeService()
    url = "https://www.youtube.com/watch?v=1993zSY5UBI"
    yt._setup_resilience()
    print("Cookie path:", yt._cookie_path)
    res = await yt._fetch_api_transcript("1993zSY5UBI")
    print("Success, length:", len(res) if res else "None")

asyncio.run(test())
