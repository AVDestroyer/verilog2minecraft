from youtube_transcript_api import YouTubeTranscriptApi
from urllib.parse import urlparse, parse_qs

def extract_video_id(url):
    parsed = urlparse(url)
    if parsed.hostname in ["www.youtube.com", "youtube.com"]:
        return parse_qs(parsed.query)["v"][0]
    if parsed.hostname == "youtu.be":
        return parsed.path[1:]
    return None

def get_transcript(url):
    vid = extract_video_id(url)
    transcript = YouTubeTranscriptApi.get_transcript(vid)
    return "\n".join([t["text"] for t in transcript])
