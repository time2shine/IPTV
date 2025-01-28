import random
import googleapiclient.discovery
import datetime
import yt_dlp
import os

# Get the current time
now = datetime.datetime.now()


# Define the path to the cookies.txt file
cookies_file_path = 'cookies.txt'

# Check if the file exists
if not os.path.exists(cookies_file_path):
    raise FileNotFoundError(f"The file {cookies_file_path} does not exist")

API_KEY_1 = os.getenv('YOUTUBE_API_1')
API_KEY_2 = os.getenv('YOUTUBE_API_2')
API_KEY_3 = os.getenv('YOUTUBE_API_3')
API_KEY_4 = os.getenv('YOUTUBE_API_4')
API_KEY_5 = os.getenv('YOUTUBE_API_5')
API_KEY_6 = os.getenv('YOUTUBE_API_6')
API_KEY_7 = os.getenv('YOUTUBE_API_7')
API_KEY_8 = os.getenv('YOUTUBE_API_8')
print(API_KEY_1)

        
def get_user_agent():
    """Return a recent Chrome user agent with random build numbers"""
    versions = [
        (122, 6267, 70),  # Chrome 122
        (121, 6167, 131), # Chrome 121
        (120, 6099, 109), # Chrome 120
    ]
    major, build, patch = random.choice(versions)
    return f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{major}.0.{build}.{patch} Safari/537.36"


def get_stream_url(url):
    """Retrieve YouTube stream URL using yt-dlp with bot mitigation"""
    ydl_opts = {
        'format': 'best',
        'cookiefile': 'cookies.txt',
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
        print(f"Error retrieving stream: {str(e)}")
        return None

def get_youtube_service(api_key):
    """Create and return the YouTube service object."""
    return googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)

def format_live_link(channel_name, channel_logo, m3u8_link):
    """Format the live link information as per the required format."""
    formatted_info = f'#EXTINF:-1 tvg-name="{channel_name}" tvg-id="" group-title="News" tvg-logo="{channel_logo}" tvg-epg="", {channel_name}\n{m3u8_link}'
    return formatted_info


def save_m3u_file(output_data, filename="YT_playlist.m3u"):
    """Save the formatted live link information to an M3U file."""
    with open(filename, "w", encoding="utf-8") as file:
        file.write("#EXTM3U\n")
        # Add the update time as a comment
        file.write(f"# Updated on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        for data in output_data:
            file.write(data + "\n")
    print(f"M3U file saved as {filename}")


def get_channel_info(youtube, channel_id):
    """Fetch the channel information such as name and logo."""
    try:
        request = youtube.channels().list(
            part="snippet",
            id=channel_id
        )
        response = request.execute()
        if 'items' in response and response['items']:
            channel_name = response['items'][0]['snippet']['title']
            channel_logo = response['items'][0]['snippet']['thumbnails']['default']['url']
            return channel_name, channel_logo
        else:
            return None, None
    except Exception as e:
        print(f"Error fetching channel info for {channel_id}: {e}")
        return None, None

def get_latest_live_link(youtube, channel_id):
    """Fetch the latest live video link from the specified YouTube channel."""
    try:
        request = youtube.search().list(
            part="snippet",
            channelId=channel_id,
            eventType="live",
            type="video",
            order="date",
            maxResults=1
        )
        response = request.execute()
        if 'items' in response and response['items']:
            video_id = response['items'][0]['id']['videoId']
            video_title = response['items'][0]['snippet']['title']
            live_link = f"https://www.youtube.com/watch?v={video_id}"
            return video_title, live_link
        else:
            return None, "No live video currently available."
    except Exception as e:
        print(f"Error fetching latest live link for {channel_id}: {e}")
        return None, "Error fetching live link."


def main(api_key, channel_ids):
    """Main function to fetch and print live video links for multiple channels."""
    youtube = get_youtube_service(api_key)
    output_data = []

    for channel_id in channel_ids:
        channel_name, channel_logo = get_channel_info(youtube, channel_id)
        video_title, live_link = get_latest_live_link(youtube, channel_id)
        if video_title:
            m3u8_link = get_stream_url(live_link)
            formatted_info = format_live_link(channel_name, channel_logo, m3u8_link)
            output_data.append(formatted_info)
        else:
            print(f"Channel ID: {channel_id} - {live_link}")

    if output_data:
        save_m3u_file(output_data)
    else:
        print("No live videos available for any of the channels.")

if __name__ == "__main__":
    # Use the provided API key based on the current hour
    if now.hour >= 0 and now.hour < 3:
        api_key = "AIzaSyBX_LlRNOxBzT5eAWzRiCWNjFS000uqsBQ"  # allmybooks
    elif now.hour >= 3 and now.hour < 6:
        api_key = "AIzaSyCgJaZsz-tsyAaIJRLc5NRYQyC-vnTCwAI"  # rokonmagura
    elif now.hour >= 6 and now.hour < 9:
        api_key = "AIzaSyA9AXuZ-x5tkUmaT5VmfWH4KFNc57NTEhA"  # amirokon1991
    elif now.hour >= 9 and now.hour < 12:
        api_key = "AIzaSyAd-mn7joueTcJoQWL3nBW2sHzsoDJtAfM"  # deshirambo5
    elif now.hour >= 12 and now.hour < 15:
        api_key = "AIzaSyAXq5VQlni9K7AKk1w2iU-EOCenzL8l4rA"  # 4kshort2021
    elif now.hour >= 15 and now.hour < 18:
        api_key = "AIzaSyAZuIBq2gMLU9josSi3zTW9Fnp_djzmlLM"  # deshirambo
    elif now.hour >= 18 and now.hour < 21:
        api_key = "AIzaSyBBYUHVcfHZ56lgsZdNB5W_WAUEgyh2hfQ"  # onlinesoft427
    elif now.hour >= 21 and now.hour < 24:
        api_key = "AIzaSyC-AStAvJQP0579qUvljAE4mV2X9eRBroo"  # deshirambo10

    # List of channel IDs to check
    channel_ids = [
        'UCxHoBXkY88Tb8z1Ssj6CWsQ', # Somoy News
        # 'UCN6sm8iHiPd0cnoUardDAnw', # Jamuna TV
        # 'UCWVqdPTigfQ-cSNwG7O9MeA', # EKHON TV
        # 'UCHLqIOMPk20w-6cFgkA90jw', # Channel 24
        # 'UCtqvtAVmad5zywaziN6CbfA', # Ekattor TV
        # 'UCATUkaOHwO9EP_W87zCiPbA', # Independent Television
        # 'UCUvXoiDEKI8VZJrr58g4VAw', # DBC NEWS
        # 'UC2P5Fd5g41Gtdqf0Uzh8Qaw', # Rtv News
        # 'UC0V3IJCnr6ZNjB9t_GLhFFA', # NTV Live
        # 'UC8NcXMG3A3f2aFQyGTpSNww', # Channel i News
        # 'UCb2O5Uo4a26CdTE7_2QA-jA', # NEWS24 Television
        # 'UCmCCTsDl-eCKw91shC7ZmMw', # Desh TV News
        # 'UCRt2klyaxgx89vPF8cFMfnQ', # Kalbela News
        # 'UCbf0XHULBkTfv2hBjaaDw9Q', # News18 Bangla
        # 'UCdF5Q5QVbYstYrTfpgUl0ZA', # Zee 24 Ghanta
        # 'UCHCR4UFsGwd_VcDa0-a4haw', # TV9 Bangla
        # 'UCajVjEHDoVn_AHsunUZz_EQ', # Republic Bangla
        # 'UCv3rFzn-GHGtqzXiaq3sWNg', # ABP ANANDA
        # 'UCNye-wNBqNL5ZzHSJj3l8Bg', # Al Jazeera English
        # 'UC7fWeaHhqgM4Ry-RMpM2YYw', # TRT World
        #
        # 'UC9nuJbEL-AMJLLqc2-ej8xQ', # Bongo
        # 'UCvoC1eVphUAe7a0m-uuoPbg', # Bongo Movies
        # 'UCsr6QVeLlkitleHoS0T4IxQ', # Banglavision DRAMA
        # 'UC0AMtPKwU61uDs--L04_kfQ', # Madani Channel Bangla Live
        # 'UCEwIUtFBhaI2L2PuKv0KL2g', # Classic Mr Bean
        # 'UCDPk9MG2RexnOMGTD-YnSnA', # Nat Geo Animals
        #
        # 'UCmst562fALOY2cKb4IFgqEg', # Boomerang UK
        # 'UCiBigY9XM-HaOxUc269ympg', # Green Gold TV - Official Channel
        # 'UCu7IDy0y-ZA0qaG51wrQY6w', # Curious George Official
        # 'UCVzLLZkDuFGAE2BGdBuBNBg', # Bluey - Official Channel
        # 'UCoBpC9J2EcbAMprw7YjC93A', # The Amazing World of Gumball
        # 'UCktaw9L-f65LzUUdjmCFkbQ', # Disney XD

    ]

    main(api_key, channel_ids)
