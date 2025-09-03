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
MAX_WORKERS = 20       # Parallel FFmpeg threads
EXCLUDE_LIST = ["Republic Bangla", "Republic Bharat", "Aaj Tak HD", "Aaj Tak", "India Today"]

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
    return url, "offline", None

def update_status_parallel(channels):
    """Update status of all links using parallel FFmpeg checks."""
    tasks = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for channel_name, info in channels.items():
            for i, link_entry in enumerate(info["links"]):
                # Convert string links to dict if needed
                if isinstance(link_entry, str):
                    info["links"][i] = {"url": link_entry, "status": "unknown", "last_online": None}
                    link_entry = info["links"][i]
                
                # Ensure 'last_online' key exists
                if "last_online" not in link_entry:
                    link_entry["last_online"] = None

                url = link_entry["url"]
                tasks.append(executor.submit(check_ffmpeg, url, channel_name))

        # Collect results and update JSON
        for future in as_completed(tasks):
            url, status, today = future.result()
            for info in channels.values():
                for link_entry in info["links"]:
                    if link_entry["url"] == url:
                        link_entry["status"] = status
                        if status == "online":
                            link_entry["last_online"] = today.isoformat()
                        # If offline and last_online is missing, leave as None

def summarize(channels, start_time):
    """Print summary of online/offline links and offline durations."""
    total_channels = len(channels)
    online_links = 0
    offline_links = 0
    today = date.today()

    print("\n=== SUMMARY ===")
    for info in channels.values():
        for link in info["links"]:
            if link.get("status") == "online":
                online_links += 1
            elif link.get("status") == "offline":
                offline_links += 1
                last_online = link.get("last_online")
                if last_online:
                    days_offline = (today - datetime.fromisoformat(last_online).date()).days
                    print(f"[OFFLINE] {link['url']} -> Offline for {days_offline} day(s)")
                else:
                    print(f"[OFFLINE] {link['url']} -> Offline (unknown duration)")

    elapsed = time.time() - start_time
    print(f"\nTotal channels: {total_channels}")
    print(f"Total online links: {online_links}")
    print(f"Total offline links: {offline_links}")
    print(f"Total runtime: {elapsed:.2f} seconds")

def main():
    start_time = time.time()

    # Load JSON
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        channels = json.load(f)

    # Update status in parallel
    update_status_parallel(channels)

    # Save updated JSON
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(channels, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Updated {JSON_FILE} with online/offline status.")

    # Print summary
    summarize(channels, start_time)

if __name__ == "__main__":
    main()
