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
# Channels dictionary
# -----------------------
CHANNELS = {
    "starjalsha.in": (
        "Star Jalsha",
        "https://upload.wikimedia.org/wikipedia/commons/e/ef/Star_Jalsha_logo_2023.png",
        "https://tvgenie.in/star-jalsha-schedule",
        scrape_tvgenie
    ),
    "colors.in": (
        "Colors",
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
    "zeebanglacinema.in": (
        "Zee Bangla Cinema",
        "https://static.wikia.nocookie.net/logopedia/images/5/59/Zee_Bangla_Cinema_%282025%29.svg",
        "https://www.tvwish.com/IN/Channels/Zee-Bangla-Cinema/33/Schedule",
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
    "dwnews": (
        "DW English",
        "https://img.favpng.com/8/20/21/logo-deutsche-welle-dw-tv-dw-espa-ol-png-favpng-HaURNeixYqyctM1CSnmKA1kWk.jpg",
        "https://www.ontvtonight.com/guide/listings/channel/69035806",
        scrape_ontvtonight
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
