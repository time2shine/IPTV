import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
from xml.dom import minidom
import logging
import html
from playwright.sync_api import sync_playwright

# -----------------------
# Logging setup
# -----------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# -----------------------
# Scrapers for different sites
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

    for item in items:
        title_tag = item.select_one("h6.desktop-only")
        time_tag = item.select_one(".detail-container p")
        if not title_tag or not time_tag:
            continue

        title = html.escape(title_tag.get_text(strip=True))
        time_text = time_tag.get_text(strip=True)

        try:
            time_part, day_part = [x.strip() for x in time_text.split(",")]
            show_time = datetime.strptime(time_part, "%I:%M %p")
            today = datetime.now()
            date_obj = today if "Today" in day_part else today + timedelta(days=1) if "Tomorrow" in day_part else today

            start = date_obj.replace(hour=show_time.hour, minute=show_time.minute, second=0, microsecond=0)
            stop = start + timedelta(minutes=30)
            programmes.append({"title": title, "start": start, "stop": stop})
        except Exception as e:
            logging.warning(f"Failed to parse time '{time_text}' for {title}: {e}")

    return {"id": channel_id, "name": display_name, "logo": logo_url, "programmes": programmes}


def scrape_tvwish(channel_id, display_name, logo_url, url, browser=None):
    """
    Scrape TVWish schedule.
    Uses requests for current show, Playwright for upcoming shows.
    If browser is provided, it will reuse it.
    """
    logging.info(f"Fetching TV schedule from TVWish for {display_name} ...")
    programmes = []

    # -------------------
    # Current show (HTML)
    # -------------------
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        current_show = soup.select_one("div.prog-list")
        if current_show:
            title_tag = current_show.select_one("h4")
            if title_tag:
                title = html.escape(title_tag.get_text(strip=True))
                start = datetime.now()
                stop = start + timedelta(minutes=30)
                programmes.append({"title": title, "start": start, "stop": stop})
                logging.info(f"Current show: {title}")
    except Exception as e:
        logging.error(f"Failed to fetch current show: {e}")

    # -------------------
    # Upcoming shows (JS rendered)
    # -------------------
    try:
        if browser is None:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                programmes += _fetch_upcoming_tvwish(browser, url)
                browser.close()
        else:
            programmes += _fetch_upcoming_tvwish(browser, url)
    except Exception as e:
        logging.error(f"Failed to fetch upcoming shows: {e}")

    return {"id": channel_id, "name": display_name, "logo": logo_url, "programmes": programmes}


def _fetch_upcoming_tvwish(browser, url):
    """
    Helper function to fetch upcoming shows from TVWish using Playwright browser.
    """
    programmes = []
    page = browser.new_page()
    page.goto(url)
    page.wait_for_selector("#divUpcoming", timeout=10000)

    html_content = page.content()
    soup = BeautifulSoup(html_content, "html.parser")

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
                start = datetime.now().replace(hour=show_time.hour, minute=show_time.minute, second=0, microsecond=0)
            except:
                start = datetime.now()
        else:
            start = datetime.now()

        stop = start + timedelta(minutes=30)
        programmes.append({"title": title, "start": start, "stop": stop})

    logging.info(f"Fetched {len(upcoming_items)} upcoming shows via Playwright")
    page.close()
    return programmes


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
    "zeebanglacinema.in": (
        "Zee Bangla Cinema",
        "https://static.wikia.nocookie.net/logopedia/images/5/59/Zee_Bangla_Cinema_%282025%29.svg",
        "https://www.tvwish.com/IN/Channels/Zee-Bangla-Cinema/33/Schedule",
        scrape_tvwish
    ),
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

        for prog in ch["programmes"]:
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
