from dataclasses import dataclass
from collections import defaultdict, Counter
from datetime import datetime, timezone, timedelta
import json, re, functools, time, os

# ---------- simple console helpers (no colors)

def banner(title: str):
    bar = "-" * len(title)
    print(bar)
    print(title)
    print(bar)

def kv(label: str, value: str, icon: str = "•"):
    print(f"{icon} {label}: {value}")

# Flush prints by default (useful for GitHub Actions)
print = functools.partial(print, flush=True)

# ---------- config

YT_FILE = "YT_playlist.m3u"
JSON_FILE = "static_channels.json"
MOVIES_FILE = "static_movies.json"
CTG_FUN_MOVIES_JSON = "scripts/static_movies(ctgfun).json"
CINEHUB_MOVIES_JSON = "scripts/static_movies(cinehub24).json"
Infobase_MOVIES_JSON = "scripts/static_movies(103.225.94.27).json"
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
    "Movies - Other",
]

MOVIE_GROUPS = {
    "Movies - Bangla",
    "Movies - English",
    "Movies - Hindi",
    "Movies - Hindi Dubbed",
    "Movies - Other",
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
    added_dt: datetime | None = None  # <-- MODIFIED
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
    """
    Map a language/category label from movie JSON links to your playlist group names.
    Unknown values default to "Movies - Other".
    """
    if not language:
        return "Movies - Other"

    key = language.strip().lower()

    # Keep groups centralized so you don't repeat strings everywhere
    groups = {
        "bangla": "Movies - Bangla",
        "english": "Movies - English",
        "hindi": "Movies - Hindi",
        "hindi_dubbed": "Movies - Hindi Dubbed",
        "other": "Movies - Other",
    }

    mapping = {
        # --- English ---
        "english": groups["english"],
        "en": groups["english"],
        "eng": groups["english"],

        # --- Hindi ---
        "hindi": groups["hindi"],

        # --- Hindi Dubbed / Dual ---
        "hindi dubbed": groups["hindi_dubbed"],
        "hindi-dubbed": groups["hindi_dubbed"],
        "hindi dub": groups["hindi_dubbed"],
        "hindi-dub": groups["hindi_dubbed"],
        "dual audio": groups["hindi_dubbed"],
        "dual-audio": groups["hindi_dubbed"],

        # --- Bangla / Bengali ---
        "bangla": groups["bangla"],
        "bn": groups["bangla"],
        "bengali": groups["bangla"],

        # --- Other buckets (Infobase / mixed categories) ---
        "other": groups["other"],
        "korean": groups["other"],
        "china": groups["other"],
        "chinese": groups["other"],
        "japanese": groups["other"],
    }

    return mapping.get(key, groups["other"])

# --- NEW HELPER FUNCTION ---
def get_movie_sort_key(x: Item):
    """
    Generates a sort key for movies:
    1. Recent items (group 0) vs. Non-recent (group 1)
    2. Recent items are sorted by added_dt descending.
       - Achieved by sorting (MAX_DATE - added_dt) ascending.
       - None/missing dates are treated as oldest (datetime.min), sorting them last.
    3. Non-recent items are sorted by year descending (-x.year).
    4. Tie-breaker is name ascending.
    """
    if x.recent:
        # Group 0: Recent
        # Use min datetime for None to sort them last (largest time delta)
        added_dt_safe = x.added_dt if x.added_dt else datetime.min.replace(tzinfo=timezone.utc)
        # Sort by (MAX_DATE - added_dt) ascending, which is date descending
        # Use total_seconds() for a simple sortable number
        sort_key = (datetime.max.replace(tzinfo=timezone.utc) - added_dt_safe).total_seconds()
        return (0, sort_key, x.name.lower())
    else:
        # Group 1: Non-recent
        # Sort by year descending
        sort_key = -x.year
        return (1, sort_key, x.name.lower())

# ---------- parsers

def parse_m3u(path: str) -> list[Item]:
    out = []
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            lines = [ln.strip() for ln in f]
    except FileNotFoundError:
        print(f"⚠️  {path} not found. Skipping.")
        return out

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
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"⚠️  {path} not found. Skipping.")
        return out
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
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"⚠️  {path} not found. Skipping.")
        return out

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

        # --- MODIFICATION START ---
        added_dt = parse_iso_utc(chosen.get("added")) # Parse once
        recent = False
        if added_dt:
            recent = (datetime.now(timezone.utc) - added_dt) <= timedelta(days=RECENT_DAYS)
        # --- MODIFICATION END ---

        base_name = f"{title} ({year})" if year != -1 else title
        name = base_name + RECENT_TAG if recent else base_name

        header = f'#EXTINF:-1 group-title="{group}",{name}'
        out.append(Item(
            header, link, group, tvg_id, tvg_logo, True,
            year=year, name=name, recent=recent,
            added_dt=added_dt,  # <-- PASS THE PARSED DATE
            source_rank=1
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

# ---------- NEW: ctgfun/cinehub consolidation (latest link wins)

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
    Prints overlap and winning-source counts.
    """
    best_by_title: dict[str, dict] = {}  # title_lower -> {year, tvg_logo, link, added_dt, language, origin, title_orig}
    titles_per_source: dict[str, set] = {}
    recent_count = 0

    print("🎬 Consolidating ctg-style movie sources")
    for path in paths:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            titles = set(data.keys())
            titles_per_source[path] = titles
            kv("Loaded", f"{len(titles)} titles from {path}", "📥")
        except FileNotFoundError:
            print(f"⚠️  {path} not found. Skipping.")
            titles_per_source[path] = set()
            continue

        for title, info in data.items():
            key = title.lower() # <-- MODIFICATION: Use lowercase key for lookup
            year = normalize_year(info.get("year"))
            tvg_logo = info.get("tvg_logo")
            links = info.get("links", [])

            chosen = _choose_latest_link_by_added(links)
            if not chosen:
                continue

            cand_added_dt = parse_iso_utc(chosen.get("added"))
            cand_language = chosen.get("language")
            record = best_by_title.get(key) # <-- MODIFICATION: Get by lowercase key

            if (record is None) or (cand_added_dt and (record["added_dt"] is None or cand_added_dt > record["added_dt"])):
                best_by_title[key] = dict( # <-- MODIFICATION: Set by lowercase key
                    year=year,
                    tvg_logo=tvg_logo or (record.get("tvg_logo") if record else None),
                    link=chosen,
                    added_dt=cand_added_dt,
                    language=cand_language,
                    origin=path,
                    title_orig=title, # <-- MODIFICATION: Store the original title of the winner
                )
            else:
                if record["tvg_logo"] in (None, "") and tvg_logo:
                    record["tvg_logo"] = tvg_logo

    # overlap & winners
    nonempty_sets = [titles_per_source[p] for p in paths if titles_per_source.get(p) is not None]
    overlap = set.intersection(*nonempty_sets) if (nonempty_sets and len(nonempty_sets) >= 2) else set()
    print(f"🧮 Overlap across ctg-style files: {len(overlap)} titles")

    winners = Counter()
    for rec in best_by_title.values():
        winners[rec["origin"]] += 1
        
        # --- MODIFIED: Use the parsed added_dt for recent check ---
        if rec["added_dt"] and (datetime.now(timezone.utc) - rec["added_dt"]) <= timedelta(days=RECENT_DAYS):
            recent_count += 1
            
    if winners:
        detail = ", ".join([f"{os.path.basename(src)}: {cnt}" for src, cnt in winners.items()])
        print(f"🏁 Winning source counts (ctg-style): {detail}")
    print(f"🆕 Recent (≤{RECENT_DAYS} days) from ctg-style picks: {recent_count}")

    # Emit items
    out: list[Item] = []
    for key, rec in best_by_title.items(): # <-- MODIFICATION: key is lowercase, rec has our data
        title = rec["title_orig"] # <-- MODIFICATION: Get the original-cased title
        year = rec["year"]
        tvg_logo = rec["tvg_logo"]
        tvg_id = generate_tvg_id(title)
        chosen = rec["link"]
        link = chosen["url"]
        group = language_to_group(rec["language"])

        # --- MODIFICATION START ---
        added_dt = rec["added_dt"] # Get the stored datetime object
        recent = False
        if added_dt:
            recent = (datetime.now(timezone.utc) - added_dt) <= timedelta(days=RECENT_DAYS)
        # --- MODIFICATION END ---

        base_name = f"{title} ({year})" if year != -1 else title
        name = base_name + RECENT_TAG if recent else base_name

        header = f'#EXTINF:-1 group-title="{group}",{name}'
        out.append(Item(
            header, link, group, tvg_id, tvg_logo, True,
            year=year, name=name, recent=recent,
            added_dt=added_dt,  # <-- PASS THE PARSED DATE
            source_rank=0
        ))

    print(f"📦 Consolidated ctg-style items: {len(out)}")
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
    banner("🎛️  IPTV Playlist Builder")

    # Load sources
    print("📂 Reading sources…")
    yt = parse_m3u(YT_FILE)
    kv("M3U channels", str(len(yt)), "📼")

    chans = parse_json_channels(JSON_FILE)
    kv("Static channels (online)", str(len(chans)), "📡")

    movies = parse_movies_json(MOVIES_FILE)
    kv("static_movies.json (online)", str(len(movies)), "🎞️")

    # Consolidate ctgfun + cinehub24 (latest link wins per title)
    ctg_like = parse_ctg_style_movies_json([CTG_FUN_MOVIES_JSON, CINEHUB_MOVIES_JSON, Infobase_MOVIES_JSON])

    # Combine & deduplicate
    print("\n🧩 Combining and de-duplicating…")
    combined = chans + yt + movies + ctg_like

    by_name: dict[str, Item] = {}
    duplicates_removed = 0
    for it in combined:
        # <-- MODIFICATION START
        base_name = it.name or channel_display_name(it.header)
        key = base_name.lower()
        # <-- MODIFICATION END
        
        if key not in by_name:
            by_name[key] = it
        else:
            cur = by_name[key]
            # Prefer lower source_rank, then has logo, then recent, then newer year
            chosen = min(
                (cur, it),
                # Note: 'recent' and 'year' logic is for DE-DUPLICATION preference,
                # not final sorting. This logic remains correct.
                key=lambda x: (x.source_rank, 0 if x.tvg_logo else 1, 0 if x.recent else 1, -x.year)
            )
            if chosen is not cur:
                by_name[key] = chosen
            duplicates_removed += 1

    if duplicates_removed:
        print(f"🔁 Removed duplicate names: {duplicates_removed}")
    else:
        print("🔁 No duplicate names found.")

    # Grouping & sorting
    groups = defaultdict(list)
    for it in by_name.values():
        groups[it.group].append(it)

    for g, lst in groups.items():
        is_movie_group = (g in MOVIE_GROUPS) or all(it.is_movie for it in lst)
        
        # --- MODIFICATION START ---
        if is_movie_group:
            lst.sort(key=get_movie_sort_key) # <-- USE THE NEW HELPER
        else:
            lst.sort(key=lambda x: x.name.lower())
        # --- MODIFICATION END ---

    # Group order
    out = []
    for g in GROUP_ORDER + sorted(k for k in groups.keys() if k not in GROUP_ORDER):
        out.extend(groups.get(g, []))

    save_m3u(out, OUTPUT_FILE)

    # ---------- Summary
    elapsed = time.time() - start
    print("")  # spacer
    banner("📊 Build Summary")

    kv("Input counts",
       f"M3U={len(yt)} • Channels={len(chans)} • static_movies={len(movies)} • ctg/cinehub={len(ctg_like)}",
       "🗂️")

    kv("Output items", str(len(out)), "✅")
    kv("Duplicates removed", str(duplicates_removed), "🔁")

    # Per-group distribution
    print("🧭 Group distribution:")
    for g in GROUP_ORDER + sorted(k for k in groups.keys() if k not in GROUP_ORDER):
        if g in groups:
            print(f"  - {g}: {len(groups[g])}")

    kv("Saved as", OUTPUT_FILE, "💾")
    kv("Elapsed", f"{elapsed:.2f}s", "⏱")
    print("\n✨ Done. Enjoy!")

if __name__ == "__main__":
    main()
