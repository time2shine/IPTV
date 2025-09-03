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
FAST_MODE = False       # True = fast FFmpeg, False = full/slow check
RETRIES = 3
MAX_WORKERS = 40       # Parallel FFmpeg threads
EXCLUDE_LIST = ["Republic Bangla", "Republic Bharat", "Aaj Tak HD", "Aaj Tak", "India Today", "Ekushay TV (Local)", "Ekushay TV"]

def check_ffmpeg(url, channel_name):
    """Check if a stream is playable with FFmpeg retries."""
    today = date.today()
    
    if any(skip.lower() in channel_name.lower() for skip in EXCLUDE_LIST):
        print(f"[SKIPPED] {channel_name}")
        return url, "online", today

    ffmpeg_cmd = ["ffmpeg", "-probesize", "1000000", "-analyzeduration", "1000000",
                  "-i", url, "-t", "2", "-f", "null", "-"]
    if FAST_MODE:
        ffmpeg_cmd = ["ffmpeg", "-probesize", "500000", "-analyzeduration", "500000",
                      "-i", url, "-t", "1", "-f", "null", "-"]

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
                            # Set first_online if never online before
                            if link_entry.get("first_online") is None:
                                link_entry["first_online"] = today.isoformat()
                            link_entry["last_offline"] = None
                        elif status == "offline":
                            # Set last_offline if not already set
                            if link_entry.get("last_offline") is None:
                                link_entry["last_offline"] = today.isoformat()

def summarize(channels, start_time):
    """Print summary of online/offline/missing links and offline durations."""
    total_channels = len(channels)
    online_links = 0
    offline_links = 0
    missing_links = 0
    today = date.today()

    print("\n=== SUMMARY ===")
    for info in channels.values():
        for link in info.get("links", []):
            url = link.get("url")
            status = link.get("status")
            if status == "online":
                online_links += 1
            elif status == "offline":
                offline_links += 1
                last_offline = link.get("last_offline")
                if last_offline:
                    days_offline = (today - datetime.fromisoformat(last_offline).date()).days
                    print(f"[OFFLINE] {url} -> Offline for {days_offline} day(s)")
                else:
                    print(f"[OFFLINE] {url} -> Offline (unknown duration)")
            elif status == "missing":
                missing_links += 1
                print(f"[MISSING] {url} -> No link provided")

    elapsed = time.time() - start_time
    print(f"\nTotal channels: {total_channels}")
    print(f"Total online links: {online_links}")
    print(f"Total offline links: {offline_links}")
    print(f"Total missing links: {missing_links}")
    print(f"Total runtime: {elapsed:.2f} seconds")

def sort_channels(channels):
    """Sort channels by group then channel name."""
    return dict(
        sorted(
            channels.items(),
            key=lambda item: (
                item[1].get("group", "").lower(),  # sort by group
                item[0].lower()                    # then by channel name
            )
        )
    )

def main():
    start_time = time.time()

    # Load JSON
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        channels = json.load(f)

    # Update status in parallel
    update_status_parallel(channels)

    # Sort channels by group then name
    channels_sorted = sort_channels(channels)

    # Save updated and sorted JSON
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(channels_sorted, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Updated {JSON_FILE} with online/offline/missing status and sorted by group/name.")

    # Print summary
    summarize(channels_sorted, start_time)

if __name__ == "__main__":
    main()
