from dataclasses import dataclass
from collections import defaultdict
from datetime import datetime, timezone, timedelta
import json, re, functools, time

print = functools.partial(print, flush=True)

YT_FILE = "YT_playlist.m3u"
JSON_FILE = "static_channels.json"
MOVIES_FILE = "static_movies.json"
CTG_FUN_MOVIES_JSON = "scripts/static_movies(ctgfun).json"
OUTPUT_FILE = "combined.m3u"
RECENT_TAG = " 🆕"
RECENT_DAYS = 30

GROUP_ORDER = [
    "Bangla",
    "Bangla News",
    "International News",
    "India","Pakistan",
    "Movies",
    "Educational",
    "Music",
    "International",
    "Travel",
    "Sports",
    "Religious",
    "Kids",
    "Movies - Bangla",
    "Movies - English",
    "Movies - Hindi",
    "Movies - Hindi Dubbed",
]

MOVIE_GROUPS = {
    "Movies - Bangla",
    "Movies - English",
    "Movies - Hindi",
    "Movies - Hindi Dubbed"}

# ---------- helpers

@dataclass
class Item:
    header: str
    link: str
    group: str
    tvg_id: str | None
    tvg_logo: str | None
    is_movie: bool
    year: int = -1
    name: str = ""
    recent: bool = False
    source_rank: int = 99  # lower is preferred (0=ctgfun json, 1=movies json, 2=yt/json, 3=m3u)

def channel_display_name(header: str) -> str:
    return header.split(",", 1)[-1].strip()

def normalize_year(y) -> int:
    try:
        if y is None or y == "": return -1
        return int(y)
    except Exception:
        return -1

def extract_year_from_title(title: str) -> int:
    m = re.search(r'\((19|20)\d{2}\)\s*$', title)
    if m: return int(m.group(0)[1:5])
    m = re.search(r'\b(19|20)\d{2}\b', title)
    return int(m.group(0)) if m else -1

def is_recent(date_str: str | None, days: int) -> bool:
    if not date_str: return False
    try:
        dt = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt) <= timedelta(days=days)
    except Exception:
        return False

def generate_tvg_id(name): return re.sub(r'[^A-Za-z0-9_]', '_', name.strip())

def language_to_group(language: str | None) -> str:
    if not language: return "Movies"
    key = language.strip().lower()
    mapping = {
        "english": "Movies - English", "en": "Movies - English", "eng": "Movies - English",
        "hindi": "Movies - Hindi",
        "hindi dubbed": "Movies - Hindi Dubbed", "hindi-dubbed": "Movies - Hindi Dubbed",
        "hindi dub": "Movies - Hindi Dubbed", "hindi-dub": "Movies - Hindi Dubbed",
        "dual audio": "Movies - Hindi Dubbed",
    }
    return mapping.get(key, "Movies")

# ---------- existing parsers lightly adapted to create Item

def parse_m3u(path: str) -> list[Item]:
    out = []
    with open(path, encoding="utf-8", errors="ignore") as f:
        lines = [ln.strip() for ln in f]
    header = link = group = tvg_id = tvg_logo = None
    for ln in lines:
        if ln.startswith("#EXTINF"):
            header = ln
            group = (re.search(r'group-title="([^"]+)"', ln) or [None,"Other"])[1]
            tvg_id = (re.search(r'tvg-id="([^"]*)"', ln) or [None,None])[1]
            tvg_logo = (re.search(r'tvg-logo="([^"]*)"', ln) or [None,None])[1]
        elif ln and not ln.startswith("#"):
            link = ln
            if header and link:
                name = channel_display_name(header)
                out.append(Item(header, link, group, tvg_id, tvg_logo, False, name=name, source_rank=3))
            header = link = None
    return out

def parse_json_channels(path: str) -> list[Item]:
    out = []
    with open(path, encoding="utf-8") as f: data = json.load(f)
    for name, info in data.items():
        group = info.get("group", "Other")
        tvg_id = info.get("tvg_id") or generate_tvg_id(name)
        tvg_logo = info.get("tvg_logo")
        links = info.get("links", [])
        online = next((l["url"] for l in links if l.get("status") == "online"), None)
        if online:
            header = f'#EXTINF:-1 group-title="{group}",{name}'
            out.append(Item(header, online, group, tvg_id, tvg_logo, False, name=name, source_rank=2))
    return out

def parse_movies_json(path: str) -> list[Item]:
    out = []
    with open(path, encoding="utf-8") as f: data = json.load(f)
    for title, info in data.items():
        group = info.get("group", "Movies")
        year = normalize_year(info.get("year"))
        tvg_logo = info.get("tvg_logo")
        tvg_id = generate_tvg_id(title)
        links = info.get("links", [])
        online = next((l["url"] for l in links if l.get("status") == "online"), None)
        if online:
            name = f"{title} ({year})" if year != -1 else title
            header = f'#EXTINF:-1 group-title="{group}",{name}'
            out.append(Item(header, online, group, tvg_id, tvg_logo, True, year=year, name=name, source_rank=1))
    return out


def parse_ctgfun_movies_json(path: str) -> list[Item]:
    out = []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    for title, info in data.items():
        year = normalize_year(info.get("year"))
        tvg_logo = info.get("tvg_logo")
        tvg_id = generate_tvg_id(title)

        links = info.get("links", [])
        if not links:
            continue

        first = links[0]
        link = first.get("url")
        if not link:
            continue

        group = language_to_group(first.get("language"))
        recent = is_recent(first.get("added"), RECENT_DAYS)

        base_name = f"{title} ({year})" if year != -1 else title
        # Add the NEW tag only for recent items
        name = base_name + RECENT_TAG if recent else base_name

        header = f'#EXTINF:-1 group-title="{group}",{name}'
        out.append(
            Item(
                header, link, group, tvg_id, tvg_logo, True,
                year=year, name=name, recent=recent, source_rank=0
            )
        )
    return out


# ---------- output

def save_m3u(items: list[Item], output_file: str):
    _EPG_URL = "https://raw.githubusercontent.com/time2shine/IPTV/refs/heads/master/epg.xml"
    with open(output_file, "w", encoding="utf-8") as f:
        # Write header with EPG for better player compatibility
        header_attrs = f'url-tvg="{_EPG_URL}" x-tvg-url="{_EPG_URL}"' if _EPG_URL else ""
        f.write(f"#EXTM3U {header_attrs}\n")
        for it in items:
            base, name = it.header.split(",", 1)[0], it.name
            if it.tvg_id:
                base = re.sub(r'tvg-id="[^"]*"', f'tvg-id="{it.tvg_id}"', base) if 'tvg-id="' in base else f'{base} tvg-id="{it.tvg_id}"'
            if it.tvg_logo:
                base = re.sub(r'tvg-logo="[^"]*"', f'tvg-logo="{it.tvg_logo}"', base) if 'tvg-logo="' in base else f'{base} tvg-logo="{it.tvg_logo}"'
            f.write(f"{base},{name}\n{it.link}\n")

# ---------- main (same behavior)

def main():
    start = time.time()
    yt = parse_m3u(YT_FILE)
    print(f"{len(yt)} channels found in {YT_FILE}")
    chans = parse_json_channels(JSON_FILE)
    print(f"{len(chans)} online channels found in {JSON_FILE}")
    movies = parse_movies_json(MOVIES_FILE)
    print(f"{len(movies)} online movie channels found in {MOVIES_FILE}")
    ctg = parse_ctgfun_movies_json(CTG_FUN_MOVIES_JSON)
    print(f"{len(ctg)} items found in {CTG_FUN_MOVIES_JSON}")

    combined = chans + yt + movies + ctg

    # Dedup by display name, prefer richer/“better” source
    by_name: dict[str, Item] = {}
    removed = []
    for it in combined:
        key = it.name or channel_display_name(it.header)
        if key not in by_name:
            by_name[key] = it
        else:
            cur = by_name[key]
            # Prefer lower source_rank, then has logo, then recent, then newer year
            cand = min(
                (cur, it),
                key=lambda x: (x.source_rank, 0 if x.tvg_logo else 1, 0 if x.recent else 1, -x.year)
            )
            removed.append(key) if cand is it else removed.append(key)  # just to log duplicates
            by_name[key] = cand
    if removed:
        print(f"Removed {len(removed)} duplicate names")

    groups = defaultdict(list)
    for it in by_name.values():
        groups[it.group].append(it)

    # Sort inside groups
    for g, lst in groups.items():
        is_movie_group = (g in MOVIE_GROUPS) or all(it.is_movie for it in lst)
        if is_movie_group:
            lst.sort(key=lambda x: (0 if x.recent else 1, -x.year, x.name.lower()))
        else:
            lst.sort(key=lambda x: x.name.lower())

    # Group order
    out = []
    for g in GROUP_ORDER + sorted(k for k in groups.keys() if k not in GROUP_ORDER):
        out.extend(groups.get(g, []))

    save_m3u(out, OUTPUT_FILE)
    print(f"✅ Combined playlist saved as {OUTPUT_FILE}")
    print(f"⏱ Total script time: {time.time()-start:.2f} seconds")

if __name__ == "__main__":
    main()
