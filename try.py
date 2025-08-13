import yt_dlp
import time

def get_live_video_url(channel_id):
    """Get the active live stream URL from a YouTube channel"""
    url = f"https://www.youtube.com/channel/{channel_id}/live"
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'forceurl': True,
        'extract_flat': True,
        'cookiefile': 'cookies.txt',  # Use cookies for potential region restrictions
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info and 'url' in info:
                return info['url']
            if info and 'entries' in info and len(info['entries']) > 0:
                return info['entries'][0]['url']
    except yt_dlp.utils.DownloadError as e:
        print(f"Error accessing channel: {e}")
    return None

def get_m3u8_url(video_url):
    """Extract M3U8 URL from a YouTube video URL with region handling"""
    ydl_opts = {
        'cookiefile': 'cookies.txt',
        'format': 'best[protocol^=m3u8]',  # Select best HLS format
        'skip_download': True,
        'forceurl': True,
        'quiet': True,
        'geo_bypass': True,  # Bypass geographic restrictions
        'geo_bypass_country': 'BD',  # Set your country code (Bangladesh)
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            if 'url' in info:
                return info['url']
    except yt_dlp.utils.DownloadError as e:
        print(f"Stream extraction error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
    return None

def get_fresh_m3u8(channel_id, max_retries=3):
    """Get fresh M3U8 URL with retry mechanism"""
    for attempt in range(max_retries):
        live_url = get_live_video_url(channel_id)
        if not live_url:
            print(f"Attempt {attempt+1}: Channel not live")
            time.sleep(2)
            continue
            
        m3u8_url = get_m3u8_url(live_url)
        if m3u8_url:
            print("Successfully retrieved M3U8 URL")
            return m3u8_url
        
        print(f"Attempt {attempt+1}: Failed to get M3U8, retrying...")
        time.sleep(3)
    
    return None

# Example usage
if __name__ == "__main__":
    channel_id = 'UCtqvtAVmad5zywaziN6CbfA'  # Replace with your channel ID
    
    print("Fetching live stream...")
    m3u8_url = get_fresh_m3u8(channel_id)
    
    if m3u8_url:
        print("\nValid M3U8 URL:")
        print(m3u8_url)
        
        # For immediate testing (optional)
        print("\nYou can test with VLC or FFmpeg:")
        print(f"vlc '{m3u8_url}'")
        print(f"ffmpeg -i '{m3u8_url}' -c copy test.mp4")
    else:
        print("Failed to get valid M3U8 URL after retries")
        print("Possible reasons:")
        print("- Channel is not currently live")
        print("- Stream is region-restricted (try VPN)")
        print("- Cookies are expired or invalid")
        print("- YouTube changed their API")
