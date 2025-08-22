import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
from xml.dom import minidom
import logging
import html

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
    """
    Scrape schedules from tvgenie.in
    Works for Star Jalsha, Colors, Zee TV if they follow the same HTML structure
    """
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
            stop = start + timedelta(minutes=30)  # default 30 mins
            programmes.append({"title": title, "start": start, "stop": stop})
        except Exception as e:
            logging.warning(f"Failed to parse time '{time_text}' for {title}: {e}")

    return {"id": channel_id, "name": display_name, "logo": logo_url, "programmes": programmes}

def scrape_tvwish(channel_id, display_name, logo_url, url):
    """
    Scrape TV schedule from tvwish.com (e.g., Zee Bangla Cinema)
    """
    logging.info(f"Fetching TV schedule from TVWish for {display_name} ...")
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        response.raise_for_status()
    except Exception as e:
        logging.error(f"Failed to fetch {url}: {e}")
        return {"id": channel_id, "name": display_name, "logo": logo_url, "programmes": []}

    soup = BeautifulSoup(response.text, "html.parser")
    programmes = []

    # -------------------
    # Current show
    # -------------------
    current_show = soup.select_one("div.prog-list")
    if current_show:
        title_tag = current_show.select_one("h4")
        if title_tag:
            title = html.escape(title_tag.get_text(strip=True))
            start = datetime.now()
            # We'll approximate stop as 30 mins later
            stop = start + timedelta(minutes=30)
            programmes.append({"title": title, "start": start, "stop": stop})

    # -------------------
    # Upcoming shows
    # -------------------
    upcoming_items = soup.select("div.card.schedule-item")
    logging.info(f"Found {len(upcoming_items)} upcoming shows for {display_name}")

    for i, item in enumerate(upcoming_items):
        # Time
        time_tag = item.select_one("div.card-header h3")
        title_tag = item.select_one("h4")
        desc_tag = item.select_one("p")
        if not time_tag or not title_tag:
            continue

        title = html.escape(title_tag.get_text(strip=True))
        description = html.escape(desc_tag.get_text(strip=True)) if desc_tag else ""
        time_text = time_tag.get_text(strip=True)  # e.g., "Fri, 7:30 PM"

        try:
            # Parse the time portion
            time_part = time_text.split(",")[-1].strip()
            show_time = datetime.strptime(time_part, "%I:%M %p")
            today = datetime.now()
            start = today.replace(hour=show_time.hour, minute=show_time.minute, second=0, microsecond=0)

            # Stop = start of next show or 30 mins if last
            if i + 1 < len(upcoming_items):
                next_time_tag = upcoming_items[i + 1].select_one("div.card-header h3")
                next_time_text = next_time_tag.get_text(strip=True).split(",")[-1].strip()
                next_show_time = datetime.strptime(next_time_text, "%I:%M %p")
                stop = today.replace(hour=next_show_time.hour, minute=next_show_time.minute, second=0, microsecond=0)
                # If stop < start, it means past midnight → add 1 day
                if stop <= start:
                    stop += timedelta(days=1)
            else:
                stop = start + timedelta(minutes=30)

            programmes.append({"title": title, "start": start, "stop": stop})

        except Exception as e:
            logging.warning(f"Failed to parse time '{time_text}' for {title}: {e}")

    return {"id": channel_id, "name": display_name, "logo": logo_url, "programmes": programmes}



def scrape_othersite(channel_id, display_name, logo_url, url):
    """
    Example scraper for another site with different HTML structure
    You must inspect that site's HTML and adjust selectors
    """
    logging.info(f"Fetching TV schedule from other site for {display_name} ...")
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        response.raise_for_status()
    except Exception as e:
        logging.error(f"Failed to fetch {url}: {e}")
        return {"id": channel_id, "name": display_name, "logo": logo_url, "programmes": []}

    soup = BeautifulSoup(response.text, "html.parser")
    programmes = []

    # Adjust selectors based on the site's HTML
    items = soup.select("div.program-item")
    logging.info(f"Found {len(items)} programmes for {display_name}")

    for item in items:
        title_tag = item.select_one(".show-name")
        time_tag = item.select_one(".time")
        if not title_tag or not time_tag:
            continue

        title = html.escape(title_tag.get_text(strip=True))
        time_text = time_tag.get_text(strip=True)

        try:
            show_time = datetime.strptime(time_text, "%I:%M %p")
            today = datetime.now()
            start = today.replace(hour=show_time.hour, minute=show_time.minute, second=0, microsecond=0)
            stop = start + timedelta(minutes=30)
            programmes.append({"title": title, "start": start, "stop": stop})
        except Exception as e:
            logging.warning(f"Failed to parse time '{time_text}' for {title}: {e}")

    return {"id": channel_id, "name": display_name, "logo": logo_url, "programmes": programmes}


# -----------------------
# Channels dictionary
# key = channel_id
# value = (display name, logo url, schedule url, scraper function)
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
    for ch_id, (name, logo, url, scraper_func) in CHANNELS.items():
        ch_data = scraper_func(ch_id, name, logo, url)
        all_channels.append(ch_data)

    build_epg(all_channels, "epg.xml")
