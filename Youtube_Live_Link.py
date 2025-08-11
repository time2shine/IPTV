import yt_dlp
import requests
import random
import time
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 30+ User-Agent strings (various browsers, OS, devices)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:117.0) Gecko/20100101 Firefox/117.0",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPad; CPU OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.5845.188 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_6_8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:117.0) Gecko/20100101 Firefox/117.0",
    "Mozilla/5.0 (Windows NT 10.0; WOW64; Trident/7.0; rv:11.0) like Gecko",
    "Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 11_7_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.6 Safari/605.1.15",
    "Mozilla/5.0 (Linux; Android 11; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.5845.188 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.5845.188 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Fedora; Linux x86_64; rv:117.0) Gecko/20100101 Firefox/117.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 10; SM-A107F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.5845.188 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.5845.188 Safari/537.36",
    "Mozilla/5.0 (iPad; CPU OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 9; SM-G960U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.5845.188 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/117.0.2045.60",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:116.0) Gecko/20100101 Firefox/116.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 8.1.0; Nexus 5X Build/OPM6.171019.030) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.5845.188 Mobile Safari/537.36",
]

ACCEPT_LANGUAGES = [
    'en-US,en;q=0.9',
    'en-GB,en;q=0.8',
    'en-AU,en;q=0.7',
    'fr-FR,fr;q=0.9,en;q=0.8',
    'de-DE,de;q=0.9,en;q=0.8',
    'es-ES,es;q=0.9,en;q=0.8',
    'it-IT,it;q=0.9,en;q=0.8',
    'nl-NL,nl;q=0.9,en;q=0.8',
    'pt-BR,pt;q=0.9,en;q=0.8',
    'ru-RU,ru;q=0.9,en;q=0.8',
]


# Your channels dict example:
channels = {
    # --- News Channels (Bangladesh) ---
    'UCxHoBXkY88Tb8z1Ssj6CWsQ': {  # Somoy News
        'channel_number': 101,
        'group_title': 'News',
        'channel_name': 'Somoy News',
        'channel_logo': 'https://yt3.googleusercontent.com/7F-3_9yjPiMJzBAuD7niglcJmFyXCrFGSEugcEroFrIkxudmhiZ9i-Q_pW4Zrn2IiCLN5dQX8A=s160-c-k-c0x00ffffff-no-rj',
    },
    'UCN6sm8iHiPd0cnoUardDAnw': {  # Jamuna TV
        'channel_number': 102,
        'group_title': 'News',
        'channel_name': 'Jamuna TV',
        'channel_logo': 'https://yt3.ggpht.com/54prTx28YpPxSpk_PfJGuOfQgcZbNdvbfk0adGePrAvINO4Mo9_bw3j-J4seXn6hNGuMr1ck=s176-c-k-c0x00ffffff-no-rj-mo',
    },
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
    'UC0AMtPKwU61uDs--L04_kfQ': {  # Madani Channel Bangla Live
        'channel_number': 251,
        'group_title': 'Religious',
        'channel_name': 'Madani Channel Bangla Live',
        'channel_logo': '',
    },

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
    'UCmst562fALOY2cKb4IFgqEg': {  # Boomerang UK
        'channel_number': 401,
        'group_title': 'Kids',
        'channel_name': 'Boomerang UK',
        'channel_logo': '',
    },
    'UCiBigY9XM-HaOxUc269ympg': {  # Green Gold TV - Official Channel
        'channel_number': 402,
        'group_title': 'Kids',
        'channel_name': 'Green Gold TV',
        'channel_logo': '',
    },
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
    'UCktaw9L-f65LzUUdjmCFkbQ': {  # Disney XD
        'channel_number': 406,
        'group_title': 'Kids',
        'channel_name': 'Disney XD',
        'channel_logo': '',
    },
    'UCNcdbMyA59zE-Vk668bKWOg': {  # Disney Jr.
        'channel_number': 407,
        'group_title': 'Kids',
        'channel_name': 'Disney Jr.',
        'channel_logo': '',
    },
    'UCWE_ywN-0aeFdGVpLQ6mIwg': {  # WildBrain Bananas
        'channel_number': 408,
        'group_title': 'Kids',
        'channel_name': 'WildBrain Bananas',
        'channel_logo': '',
    },
    'UCu59yAFE8fM0sVNTipR4edw': {  # Masha and The Bear
        'channel_number': 409,
        'group_title': 'Kids',
        'channel_name': 'Masha and The Bear',
        'channel_logo': '',
    },
}

def get_random_headers():
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept-Language': random.choice(ACCEPT_LANGUAGES),
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
    }

def get_youtube_live_m3u8(channel_id, cookies_file='cookies.txt'):
    headers = get_random_headers()
    channel_live_url = f'https://www.youtube.com/channel/{channel_id}/live'
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'forceurl': True,
        'format': 'best[ext=m3u8_native]/best',
        'cookiefile': cookies_file,
        'http_headers': headers,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(channel_live_url, download=False)
            formats = info.get('formats', [])
            for f in formats:
                if f.get('ext') == 'm3u8_native':
                    return f.get('url')
            return info.get('url', None)
        except Exception as e:
            logging.warning(f"Error fetching live stream for {channel_id}: {e}")
            return None

def check_m3u8_link(url, retries=2):
    for attempt in range(retries):
        try:
            resp = requests.head(url, timeout=5, allow_redirects=True)
            if resp.status_code == 200:
                return True
            else:
                logging.debug(f"HEAD request status {resp.status_code} for URL: {url}")
        except requests.RequestException as e:
            logging.debug(f"Attempt {attempt+1} failed checking URL {url}: {e}")
        time.sleep(random.uniform(0.5, 1.5))  # small delay before retry
    return False

def save_to_m3u(channels, filename='YT_playlist.m3u'):
    with open(filename, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U\n')
        for channel_id, info in channels.items():
            logging.info(f"Processing channel: {info['channel_name']} ({channel_id})")
            m3u8_url = get_youtube_live_m3u8(channel_id)
            if m3u8_url and check_m3u8_link(m3u8_url):
                line_info = (
                    f'#EXTINF:-1 '
                    f'tvg-chno="{info["channel_number"]}" '
                    f'tvg-name="{info["channel_name"]}" '
                    f'tvg-id="" '
                    f'group-title="{info["group_title"]}" '
                    f'tvg-logo="{info["channel_logo"]}" '
                    f'tvg-epg="", {info["channel_name"]}\n'
                )
                f.write(line_info)
                f.write(m3u8_url + '\n')
                logging.info(f"Added: {info['channel_name']}")
            else:
                logging.info(f"Skipped {info['channel_name']}: No valid live stream or URL not reachable.")
            # Random delay between 1 to 3 seconds between channel processing
            time.sleep(random.uniform(1, 3))

if __name__ == '__main__':
    save_to_m3u(channels)
