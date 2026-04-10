import youtube_transcript_api
from youtube_transcript_api import YouTubeTranscriptApi

video_id = "tA42nHmmEKw"

print(f"Testing YouTubeTranscriptApi.list({video_id})...")
try:
    try:
        # Check if they are class methods
        result = YouTubeTranscriptApi.list(video_id)
        print("Success! YouTubeTranscriptApi.list() is a class method.")
        print(f"Result type: {type(result)}")
    except TypeError:
        # Maybe instance method?
        api = YouTubeTranscriptApi()
        result = api.list(video_id)
        print("Success! YouTubeTranscriptApi.list() is an instance method.")
except Exception as e:
    print(f"YouTubeTranscriptApi.list() failed: {e}")

print(f"\nTesting YouTubeTranscriptApi.fetch([{video_id}])...")
try:
    try:
        result = YouTubeTranscriptApi.fetch([video_id])
        print("Success! YouTubeTranscriptApi.fetch() is a class method.")
    except TypeError:
        api = YouTubeTranscriptApi()
        result = api.fetch([video_id])
        print("Success! YouTubeTranscriptApi.fetch() is an instance method.")
except Exception as e:
    print(f"YouTubeTranscriptApi.fetch() failed: {e}")
