import yt_dlp

def get_live_video_url(channel_id):
    url = f"https://www.youtube.com/channel/{channel_id}/live"
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'forceurl': True,  # Only get URL (not download)
        'extract_flat': True,  # Do not resolve full info, faster
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        # If live video is active, yt-dlp gives info about that video
        if info and 'url' in info:
            return info['url']
        # Sometimes info['entries'] contains the video list
        if info and 'entries' in info and len(info['entries']) > 0:
            return info['entries'][0]['url']
    return None

channel_id = 'UCxHoBXkY88Tb8z1Ssj6CWsQ'  # Your example channel
live_url = get_live_video_url(channel_id)
print("Live video URL:", live_url)
