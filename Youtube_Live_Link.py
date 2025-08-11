import random
import yt_dlp
import requests
import os
import datetime
import logging

# --- CONFIG ---
cookies_file_path = 'cookies.txt'
CHECK_M3U8_TIMEOUT = 10  # seconds

# --- LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- Check cookies file exists ---
if not os.path.exists(cookies_file_path):
    logger.warning(f"Cookies file not found: {cookies_file_path}. Proceeding without cookies.")

def get_user_agent():
    versions = [
        (122, 6267, 70), (121, 6167, 131), (120, 6099, 109)
    ]
    major, build, patch = random.choice(versions)
    return (
        f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        f"AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{major}.0.{build}.{patch} Safari/537.36"
    )

def get_live_video_url(channel_id):
    """Check if the channel is live by requesting /channel/{channel_id}/live.
    If redirected to /watch?v=video_id, return that live video URL.
    Else None."""
    url = f"https://www.youtube.com/channel/{channel_id}/live"
    headers = {
        'User-Agent': get_user_agent(),
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.youtube.com/',
    }
    try:
        # Allow redirects to find the final URL
        response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        final_url = response.url
        if '/watch?v=' in final_url:
            logger.info(f"Live video found for channel {channel_id}: {final_url}")
            return final_url
        else:
            logger.info(f"No live video found for channel {channel_id}")
            return None
    except Exception as e:
        logger.error(f"Error checking live video for channel {channel_id}: {e}")
        return None

def get_stream_url(url):
    ydl_opts = {
        'format': 'best',
        'cookiefile': cookies_file_path if os.path.exists(cookies_file_path) else None,
        'force_ipv4': True,
        'retries': 5,
        'fragment_retries': 5,
        'skip_unavailable_fragments': True,
        'extractor_args': {'youtube': {'skip': ['translated_subs']}},
        'http_headers': {
            'User-Agent': get_user_agent(),
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.youtube.com/',
        },
        'quiet': True,
        'no_warnings': True
    }

    # Remove None keys (like cookiefile if no cookie)
    ydl_opts = {k:v for k,v in ydl_opts.items() if v is not None}

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            m3u8_urls = [
                fmt['manifest_url'] for fmt in info.get('formats', [])
                if fmt.get('protocol') in ['m3u8', 'm3u8_native']
            ]
            if m3u8_urls:
                return m3u8_urls[0]  # Return first m3u8 URL found
            else:
                logger.warning(f"No m3u8 stream found for {url}")
                return None
    except Exception as e:
        logger.error(f"Failed to extract stream URL from {url}: {e}")
        return None

def check_m3u8_url(url):
    """Check if the m3u8 URL is reachable (HEAD request)"""
    headers = {
        'User-Agent': get_user_agent(),
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.youtube.com/',
    }
    try:
        r = requests.head(url, headers=headers, timeout=CHECK_M3U8_TIMEOUT)
        if r.status_code == 200:
            return True
        else:
            logger.warning(f"m3u8 URL not reachable (status {r.status_code}): {url}")
            return False
    except Exception as e:
        logger.warning(f"Failed to reach m3u8 URL: {url} - {e}")
        return False

def format_live_link(channel_name, channel_logo, m3u8_link, channel_number, group_title):
    return (
        f'#EXTINF:-1 tvg-chno="{channel_number}" tvg-name="{channel_name}" '
        f'tvg-id="" group-title="{group_title}" tvg-logo="{channel_logo}" tvg-epg="", '
        f'{channel_name}\n{m3u8_link}'
    )

def save_m3u_file(output_data, base_filename="YT_playlist"):
    filename = f"{base_filename}.m3u"
    with open(filename, "w", encoding="utf-8") as file:
        file.write("#EXTM3U\n")
        file.write(f"# Updated on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        for data in output_data:
            file.write(data + "\n")
    logger.info(f"M3U playlist saved as {filename}")

# --- Channel metadata (simplified example, add your channels here) ---
channel_metadata = {
    'UCWVqdPTigfQ-cSNwG7O9MeA': {
        'channel_number': 103,
        'group_title': 'News',
        'channel_name': 'EKHON TV',
        'channel_logo': 'https://yt3.googleusercontent.com/66cO7vPXs2Xssf6fq2cn90oDsJ3OFMThb57qfRkRMjaSqg3ouTG6m9WQKZFg6GmUS5G8wkPu7ik=s72-c-k-c0x00ffffff-no-rj',
    },
    # Add other channels...
}

def main():
    output_data = []

    for channel_id, meta in channel_metadata.items():
        logger.info(f"Processing channel: {meta['channel_name']}")

        live_url = get_live_video_url(channel_id)
        if not live_url:
            logger.info(f"No live stream for {meta['channel_name']}")
            continue

        m3u8_url = get_stream_url(live_url)
        if not m3u8_url:
            logger.info(f"No m3u8 stream for {meta['channel_name']}")
            continue

        if not check_m3u8_url(m3u8_url):
            logger.info(f"m3u8 URL unreachable for {meta['channel_name']}")
            continue

        formatted = format_live_link(
            meta['channel_name'], meta['channel_logo'],
            m3u8_url, meta['channel_number'], meta['group_title']
        )
        output_data.append(formatted)

    if output_data:
        save_m3u_file(output_data)
    else:
        logger.warning("No live streams with valid m3u8 found.")

if __name__ == "__main__":
    main()
