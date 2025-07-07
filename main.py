import random
import googleapiclient.discovery
import datetime
import yt_dlp
import os

# Get the current time
now = datetime.datetime.now()

# Define the path to the cookies.txt file
cookies_file_path = 'cookies.txt'

# No stream URL found message
no_stream = 'https://raw.githubusercontent.com/time2shine/IPTV/refs/heads/master/no_stream.mp4'

# Check if the file exists
if not os.path.exists(cookies_file_path):
    raise FileNotFoundError(f"The file {cookies_file_path} does not exist")

def get_user_agent():
    """Return a recent Chrome user agent with random build numbers."""
    versions = [
        (122, 6267, 70),   # Chrome 122
        (121, 6167, 131),  # Chrome 121
        (120, 6099, 109),  # Chrome 120
    ]
    major, build, patch = random.choice(versions)
    return (
        f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        f"AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{major}.0.{build}.{patch} Safari/537.36"
    )

def get_stream_url(url):
    """Retrieve YouTube stream URL using yt-dlp with bot mitigation."""
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
        print(f"Error retrieving stream for URL {url}: {str(e)}")
        return None

def get_youtube_service(api_key):
    """Create and return the YouTube service object."""
    return googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)

def format_live_link(channel_name, channel_logo, m3u8_link, channel_number, group_title):
    """Format the live link information with channel number and group title."""
    formatted_info = (
        f'#EXTINF:-1 tvg-chno="{channel_number}" tvg-name="{channel_name}" '
        f'tvg-id="" group-title="{group_title}" tvg-logo="{channel_logo}" tvg-epg="", '
        f'{channel_name}\n{m3u8_link}'
    )
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
    "Fetch the channel information such as logo."
    try:
        request = youtube.channels().list(
            part="snippet",
            id=channel_id
        )
        response = request.execute()
        if 'items' in response and response['items']:
            snippet = response['items'][0]['snippet']
            thumbnails = snippet.get('thumbnails', {})
            channel_logo = thumbnails.get('default', {}).get('url', '')
            return channel_logo
        else:
            return None
    except Exception as e:
        print(f"Error fetching channel info for {channel_id}: {e}")
        return None

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
            live_link = f"https://www.youtube.com/watch?v={video_id}"
            return live_link
        else:
            return None, None  # No live video currently available
    except Exception as e:
        print(f"Error fetching latest live link for {channel_id}: {e}")
        return None, None

# Combined mapping of channel IDs to their metadata
channel_metadata = {
    # --- News Channels (Bangladesh) ---
    # 'UCxHoBXkY88Tb8z1Ssj6CWsQ': {  # Somoy News
    #     'channel_number': 101,
    #     'group_title': 'News',
    #     'channel_name': 'Somoy News',
    # },
    # 'UCN6sm8iHiPd0cnoUardDAnw': {  # Jamuna TV
    #     'channel_number': 102,
    #     'group_title': 'News',
    #     'channel_name': 'Jamuna TV',
    # },
    'UCWVqdPTigfQ-cSNwG7O9MeA': {  # EKHON TV
        'channel_number': 103,
        'group_title': 'News',
        'channel_name': 'EKHON TV',
    },
    'UCHLqIOMPk20w-6cFgkA90jw': {  # Channel 24
        'channel_number': 104,
        'group_title': 'News',
        'channel_name': 'Channel 24',
    },
    'UCtqvtAVmad5zywaziN6CbfA': {  # Ekattor TV
        'channel_number': 105,
        'group_title': 'News',
        'channel_name': 'Ekattor TV',
    },
    'UCATUkaOHwO9EP_W87zCiPbA': {  # Independent Television
        'channel_number': 106,
        'group_title': 'News',
        'channel_name': 'Independent Television',
    },
    'UCUvXoiDEKI8VZJrr58g4VAw': {  # DBC NEWS
        'channel_number': 107,
        'group_title': 'News',
        'channel_name': 'DBC News',
    },
    'UC2P5Fd5g41Gtdqf0Uzh8Qaw': {  # Rtv News
        'channel_number': 108,
        'group_title': 'News',
        'channel_name': 'Rtv News',
    },
    'UC0V3IJCnr6ZNjB9t_GLhFFA': {  # NTV Live
        'channel_number': 109,
        'group_title': 'News',
        'channel_name': 'NTV Live',
    },
    'UC8NcXMG3A3f2aFQyGTpSNww': {  # Channel i News
        'channel_number': 110,
        'group_title': 'News',
        'channel_name': 'Channel i News',
    },
    'UCb2O5Uo4a26CdTE7_2QA-jA': {  # NEWS24 Television
        'channel_number': 111,
        'group_title': 'News',
        'channel_name': 'NEWS24 Television',
    },
    'UCmCCTsDl-eCKw91shC7ZmMw': {  # Desh TV News
        'channel_number': 112,
        'group_title': 'News',
        'channel_name': 'Desh TV News',
    },
    'UCRt2klyaxgx89vPF8cFMfnQ': {  # Kalbela News
        'channel_number': 113,
        'group_title': 'News',
        'channel_name': 'Kalbela News',
    },

    # --- News Channels (India) ---
    'UCbf0XHULBkTfv2hBjaaDw9Q': {  # News18 Bangla
        'channel_number': 121,
        'group_title': 'News',
        'channel_name': 'News18 Bangla',
    },
    'UCdF5Q5QVbYstYrTfpgUl0ZA': {  # Zee 24 Ghanta
        'channel_number': 122,
        'group_title': 'News',
        'channel_name': 'Zee 24 Ghanta',
    },
    'UCHCR4UFsGwd_VcDa0-a4haw': {  # TV9 Bangla
        'channel_number': 123,
        'group_title': 'News',
        'channel_name': 'TV9 Bangla',
    },
    'UCajVjEHDoVn_AHsunUZz_EQ': {  # Republic Bangla
        'channel_number': 124,
        'group_title': 'News',
        'channel_name': 'Republic Bangla',
    },
    'UCv3rFzn-GHGtqzXiaq3sWNg': {  # ABP ANANDA
        'channel_number': 125,
        'group_title': 'News',
        'channel_name': 'ABP Ananda',
    },

    # --- International News Channels ---
    'UCNye-wNBqNL5ZzHSJj3l8Bg': {  # Al Jazeera English
        'channel_number': 150,
        'group_title': 'International News',
        'channel_name': 'Al Jazeera English',
    },
    'UC7fWeaHhqgM4Ry-RMpM2YYw': {  # TRT World
        'channel_number': 151,
        'group_title': 'International News',
        'channel_name': 'TRT World',
    },
    'UCknLrEdhRCp1aegoMqRaCZg': {  # DW News
        'channel_number': 152,
        'group_title': 'International News',
        'channel_name': 'DW News',
    },
    'UCUMZ7gohGI9HcU9VNsr2FJQ': {  # Bloomberg Originals
        'channel_number': 153,
        'group_title': 'International News',
        'channel_name': 'Bloomberg Originals',
    },

    # --- Entertainment Channels ---
    'UC9nuJbEL-AMJLLqc2-ej8xQ': {  # Bongo
        'channel_number': 201,
        'group_title': 'Entertainment',
        'channel_name': 'Bongo',
    },
    'UCvoC1eVphUAe7a0m-uuoPbg': {  # Bongo Movies
        'channel_number': 202,
        'group_title': 'Entertainment',
        'channel_name': 'Bongo Movies',
    },
    'UCsr6QVeLlkitleHoS0T4IxQ': {  # Banglavision DRAMA
        'channel_number': 203,
        'group_title': 'Entertainment',
        'channel_name': 'Banglavision DRAMA',
    },
    'UCEwIUtFBhaI2L2PuKv0KL2g': {  # Classic Mr Bean
        'channel_number': 204,
        'group_title': 'Entertainment',
        'channel_name': 'Classic Mr Bean',
    },
    'UCkAGrHCLFmlK3H2kd6isipg': {  # Mr Bean
        'channel_number': 205,
        'group_title': 'Entertainment',
        'channel_name': 'Mr Bean',
    },
    'UC5V8MdQsT_gLlw8rTyf7jVQ': {  # ClipZone: Comedy Callbacks
        'channel_number': 206,
        'group_title': 'Entertainment',
        'channel_name': 'ClipZone: Comedy Callbacks',
    },
    'UCQt7Z-GE0wF8AzFNvQEqjvg': {  # ClipZone: Heroes & Villains
        'channel_number': 207,
        'group_title': 'Entertainment',
        'channel_name': 'ClipZone: Heroes & Villains',
    },
    'UCw7SNYrYei7F5ttQO3o-rpA': {  # Disney Channel
        'channel_number': 208,
        'group_title': 'Entertainment',
        'channel_name': 'Disney Channel',
    },

    # --- Religious Channels ---
    'UC0AMtPKwU61uDs--L04_kfQ': {  # Madani Channel Bangla Live
        'channel_number': 251,
        'group_title': 'Religious',
        'channel_name': 'Madani Channel Bangla Live',
    },

    # --- Wildlife and Educational Channels ---
    'UCDPk9MG2RexnOMGTD-YnSnA': {  # Nat Geo Animals
        'channel_number': 301,
        'group_title': 'Educational',
        'channel_name': 'Nat Geo Animals',
    },
    'UCpVm7bg6pXKo1Pr6k5kxG9A': {  # National Geographic
        'channel_number': 302,
        'group_title': 'Educational',
        'channel_name': 'National Geographic',
    },

    # --- Kids Channels ---
    'UCmst562fALOY2cKb4IFgqEg': {  # Boomerang UK
        'channel_number': 401,
        'group_title': 'Kids',
        'channel_name': 'Boomerang UK',
    },
    'UCiBigY9XM-HaOxUc269ympg': {  # Green Gold TV - Official Channel
        'channel_number': 402,
        'group_title': 'Kids',
        'channel_name': 'Green Gold TV',
    },
    'UCu7IDy0y-ZA0qaG51wrQY6w': {  # Curious George Official
        'channel_number': 403,
        'group_title': 'Kids',
        'channel_name': 'Curious George Official',
    },
    'UCVzLLZkDuFGAE2BGdBuBNBg': {  # Bluey - Official Channel
        'channel_number': 404,
        'group_title': 'Kids',
        'channel_name': 'Bluey - Official Channel',
    },
    'UCoBpC9J2EcbAMprw7YjC93A': {  # The Amazing World of Gumball
        'channel_number': 405,
        'group_title': 'Kids',
        'channel_name': 'The Amazing World of Gumball',
    },
    'UCktaw9L-f65LzUUdjmCFkbQ': {  # Disney XD
        'channel_number': 406,
        'group_title': 'Kids',
        'channel_name': 'Disney XD',
    },
    'UCNcdbMyA59zE-Vk668bKWOg': {  # Disney Jr.
        'channel_number': 407,
        'group_title': 'Kids',
        'channel_name': 'Disney Jr.',
    },
    'UCWE_ywN-0aeFdGVpLQ6mIwg': {  # WildBrain Bananas
        'channel_number': 408,
        'group_title': 'Kids',
        'channel_name': 'WildBrain Bananas',
    },
    'UCu59yAFE8fM0sVNTipR4edw': {  # Masha and The Bear
        'channel_number': 409,
        'group_title': 'Kids',
        'channel_name': 'Masha and The Bear',
    },
}

def main(api_key):
    """Main function to fetch and format live video links for multiple channels."""
    youtube = get_youtube_service(api_key)
    output_data = []

    for channel_id, metadata in channel_metadata.items():
        # Retrieve channel metadata
        channel_number = metadata.get('channel_number', '0')
        group_title = metadata.get('group_title', 'Others')
        channel_name = metadata.get('channel_name', 'Unknown')

        # Fetch channel info (logo)
        channel_logo = get_channel_info(youtube, channel_id)

        # Fetch the latest live link
        live_link = get_latest_live_link(youtube, channel_id)
        if live_link:
            m3u8_link = get_stream_url(live_link)
            if m3u8_link:
                formatted_info = format_live_link(
                    channel_name, channel_logo, m3u8_link, channel_number, group_title
                )
            else:
                # Include the channel with an empty URL if m3u8 link isn't found
                formatted_info = format_live_link(
                    channel_name, channel_logo, 'https://raw.githubusercontent.com/time2shine/IPTV/refs/heads/master/no_stream.mp4', channel_number, group_title
                )
        else:
            # Include the channel with an empty URL if no live video is available
            formatted_info = format_live_link(
                channel_name, channel_logo, 'https://raw.githubusercontent.com/time2shine/IPTV/refs/heads/master/no_stream.mp4', channel_number, group_title
            )

        output_data.append(formatted_info)

    if output_data:
        save_m3u_file(output_data)
    else:
        print("No videos available for any of the channels.")

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

    main(api_key)
