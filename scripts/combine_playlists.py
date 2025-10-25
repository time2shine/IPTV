from dataclasses import dataclass
from collections import defaultdict
from datetime import datetime, timezone, timedelta
import json, re, functools, time

print = functools.partial(print, flush=True)

YT_FILE = "YT_playlist.m3u"
JSON_FILE = "static_channels.json"
MOVIES_FILE = "static_movies.json"
CTG_FUN_MOVIES_JSON = "scripts/static_movies(ctgfun).json"
CINEHUB_MOVIES_JSON = "scripts/static_movies(cinehub24).json"  # NEW
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
    "Movies - Hindi Dubbed"
}

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
    # lower is preferred (0 = ctgfun/cinehub json, 1 = movies json, 2 = yt/json, 3 = m3u)
    source_rank: int = 99

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

def parse_iso_utc(date_str: str | None) -> datetime | None:
    """Parse ISO-like strings to UTC; return None if invalid/missing."""
    if not date_str:
        return None
    try:
        s = date_str.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt
    except Exception:
        return None

def is_recent(date_str: str | None, days: int) -> bool:
    dt = parse_iso_utc(date_str)
    if not dt: return False
    return (datetime.now(timezone.utc) - dt) <= timedelta(days=days)

def generate_tvg_id(name): return re.sub(r'[^A-Za-z0-9_]', '_', name.strip())

def language_to_group(language: str | None) -> str:
    if not language:
        return "Movies"
    key = language.strip().lower()
    mapping = {
        # English
        "english": "Movies - English", "en": "Movies - English", "eng": "Movies - English",
        # Hindi (+ dubbed buckets)
        "hindi": "Movies - Hindi",
        "hindi dubbed": "Movies - Hindi Dubbed", "hindi-dubbed": "Movies - Hindi Dubbed",
        "hindi dub": "Movies - Hindi Dubbed", "hindi-dub": "Movies - Hindi Dubbed",
        "dual audio": "Movies - Hindi Dubbed",
        # Bangla / Bengali
        "bangla": "Movies - Bangla", "bn": "Movies - Bangla",
        "bengali": "Movies - Bangla",
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
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
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
    """
    static_movies.json: same shape as ctgfun but may include 'status'.
    - choose_best_link() handles 'status' if present
    - group is derived from chosen link.language
    - recent tag uses chosen link.added
    """
    out = []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    for title, info in data.items():
        year = normalize_year(info.get("year"))
        tvg_logo = info.get("tvg_logo")
        tvg_id = generate_tvg_id(title)
        links = info.get("links", [])

        chosen = choose_best_link(links)
        if not chosen:
            continue

        link = chosen["url"]
        group = language_to_group(chosen.get("language"))
        recent = is_recent(chosen.get("added"), RECENT_DAYS)

        base_name = f"{title} ({year})" if year != -1 else title
        name = base_name + RECENT_TAG if recent else base_name

        header = f'#EXTINF:-1 group-title="{group}",{name}'
        out.append(Item(
            header, link, group, tvg_id, tvg_logo, True,
            year=year, name=name, recent=recent, source_rank=1
        ))
    return out

def choose_best_link(links: list[dict]) -> dict | None:
    """
    Prefer the first link that is explicitly online (if 'status' is present),
    otherwise fall back to the first link that simply has a URL.
    Works for both ctgfun (no status) and static_movies (with status).
    """
    if not links:
        return None
    online = next((l for l in links if l.get("url") and l.get("status") == "online"), None)
    if online:
        return online
    return next((l for l in links if l.get("url")), None)

# ---------- NEW: ctgfun/cinehub loader with "latest link wins" across files

def _choose_latest_link_by_added(links: list[dict]) -> dict | None:
    """
    For ctgfun-like sources (no status), choose the link with the most recent 'added' timestamp.
    If none have a parseable 'added', fall back to the first link with a URL.
    """
    if not links:
        return None
    with_url = [l for l in links if l.get("url")]
    if not with_url:
        return None
    dated = [(parse_iso_utc(l.get("added")), l) for l in with_url]
    valid = [pair for pair in dated if pair[0] is not None]
    if valid:
        # newest by datetime
        return max(valid, key=lambda x: x[0])[1]
    return with_url[0]

def parse_ctg_style_movies_json(paths: list[str]) -> list[Item]:
    """
    Load multiple ctgfun-like movie JSON files and consolidate by title.
    If a title exists in multiple files, pick the link with the latest 'added' timestamp across files.
    """
    best_by_title: dict[str, dict] = {}  # title -> {year, tvg_logo, link(dict), added_dt, language}
    total_titles = 0

    for path in paths:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            print(f"⚠️  File not found: {path}")
            continue

        total_titles += len(data)
        for title, info in data.items():
            year = normalize_year(info.get("year"))
            tvg_logo = info.get("tvg_logo")
            links = info.get("links", [])

            chosen = _choose_latest_link_by_added(links)
            if not chosen:
                continue

            cand_added_dt = parse_iso_utc(chosen.get("added"))
            cand_language = chosen.get("language")
            record = best_by_title.get(title)

            if (record is None) or (
                (cand_added_dt and (record["added_dt"] is None or cand_added_dt > record["added_dt"]))
            ):
                best_by_title[title] = dict(
                    year=year,
                    tvg_logo=tvg_logo or (record.get("tvg_logo") if record else None),
                    link=chosen,
                    added_dt=cand_added_dt,
                    language=cand_language,
                )
            else:
                if record["tvg_logo"] in (None, "") and tvg_logo:
                    record["tvg_logo"] = tvg_logo

    out: list[Item] = []
    for title, rec in best_by_title.items():
        year = rec["year"]
        tvg_logo = rec["tvg_logo"]
        tvg_id = generate_tvg_id(title)
        chosen = rec["link"]
        link = chosen["url"]
        group = language_to_group(rec["language"])
        recent = is_recent(chosen.get("added"), RECENT_DAYS)

        base_name = f"{title} ({year})" if year != -1 else title
        name = base_name + RECENT_TAG if recent else base_name

        header = f'#EXTINF:-1 group-title="{group}",{name}'
        out.append(Item(
            header, link, group, tvg_id, tvg_logo, True,
            year=year, name=name, recent=recent, source_rank=0
        ))

    print(f"{len(out)} items consolidated from ctg-style sources: {', '.join(paths)} (scanned {total_titles} titles)")
    return out

# ---------- output

def save_m3u(items: list[Item], output_file: str):
    _EPG_URL = "https://raw.githubusercontent.com/time2shine/IPTV/refs/heads/master/epg.xml"
    with open(output_file, "w", encoding="utf-8") as f:
        header_attrs = f'url-tvg="{_EPG_URL}" x-tvg-url="{_EPG_URL}"' if _EPG_URL else ""
        f.write(f"#EXTM3U {header_attrs}\n")
        for it in items:
            base, name = it.header.split(",", 1)[0], it.name
            if it.tvg_id:
                base = re.sub(r'tvg-id="[^"]*"', f'tvg-id="{it.tvg_id}"', base) if 'tvg-id="' in base else f'{base} tvg-id="{it.tvg_id}"'
            if it.tvg_logo:
                base = re.sub(r'tvg-logo="[^"]*"', f'tvg-logo="{it.tvg_logo}"', base) if 'tvg-logo="' in base else f'{base} tvg-logo="{it.tvg_logo}"'
            f.write(f"{base},{name}\n{it.link}\n")

# ---------- main

def main():
    start = time.time()
    yt = parse_m3u(YT_FILE)
    print(f"{len(yt)} channels found in {YT_FILE}")
    chans = parse_json_channels(JSON_FILE)
    print(f"{len(chans)} online channels found in {JSON_FILE}")
    movies = parse_movies_json(MOVIES_FILE)
    print(f"{len(movies)} online movie channels found in {MOVIES_FILE}")

    # NEW: consolidate ctgfun + cinehub24 (latest link wins per title)
    ctg_like = parse_ctg_style_movies_json([CTG_FUN_MOVIES_JSON, CINEHUB_MOVIES_JSON])

    combined = chans + yt + movies + ctg_like

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
            removed.append(key)
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
