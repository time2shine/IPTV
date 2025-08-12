import random
import googleapiclient.discovery
import datetime
import yt_dlp
import os
import time
import logging

# --- CONFIG ---
cookies_file_path = 'cookies.txt'
MAX_API_RETRIES = 1
RETRY_WAIT_SECONDS = 3
link = 'https://www.youtube.com/watch?v=uCrFivSCzNo'

# --- LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- TIME ---
now = datetime.datetime.now()


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


def get_youtube_service(api_key):
    return googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)


def get_latest_live_link(youtube, channel_id):
    for attempt in range(1, MAX_API_RETRIES + 1):
        try:
            request = youtube.search().list(
                part="id",
                channelId=channel_id,
                eventType="live",
                type="video",
                order="date",
                maxResults=1
            )
            response = request.execute()
            items = response.get('items')
            if items:
                video_id = items[0]['id']['videoId']
                return f"https://www.youtube.com/watch?v={video_id}"
            return None
        except Exception as e:
            logger.warning(f"API error on attempt {attempt} for {channel_id}: {e}")
            if attempt < MAX_API_RETRIES:
                time.sleep(RETRY_WAIT_SECONDS)
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



# Your channel metadata dictionary
channel_metadata = {
    # --- News Channels (Bangladesh) ---
    'UCWVqdPTigfQ-cSNwG7O9MeA': {  # EKHON TV
        'channel_number': 103,
        'group_title': 'News',
        'channel_name': 'EKHON TV',
        'channel_logo': 'https://yt3.googleusercontent.com/66cO7vPXs2Xssf6fq2cn90oDsJ3OFMThb57qfRkRMjaSqg3ouTG6m9WQKZFg6GmUS5G8wkPu7ik=s72-c-k-c0x00ffffff-no-rj',
    },
    'UCHLqIOMPk20w-6cFgkA90jw': {  # Channel 24
        'channel_number': 104,
        'group_title': 'News',
        'channel_name': 'Channel 24',
        'channel_logo': 'https://yt3.googleusercontent.com/8Q8MCd6ypr2Hzbp60VE_stJPl063kQYfeTxdIQkAXRfhdzxByLl0sJYHsk43uTM4W_cOzwcbPQ=s160-c-k-c0x00ffffff-no-rj',
    },
}


def main(api_key):
    youtube = get_youtube_service(api_key)
    output_data = []

    for channel_id, metadata in channel_metadata.items():
        channel_number = metadata.get('channel_number', '0')
        group_title = metadata.get('group_title', 'Others')
        channel_name = metadata.get('channel_name', 'Unknown')
        channel_logo = metadata.get('channel_logo', '')

        logger.info(f"Checking channel: {channel_name}")

        live_link = link
        if not live_link:
            logger.warning(f"Skipping {channel_name}: no live video found")
            continue

        m3u8_link = get_stream_url(live_link)
        if not m3u8_link:
            logger.warning(f"Skipping {channel_name}: no stream link found")
            continue

        formatted_info = format_live_link(
            channel_name, channel_logo, m3u8_link, channel_number, group_title
        )
        output_data.append(formatted_info)

    if output_data:
        save_m3u_file(output_data)
    else:
        logger.warning("No live streams found for any channels.")


if __name__ == "__main__":
    if 0 <= now.hour < 3:
        api_key = "AIzaSyBX_LlRNOxBzT5eAWzRiCWNjFS000uqsBQ"
    elif 3 <= now.hour < 6:
        api_key = "AIzaSyCgJaZsz-tsyAaIJRLc5NRYQyC-vnTCwAI"
    elif 6 <= now.hour < 9:
        api_key = "AIzaSyDJ5CkvzxGaJL99SdGqENypUVcm0nFaKEQ"
    elif 9 <= now.hour < 12:
        api_key = "AIzaSyDO8JaYU6HbD8PdypJhG-EkFi4nojq0hrE"
    elif 12 <= now.hour < 15:
        api_key = "AIzaSyCxklIr0fXmsjmiwzoDfBBT0DxtMpWQS68"
    elif 15 <= now.hour < 18:
        api_key = "AIzaSyDm19wlhqTIThL6FTfMRKSgs0jIq689nQU"
    elif 18 <= now.hour < 21:
        api_key = "AIzaSyC4KNVzGqbfgikRGM63R3LCt4CRwAtRdYU"
    else:
        api_key = "AIzaSyCzk9DwsciObuhF3sNUbX1BdBBt0sNRwOw"

    main(api_key)
