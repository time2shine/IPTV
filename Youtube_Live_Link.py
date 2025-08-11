import random
import datetime
import yt_dlp
import os
import time
import logging

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

# --- Check cookies file exists ---
if not os.path.exists(cookies_file_path):
    raise FileNotFoundError(f"Missing cookies file: {cookies_file_path}")


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
    url = f"https://www.youtube.com/channel/{channel_id}/live"
    ydl_opts = {
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
        'no_warnings': True
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


def get_stream_url(url):
    ydl_opts = {
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
        'no_warnings': True
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return next(
                (fmt['url'] for fmt in info['formats']
                 if fmt.get('protocol') in ['m3u8', 'm3u8_native']),
                None
            )
    except Exception as e:
        logger.error(f"Failed to get stream URL for {url}: {e}")
        return None


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


def save_to_m3u(channels_dict):
    output_data = []

    for channel_id, info in channels_dict.items():
        logger.info(f"Processing channel: {info['channel_name']} (ID: {channel_id})")
        live_url = None
        m3u8_link = None

        # Retry logic for getting live video url
        for attempt in range(MAX_API_RETRIES + 1):
            try:
                live_url = get_live_video_url(channel_id)
                if live_url:
                    break
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed to get live video URL for {info['channel_name']}: {e}")
                time.sleep(RETRY_WAIT_SECONDS)

        if not live_url:
            logger.warning(f"No live video found for {info['channel_name']} ({channel_id}). Skipping.")
            continue

        # Retry logic for getting m3u8 stream url
        for attempt in range(MAX_API_RETRIES + 1):
            try:
                m3u8_link = get_stream_url(live_url)
                if m3u8_link:
                    break
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed to get m3u8 stream URL for {info['channel_name']}: {e}")
                time.sleep(RETRY_WAIT_SECONDS)

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

    save_m3u_file(output_data)


# Example channels dictionary (use your full list here)
channels = {
    'UCxHoBXkY88Tb8z1Ssj6CWsQ': {  # Somoy News
        'channel_number': 101,
        'group_title': 'News',
        'channel_name': 'Somoy News',
        'channel_logo': 'https://yt3.googleusercontent.com/7F-3_9yjPiMJzBAuD7niglcJmFyXCrFGSEugcEroFrIkxudmhiZ9i-Q_pW4Zrn2IiCLN5dQX8A=s160-c-k-c0x00ffffff-no-rj',
    },
    # Add other channels as needed...
}

if __name__ == '__main__':
    save_to_m3u(channels)
