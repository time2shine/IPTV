import yt_dlp
import os
import datetime
import logging

# --- CONFIG ---
cookies_file_path = 'cookies.txt'

# Force BD region parameters for YouTube
def force_bd_region(url: str) -> str:
    if '?' in url:
        return url + "&gl=BD&gcr=BD&hl=bn"
    else:
        return url + "?gl=BD&gcr=BD&hl=bn"

def get_stream_url(video_url: str) -> str:
    ydl_opts = {
        'cookies': cookies_file_path,
        'format': 'best[ext=m3u8]/best',
        'quiet': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            if 'url' in info:
                return info['url']
            elif 'formats' in info:
                for f in info['formats']:
                    if f.get('protocol') == 'm3u8_native' and f.get('url'):
                        return f['url']
    except Exception as e:
        logging.error(f"Error fetching stream URL: {e}")
    return None

if __name__ == "__main__":
    link = 'https://www.youtube.com/watch?v=TdwhCOFh9OA'
    bd_link = force_bd_region(link)
    stream_url = get_stream_url(bd_link)
    if stream_url:
        print("#EXTM3U")
        print(f"# Updated on {datetime.datetime.now()}")
        print(f"#EXTINF:-1, Test Channel")
        print(stream_url)
    else:
        print("Failed to get stream URL.")
