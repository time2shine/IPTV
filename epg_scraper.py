import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
import xml.etree.ElementTree as ET
from xml.dom import minidom
import logging
import html
from playwright.sync_api import sync_playwright
import pytz

# -----------------------
# Logging setup
# -----------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# -----------------------
# Scrapers for tvgenie sites
# -----------------------
def scrape_tvgenie(channel_id, display_name, logo_url, url):
    logging.info(f"Fetching TV schedule from tvgenie for {display_name} ...")
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        response.raise_for_status()
    except Exception as e:
        logging.error(f"Failed to fetch {url}: {e}")
        return {"id": channel_id, "name": display_name, "logo": logo_url, "programmes": []}

    soup = BeautifulSoup(response.text, "html.parser")
    programmes = []

    items = soup.select("div.requested-movies.card")
    logging.info(f"Found {len(items)} programmes for {display_name}")

    now = datetime.now()

    for item in items:
        title_tag = item.select_one("h6.desktop-only")
        time_tag = item.select_one(".detail-container p")
        if not title_tag or not time_tag:
            continue

        title = title_tag.get_text(strip=True)
        time_text = time_tag.get_text(strip=True)

        try:
            time_part, day_part = [x.strip() for x in time_text.split(",")]
            show_time = datetime.strptime(time_part, "%I:%M %p")
            date_obj = now if "Today" in day_part else now + timedelta(days=1) if "Tomorrow" in day_part else now

            start = date_obj.replace(hour=show_time.hour, minute=show_time.minute, second=0, microsecond=0) + timedelta(minutes=30)
            # Skip past shows
            if start < now:
                continue
            stop = start + timedelta(minutes=30)
            programmes.append({"title": title, "start": start, "stop": stop})
        except Exception as e:
            logging.warning(f"Failed to parse time '{time_text}' for {title}: {e}")

    return {"id": channel_id, "name": display_name, "logo": logo_url, "programmes": programmes}


# -----------------------
# Scrapers for tvwish sites
# -----------------------
def scrape_tvwish(channel_id, display_name, logo_url, url, browser=None):
    """
    Scrape TVWish schedule (Indian time) and convert to Bangladesh time.
    """
    logging.info(f"Fetching TV schedule from TVWish for {display_name} ...")
    programmes = []
    now = datetime.now()

    # -------------------
    # Upcoming shows (JS rendered)
    # -------------------
    try:
        if browser is None:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                programmes += _fetch_upcoming_tvwish(browser, url, now)
                browser.close()
        else:
            programmes += _fetch_upcoming_tvwish(browser, url, now)
    except Exception as e:
        logging.error(f"Failed to fetch upcoming shows: {e}")

    # -------------------
    # Current show (HTML)
    # -------------------
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        current_show = soup.select_one("div.prog-list")
        if current_show and programmes:
            title_tag = current_show.select_one("h4")
            if title_tag:
                title = html.escape(title_tag.get_text(strip=True))
                first_upcoming_start = programmes[0]["start"]
                start = max(now, first_upcoming_start - timedelta(minutes=30))
                stop = first_upcoming_start - timedelta(minutes=1)
                if stop <= start:
                    stop = start + timedelta(minutes=1)
                programmes.insert(0, {"title": title, "start": start, "stop": stop})
                logging.info(f"Current show: {title}")
    except Exception as e:
        logging.error(f"Failed to fetch current show: {e}")

    return {"id": channel_id, "name": display_name, "logo": logo_url, "programmes": programmes}


def _fetch_upcoming_tvwish(browser, url, now):
    """
    Fetch upcoming shows from TVWish and shift Indian time to Bangladesh time.
    """
    programmes = []
    page = browser.new_page()
    page.goto(url)
    page.wait_for_selector("#divUpcoming", timeout=10000)

    soup = BeautifulSoup(page.content(), "html.parser")
    upcoming_items = soup.select("#divUpcoming div.card.schedule-item")

    for item in upcoming_items:
        title_tag = item.select_one("h4.text-warning")
        if not title_tag:
            continue
        title = html.escape(title_tag.get_text(strip=True))

        time_tag = item.select_one("div.card-header h3")
        if time_tag:
            time_text = time_tag.get_text(strip=True).split(",")[-1].strip()
            try:
                show_time = datetime.strptime(time_text, "%I:%M %p")
                # Convert Indian time to Bangladesh time (+30 mins)
                start = now.replace(hour=show_time.hour, minute=show_time.minute, second=0, microsecond=0) + timedelta(minutes=30)
                if start < now:
                    start += timedelta(days=1)
            except:
                start = now
        else:
            start = now

        stop = start + timedelta(minutes=30)
        programmes.append({"title": title, "start": start, "stop": stop})

    logging.info(f"Fetched {len(upcoming_items)} upcoming shows via Playwright")
    page.close()
    return programmes

# -----------------------
# Scape from ontvtonight
# -----------------------

def scrape_ontvtonight(channel_id, display_name, logo_url, url):
    logging.info(f"Fetching schedule from OnTVTonight for {display_name} ...")
    programmes = []

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        table = soup.find("table", class_="table table-hover")
        if not table:
            logging.warning("No schedule table found.")
            return {"id": channel_id, "name": display_name, "logo": logo_url, "programmes": programmes}

        rows = table.find_all("tr")
        epg_list = []

        for row in rows:
            cols = row.find_all("td")
            if len(cols) >= 2:
                time_str = cols[0].get_text(strip=True)
                title_el = cols[1].find("a") or cols[1]
                title = html.escape(title_el.get_text(strip=True))

                try:
                    # Parse time (e.g. "10:30 am")
                    time_obj = datetime.strptime(time_str, "%I:%M %p")
                except ValueError:
                    continue

                # Apply today's date (local server date)
                now = datetime.now()
                time_obj = now.replace(hour=time_obj.hour, minute=time_obj.minute, second=0, microsecond=0)

                # Add 10 hours manually
                time_in_target = time_obj + timedelta(hours=10)

                epg_list.append({"title": title, "start": time_in_target})

        # Sort by start time
        epg_list.sort(key=lambda x: x["start"])

        # Add stop times
        for i in range(len(epg_list)):
            start = epg_list[i]["start"]
            stop = epg_list[i + 1]["start"] if i + 1 < len(epg_list) else start + timedelta(minutes=30)
            if stop <= start:
                stop = start + timedelta(minutes=1)

            programmes.append({
                "title": epg_list[i]["title"],
                "start": start,
                "stop": stop
            })

        logging.info(f"Fetched {len(programmes)} programmes for {display_name}")

    except Exception as e:
        logging.error(f"Failed to fetch schedule for {display_name}: {e}")

    return {"id": channel_id, "name": display_name, "logo": logo_url, "programmes": programmes}



# -----------------------
# Scape from epg.pw site
# -----------------------
def scrape_epgpw(channel_id, display_name, logo_url, url):
    """
    Scrape TV schedule from epg.pw using panel structure.
    Extracts title, start time, stop time (in Asia/Dhaka timezone).
    """
    logging.info(f"Fetching schedule from epg.pw for {display_name} ...")
    programmes = []

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Get Asia/Dhaka timezone
        tz = pytz.timezone("Asia/Dhaka")
        now = datetime.now(tz)

        # Extract all day panels
        panels = soup.select("article.panel")
        if not panels:
            logging.warning("No schedule panels found on epg.pw page.")
            return {"id": channel_id, "name": display_name, "logo": logo_url, "programmes": programmes}

        for panel in panels:
            # Extract date from header
            date_header = panel.select_one("p.panel-heading")
            if not date_header:
                continue
            date_text = date_header.get_text(strip=True)  # Example: 2025-08-25
            try:
                day_date = datetime.strptime(date_text, "%Y-%m-%d").date()
            except ValueError:
                logging.warning(f"Invalid date format: {date_text}")
                continue

            # Extract all shows for that date
            blocks = panel.select("a.panel-block")
            for block in blocks:
                time_tag = block.select_one("span")
                if not time_tag:
                    continue

                show_time = time_tag.get_text(strip=True)  # Example: 23:30
                for dropdown in block.select(".dropdown-menu"):
                    dropdown.extract()  # Remove dropdown description completely

                time_tag.extract()  # Remove time
                show_name = block.get_text(strip=True)  # Now only main title remains

                # Combine date + time
                try:
                    start_dt = datetime.strptime(show_time, "%H:%M")
                    start_dt = tz.localize(datetime.combine(day_date, start_dt.time()))
                except ValueError:
                    logging.warning(f"Failed to parse time '{show_time}' for {show_name}")
                    continue

                programmes.append({
                    "title": html.escape(show_name),
                    "start": start_dt
                })

        # Sort and assign stop times
        programmes.sort(key=lambda x: x["start"])
        for i in range(len(programmes)):
            start = programmes[i]["start"]
            stop = programmes[i + 1]["start"] if i + 1 < len(programmes) else start + timedelta(minutes=30)
            programmes[i]["stop"] = stop

        logging.info(f"Fetched {len(programmes)} programmes for {display_name} from epg.pw")

    except Exception as e:
        logging.error(f"Failed to fetch schedule for {display_name} from epg.pw: {e}")

    return {"id": channel_id, "name": display_name, "logo": logo_url, "programmes": programmes}



# -----------------------
# Scape from tvpassport site
# -----------------------
def scrape_tvpassport(channel_id, display_name, logo_url, url):
    logging.info(f"Fetching schedule from TVPassport for {display_name} ...")
    programmes = []

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Select all program items
        items = soup.select(".list-group-item")
        if not items:
            logging.warning(f"No schedule table found on {url}")
            return {"id": channel_id, "name": display_name, "logo": logo_url, "programmes": programmes}

        for item in items:
            start_time = item.get("data-st")       # Example: "2025-08-27 05:00:00"
            duration = item.get("data-duration")  # Example: "60"
            show_name = item.get("data-showname") # Example: "Some Show"

            if not start_time or not show_name:
                continue  # Skip invalid rows

            try:
                # Parse start time (string like "2025-08-27 05:00:00")
                start_dt = datetime.strptime(start_time.strip(), "%Y-%m-%d %H:%M:%S")

                # Adjust to local time if needed (+10 for Bangladesh)
                start_dt = start_dt + timedelta(hours=10) 

                # Compute stop time
                duration_minutes = int(duration) if duration and duration.isdigit() else 30
                stop_dt = start_dt + timedelta(minutes=duration_minutes)

                programmes.append({
                    "title": html.escape(show_name.strip()),
                    "start": start_dt,
                    "stop": stop_dt
                })
            except Exception as e:
                logging.warning(f"Failed to parse show: {show_name} - {e}")
                continue

        logging.info(f"Fetched {len(programmes)} programmes for {display_name} from TVPassport")

    except Exception as e:
        logging.error(f"Failed to fetch schedule for {display_name} from TVPassport: {e}")

    return {"id": channel_id, "name": display_name, "logo": logo_url, "programmes": programmes}


# -----------------------
# Scape from tvguide site
# -----------------------
def scrape_tvguide(channel_id, display_name, logo_url, url):
    """
    Scrape schedule from TVGuide UK (example: TRT World) and return programmes with start, stop, title.
    """
    logging.info(f"Fetching schedule from TVGuide for {display_name} ...")
    programmes = []

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        tz = pytz.timezone("Asia/Dhaka")
        now = datetime.now(tz)

        items = soup.select(".js-schedule")
        logging.info(f"Found {len(items)} programmes for {display_name}")

        epg_list = []
        for div in items:
            start_time = div.get("data-date")  # Example: "2025-09-02T10:00:00"
            title_tag = div.select_one(".flex-grow a")
            title = title_tag.text.strip() if title_tag else ""
            if not start_time or not title:
                continue

            try:
                # Convert string to datetime (UTC assumed), then to Asia/Dhaka
                start_dt = datetime.fromisoformat(start_time)
                if start_dt.tzinfo is None:
                    start_dt = pytz.UTC.localize(start_dt)
                start_dt = start_dt.astimezone(tz)
            except Exception as e:
                logging.warning(f"Failed to parse time '{start_time}' for {title}: {e}")
                continue

            epg_list.append({"title": html.escape(title), "start": start_dt})

        # Sort by start time
        epg_list.sort(key=lambda x: x["start"])

        # Assign stop times (next start or +30 min)
        for i in range(len(epg_list)):
            start = epg_list[i]["start"]
            stop = epg_list[i + 1]["start"] if i + 1 < len(epg_list) else start + timedelta(minutes=30)
            if stop <= start:
                stop = start + timedelta(minutes=1)

            programmes.append({
                "title": epg_list[i]["title"],
                "start": start,
                "stop": stop
            })

        logging.info(f"Processed {len(programmes)} programmes for {display_name}")

    except Exception as e:
        logging.error(f"Failed to fetch schedule for {display_name} from TVGuide: {e}")

    return {"id": channel_id, "name": display_name, "logo": logo_url, "programmes": programmes}


# -----------------------
# Channels dictionary
# -----------------------
CHANNELS = {
    "TRTWorld.tr": (
        "TRT World",
        "https://static.wikia.nocookie.net/logopedia/images/6/6e/TRT_World_logo.svg",
        "https://www.tvguide.co.uk/channel/trt-world",
        scrape_tvguide
    ),
    "SonyEntertainmentHD": (
        "ENT | Sony Entertainment HD",
        "https://www.sonypicturesnetworks.com/images/logos/SET-LOGO-HD.png",
        "https://www.tvpassport.com/tv-listings/stations/sony-hd/6440",
        scrape_tvpassport
    ),
    "FoxNews.us": (
        "Fox News",
        "https://static.wikia.nocookie.net/logopedia/images/3/39/Fox_News_Channel_%282017%29.svg",
        "https://www.tvpassport.com/tv-listings/stations/fox-news/1083",
        scrape_tvpassport
    ),
    "EuronewsEnglish.fr": (
        "Euronews English",
        "https://static.wikia.nocookie.net/logopedia/images/f/f9/Euronews_2022_Stacked_III.svg",
        "https://www.tvpassport.com/tv-listings/stations/euronews/2121",
        scrape_tvpassport
    ),
    "CNN.us": (
        "CNN",
        "https://static.wikia.nocookie.net/logopedia/images/5/52/CNN_%282014%29.svg",
        "https://www.tvpassport.com/tv-listings/stations/cnn/70",
        scrape_tvpassport
    ),
    "DangalTV.in": (
        "ENT | Dangal TV"",
        "https://static.wikia.nocookie.net/logopedia/images/3/36/Dangalv2.png",
        "https://tvgenie.in/dangal-schedule",
        scrape_tvgenie
    ),
    "COLORS.in": (
        "ENT | COLORS HD",
        "https://static.wikia.nocookie.net/logopedia/images/1/19/Colorstv-logo-black-background.jpg",
        "https://tvgenie.in/colors-hd-schedule",
        scrape_tvgenie
    ),
    "IndiaTV.in": (
        "India TV",
        "https://static.wikia.nocookie.net/logopedia/images/1/10/India_TV_Orange.jpg",
        "https://tvgenie.in/india-tv-schedule",
        scrape_tvgenie
    ),
    "DDNews.in": (
        "DD News",
        "https://static.wikia.nocookie.net/logopedia/images/d/d6/DD_News_new_logo_2024.jpg",
        "https://tvgenie.in/dd-news-schedule",
        scrape_tvgenie
    ),
    "CNBCAwaaz": (
        "CNBC Awaaz",
        "https://static.wikia.nocookie.net/logopedia/images/1/18/CNBC_Awaaz_2025.svg",
        "https://tvgenie.in/cnbc-awaaz-schedule",
        scrape_tvgenie
    ),
    "BharatSamacharTV.in": (
        "Bharat Samachar TV",
        "https://bharatsamachartv.com/images/logo.png",
        "https://tvgenie.in/bharat-samachar-schedule",
        scrape_tvgenie
    ),
    "Abp.in": (
        "ABP News",
        "https://static.wikia.nocookie.net/logopedia/images/e/eb/ABP_News.svg",
        "https://tvgenie.in/abp-news-schedule",
        scrape_tvgenie
    ),
    "AajTak.in": (
        "Aaj Tak HD",
        "https://static.wikia.nocookie.net/logopedia/images/9/93/Aaj_Tak_HD_v2.png",
        "https://tvgenie.in/aaj-tak-hd-schedule",
        scrape_tvgenie
    ),
    "ZEETV.tv": (
        "ZEE TV HD",
        "https://1000logos.net/wp-content/uploads/2025/05/Zee-TV-Logo-768x432.png",
        "https://tvgenie.in/zee-tv-hd-schedule",
        scrape_tvgenie
    ),
    "STARBHARATHD": (
        "STAR BHARAT HD",
        "https://static.wikia.nocookie.net/logopedia/images/b/b9/Star_bharat_hd_clean.png",
        "https://tvgenie.in/star-bharat-hd-schedule",
        scrape_tvgenie
    ),
    "STARBHARAT": (
        "STAR BHARAT",
        "https://static.wikia.nocookie.net/logopedia/images/7/7b/Star_Bharat_2022.png",
        "https://tvgenie.in/star-bharat-schedule",
        scrape_tvgenie
    ),
    "EpicTV.in": (
        "Epic TV",
        "https://static.wikia.nocookie.net/logopedia/images/4/41/Epic_TV_%282021%29.jpg",
        "https://tvgenie.in/epic-schedule",
        scrape_tvgenie
    ),
    "E24.in": (
        "E24",
        "https://static.wikia.nocookie.net/logopedia/images/4/48/E24_new.jpg",
        "https://tvgenie.in/e24-schedule",
        scrape_tvgenie
    ),
    "DDNational.in@HD": (
        "DD National HD",
        "https://static.wikia.nocookie.net/logopedia/images/2/2a/Ddnational2023.png",
        "https://tvgenie.in/dd-national-schedule",
        scrape_tvgenie
    ),
    "AndTV.in": (
        "&TV HD",
        "https://static.wikia.nocookie.net/logopedia/images/4/4c/%26TV_HD_%282025%29.svg",
        "https://tvgenie.in/and-tv-hd-schedule",
        scrape_tvgenie
    ),
    "starjalsha.in": (
        "Star Jalsha",
        "https://upload.wikimedia.org/wikipedia/commons/e/ef/Star_Jalsha_logo_2023.png",
        "https://tvgenie.in/star-jalsha-schedule",
        scrape_tvgenie
    ),
    "colorsBangla.in": (
        "Colors Bangla HD",
        "https://static.wikia.nocookie.net/logopedia/images/2/2d/Colors-Bangla-Logo-new.jpg",
        "https://tvgenie.in/colors-bangla-hd-schedule",
        scrape_tvgenie
    ),
    "zeebangla.in": (
        "Zee Bangla TV",
        "http://openboxv8s.com/india/zee_bangla.jpg",
        "https://tvgenie.in/zee-bangla-hd-schedule",
        scrape_tvgenie
    ),
    "indiatoday.in": (
        "India Today",
        "https://images.seeklogo.com/logo-png/44/1/india-today-logo-png_seeklogo-440312.png",
        "https://tvgenie.in/india-today-schedule",
        scrape_tvgenie
    ),
    "ndtvenglish": (
        "NDTV English",
        "https://logotyp.us/file/ndtv.svg",
        "https://tvgenie.in/ndtv-24x7-schedule",
        scrape_tvgenie
    ),
    "ndtvindia": (
        "NDTV India",
        "https://logotyp.us/file/ndtv.svg",
        "https://tvgenie.in/ndtv-india-schedule",
        scrape_tvgenie
    ),
    "starsports1hd.in": (
        "Star Sports 1 HD",
        "hhttp://openboxv8s.com/india/star_sports_in_1_hindi.png",
        "https://tvgenie.in/star-sports-1-hd-schedule",
        scrape_tvgenie
    ),
    "starsports1hindi.in": (
        "Star Sports 1 Hindi",
        "https://static.epg.best/cn/StarSports1.cn.png",
        "https://tvgenie.in/star-sports-1-hd-hindi-schedule",
        scrape_tvgenie
    ),
    "starsports.tamil": (
        "Star Sports Tamil 1",
        "https://static.wikia.nocookie.net/logopedia/images/f/fb/Star_Sports_Tamil.png",
        "https://tvgenie.in/star-sports-1-tamil-schedule",
        scrape_tvgenie
    ),
    "starsports2hd.in": (
        "Star Sports 2 4K",
        "https://static.wikia.nocookie.net/logopedia/images/c/c3/SS2_Crop.jpg",
        "https://tvgenie.in/star-sports-2-hd-schedule",
        scrape_tvgenie
    ),
    "starsports3.in": (
        "Star Sports 3 HD",
        "https://i.pinimg.com/originals/c7/5d/56/c75d563b3cda837cd3fb1ce5ff5089cd.png",
        "https://tvgenie.in/star-sports-3-schedule",
        scrape_tvgenie
    ),
    "starsportsselect1.in": (
        "Star Sports Select 1 HD",
        "https://static.epg.best/in/StarSportsSelect1.in.png",
        "https://tvgenie.in/star-sports-select-1-hd-schedule",
        scrape_tvgenie
    ),
    "starsportsselect2.in": (
        "Star Sports Select 2 HD",
        "http://openboxv8s.com/india/star_sports2_in.jpg",
        "https://tvgenie.in/star-sports-select-2-schedule",
        scrape_tvgenie
    ),
    "sonyten1.in": (
        "Sony Ten 1 HD",
        "https://static.epg.best/in/SonyTEN1.in.png",
        "https://tvgenie.in/sony-ten-1-hd-schedule",
        scrape_tvgenie
    ),
    "sonyten2.in": (
        "Sony Ten 2 HD",
        "https://static.epg.best/in/SonyTEN2.in.png",
        "https://tvgenie.in/sony-ten-2-hd-schedule",
        scrape_tvgenie
    ),
    "sonyten3.in": (
        "Sony Ten 3 HD",
        "https://static.epg.best/in/SonyTEN3.in.png",
        "https://tvgenie.in/sony-ten-3-hd-schedule",
        scrape_tvgenie
    ),
    "IsharaTV.in": (
        "ENT | Ishara TV",
        "https://static.wikia.nocookie.net/logopedia/images/7/75/Ishara_tv.png",
        "https://www.tvwish.com/IN/Channels/Ishara/1394/Schedule",
        scrape_tvwish
    ),
    "EpicTV.in": (
        "ENT | Epic TV",
        "https://static.wikia.nocookie.net/logopedia/images/4/41/Epic_TV_%282021%29.jpg",
        "https://www.tvwish.com/IN/Channels/EPIC/614/Schedule",
        scrape_tvwish
    ),
    "DANGAL2": (
        "ENT | DANGAL2",
        "https://static.wikia.nocookie.net/logopedia/images/a/ac/Dangal_2.png",
        "https://www.tvwish.com/IN/Channels/Dangal-2/1287/Schedule",
        scrape_tvwish
    ),
    "BhojpuriCinema.in": (
        "Bhojpuri Cinema",
        "https://static.wikia.nocookie.net/logopedia/images/a/ad/Bhojpuri_cinema.png",
        "https://www.tvwish.com/IN/Channels/Bhojpuri-Cinema/704/Schedule",
        scrape_tvwish
    ),
    "B4UMovies.in": (
        "B4U Movies",
        "https://b4umovies.in/images/logo.jpg",
        "https://www.tvwish.com/IN/Channels/B4U-Movies/22/Schedule",
        scrape_tvwish
    ),
    "B4UKadak.in": (
        "B4U Kadak",
        "https://static.wikia.nocookie.net/logopedia/images/a/ab/B4U_Kadak.jpeg",
        "https://www.tvwish.com/IN/Channels/B4U-Kadak/713/Schedule",
        scrape_tvwish
    ),
    "Goldmines.in": (
        "Goldmines",
        "https://static.wikia.nocookie.net/jhmovie/images/7/7b/Goldmines_logo.png",
        "https://www.tvwish.com/IN/Channels/Goldmines/745/Schedule",
        scrape_tvwish
    ),
    "GoldminesMovies.in": (
        "Goldmines Movies",
        "https://static.wikia.nocookie.net/logopedia/images/5/50/Goldmines_old_logo.jpg",
        "https://www.tvwish.com/IN/Channels/Goldmines-Movies/1557/Schedule",
        scrape_tvwish
    ),
    "zeebanglacinema.in": (
        "Zee Bangla Cinema",
        "https://static.wikia.nocookie.net/logopedia/images/5/59/Zee_Bangla_Cinema_%282025%29.svg",
        "https://www.tvwish.com/IN/Channels/Zee-Bangla-Cinema/33/Schedule",
        scrape_tvwish
    ),
    "colorsbanglacinemahd.in": (
        "COLORS BANGLA CINEMA HD",
        "https://static.wikia.nocookie.net/logopedia/images/2/2d/Colors-Bangla-Logo-new.jpg",
        "https://www.tvwish.com/IN/Channels/Colors-Bangla-Cinema/1758/Schedule",
        scrape_tvwish
    ),
    "akashaat.in": (
        "AKASH 8",
        "https://static.wikia.nocookie.net/etv-gspn-bangla/images/3/34/Aakash_Aath_logo_%282013%29.png",
        "https://www.tvwish.com/IN/Channels/Aakash-Aath/1288/Schedule",
        scrape_tvwish
    ),
    "sunbangla.in": (
        "SUN Bangla",
        "https://upload.wikimedia.org/wikipedia/en/b/b3/Sun_Bangla.png",
        "https://www.tvwish.com/IN/Channels/Sun-Bangla/716/Schedule",
        scrape_tvwish
    ),
    "enter10bangla.in": (
        "Enter 10 Bangla",
        "https://raw.githubusercontent.com/subirkumarpaul/Logo/main/Enter%2010%20Bangla.jpeg",
        "https://www.tvwish.com/IN/Channels/Enterr10-Bangla/1743/Schedule",
        scrape_tvwish
    ),
    "sangeetbangla.in": (
        "SANGEET BANGLA",
        "https://static.wikia.nocookie.net/logopedia/images/d/da/Sangeet_Bangla_logo_2006.png",
        "https://www.tvwish.com/IN/Channels/Sangeet-Bangla/1768/Schedule",
        scrape_tvwish
    ),
    "sonymaxhd.in": (
        "SONY MAX HD",
        "https://static.wikia.nocookie.net/logopedia/images/8/84/Sony_Max_HD_2022.png",
        "https://www.tvwish.com/IN/Channels/Sony-Max-HD/31/Schedule",
        scrape_tvwish
    ),
    "sonysabhd.in": (
        "SONY SAB HD",
        "https://static.wikia.nocookie.net/logopedia/images/1/18/SONY_SAB_SD.png",
        "https://www.tvwish.com/IN/Channels/Sony-SAB-HD/669/Schedule",
        scrape_tvwish
    ),
    "RepublicBangla.in": (
        "Republic Bangla",
        "https://static.wikia.nocookie.net/logopedia/images/9/93/R.Bangla_logo_with_tagline.jpg",
        "https://www.tvwish.com/IN/Channels/Republic-Bangla/1729/Schedule",
        scrape_tvwish
    ),
    "DisneyJunior.in": (
        "Disney Junior",
        "https://upload.wikimedia.org/wikipedia/commons/3/36/2019_Disney_Junior_logo.svg",
        "https://www.tvwish.com/IN/Channels/Disney-Junior/611/Schedule",
        scrape_tvwish
    ),
    "DDBharati.in": (
        "DD Bharati",
        "https://static.wikia.nocookie.net/logopedia/images/d/db/DD_Bharati_english.png",
        "https://www.ontvtonight.com/guide/listings/channel/1225515954",
        scrape_ontvtonight
    ),
    "DisneyJunior.in@East": (
        "Disney Junior East",
        "https://upload.wikimedia.org/wikipedia/commons/3/36/2019_Disney_Junior_logo.svg",
        "https://www.ontvtonight.com/guide/listings/channel/69044944",
        scrape_ontvtonight
    ),
    "DisneyChannel.us@East": (
        "Disney Channel East",
        "https://upload.wikimedia.org/wikipedia/commons/3/3d/2022_Disney_Channel_logo.svg",
        "https://www.ontvtonight.com/guide/listings/channel/69047105",
        scrape_ontvtonight
    ),
    "DisneyXD.us": (
        "Disney XD",
        "https://upload.wikimedia.org/wikipedia/commons/a/a8/2015_Disney_XD_logo.svg",
        "https://www.ontvtonight.com/guide/listings/channel/69045318",
        scrape_ontvtonight
    ),
    "dwnews": (
        "DW English",
        "https://img.favpng.com/8/20/21/logo-deutsche-welle-dw-tv-dw-espa-ol-png-favpng-HaURNeixYqyctM1CSnmKA1kWk.jpg",
        "https://www.ontvtonight.com/guide/listings/channel/69035806",
        scrape_ontvtonight
    ),
    "my9.us": (
        "My 9",
        "https://cdn.titantv.com/i4fXAxGXCj88NotOCDfyK-YZKL1vqYrc0fXzRxmrvPg.png",
        "https://www.ontvtonight.com/guide/listings/channel/1714278231/my-9.html",
        scrape_ontvtonight
    ),
    "SkyNews.us": (
        "Sky News",
        "https://static.wikia.nocookie.net/logopedia/images/1/16/Sky_News_2020.svg",
        "https://www.ontvtonight.com/guide/listings/channel/69041608/sky-news-hq-hdtv.html",
        scrape_ontvtonight
    ),
    "aljazeera.com": (
        "Al Jazeera English",
        "https://emergencyuk.org/wp-content/uploads/2017/03/Aljazeera-logo-English-1024x768.png",
        "https://epg.pw/last/190468.html?lang=en",
        scrape_epgpw
    ),
    "WION.in": (
        "WION",
        "https://static.wikia.nocookie.net/logopedia/images/1/1d/WION_World_Is_One_News.svg",
        "https://epg.pw/last/9416.html?lang=en",
        scrape_epgpw
    ),
    "CGTN.cn": (
        "CGTN",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/8/81/CGTN.svg/512px-CGTN.svg.png",
        "https://epg.pw/last/431469.html?lang=en",
        scrape_epgpw
    ),
    "cna.sg": (
        "Channel News Asia",
        "https://logowik.com/content/uploads/images/cna-channel-news-asia9392.jpg",
        "https://epg.pw/last/171959.html?lang=en",
        scrape_epgpw
    ),
    "TRT World": (
        "TRTWorld.tr",
        "https://static.wikia.nocookie.net/logopedia/images/6/6e/TRT_World_logo.svg",
        "https://epg.pw/last/9440.html?lang=en",
        scrape_epgpw
    ),
    "Bloomberg TV": (
        "BloombergTV.us",
        "https://static.wikia.nocookie.net/logopedia/images/9/93/Bloomberg_tv_2016.svg",
        "https://epg.pw/last/446971.html?lang=en",
        scrape_epgpw
    )
}


# -----------------------
# Build XMLTV file
# -----------------------
def build_epg(channels_data, filename="epg.xml"):
    logging.info("Building EPG XML ...")
    tv = ET.Element("tv")

    for ch in channels_data:
        channel_elem = ET.SubElement(tv, "channel", {"id": ch["id"]})
        ET.SubElement(channel_elem, "display-name").text = ch["name"]
        if ch["logo"]:
            ET.SubElement(channel_elem, "icon", {"src": ch["logo"]})

        sorted_programmes = sorted(ch["programmes"], key=lambda x: x["start"])
        cleaned_programmes = []
        prev_stop = None

        for prog in sorted_programmes:
            start = prog["start"]
            stop = prog["stop"]

            if prev_stop and start < prev_stop:
                start = prev_stop

            if prev_stop and start > prev_stop:
                last = cleaned_programmes[-1]
                last["stop"] = start

            if stop <= start:
                stop = start + timedelta(minutes=1)

            cleaned_programmes.append({"title": prog["title"], "start": start, "stop": stop})
            prev_stop = stop

        for prog in cleaned_programmes:
            start_str = prog["start"].strftime("%Y%m%d%H%M%S +0600")
            stop_str = prog["stop"].strftime("%Y%m%d%H%M%S +0600")
            prog_elem = ET.SubElement(tv, "programme", {"start": start_str, "stop": stop_str, "channel": ch["id"]})
            ET.SubElement(prog_elem, "title", {"lang": "bn"}).text = prog["title"]

    xml_str = ET.tostring(tv, encoding="utf-8")
    pretty_xml = minidom.parseString(xml_str).toprettyxml(indent="  ")

    with open(filename, "w", encoding="utf-8") as f:
        f.write(pretty_xml)

    logging.info(f"EPG saved to {filename}")


# -----------------------
# Main
# -----------------------
if __name__ == "__main__":
    all_channels = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for ch_id, (name, logo, url, scraper_func) in CHANNELS.items():
            if scraper_func == scrape_tvwish:
                ch_data = scraper_func(ch_id, name, logo, url, browser=browser)
            else:
                ch_data = scraper_func(ch_id, name, logo, url)
            all_channels.append(ch_data)
        browser.close()

    build_epg(all_channels, "epg.xml")
