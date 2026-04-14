import asyncio
import yt_dlp

async def main():
    opts = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True,
        "extract_audio": True,
        "extract_flat": True, # don't download videos
    }
    
    url = "https://youtube.com/playlist?list=PLyqSpQzTE6M_fFg1zZmeGIkeni"
    print("Testing playlist extraction with default yt-dlp headers...")
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            videos = info.get("entries", [])
            print(f"Success! Found {len(videos)} videos.")
    except Exception as e:
        print("Failed:", e)

    # NOW WITH CUSTOM HEADERS
    opts["http_headers"] = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,webp,image/apng,*/*;q=0.8",
    }
    print("Testing playlist extraction WITH broken HTML Accept headers...")
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            print(f"Success!")
    except Exception as e:
        print("Failed:", e)

if __name__ == "__main__":
    asyncio.run(main())
