import json
import re
import functools
import time

# Force print to flush immediately
print = functools.partial(print, flush=True)

# File names
YT_FILE = "YT_playlist.m3u"
JSON_FILE = "static_channels.json"
OUTPUT_FILE = "combined.m3u"

# Group order
GROUP_ORDER = [
    "Bangla",
    "Bangla News",
    "International News",
    "India",
    "Pakistan",
    "Movie",
    "Educational",
    "Music",
    "International",
    "Technology",
    "Travel",
    "Sports",
    "Religious",
    "Kids",
]

def parse_m3u(file_path):
    """Parse M3U file and return list of (header, link, group, tvg_id, tvg_logo)."""
    channels = []
    with open(file_path, encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    header, link = None, None
    for line in lines:
        line = line.strip()
        if line.startswith("#EXTINF"):
            header = line
            match_group = re.search(r'group-title="([^"]+)"', line)
            group = match_group.group(1).strip() if match_group else "Other"

            match_tvg = re.search(r'tvg-id="([^"]*)"', line)
            tvg_id = match_tvg.group(1) if match_tvg else None

            match_logo = re.search(r'tvg-logo="([^"]*)"', line)
            tvg_logo = match_logo.group(1) if match_logo else None
        elif line and not line.startswith("#"):
            link = line
            if header and link:
                channels.append((header, link, group, tvg_id, tvg_logo))
            header, link = None, None
    return channels

def generate_tvg_id(name):
    """Generate a safe tvg-id from channel name."""
    return re.sub(r'[^A-Za-z0-9_]', '_', name.strip())

def parse_json(file_path):
    """Parse JSON file and extract only first online link for each channel."""
    channels = []
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)

    for channel_name, info in data.items():
        group = info.get("group", "Other")
        tvg_id = info.get("tvg_id")
        if not tvg_id:
            tvg_id = generate_tvg_id(channel_name)  # Auto-generate tvg-id
        tvg_logo = info.get("tvg_logo")  # Optional logo

        links = info.get("links", [])
        # Find first online link
        online_link = next((l["url"] for l in links if l.get("status") == "online"), None)
        if online_link:
            # Build M3U header
            header = f'#EXTINF:-1 group-title="{group}",{channel_name}'
            channels.append((header, online_link, group, tvg_id, tvg_logo))
    return channels

def save_m3u(channels, output_file):
    """Save combined channels to M3U file."""
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for header, link, group, tvg_id, tvg_logo in channels:
            new_header = header
            if tvg_id or tvg_logo:
                parts = new_header.split(",", 1)
                new_header = parts[0]
                if tvg_id:
                    new_header += f' tvg-id="{tvg_id}"'
                if tvg_logo:
                    new_header += f' tvg-logo="{tvg_logo}"'
                new_header += f',{parts[1]}'
            f.write(f"{new_header}\n{link}\n")

def main():
    start_time = time.time()

    # Parse YT playlist
    print("Parsing YouTube playlist...")
    yt_channels = parse_m3u(YT_FILE)
    print(f"{len(yt_channels)} channels found in {YT_FILE}\n")

    # Parse JSON playlist
    print("Parsing JSON playlist...")
    json_channels = parse_json(JSON_FILE)
    print(f"{len(json_channels)} online channels found in {JSON_FILE}\n")

    # Combine
    combined_channels = yt_channels + json_channels

    # Deduplicate by channel name
    unique_by_name = {}
    removed_channels = []
    for h, l, g, tid, logo in combined_channels:
        channel_name = h.split(",")[-1].strip()
        if channel_name not in unique_by_name:
            unique_by_name[channel_name] = (h, l, g, tid, logo)
        else:
            removed_channels.append(channel_name)

    if removed_channels:
        print(f"Removed {len(removed_channels)} duplicate channels: {removed_channels}")

    unique_channels = list(unique_by_name.values())

    # Group channels
    groups = {}
    for h, l, g, tid, logo in unique_channels:
        groups.setdefault(g, []).append((h, l, g, tid, logo))

    # Sort channels in each group
    for g_name, ch_list in groups.items():
        groups[g_name] = sorted(ch_list, key=lambda x: x[0].split(",")[-1].strip().lower())

    # Sort groups by predefined order
    sorted_channels = []
    for g in GROUP_ORDER + sorted([k for k in groups.keys() if k not in GROUP_ORDER]):
        sorted_channels.extend(groups.get(g, []))

    # Save combined playlist
    save_m3u(sorted_channels, OUTPUT_FILE)
    print(f"✅ Combined playlist saved as {OUTPUT_FILE}")
    print(f"⏱ Total script time: {time.time() - start_time:.2f} seconds")

if __name__ == "__main__":
    main()
