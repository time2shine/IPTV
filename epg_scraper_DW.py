import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
from xml.dom import minidom
import logging
import html
import os

# -----------------------
# Logging setup
# -----------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


def scrape_dw(channel_id, display_name, logo_url, url):
    logging.info(f"Fetching DW English schedule from {display_name} ...")
    programmes = []
    now = datetime.now()

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")

        # ✅ 1. Get current program from <h2 aria-label>
        current_tag = soup.find("h2", attrs={"aria-label": True})
        current_title = None
        if current_tag:
            current_title = html.escape(current_tag.get_text(strip=True))
            logging.info(f"Current Program: {current_title}")
        else:
            logging.warning("No current program found.")

        # ✅ 2. Get upcoming schedule rows
        schedule_rows = soup.find_all("div", attrs={"role": "row"})
        upcoming_programmes = []

        for row in schedule_rows:
            time_tag = row.find("span", attrs={"role": "cell", "class": lambda c: c and "time" in c})
            program_names = row.find("div", attrs={"role": "cell", "class": lambda c: c and "program-names" in c})

            if time_tag and program_names:
                time_text = time_tag.get_text(strip=True)
                names = program_names.find_all("span")
                main_title = names[0].get_text(strip=True) if len(names) > 0 else ""

                try:
                    show_time = datetime.strptime(time_text, "%H:%M")
                    start_time = now.replace(hour=show_time.hour, minute=show_time.minute, second=0, microsecond=0)
                    if start_time < now:
                        start_time += timedelta(days=1)
                except:
                    start_time = now

                stop_time = start_time + timedelta(minutes=30)  # assume 30 mins
                upcoming_programmes.append({
                    "title": html.escape(main_title),
                    "start": start_time,
                    "stop": stop_time
                })

        # ✅ 3. Handle current program time
        if current_title:
            if upcoming_programmes:
                next_start = upcoming_programmes[0]["start"]
                current_start = next_start - timedelta(minutes=30)
                current_stop = next_start - timedelta(minutes=1)
            else:
                current_start = now - timedelta(minutes=30)
                current_stop = now + timedelta(minutes=30)

            programmes.append({
                "title": current_title,
                "start": current_start,
                "stop": current_stop
            })

        # ✅ 4. Merge current and upcoming programmes
        programmes.extend(upcoming_programmes)

        logging.info(f"Fetched {len(programmes)} programmes for {display_name}")

    except Exception as e:
        logging.error(f"Failed to fetch DW English: {e}")

    return {"id": channel_id, "name": display_name, "logo": logo_url, "programmes": programmes}


CHANNELS = {
    "dwnews": (
        "DW English",
        "https://img.favpng.com/8/20/21/logo-deutsche-welle-dw-tv-dw-espa-ol-png-favpng-HaURNeixYqyctM1CSnmKA1kWk.jpg",
        "https://www.dw.com/en/live-tv/channel-english",
        scrape_dw
    ),
}


def update_epg(channels_data, filename="epg.xml"):
    logging.info("Updating EPG XML ...")

    # ✅ 1. Load existing EPG or create new
    if os.path.exists(filename):
        tree = ET.parse(filename)
        tv = tree.getroot()
    else:
        tv = ET.Element("tv")

    # ✅ 2. Remove old entries for updated channels
    for ch_data in channels_data:
        channel_id = ch_data["id"]

        # Remove channel entry
        for channel_elem in tv.findall("channel"):
            if channel_elem.get("id") == channel_id:
                tv.remove(channel_elem)

        # Remove programme entries
        for prog_elem in tv.findall("programme"):
            if prog_elem.get("channel") == channel_id:
                tv.remove(prog_elem)

    # ✅ 3. Add updated channels and programmes
    for ch_data in channels_data:
        channel_elem = ET.SubElement(tv, "channel", {"id": ch_data["id"]})
        ET.SubElement(channel_elem, "display-name").text = ch_data["name"]
        if ch_data["logo"]:
            ET.SubElement(channel_elem, "icon", {"src": ch_data["logo"]})

        sorted_programmes = sorted(ch_data["programmes"], key=lambda x: x["start"])
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
            prog_elem = ET.SubElement(tv, "programme", {"start": start_str, "stop": stop_str, "channel": ch_data["id"]})
            ET.SubElement(prog_elem, "title", {"lang": "bn"}).text = prog["title"]

    # ✅ 4. Save updated XML (pretty, no extra blank lines)
    xml_str = ET.tostring(tv, encoding="utf-8")
    pretty_xml = minidom.parseString(xml_str).toprettyxml(indent="  ")

    # Remove empty lines
    pretty_xml = "\n".join([line for line in pretty_xml.split("\n") if line.strip()])

    with open(filename, "w", encoding="utf-8") as f:
        f.write(pretty_xml)

    logging.info(f"EPG updated and saved to {filename}")


if __name__ == "__main__":
    all_channels = []

    for ch_id, (name, logo, url, scraper_func) in CHANNELS.items():
        ch_data = scraper_func(ch_id, name, logo, url)
        all_channels.append(ch_data)

    update_epg(all_channels, "epg.xml")
