import json
import subprocess
import functools
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from datetime import datetime, date

# Force print to flush immediately
print = functools.partial(print, flush=True)

# Config
JSON_FILE = "static_channels.json"
FAST_MODE = False  # True = fast FFmpeg, False = full/slow check
RETRIES = 3
MAX_WORKERS = 100  # Parallel FFmpeg threads

EXCLUDE_LIST = [
    "RACING | MTRSPT1",
    "HINDI | RDC Movies",
    "OTHER | Cowboy Channel",
    "NEWS | Republic Bharat",
    "NEWS | Aaj Tak HD",
    "NEWS | Aaj Tak",
    "NEWS | India TV",
    "NEWS | India Today",
    "NEWS | India Daily 24x7",
    "NEWS | ARY NEWS",
    "NEWS | News9Live",
    "NEWS | CNN News 18",
    "BD | TBN 24 USA",
    "HI | Shemaroo Filmigaane",
    "HI | YRF Music HD",
    "IN | Republic Bangla",
    "IN | TV9 Bangla",
    "CR | Cricket Gold",
    "Ekushay TV (Local)",
    "AccuWeather NOW",
    "Outdoor Channel",
    "RT NEWS GLOBAL",
    "POWERtube TV",
    "Ekushay TV",
    "TVRI World",
    "Spacetoon",
    "Sky News",
    "GB News"
]

# ✅ Whitelist domains (any URL containing these will be auto-marked as online)
WHITELIST_DOMAINS = [
    "https://lightning-now80s-rakuten.amagi.tv",
    "https://cdn-ue1-prod.tsv2.amagi.tv",
    "https://tiger-hub.vercel.app",
    "https://amg01448-samsungin",
    "https://live.dinesh29.com",
    "https://app.hughag.store",
    "http://fl1.moveonjoy.com",
    "https://mtv.sunplex.live",
    "https://cdn-4.pishow.tv",
    "https://epg.provider",
    "http://41.205.93.154",
    "http://filex.tv:8080",
    "https://amg"
]

def check_ffmpeg(url, channel_name):
    """Check if a stream is playable with FFmpeg retries."""
    today = date.today()

    # Skip excluded channels
    if any(skip.lower() in channel_name.lower() for skip in EXCLUDE_LIST):
        print(f"[SKIPPED] {channel_name}")
        return url, "online", today

    # ✅ Skip ffmpeg check for whitelisted domains
    if any(domain in url for domain in WHITELIST_DOMAINS):
        print(f"[WHITELISTED] {channel_name} -> {url}")
        return url, "online", today

    # Build ffmpeg command
    ffmpeg_cmd = ["ffmpeg", "-probesize", "1000000", "-analyzeduration", "1000000",
                  "-i", url, "-t", "2", "-f", "null", "-"]
    if FAST_MODE:
        ffmpeg_cmd = ["ffmpeg", "-probesize", "500000", "-analyzeduration", "500000",
                      "-i", url, "-t", "1", "-f", "null", "-"]

    # Run ffmpeg with retries
    for attempt in range(1, RETRIES + 2):
        try:
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=15)
            if "error" not in result.stderr.lower():
                print(f"[ONLINE] {channel_name} -> {url}")
                return url, "online", today
        except Exception:
            pass

    print(f"[OFFLINE] {channel_name} -> {url}")
    return url, "offline", today

def update_status_parallel(channels):
    """Update status of all links using parallel FFmpeg checks."""
    tasks = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for channel_name, info in channels.items():
            # Ensure 'links' exists and is a list
            if "links" not in info or not isinstance(info["links"], list):
                info["links"] = []

            for i, link_entry in enumerate(info["links"]):
                # If link is empty or None, mark as missing but keep in JSON
                if not link_entry:
                    info["links"][i] = {"url": None, "status": "missing",
                                        "first_online": None, "last_offline": None}
                    continue

                # Convert string link to dict
                if isinstance(link_entry, str):
                    info["links"][i] = {"url": link_entry, "status": "unknown",
                                        "first_online": None, "last_offline": None}
                    link_entry = info["links"][i]

                # Ensure keys exist
                link_entry.setdefault("first_online", None)
                link_entry.setdefault("last_offline", None)

                url = link_entry.get("url")
                if not url:
                    link_entry["status"] = "missing"
                    continue

                tasks.append(executor.submit(check_ffmpeg, url, channel_name))

        # Collect results and update JSON
        for future in as_completed(tasks):
            url, status, today = future.result()
            for info in channels.values():
                for link_entry in info["links"]:
                    if link_entry.get("url") == url:
                        link_entry["status"] = status
                        if status == "online":
                            if link_entry.get("first_online") is None:
                                link_entry["first_online"] = today.isoformat()
                            link_entry["last_offline"] = None
                        elif status == "offline":
                            if link_entry.get("last_offline") is None:
                                link_entry["last_offline"] = today.isoformat()

def categorize_link(channel_name, url, status):
    """Determine the category of a link for sorting."""
    if status == "missing":
        return "MISSING"
    if status == "offline":
        return "OFFLINE"
    if any(skip.lower() in channel_name.lower() for skip in EXCLUDE_LIST):
        return "EXCLUDED"
    if any(domain in url for domain in WHITELIST_DOMAINS):
        return "WHITELISTED"
    return status.upper()

def summarize(channels, start_time):
    """Print sorted summary: MISSING → OFFLINE → EXCLUDED → WHITELISTED."""
    today = date.today()
    entries = []

    online_links = offline_links = missing_links = excluded_links = whitelist_links = 0

    for channel_name, info in channels.items():
        for link in info.get("links", []):
            url = link.get("url")
            status = link.get("status", "unknown")

            category = categorize_link(channel_name, url, status)

            if category == "MISSING":
                missing_links += 1
            elif category == "OFFLINE":
                offline_links += 1
            elif category == "EXCLUDED":
                excluded_links += 1
            elif category == "WHITELISTED":
                whitelist_links += 1
            elif status == "online":
                online_links += 1

            entries.append({
                "category": category,
                "channel": channel_name,
                "url": url,
                "last_offline": link.get("last_offline"),
            })

    # Sort categories first, then URL alphabetically
    category_order = {"MISSING": 0, "OFFLINE": 1, "EXCLUDED": 2, "WHITELISTED": 3}
    entries.sort(key=lambda x: (category_order.get(x["category"], 4), str(x["url"])))

    print("\n=== SUMMARY ===")
    for e in entries:
        if e["category"] == "MISSING":
            print(f"[MISSING] {e['channel']} -> No link provided")
        elif e["category"] == "OFFLINE":
            days_offline = "unknown duration"
            if e["last_offline"]:
                days_offline = f"{(today - datetime.fromisoformat(e['last_offline']).date()).days:>5} day(s)"
            print(f"[OFFLINE] {e['channel']:<30} | Offline for {days_offline} -> {e['url']}")
        elif e["category"] == "EXCLUDED":
            print(f"[EXCLUDED] {e['channel']} -> {e['url']}")
        elif e["category"] == "WHITELISTED":
            print(f"[WHITELISTED] {e['channel']} -> {e['url']}")

    elapsed = time.time() - start_time
    separator = "=" * 50
    print(f"\n{separator}")
    print(f"{'Total channels':<20}: {len(channels)}")
    print(f"{'Total online links':<20}: {online_links}")
    print(f"{'Total offline links':<20}: {offline_links}")
    print(f"{'Total missing links':<20}: {missing_links}")
    print(f"{'Excluded links':<20}: {excluded_links}")
    print(f"{'Whitelisted links':<20}: {whitelist_links}")
    print(f"{'Total runtime':<20}: {elapsed:.2f} seconds")
    print(f"{separator}\n")

def sort_channels(channels):
    """Sort channels by group then channel name."""
    return dict(
        sorted(
            channels.items(),
            key=lambda item: (
                item[1].get("group", "").lower(),
                item[0].lower()
            )
        )
    )

def mark_old_offline_links(channels, days_threshold=10):
    """Mark links offline for >= days_threshold days by setting URL to empty."""
    today = date.today()
    for channel_name, info in channels.items():
        for link in info.get("links", []):
            status = link.get("status", "unknown")
            last_offline = link.get("last_offline")

            if status == "offline" and last_offline:
                last_offline_date = datetime.fromisoformat(last_offline).date()
                offline_days = (today - last_offline_date).days
                if offline_days >= days_threshold:
                    print(f"[RESET URL] {channel_name} -> Offline for {offline_days} day(s) -> {link.get('url')}")
                    link["url"] = ""

def main():
    start_time = time.time()

    # Load JSON
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        channels = json.load(f)

    # Update status in parallel
    update_status_parallel(channels)

    # Sort channels by group then name
    channels_sorted = sort_channels(channels)

    # Mark links offline for 10+ days by emptying URL
    mark_old_offline_links(channels_sorted, days_threshold=10)

    # Save updated and sorted JSON
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(channels_sorted, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Updated {JSON_FILE} with online/offline/missing status, reset URLs for old offline links, and sorted by group/name.")

    # Print summary
    summarize(channels_sorted, start_time)

if __name__ == "__main__":
    main()
