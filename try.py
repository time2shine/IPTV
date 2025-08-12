import random
import datetime
import yt_dlp
import os
import time
import logging
from typing import Optional

# --- CONFIG ---
cookies_file_path = 'cookies.txt'
MAX_API_RETRIES = 1
RETRY_WAIT_SECONDS = 3

# --- LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

if not os.path.exists(cookies_file_path):
    raise FileNotFoundError(f"Missing cookies file: {cookies_file_path}")


def force_bd_region(url: str) -> str:
    """Append Bangladesh geo parameters to the URL."""
    params = "gl=BD&gcr=BD&hl=bn"
    if '?' in url:
        return f"{url}&{params}"
    else:
        return f"{url}?{params}"


def get_user_agent() -> str:
    versions = [
        (122, 6267, 70), (121, 6167, 131), (120, 6099, 109)
    ]
    major, build, patch = random.choice(versions)
    return (
        f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        f"AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{major}.0.{build}.{patch} Safari/537.36"
    )


# Base yt_dlp options reused for all yt_dlp calls
def get_ydl_opts() -> dict:
    return {
        'format': 'best',
        'cookiefile': cookies_file_path,
        'force_ipv4': True,
        'retries': 10,
        'fragment_retries': 10,
        'skip_unavailable_fragments': True,
        'extractor_args': {'youtube': {'skip': ['translated_subs']}},
        'http_headers': {
            'User-Agent': get_user_agent(),
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.youtube.com/',
            'Sec-Fetch-Mode': 'navigate',
        },
        'quiet': True,
        'no_warnings': True,
    }


def retry(func, *args, retries=MAX_API_RETRIES, wait=RETRY_WAIT_SECONDS, **kwargs):
    """Retry helper function."""
    for attempt in range(retries + 1):
        try:
            result = func(*args, **kwargs)
            if result:
                return result
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed: {e}")
        if attempt < retries:
            time.sleep(wait)
    return None


def get_live_video_url(channel_id: str) -> Optional[str]:
    """Get live video URL for a given channel ID."""
    url = force_bd_region(f"https://www.youtube.com/channel/{channel_id}/live")
    ydl_opts = get_ydl_opts()

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        # Live video direct url
        if info and 'url' in info:
            return info['url']
        # Or first entry in entries
        if info and 'entries' in info and info['entries']:
            return info['entries'][0]['url']
    return None


def get_stream_url(url: str) -> Optional[str]:
    """Extract m3u8 stream URL from a YouTube video URL."""
    url = force_bd_region(url)
    ydl_opts = get_ydl_opts()

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return next(
                (fmt['url'] for fmt in info.get('formats', [])
                 if fmt.get('protocol') in ('m3u8', 'm3u8_native')),
                None
            )
    except Exception as e:
        logger.error(f"Failed to get stream URL for {url}: {e}")
        return None


def format_live_link(channel_name: str, channel_logo: str, m3u8_link: str, channel_number: int, group_title: str) -> str:
    return (
        f'#EXTINF:-1 tvg-chno="{channel_number}" tvg-name="{channel_name}" '
        f'tvg-id="" group-title="{group_title}" tvg-logo="{channel_logo}" tvg-epg="", '
        f'{channel_name}\n{m3u8_link}'
    )


def save_m3u_file(output_data: list[str], base_filename: str = "YT_playlist") -> None:
    filename = f"{base_filename}.m3u"
    with open(filename, "w", encoding="utf-8") as file:
        file.write("#EXTM3U\n")
        file.write(f"# Updated on {datetime.datetime.now():%Y-%m-%d %H:%M:%S}\n")
        for line in output_data:
            file.write(line + "\n")
    logger.info(f"M3U playlist saved as {filename}")


def save_to_m3u(channels_dict: dict) -> None:
    output_data = []
    for channel_id, info in channels_dict.items():
        logger.info(f"Processing channel: {info['channel_name']} (ID: {channel_id})")

        live_url = retry(get_live_video_url, channel_id)
        if not live_url:
            logger.warning(f"No live video found for {info['channel_name']} ({channel_id}). Skipping.")
            continue

        m3u8_link = retry(get_stream_url, live_url)
        if not m3u8_link:
            logger.warning(f"Could not extract m3u8 stream URL for {info['channel_name']} ({channel_id}). Skipping.")
            continue

        line = format_live_link(
            channel_name=info['channel_name'],
            channel_logo=info.get('channel_logo', ''),
            m3u8_link=m3u8_link,
            channel_number=info.get('channel_number', 0),
            group_title=info.get('group_title', '')
        )
        output_data.append(line)

    if output_data:
        save_m3u_file(output_data)
    else:
        logger.warning("No live streams found for any channels.")


# Example channels dictionary (add more channels as needed)
channels = {
    'UCxHoBXkY88Tb8z1Ssj6CWsQ': {  # Somoy News
        'channel_number': 101,
        'group_title': 'News',
        'channel_name': 'Somoy News',
        'channel_logo': 'https://yt3.googleusercontent.com/7F-3_9yjPiMJzBAuD7niglcJmFyXCrFGSEugcEroFrIkxudmhiZ9i-Q_pW4Zrn2IiCLN5dQX8A=s160-c-k-c0x00ffffff-no-rj',
    },
    # Add other channels here...
}

if __name__ == '__main__':
    save_to_m3u(channels)
