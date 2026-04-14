import asyncio
from dotenv import load_dotenv
load_dotenv()
from app.services.youtube_service import YouTubeService

async def main():
    service = YouTubeService()
    url = "https://youtu.be/1993zSY5UBI?si=foo"
    print("Testing audio extraction...")
    try:
        audio = await service._download_media_audio(url)
        print(f"Success! Audio path: {audio}")
    except Exception as e:
        print("Failed:", type(e).__name__, e)

if __name__ == "__main__":
    asyncio.run(main())
