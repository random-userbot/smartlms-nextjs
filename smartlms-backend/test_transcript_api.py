from youtube_transcript_api import YouTubeTranscriptApi
print([m for m in dir(YouTubeTranscriptApi) if not m.startswith("_")])
print(help(YouTubeTranscriptApi.__init__))
print(help(YouTubeTranscriptApi.list))
