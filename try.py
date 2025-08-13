import yt_dlp
import time
import requests
from urllib.parse import parse_qs, urlparse

def get_live_video_url(channel_id):
    """Get the active live stream URL from a YouTube channel with freshness"""
    url = f"https://www.youtube.com/channel/{channel_id}/live"
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'forceurl': True,
        'extract_flat': True,
        'cookiefile': 'cookies.txt',
        'geo_bypass': True,
        'geo_bypass_country': 'US',  # Use US as proxy country
        'proxy': 'https://'  # Force fresh connection
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info and 'url' in info:
                return info['url']
            if info and 'entries' in info and len(info['entries']) > 0:
                return info['entries'][0]['url']
    except Exception as e:
        print(f"Error getting live URL: {str(e)[:100]}")
    return None

def get_m3u8_url(video_url):
    """Extract M3U8 URL with signature decoding and timestamp refresh"""
    try:
        # Force fresh URL with current timestamp
        parsed = urlparse(video_url)
        query = parse_qs(parsed.query)
        query['expire'] = [str(int(time.time()) + 7200)]  # 2 hours validity
        new_query = '&'.join([f"{k}={v[0]}" for k,v in query.items()])
        fresh_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{new_query}"

        ydl_opts = {
            'cookiefile': 'cookies.txt',
            'format': 'best[protocol^=m3u8]',
            'skip_download': True,
            'quiet': True,
            'forceurl': True,
            'geo_bypass': True,
            'geo_bypass_country': 'US',  # Bypass regional restrictions
            'proxy': 'https://',  # Bypass local network restrictions
            'external_downloader': 'aria2c',  # Better handling of HLS streams
            'external_downloader_args': ['--auto-file-renaming=false']
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(fresh_url, download=False)
            return info['url']
    except Exception as e:
        print(f"Error getting M3U8: {str(e)[:100]}")
    return None

def verify_m3u8_url(m3u8_url):
    """Check if M3U8 URL is actually playable"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://www.youtube.com/',
            'Origin': 'https://www.youtube.com'
        }
        response = requests.get(
            m3u8_url, 
            headers=headers,
            timeout=10,
            stream=True
        )
        response.raise_for_status()
        
        # Check if response contains actual playlist
        if '#EXTM3U' in response.text[:100]:
            return True
    except Exception as e:
        print(f"URL verification failed: {str(e)[:100]}")
    return False

def get_working_stream(channel_id, max_retries=5):
    """Get verified working stream URL with multiple fallbacks"""
    for attempt in range(max_retries):
        print(f"\nAttempt {attempt+1}/{max_retries}")
        
        # Get fresh live URL
        live_url = get_live_video_url(channel_id)
        if not live_url:
            print("No live stream found")
            time.sleep(3)
            continue
        print(f"Live URL: {live_url[:80]}...")
        
        # Get M3U8 URL with fresh parameters
        m3u8_url = get_m3u8_url(live_url)
        if not m3u8_url:
            print("Failed to extract M3U8")
            time.sleep(3)
            continue
        print(f"M3U8 URL: {m3u8_url[:80]}...")
        
        # Verify URL actually works
        if verify_m3u8_url(m3u8_url):
            print("✅ Verified working stream")
            return m3u8_url
        
        print("❌ Stream verification failed")
        time.sleep(5)
    
    return None

if __name__ == "__main__":
    channel_id = 'UCtqvtAVmad5zywaziN6CbfA'
    
    print("Fetching working stream...")
    working_url = get_working_stream(channel_id)
    
    if working_url:
        print("\nWORKING STREAM URL:")
        print(working_url)
        
        print("\nTest with:")
        print(f"ffplay -i '{working_url}'")
        print(f"vlc '{working_url}'")
    else:
        print("\nFailed to get working stream. Possible solutions:")
        print("1. Use VPN (recommended: US server)")
        print("2. Update cookies.txt (export fresh cookies)")
        print("3. Check channel is actually live")
        print("4. Try different network (mobile hotspot)")
