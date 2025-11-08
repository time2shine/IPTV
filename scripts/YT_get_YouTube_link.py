import random
import time
import datetime
import yt_dlp
import os
import logging
import json
from pathlib import Path
# from .YT_channels import channel_metadata  # replaced by JSON loader

# --- Load channels from JSON (same directory as this script) ---
_here = Path(__file__).resolve().parent
with open(_here / "YT_channels.json", "r", encoding="utf-8") as f:
    channel_metadata = json.load(f)

# --- Setup logging ---
logger = logging.getLogger("yt_logger")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('[%(levelname)s] %(asctime)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# --- Cookies file ---
cookies_file_path = 'cookies.txt'
if not os.path.exists(cookies_file_path):
    raise FileNotFoundError(f"Missing cookies file: {cookies_file_path}")

# --- User-Agent generator ---
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

# --- Get live YouTube URL ---
def get_live_watch_url(channel_id):
    url = f"https://www.youtube.com/channel/{channel_id}/live"
    ydl_opts = {
        'cookiefile': cookies_file_path,
        'force_ipv4': True,
        'http_headers': {
            'User-Agent': get_user_agent(),
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.youtube.com/',
            'Sec-Fetch-Mode': 'navigate',
        },
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return None

            if info.get("is_live"):
                return info.get("webpage_url") or f"https://www.youtube.com/watch?v={info['id']}"

            if "entries" in info:
                for entry in info["entries"]:
                    if entry.get("is_live"):
                        return entry.get("webpage_url") or f"https://www.youtube.com/watch?v={entry['id']}"
    except yt_dlp.utils.DownloadError as e:
        return None
    except Exception as e:
        logger.error(f"Unexpected error for channel {channel_id}: {e}")
        return None

    return None

# --- Get m3u8 stream URL ---
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
                (fmt['manifest_url'] for fmt in info['formats']
                 if fmt.get('protocol') in ['m3u8', 'm3u8_native']),
                None
            )
    except Exception as e:
        logger.error(f"Failed to get stream URL for {url}: {e}")
        return None

# --- Format M3U line ---
def format_live_link(channel_name, channel_logo, m3u8_link, group_title):
    return (
        f'#EXTINF:-1 group-title="{group_title}" tvg-id="YouTube" tvg-logo="{channel_logo}", {channel_name}\n'
        f'{m3u8_link}'
    )

# --- Save M3U file ---
def save_m3u_file(output_data, base_filename="YT_playlist"):
    filename = f"{base_filename}.m3u"

    with open(filename, "w", encoding="utf-8") as file:
        file.write("#EXTM3U\n")
        file.write(f"# Updated on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        for data in output_data:
            file.write(data + "\n")
    logger.info(f"M3U playlist saved as {filename}")

# --- Main process ---
def main():
    output_data = []

    for channel_id, metadata in channel_metadata.items():
        group_title = metadata.get('group_title', 'Others')
        channel_name = metadata.get('channel_name', 'Unknown')
        channel_logo = metadata.get('channel_logo', '')

        logger.info(f"Checking channel: {channel_name}")

        live_link = get_live_watch_url(channel_id)
        if not live_link:
            logger.warning(f"Skipping {channel_name}: no live video found")
            continue

        m3u8_link = get_stream_url(live_link)
        if not m3u8_link:
            logger.warning(f"Skipping {channel_name}: no stream link found")
            continue

        formatted_info = format_live_link(
            channel_name, channel_logo, m3u8_link, group_title
        )
        output_data.append(formatted_info)

    if output_data:
        save_m3u_file(output_data)
    else:
        logger.warning("No live streams found for any channels.")

# --- Entry point ---
if __name__ == '__main__':
    main()
