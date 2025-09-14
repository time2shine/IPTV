import json
import re
import functools
import time

# Force print to flush immediately
print = functools.partial(print, flush=True)

# File names
YT_FILE = "YT_playlist.m3u"
JSON_FILE = "static_channels.json"
MOVIES_FILE = "static_movies.json"
OUTPUT_FILE = "combined.m3u"

# Group order
GROUP_ORDER = [
    "Bangla",
    "Bangla News",
    "International News",
    "India",
    "Pakistan",
    "Movies",
    "Educational",
    "Music",
    "International",
    "Technology",
    "Travel",
    "Sports",
    "Religious",
    "Kids",
    "Movies - Bangla",
    "Movies - English",
    "Movies - Hindi",
]

def parse_m3u(file_path):
    """Parse M3U file and return list of (header, link, group, tvg_id, tvg_logo, is_movie)."""
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
                channels.append((header, link, group, tvg_id, tvg_logo, False))  # Not a movie JSON
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
        tvg_id = info.get("tvg_id") or generate_tvg_id(channel_name)
        tvg_logo = info.get("tvg_logo")

        links = info.get("links", [])
        online_link = next((l["url"] for l in links if l.get("status") == "online"), None)
        if online_link:
            header = f'#EXTINF:-1 group-title="{group}",{channel_name}'
            channels.append((header, online_link, group, tvg_id, tvg_logo, False))  # Not a movie JSON
    return channels

def parse_movies_json(file_path):
    """Parse movies JSON and extract first online link, adding year to name. Preserve order."""
    channels = []
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)

    for movie_name, info in data.items():
        group = info.get("group", "Movies")
        year = info.get("year")
        tvg_logo = info.get("tvg_logo")
        tvg_id = generate_tvg_id(movie_name)

        display_name = f"{movie_name} ({year})" if year else movie_name

        links = info.get("links", [])
        online_link = next((l["url"] for l in links if l.get("status") == "online"), None)
        if online_link:
            header = f'#EXTINF:-1 group-title="{group}",{display_name}'
            channels.append((header, online_link, group, tvg_id, tvg_logo, True))  # Flag as movie JSON
    return channels

def save_m3u(channels, output_file):
    """Save combined channels to M3U file with normalized headers."""
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for header, link, group, tvg_id, tvg_logo, _ in channels:
            parts = header.split(",", 1)
            base_header = parts[0]
            channel_name = parts[1] if len(parts) > 1 else ""

            if tvg_id:
                if 'tvg-id="' in base_header:
                    base_header = re.sub(r'tvg-id="[^"]*"', f'tvg-id="{tvg_id}"', base_header)
                else:
                    base_header += f' tvg-id="{tvg_id}"'

            if tvg_logo:
                if 'tvg-logo="' in base_header:
                    base_header = re.sub(r'tvg-logo="[^"]*"', f'tvg-logo="{tvg_logo}"', base_header)
                else:
                    base_header += f' tvg-logo="{tvg_logo}"'

            new_header = f"{base_header},{channel_name}"
            f.write(f"{new_header}\n{link}\n")

def main():
    start_time = time.time()

    print("Parsing YouTube playlist...")
    yt_channels = parse_m3u(YT_FILE)
    print(f"{len(yt_channels)} channels found in {YT_FILE}\n")

    print("Parsing JSON playlist...")
    json_channels = parse_json(JSON_FILE)
    print(f"{len(json_channels)} online channels found in {JSON_FILE}\n")

    print("Parsing Movies JSON playlist...")
    movie_channels = parse_movies_json(MOVIES_FILE)
    print(f"{len(movie_channels)} online movie channels found in {MOVIES_FILE}\n")

    # Combine all
    combined_channels = yt_channels + json_channels + movie_channels

    # Deduplicate by channel name
    unique_by_name = {}
    removed_channels = []
    for h, l, g, tid, logo, is_movie in combined_channels:
        channel_name = h.split(",")[-1].strip()
        if channel_name not in unique_by_name:
            unique_by_name[channel_name] = (h, l, g, tid, logo, is_movie)
        else:
            removed_channels.append(channel_name)

    if removed_channels:
        print(f"Removed {len(removed_channels)} duplicate channels: {removed_channels}")

    unique_channels = list(unique_by_name.values())

    # Group channels
    groups = {}
    for h, l, g, tid, logo, is_movie in unique_channels:
        groups.setdefault(g, []).append((h, l, g, tid, logo, is_movie))

    # Sort channels in each group
    for g_name, ch_list in groups.items():
        # Preserve order if any channel in group came from movies JSON
        if any(is_movie for _, _, _, _, _, is_movie in ch_list):
            groups[g_name] = ch_list
        else:
            groups[g_name] = sorted(ch_list, key=lambda x: x[0].split(",")[-1].strip().lower())

    # Sort groups by predefined order
    sorted_channels = []
    for g in GROUP_ORDER + sorted([k for k in groups.keys() if k not in GROUP_ORDER]):
        sorted_channels.extend(groups.get(g, []))

    save_m3u(sorted_channels, OUTPUT_FILE)
    print(f"✅ Combined playlist saved as {OUTPUT_FILE}")
    print(f"⏱ Total script time: {time.time() - start_time:.2f} seconds")

if __name__ == "__main__":
    main()
