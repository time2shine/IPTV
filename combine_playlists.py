import json
import re
import functools
import time
from datetime import datetime, timezone, timedelta

# Force print to flush immediately
print = functools.partial(print, flush=True)

# File names
YT_FILE = "YT_playlist.m3u"
JSON_FILE = "static_channels.json"
MOVIES_FILE = "static_movies.json"
CTG_FUN_MOVIES_JSON = "static_movies(ctgfun).json"   # NEW
OUTPUT_FILE = "combined.m3u"

# (Removed) All movie M3Us files; replaced by CTG_FUN_MOVIES_JSON
# MOVIE_M3U_FILES = [
#     "(ctgfun)Movies_Hindi_Dubbed.m3u",
#     "(ctgfun)Movies_English.m3u",
#     "(ctgfun)Movies_Hindi.m3u",
#     # add more here...
# ]

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
    "Movies - Hindi Dubbed",
]

# Movie groups for special sorting (year desc, then name asc)
MOVIE_GROUPS = {
    "Movies - Bangla",
    "Movies - English",
    "Movies - Hindi",
    "Movies - Hindi Dubbed",
}

RECENT_DAYS = 30  # "recent" window for ctgfun movies


def parse_m3u(file_path):
    """Parse M3U file and return list of (header, link, group, tvg_id, tvg_logo, is_movie=False)."""
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
                channels.append((header, link, group, tvg_id, tvg_logo, False))  # Not a movie M3U
            header, link = None, None
    return channels


def generate_tvg_id(name):
    """Generate a safe tvg-id from channel/movie name."""
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
            channels.append((header, online_link, group, tvg_id, tvg_logo, False))
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


def language_to_group(language: str) -> str:
    """Map language to target movie group."""
    if not language:
        return "Movies"
    lang = language.strip().lower()
    if lang == "english":
        return "Movies - English"
    if lang == "hindi":
        return "Movies - Hindi"
    if lang in {"hindi dubbed", "hindi-dubbed", "hindi dub", "hindi-dub"}:
        return "Movies - Hindi Dubbed"
    return "Movies"


def parse_ctgfun_movies_json(file_path):
    """
    Parse ctgfun-style movies JSON:
    {
      "Title": {
        "year": "2025",
        "tvg_logo": "...",
        "links": [
          {"url": "...", "added": "YYYY-MM-DD", "language": "English", "source": "..."},
          ...
        ]
      }, ...
    }

    Returns list of tuples:
    (header, link, group, tvg_id, tvg_logo, is_movie, meta_dict)
    where meta_dict contains {"year": int|-1, "recent": bool}
    """
    out = []
    now = datetime.now(timezone.utc)
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)

    for title, info in data.items():
        year_str = info.get("year")
        # Normalize year to int or -1
        try:
            year_val = int(year_str) if year_str else -1
        except Exception:
            year_val = -1

        tvg_logo = info.get("tvg_logo")
        tvg_id = generate_tvg_id(title)

        links = info.get("links", [])
        if not links:
            continue

        first = links[0]
        link = first.get("url")
        if not link:
            continue

        language = first.get("language", "")
        group = language_to_group(language)

        # Determine "recent" by added date within RECENT_DAYS
        recent = False
        added = first.get("added")
        if added:
            try:
                # Interpret 'added' as naive local date; treat as UTC midnight for comparison
                added_dt = datetime.fromisoformat(added).replace(tzinfo=timezone.utc)
                recent = (now - added_dt) <= timedelta(days=RECENT_DAYS)
            except Exception:
                recent = False

        display_name = f"{title} ({year_val})" if year_val != -1 else title
        header = f'#EXTINF:-1 group-title="{group}",{display_name}'

        # Pack meta so sort can prioritize recent first, then year desc, then name asc
        meta = {"year": year_val, "recent": recent}
        out.append((header, link, group, tvg_id, tvg_logo, True, meta))

    return out


def extract_year_from_title(title: str) -> int:
    """
    Prefer a year in trailing parentheses, e.g., 'Name (1991)'.
    Fallback: first 19xx/20xx anywhere.
    Returns -1 when not found so 'no-year' items sort last.
    """
    m = re.search(r'\((19|20)\d{2}\)\s*$', title)
    if m:
        return int(m.group(0)[1:5])  # strip parens and cast
    m = re.search(r'\b(19|20)\d{2}\b', title)
    return int(m.group(0)) if m else -1


def save_m3u(channels, output_file):
    """Save combined channels to M3U file with normalized headers."""
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for item in channels:
            # Support both 6-tuple (legacy) and 7-tuple (with meta) entries
            if len(item) == 7:
                header, link, group, tvg_id, tvg_logo, _, _meta = item
            else:
                header, link, group, tvg_id, tvg_logo, _ = item

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

    print(f"Parsing ctgfun Movies JSON: {CTG_FUN_MOVIES_JSON} ...")
    ctgfun_channels = parse_ctgfun_movies_json(CTG_FUN_MOVIES_JSON)
    print(f"{len(ctgfun_channels)} items found in {CTG_FUN_MOVIES_JSON}\n")

    # Combine all
    combined_channels = (
        json_channels
        + yt_channels
        + movie_channels
        + ctgfun_channels   # new unified ctgfun JSON
    )

    # Deduplicate by channel/movie name (last part after the comma in EXTINF)
    unique_by_name = {}
    removed_channels = []
    for item in combined_channels:
        # Support both 6-tuple and 7-tuple entries
        header = item[0]
        channel_name = header.split(",", 1)[-1].strip()
        if channel_name not in unique_by_name:
            unique_by_name[channel_name] = item
        else:
            removed_channels.append(channel_name)

    if removed_channels:
        print(f"Removed {len(removed_channels)} duplicate channels: {removed_channels}")

    unique_channels = list(unique_by_name.values())

    # Group channels
    groups = {}
    for item in unique_channels:
        # item may be 6-tuple or 7-tuple
        group = item[2]
        groups.setdefault(group, []).append(item)

    # Sort channels in each group
    for g_name, ch_list in groups.items():
        # Is this a movie group or a group consisting entirely of movie items?
        is_movie_group = (g_name in MOVIE_GROUPS) or all((len(x) >= 6 and x[5] is True) for x in ch_list)

        if is_movie_group:
            # Sort with "recent first", then year desc, then name asc.
            def movie_sort_key(x):
                header = x[0]
                name = header.split(",", 1)[-1].strip().lower()
                # If we have meta from ctgfun JSON, prefer it; else derive year from title
                if len(x) == 7 and isinstance(x[6], dict):
                    meta = x[6]
                    year = meta.get("year", -1)
                    recent = meta.get("recent", False)
                else:
                    year = extract_year_from_title(header.split(",", 1)[-1].strip())
                    recent = False  # only ctgfun JSON participates in the "recent pin" rule
                recent_rank = 0 if recent else 1
                return (recent_rank, -int(year) if isinstance(year, int) else -1, name)

            groups[g_name] = sorted(ch_list, key=movie_sort_key)

        else:
            # Alphabetical by name for regular channel groups
            groups[g_name] = sorted(
                ch_list, key=lambda x: x[0].split(",", 1)[-1].strip().lower()
            )

    # Sort groups by predefined order, then any others alphabetically
    sorted_channels = []
    for g in GROUP_ORDER + sorted([k for k in groups.keys() if k not in GROUP_ORDER]):
        sorted_channels.extend(groups.get(g, []))

    save_m3u(sorted_channels, OUTPUT_FILE)
    print(f"✅ Combined playlist saved as {OUTPUT_FILE}")
    print(f"⏱ Total script time: {time.time() - start_time:.2f} seconds")


if __name__ == "__main__":
    main()
