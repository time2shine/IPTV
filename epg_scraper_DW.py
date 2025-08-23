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


def scrape_dw(channel_id, display_name, logo_url, url, browser=None):
    logging.info(f"Fetching DW English schedule from {url} ...")
    programmes = []
    now = datetime.now()

    try:
        page = browser.new_page()
        page.goto(url, timeout=15000)
        page.wait_for_selector("section", timeout=15000)

        soup = BeautifulSoup(page.content(), "html.parser")
        schedule_items = soup.select("section li, div.schedule-item, div:has(time)")

        for item in schedule_items:
            time_tag = item.find("time")
            title_tag = item.find("h3") or item.find("span") or item.find("p")
            if not time_tag or not title_tag:
                continue

            time_text = time_tag.get_text(strip=True)
            title = html.escape(title_tag.get_text(strip=True))

            try:
                show_time = datetime.strptime(time_text, "%H:%M")  # DW uses 24h format
                start = now.replace(hour=show_time.hour, minute=show_time.minute, second=0, microsecond=0)
                if start < now:
                    start += timedelta(days=1)
            except:
                start = now

            stop = start + timedelta(minutes=30)  # default 30 min
            programmes.append({"title": title, "start": start, "stop": stop})

        page.close()
        logging.info(f"Fetched {len(programmes)} programmes for {display_name}")

    except Exception as e:
        logging.error(f"Failed to fetch DW English: {e}")

    return {"id": channel_id, "name": display_name, "logo": logo_url, "programmes": programmes}


# -----------------------
# Channels dictionary
# -----------------------
CHANNELS = {
    "dwnews": (
        "DW English",
        "https://img.favpng.com/8/20/21/logo-deutsche-welle-dw-tv-dw-espa-ol-png-favpng-HaURNeixYqyctM1CSnmKA1kWk.jpg",  # DW logo
        "https://www.dw.com/en/live-tv/channel-english",
        scrape_dw  # new scraper function
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
