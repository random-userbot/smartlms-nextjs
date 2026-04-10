import youtube_transcript_api
from youtube_transcript_api import YouTubeTranscriptApi

print(f"Module: {youtube_transcript_api}")
print(f"Module attributes: {dir(youtube_transcript_api)}")
print(f"Class: {YouTubeTranscriptApi}")
print(f"Class attributes: {dir(YouTubeTranscriptApi)}")

try:
    print(f"get_transcript exists in class: {hasattr(YouTubeTranscriptApi, 'get_transcript')}")
    print(f"list_transcripts exists in class: {hasattr(YouTubeTranscriptApi, 'list_transcripts')}")
except Exception as e:
    print(f"Error checking attributes: {e}")
