import re
import subprocess
import concurrent.futures
import functools
import time

# Force print to flush immediately (real-time logging in GitHub Actions)
print = functools.partial(print, flush=True)

# File names
YT_FILE = "YT_playlist.m3u"
WORKING_FILE = "Working_Playlist.m3u"
OUTPUT_FILE = "combined.m3u"

# Group order
GROUP_ORDER = [
    "Entertainment",
    "News",
    "News India",
    "International News",
    "Sports",
    "Religious",
    "Kids",
]

# FFmpeg check toggle
FFMPEG_CHECK = True

# FFmpeg fast mode toggle
FAST_MODE = False

# Max retries for FFmpeg
RETRIES = 3

# Lists to track online/offline channels
ONLINE_CHANNELS = []
OFFLINE_CHANNELS = []

def parse_m3u(file_path):
    """Parse M3U file and return list of (header, link, group)."""
    channels = []
    with open(file_path, encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    header, link = None, None
    for line in lines:
        line = line.strip()
        if line.startswith("#EXTINF"):
            header = line
            match = re.search(r'group-title="([^"]+)"', line)
            group = match.group(1) if match else "Other"
        elif line and not line.startswith("#"):
            link = line
            if header and link:
                channels.append((header, link, group))
            header, link = None, None
    return channels

def save_m3u(channels, output_file):
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for header, link, _ in channels:
            f.write(f"{header}\n{link}\n")

def check_ffmpeg(stream):
    """Check if stream is playable using FFmpeg with retries."""
    header, url, group = stream
    channel_name = header.split(",")[-1].strip() if "," in header else url

    if FAST_MODE:
        ffmpeg_cmd = ["ffmpeg", "-probesize", "500000", "-analyzeduration", "500000",
                      "-i", url, "-t", "1", "-f", "null", "-"]
    else:
        ffmpeg_cmd = ["ffmpeg", "-probesize", "1000000", "-analyzeduration", "1000000",
                      "-i", url, "-t", "2", "-f", "null", "-"]

    for attempt in range(1, RETRIES + 2):
        print(f"[Checking] {channel_name} (Attempt {attempt})")
        try:
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=15)
            if "error" not in result.stderr.lower():
                print(f"[ONLINE] {channel_name}")
                ONLINE_CHANNELS.append(channel_name)
                return (header, url, group)
        except Exception:
            pass
        if attempt <= RETRIES:
            print(f"[Retry {attempt}] {channel_name} failed, retrying...")

    print(f"[OFFLINE] {channel_name}")
    OFFLINE_CHANNELS.append(channel_name)
    return None

def main():
    start_time = time.time()

    # Parse YouTube playlist
    print("Parsing YouTube playlist (no FFmpeg check)...")
    yt_channels = parse_m3u(YT_FILE)
    print(f"{len(yt_channels)} channels found in {YT_FILE}\n")

    # Parse Working playlist
    print("Parsing Working playlist...")
    working_channels = parse_m3u(WORKING_FILE)
    print(f"{len(working_channels)} channels found in {WORKING_FILE}\n")

    # FFmpeg validation
    valid_working = []
    if FFMPEG_CHECK:
        print(f"Checking {len(working_channels)} streams via FFmpeg {'(fast mode)' if FAST_MODE else '(full mode)'}...\n")
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = executor.map(check_ffmpeg, working_channels)
            for res in results:
                if res:
                    valid_working.append(res)
        print(f"\n✅ {len(valid_working)} valid streams found in Working playlist")
    else:
        print("Skipping FFmpeg check for Working playlist.")
        valid_working = working_channels

    # Combine lists
    all_channels = yt_channels + valid_working

    # Deduplicate by link
    unique = {}
    for h, l, g in all_channels:
        if l not in unique:
            unique[l] = (h, l, g)

    # Sort by group order
    def group_key(item):
        g = item[2]
        if g in GROUP_ORDER:
            return GROUP_ORDER.index(g)
        return len(GROUP_ORDER)

    sorted_channels = sorted(unique.values(), key=group_key)

    # Save combined playlist
    save_m3u(sorted_channels, OUTPUT_FILE)
    print(f"\n✅ Combined playlist saved as {OUTPUT_FILE}")

    # Summary
    print(f"\n=== SUMMARY ===")
    print(f"Total online channels: {len(ONLINE_CHANNELS)}")
    for ch in ONLINE_CHANNELS:
        print(f" - {ch}")
    print(f"\nTotal offline channels: {len(OFFLINE_CHANNELS)}")
    for ch in OFFLINE_CHANNELS:
        print(f" - {ch}")

    print(f"\n⏱ Total script time: {time.time() - start_time:.2f} seconds")

if __name__ == "__main__":
    main()
