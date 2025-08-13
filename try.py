import yt_dlp

def get_live_video_url(channel_id):
    url = f"https://www.youtube.com/channel/{channel_id}/live"
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'forceurl': True,
        'extract_flat': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        if info and 'url' in info:
            return info['url']
        if info and 'entries' in info and len(info['entries']) > 0:
            return info['entries'][0]['url']
    return None

def get_m3u8_url(video_url):
    ydl_opts = {
        'cookiefile': 'cookies.txt',  # Use cookies for age-restricted/content access
        'format': 'best[protocol^=m3u8]',  # Select HLS manifest format
        'quiet': True,
        'skip_download': True,
        'forceurl': True,  # Only extract the URL
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=False)
        if 'url' in info:
            return info['url']
    return None

# Example usage
channel_id = 'UCtqvtAVmad5zywaziN6CbfA'
live_url = get_live_video_url(channel_id)

if live_url:
    print(f"Live video URL: {live_url}")
    m3u8_url = get_m3u8_url(live_url)
    if m3u8_url:
        print(f"M3U8 URL: {m3u8_url}")
    else:
        print("Failed to extract M3U8 URL")
else:
    print("Channel is not live or URL not found")
