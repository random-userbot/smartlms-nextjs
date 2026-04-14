import asyncio
from dotenv import load_dotenv
load_dotenv()
from app.services.youtube_service import YouTubeService
async def main():
    service = YouTubeService()
    url = "https://youtube.com/playlist?list=PLyqSpQzTE6M_fFg1zZmeGIkeni"
    print("Testing playlist extraction...")
    try:
        videos = await service.get_playlist_videos(url)
        print(f"Success! Found {len(videos)} videos.")
        if videos:
            print("First video:", videos[0].get("title"))
    except Exception as e:
        print("Failed:", e)
if __name__ == "__main__":
    asyncio.run(main())
