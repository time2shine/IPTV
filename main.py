import random
import googleapiclient.discovery
import datetime
import yt_dlp
import os
import time
import logging
from datetime import datetime, timedelta

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
    'UCtqvtAVmad5zywaziN6CbfA': {  # Ekattor TV
        'channel_number': 105,
        'group_title': 'News',
        'channel_name': 'Ekattor TV',
        'channel_logo': 'https://yt3.googleusercontent.com/M8Rqad6_uN86mMSvd9KGkE5G2mrVAgvfTV-VCsQb6jhfF5hEbcQCEJiInih4wb2fMQ_RG7Ku=s160-c-k-c0x00ffffff-no-rj',
    },
    'UCATUkaOHwO9EP_W87zCiPbA': {  # Independent Television
        'channel_number': 106,
        'group_title': 'News',
        'channel_name': 'Independent Television',
        'channel_logo': 'https://yt3.googleusercontent.com/JO8MicN497ze8WVXcu-wmA2WAMqhO8UIQhslV3VhiRu1kaQU3r9nOB4IVkmUt0ALC23DVSSp=s160-c-k-c0x00ffffff-no-rj',
    },
    'UCUvXoiDEKI8VZJrr58g4VAw': {  # DBC NEWS
        'channel_number': 107,
        'group_title': 'News',
        'channel_name': 'DBC News',
        'channel_logo': 'https://yt3.googleusercontent.com/ytc/AIdro_mcjICfjqYwOn4eljNmtsZLBpOmW0t0JlzJUhXSslAkBVo=s160-c-k-c0x00ffffff-no-rj',
    },
    'UC2P5Fd5g41Gtdqf0Uzh8Qaw': {  # Rtv News
        'channel_number': 108,
        'group_title': 'News',
        'channel_name': 'Rtv News',
        'channel_logo': 'https://yt3.googleusercontent.com/Jw5N_GsIqsDis5cvYkAlJZFU2Z3m_6q6GaTdmUK0hJ4bsadl4He51sFu1LoCGKmf3QiTG-9P5G4=s160-c-k-c0x00ffffff-no-rj',
    },
    'UC0V3IJCnr6ZNjB9t_GLhFFA': {  # NTV Live
        'channel_number': 109,
        'group_title': 'News',
        'channel_name': 'NTV Live',
        'channel_logo': 'https://yt3.googleusercontent.com/NgVaE3RsOhC9cIV_6kTp0h2ikrHIFG8QPJF5IrRg_nPiQbQeG-dzK5SHLmi_MDEyVNj73aeSHg=s160-c-k-c0x00ffffff-no-rj',
    },
    'UC8NcXMG3A3f2aFQyGTpSNww': {  # Channel i News
        'channel_number': 110,
        'group_title': 'News',
        'channel_name': 'Channel i News',
        'channel_logo': 'https://yt3.googleusercontent.com/Yv5b1h00Dj_JkJsCD8IEuodFSRq3hFiFi0AQc-W5JrJkrAyX98lxWGUUhjqZzOA-NU5LwUzU=s160-c-k-c0x00ffffff-no-rj',
    },
    'UCb2O5Uo4a26CdTE7_2QA-jA': {  # NEWS24 Television
        'channel_number': 111,
        'group_title': 'News',
        'channel_name': 'NEWS24 Television',
        'channel_logo': 'https://yt3.googleusercontent.com/bn7BHmnbqkIJMoQWzUk3K5Wzzt_mVgVdjQ5XV8PWdQS18_w4ZVZOSFwe_ZIKaO3KitQPVuQczA=s160-c-k-c0x00ffffff-no-rj',
    },
    'UCRt2klyaxgx89vPF8cFMfnQ': {  # Kalbela News
        'channel_number': 113,
        'group_title': 'News',
        'channel_name': 'Kalbela News',
        'channel_logo': 'https://yt3.googleusercontent.com/DdtUl06VkqvZvr9aDFP6iX-qxWxV5Aqlk1d4mTUdD1E34wwX333DKo56iJiSJ3hojEeeW_kVzEc=s160-c-k-c0x00ffffff-no-rj',
    },
    'UC9Rgo0CrNyd7OWliLekqqGA': {  # ATN News
        'channel_number': 114,
        'group_title': 'News',
        'channel_name': 'ATN News',
        'channel_logo': 'https://yt3.googleusercontent.com/ceDID2koAfvhvykNroiBjW4SkTrkGVrjFk1EkWRz8SZdhV_dFsCtuJ3w9l0D-y06VgHjvB-WqA=s160-c-k-c0x00ffffff-no-rj',
    },

    # --- News Channels (India) ---
    'UCbf0XHULBkTfv2hBjaaDw9Q': {  # News18 Bangla
        'channel_number': 121,
        'group_title': 'News',
        'channel_name': 'News18 Bangla',
        'channel_logo': 'https://yt3.googleusercontent.com/0pVAsTdgTX-iREI9xZUMsYbqjpclujOiC7mocZIvLlWYVmhKRP131kzwVzM-i63lQz2YMMXo=s160-c-k-c0x00ffffff-no-rj',
    },
    'UCdF5Q5QVbYstYrTfpgUl0ZA': {  # Zee 24 Ghanta
        'channel_number': 122,
        'group_title': 'News',
        'channel_name': 'Zee 24 Ghanta',
        'channel_logo': 'https://yt3.googleusercontent.com/ou3JhDnH8ChdzRKooH5hGjTRGKpr9dGhi7lv7QW2zgmrnme0HbPKc8qI3yu8ZdI6NZna-CdJFw=s160-c-k-c0x00ffffff-no-rj',
    },
    'UCHCR4UFsGwd_VcDa0-a4haw': {  # TV9 Bangla
        'channel_number': 123,
        'group_title': 'News',
        'channel_name': 'TV9 Bangla',
        'channel_logo': 'https://yt3.googleusercontent.com/d8QNkJ7Jby9hVSTm67-E4nfbI-7CTgP262NPVGfYpoTZaxLw7uAOPxs5dJtARjEFQijsRsuiFQ=s160-c-k-c0x00ffffff-no-rj',
    },
    'UCajVjEHDoVn_AHsunUZz_EQ': {  # Republic Bangla
        'channel_number': 124,
        'group_title': 'News',
        'channel_name': 'Republic Bangla',
        'channel_logo': 'https://yt3.googleusercontent.com/ytc/AIdro_nvgVv3ZKeS6nLI_ZGZw-pZpt88bQpFPZNbUOADI3Bvz9k=s160-c-k-c0x00ffffff-no-rj',
    },
    'UCv3rFzn-GHGtqzXiaq3sWNg': {  # ABP ANANDA
        'channel_number': 125,
        'group_title': 'News',
        'channel_name': 'ABP Ananda',
        'channel_logo': 'https://yt3.googleusercontent.com/ytc/AIdro_kLTXHZwzmSJJh3W6bm_134dfLEh_vjEpjL8QE8Yn4l6cs=s160-c-k-c0x00ffffff-no-rj',
    },

    # --- International News Channels ---
    'UCNye-wNBqNL5ZzHSJj3l8Bg': {  # Al Jazeera English
        'channel_number': 150,
        'group_title': 'International News',
        'channel_name': 'Al Jazeera English',
        'channel_logo': '',
    },
    'UC7fWeaHhqgM4Ry-RMpM2YYw': {  # TRT World
        'channel_number': 151,
        'group_title': 'International News',
        'channel_name': 'TRT World',
        'channel_logo': '',
    },
    'UCknLrEdhRCp1aegoMqRaCZg': {  # DW News
        'channel_number': 152,
        'group_title': 'International News',
        'channel_name': 'DW News',
        'channel_logo': '',
    },
    'UCUMZ7gohGI9HcU9VNsr2FJQ': {  # Bloomberg Originals
        'channel_number': 153,
        'group_title': 'International News',
        'channel_name': 'Bloomberg Originals',
        'channel_logo': '',
    },

    # --- Entertainment Channels ---
    'UC9nuJbEL-AMJLLqc2-ej8xQ': {  # Bongo
        'channel_number': 201,
        'group_title': 'Entertainment',
        'channel_name': 'Bongo',
        'channel_logo': '',
    },
    'UCvoC1eVphUAe7a0m-uuoPbg': {  # Bongo Movies
        'channel_number': 202,
        'group_title': 'Entertainment',
        'channel_name': 'Bongo Movies',
        'channel_logo': '',
    },
    'UCsr6QVeLlkitleHoS0T4IxQ': {  # Banglavision DRAMA
        'channel_number': 203,
        'group_title': 'Entertainment',
        'channel_name': 'Banglavision DRAMA',
        'channel_logo': '',
    },
    'UCEwIUtFBhaI2L2PuKv0KL2g': {  # Classic Mr Bean
        'channel_number': 204,
        'group_title': 'Entertainment',
        'channel_name': 'Classic Mr Bean',
        'channel_logo': '',
    },
    'UCkAGrHCLFmlK3H2kd6isipg': {  # Mr Bean
        'channel_number': 205,
        'group_title': 'Entertainment',
        'channel_name': 'Mr Bean',
        'channel_logo': '',
    },
    'UC5V8MdQsT_gLlw8rTyf7jVQ': {  # ClipZone: Comedy Callbacks
        'channel_number': 206,
        'group_title': 'Entertainment',
        'channel_name': 'ClipZone: Comedy Callbacks',
        'channel_logo': '',
    },
    'UCQt7Z-GE0wF8AzFNvQEqjvg': {  # ClipZone: Heroes & Villains
        'channel_number': 207,
        'group_title': 'Entertainment',
        'channel_name': 'ClipZone: Heroes & Villains',
        'channel_logo': '',
    },
    'UCw7SNYrYei7F5ttQO3o-rpA': {  # Disney Channel
        'channel_number': 208,
        'group_title': 'Entertainment',
        'channel_name': 'Disney Channel',
        'channel_logo': '',
    },

    # --- Religious Channels ---

    # --- Wildlife and Educational Channels ---
    'UCDPk9MG2RexnOMGTD-YnSnA': {  # Nat Geo Animals
        'channel_number': 301,
        'group_title': 'Educational',
        'channel_name': 'Nat Geo Animals',
        'channel_logo': '',
    },
    'UCpVm7bg6pXKo1Pr6k5kxG9A': {  # National Geographic
        'channel_number': 302,
        'group_title': 'Educational',
        'channel_name': 'National Geographic',
        'channel_logo': '',
    },

    # --- Kids Channels ---
    'UCu7IDy0y-ZA0qaG51wrQY6w': {  # Curious George Official
        'channel_number': 403,
        'group_title': 'Kids',
        'channel_name': 'Curious George Official',
        'channel_logo': '',
    },
    'UCVzLLZkDuFGAE2BGdBuBNBg': {  # Bluey - Official Channel
        'channel_number': 404,
        'group_title': 'Kids',
        'channel_name': 'Bluey - Official Channel',
        'channel_logo': '',
    },
    'UCoBpC9J2EcbAMprw7YjC93A': {  # The Amazing World of Gumball
        'channel_number': 405,
        'group_title': 'Kids',
        'channel_name': 'The Amazing World of Gumball',
        'channel_logo': '',
    },
    'UCu59yAFE8fM0sVNTipR4edw': {  # Masha and The Bear
        'channel_number': 409,
        'group_title': 'Kids',
        'channel_name': 'Masha and The Bear',
        'channel_logo': '',
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

        live_link = get_latest_live_link(youtube, channel_id)
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
    # Convert UTC time to Bangladesh time
    utc_now = datetime.utcnow()
    now = utc_now + timedelta(hours=6)
    
    if 8 <= now.hour < 12:
        api_key = "AIzaSyCgJaZsz-tsyAaIJRLc5NRYQyC-vnTCwAI"
    elif 12 <= now.hour < 16:
        api_key = "AIzaSyBX_LlRNOxBzT5eAWzRiCWNjFS000uqsBQ"
    elif 16 <= now.hour < 20:
        api_key = "AIzaSyDm19wlhqTIThL6FTfMRKSgs0jIq689nQU"
    elif 20 <= now.hour < 24:
        api_key = "AIzaSyC4KNVzGqbfgikRGM63R3LCt4CRwAtRdYU"
    else:
        # Skip between 0–8 AM
        api_key = None

    main(api_key)





