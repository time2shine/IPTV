import json
import subprocess
import functools
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# Force print to flush immediately
print = functools.partial(print, flush=True)

# Config
JSON_FILE = "static_channels.json"
FAST_MODE = True       # True = fast FFmpeg, False = full/slow check
RETRIES = 3
MAX_WORKERS = 10       # Parallel FFmpeg threads
EXCLUDE_LIST = ["Republic Bangla", "Republic Bharat", "Aaj Tak HD", "Aaj Tak", "India Today"]

def check_ffmpeg(url, channel_name):
    """Check if a stream is playable with FFmpeg retries."""
    if any(skip.lower() in channel_name.lower() for skip in EXCLUDE_LIST):
        print(f"[SKIPPED] {channel_name}")
        return url, "online"

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
                return url, "online"
        except Exception:
            pass

    print(f"[OFFLINE] {channel_name} -> {url}")
    return url, "offline"

def update_status_parallel(channels):
    """Update status of all links using parallel FFmpeg checks."""
    tasks = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for channel_name, info in channels.items():
            for i, link_entry in enumerate(info["links"]):
                if isinstance(link_entry, str):
                    info["links"][i] = {"url": link_entry, "status": "unknown"}
                    link_entry = info["links"][i]

                url = link_entry["url"]
                tasks.append(executor.submit(check_ffmpeg, url, channel_name))

        # Collect results and update JSON
        for future in as_completed(tasks):
            url, status = future.result()
            for info in channels.values():
                for link_entry in info["links"]:
                    if link_entry["url"] == url:
                        link_entry["status"] = status

def summarize(channels, start_time):
    """Print summary of online/offline links and total runtime."""
    total_channels = len(channels)
    online_links = sum(
        1 for info in channels.values() for link in info["links"] if link.get("status") == "online"
    )
    offline_links = sum(
        1 for info in channels.values() for link in info["links"] if link.get("status") == "offline"
    )
    elapsed = time.time() - start_time

    print("\n=== SUMMARY ===")
    print(f"Total channels: {total_channels}")
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
