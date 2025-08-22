import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
import logging
from xml.dom import minidom

# -----------------------
# Logging setup
# -----------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# -----------------------
# Channels to scrape
# key = channel_id for XML
# value = (display name, logo url, schedule url)
# -----------------------
CHANNELS = {
    "starjalsha.in": (
        "Star Jalsha",
        "https://upload.wikimedia.org/wikipedia/en/d/d0/Star_Jalsha_logo.png",
        "https://tvgenie.in/star-jalsha-schedule"
    ),
    # Add more channels if needed
}


# -----------------------
# Scrape a single channel
# -----------------------
def scrape_channel(channel_id, display_name, logo_url, url):
    logging.info(f"Fetching schedule for {display_name} ...")
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        response.raise_for_status()
    except Exception as e:
        logging.error(f"Failed to fetch {url}: {e}")
        return {
            "id": channel_id,
            "name": display_name,
            "logo": logo_url,
            "programmes": []
        }

    soup = BeautifulSoup(response.text, "html.parser")
    programmes = []

    # Each programme block
    items = soup.select("div.requested-movies.card")
    logging.info(f"Found {len(items)} programmes for {display_name}")

    for item in items:
        title_tag = item.select_one("h6.desktop-only")
        time_tag = item.select_one(".detail-container p")

        if not title_tag or not time_tag:
            continue

        title = title_tag.get_text(strip=True)
        time_text = time_tag.get_text(strip=True)  # e.g., "1:30 AM, Today"

        try:
            time_part, day_part = [x.strip() for x in time_text.split(",")]
            show_time = datetime.strptime(time_part, "%I:%M %p")
            today = datetime.now()

            if "Today" in day_part:
                date_obj = today
            elif "Tomorrow" in day_part:
                date_obj = today + timedelta(days=1)
            else:
                date_obj = today  # fallback

            start = date_obj.replace(
                hour=show_time.hour,
                minute=show_time.minute,
                second=0,
                microsecond=0
            )
            stop = start + timedelta(minutes=30)  # assume 30 minutes

            programmes.append({
                "title": title,
                "start": start,
                "stop": stop
            })

        except Exception as e:
            logging.warning(f"Failed to parse time '{time_text}' for {title}: {e}")

    return {
        "id": channel_id,
        "name": display_name,
        "logo": logo_url,
        "programmes": programmes
    }


# -----------------------
# Build XMLTV file
# -----------------------
def build_epg(channels_data, filename="epg.xml"):
    logging.info("Building EPG XML ...")
    tv = ET.Element("tv")

    for ch in channels_data:
        # Channel metadata
        channel_elem = ET.SubElement(tv, "channel", {"id": ch["id"]})
        ET.SubElement(channel_elem, "display-name").text = ch["name"]
        if ch["logo"]:
            ET.SubElement(channel_elem, "icon", {"src": ch["logo"]})

        # Programmes
        for prog in ch["programmes"]:
            start_str = prog["start"].strftime("%Y%m%d%H%M%S +0600")
            stop_str = prog["stop"].strftime("%Y%m%d%H%M%S +0600")

            prog_elem = ET.SubElement(tv, "programme", {
                "start": start_str,
                "stop": stop_str,
                "channel": ch["id"]
            })
            ET.SubElement(prog_elem, "title", {"lang": "bn"}).text = prog["title"]

    # Pretty print XML
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

    for ch_id, (name, logo, url) in CHANNELS.items():
        ch_data = scrape_channel(ch_id, name, logo, url)
        all_channels.append(ch_data)

    build_epg(all_channels, "epg.xml")
