import re

# File names
INPUT_FILES = ["YT_playlist.m3u", "Working_Playlist.m3u"]
OUTPUT_FILE = "combined.m3u"

# Group order
GROUP_ORDER = [
    "Entertainment",
    "News",
    "News India",
    "International News",
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
            # extract group-title
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


def main():
    all_channels = []
    for file in INPUT_FILES:
        all_channels.extend(parse_m3u(file))

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
        return len(GROUP_ORDER)  # others go at the bottom

    sorted_channels = sorted(unique.values(), key=group_key)

    save_m3u(sorted_channels, OUTPUT_FILE)
    print(f"✅ Combined playlist saved as {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
