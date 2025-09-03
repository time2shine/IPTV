import json
import subprocess
import concurrent.futures
import functools
import time

# Force print to flush immediately
print = functools.partial(print, flush=True)

JSON_FILE = "static_channels.json"

# Channels to skip FFmpeg check (optional)
EXCLUDE_LIST = [
    "Republic Bangla",
    "Republic Bharat",
    "Aaj Tak HD",
    "Aaj Tak",
    "India Today",
]

# FFmpeg fast mode toggle
FAST_MODE = False

# Max retries for FFmpeg
RETRIES = 3

# Lists to track status
ONLINE_CHANNELS = []
OFFLINE_CHANNELS = []

def check_ffmpeg(url, channel_name):
    """Check if m3u8 stream is playable via FFmpeg."""
    if any(skip.lower() in channel_name.lower() for skip in EXCLUDE_LIST):
        print(f"[SKIPPED] {channel_name}")
        return "online"

    ffmpeg_cmd = [
        "ffmpeg",
        "-probesize", "1000000",
        "-analyzeduration", "1000000",
        "-i", url,
        "-t", "2",
        "-f", "null", "-"
    ]
    if FAST_MODE:
        ffmpeg_cmd = [
            "ffmpeg",
            "-probesize", "500000",
            "-analyzeduration", "500000",
            "-i", url,
            "-t", "1",
            "-f", "null", "-"
        ]

    for attempt in range(1, RETRIES + 2):
        try:
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=15)
            if "error" not in result.stderr.lower():
                print(f"[ONLINE] {channel_name}")
                return "online"
        except Exception:
            pass

    print(f"[OFFLINE] {channel_name}")
    return "offline"

def process_channel(channel_name, channel_data):
    """Check all links for a single channel and update their status."""
    for link in channel_data.get("links", []):
        url = link.get("url")
        status = check_ffmpeg(url, channel_name)
        link["status"] = status
        if status == "online":
            ONLINE_CHANNELS.append(f"{channel_name}: {url}")
        else:
            OFFLINE_CHANNELS.append(f"{channel_name}: {url}")
    return channel_name, channel_data

def main():
    start_time = time.time()

    with open(JSON_FILE, "r", encoding="utf-8") as f:
        channels = json.load(f)

    print(f"Checking {len(channels)} channels from {JSON_FILE}...\n")

    # Use ThreadPoolExecutor for parallel FFmpeg checks
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(process_channel, name, data): name for name, data in channels.items()}
        for future in concurrent.futures.as_completed(futures):
            name, updated_data = future.result()
            channels[name] = updated_data

    # Save updated JSON
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(channels, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Status check complete. Updated JSON saved as {JSON_FILE}")
    print(f"\n=== SUMMARY ===")
    print(f"Total online streams: {len(ONLINE_CHANNELS)}")
    for ch in ONLINE_CHANNELS:
        print(f" - {ch}")
    print(f"\nTotal offline streams: {len(OFFLINE_CHANNELS)}")
    for ch in OFFLINE_CHANNELS:
        print(f" - {ch}")
    print(f"\n⏱ Total script time: {time.time() - start_time:.2f} seconds")

if __name__ == "__main__":
    main()
