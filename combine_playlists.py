import re
import subprocess
import concurrent.futures

# File names
YT_FILE = "YT_playlist.m3u"
WORKING_FILE = "Working_Playlist.m3u"
OUTPUT_FILE = "combined.m3u"

# Enable/disable FFmpeg checking
CHECK_FFMPEG = True  # Set to False to skip FFmpeg validation

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
    """Check if stream is playable using FFmpeg (fast check)."""
    header, url, group = stream
    # Extract channel name from header
    name = header.split(",")[-1].strip() if "," in header else url
    try:
        result = subprocess.run(
            ["ffmpeg", "-probesize", "500000", "-analyzeduration", "500000",
             "-i", url, "-t", "1", "-f", "null", "-"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if "error" not in result.stderr.lower():
            print(f"[ONLINE] {name}")
            return (header, url, group)
    except Exception:
        pass
    print(f"[OFFLINE] {name}")
    return None

def main():
    print("Parsing YouTube playlist (no FFmpeg check)...")
    yt_channels = parse_m3u(YT_FILE)

    print("Parsing Working playlist...")
    working_channels = parse_m3u(WORKING_FILE)

    valid_working = []
    if CHECK_FFMPEG:
        print(f"Checking {len(working_channels)} streams from {WORKING_FILE} via FFmpeg (fast mode)...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            results = executor.map(check_ffmpeg, working_channels)
            for res in results:
                if res:
                    valid_working.append(res)
        print(f"{len(valid_working)} valid streams found in {WORKING_FILE}")
    else:
        print("Skipping FFmpeg check for Working_Playlist.m3u")
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
        return GROUP_ORDER.index(g) if g in GROUP_ORDER else len(GROUP_ORDER)

    sorted_channels = sorted(unique.values(), key=group_key)
    save_m3u(sorted_channels, OUTPUT_FILE)
    print(f"✅ Combined playlist saved as {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
