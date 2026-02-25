import json
import time
import requests
import functools
import subprocess
import os, shutil
import tempfile
import random
from datetime import datetime, date
from typing import Tuple, Optional, Dict
from concurrent.futures import ThreadPoolExecutor

# -----------------------------------------------------------------------------
# Instant-flush prints
# -----------------------------------------------------------------------------
print = functools.partial(print, flush=True)

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
RETRIES = 2                     # Retries for FFmpeg attempts
FAST_MODE = False               # True = faster/lighter FFmpeg probe
# Cap worker pool to keep sockets/CPU sane
MAX_WORKERS = 120
JSON_FILE = "static_channels.json"

# HTTP header probe
HEAD_RETRIES = 3
HEAD_TIMEOUT = 5                # seconds per attempt

# FFmpeg probe
FFMPEG_TIMEOUT = 20             # subprocess timeout (seconds)
FFMPEG_TEST_DURATION = 2        # seconds of demuxing work
MAX_ALLOWED_DURATION = 12       # classify above this as "slow" (still online)
FFMPEG_ANALYZE = 1_000_000      # reduced when FAST_MODE
FFMPEG_PROBESIZE = 1_000_000    # reduced when FAST_MODE

# MPV fallback probe (used only if FFmpeg fails)
MPV_TIMEOUT = 150
MPV_EXECUTABLE = os.getenv("MPV_PATH", "mpv")
HAS_MPV = shutil.which(MPV_EXECUTABLE) is not None

# HTTP headers commonly required by some origins/CDNs
HEADERS: Dict[str, str] = {
    "User-Agent": "VLC/3.0.18 LibVLC/3.0.18",
    "Referer": "https://live.dinesh29.com.np/",
    "Origin": "https://live.dinesh29.com.np",
    "Accept": "*/*",
    # "Connection" intentionally omitted; requests manages keep-alive
}

# Content-type heuristics
INVALID_CONTENT = []
VALID_CONTENT = [
    "application/vnd.apple.mpegurl",
    "application/octet-stream",
    "application/x-mpegurl",
    "application/mpegurl",
    "audio/x-mpegurl",
    "audio/mpegurl",
    "video/mp2t",
    "video/mp4",
    "video",
]

# Focused fatal patterns (avoid generic "error"/"failed")
FATAL_PATTERNS = [
    # HTTP / network errors
    "404 not found", "403 forbidden", "400 bad request", "401 unauthorized",
    "connection refused", "failed to resolve", "timed out", "network error",
    "server returned 403", "server returned 404", "gateway timeout",
    # Codec / format errors
    "invalid data found", "no stream", "could not find codec parameters",
    "unsupported codec", "unknown format",
    # Streaming / playlist issues
    "empty playlist", "invalid m3u8", "missing segment", "playlist parsing error",
    # DRM / encryption / access control
    "drm", "encrypted", "encryption", "no key", "#ext-x-session-key", "#ext-x-key",
]

# -----------------------------------------------------------------------------
# Your existing lists (preserved)
# -----------------------------------------------------------------------------
EXCLUDE_LIST = [
    # "NEWS | Republic Bharat",
    # "NEWS | Aaj Tak HD",
]

# ✅ Whitelist domains (any URL containing these will be auto-marked as online)
WHITELIST_DOMAINS = [
    "https://app24.jagobd.com.bd/c3VydmVyX8RpbEU9Mi8xNy8yMFDDEHGcfRgzQ6NTAgdEoaeFzbF92YWxIZTO0U0ezN1IzMyfvcEdsEfeDeKiNkVN3PTOmdFsaWRtaW51aiPhnPTI2/atnws-sg.stream",
    "https://app24.jagobd.com.bd/c3VydmVyX8RpbEU9Mi8xNy8yMFDDEHGcfRgzQ6NTAgdEoaeFzbF92YWxIZTO0U0ezN1IzMyfvcEdsEfeDeKiNkVN3PTOmdFsaWRtaW51aiPhnPTI2/gazibdz.stream",
    "https://amg00721-amg00721c6-freelivesports-emea-9595.playouts.now.amagi.tv/ts-eu-w1-n2/playlist/amg00721-inverleigh-unbtn3row-freelivesportsemea",
    "https://amg01448-samsungin-cnbcawaaznw18-samsungin-ad-wj.amagi.tv/ts-ap-s1-n1/playlist/amg01448-samsungin-cnbcawaaznw18-samsungin",
    "https://amg01448-samsungin-cnnnewsnw18-samsungin-ad-gv.amagi.tv/ts-eu-w1-n2/playlist/amg01448-samsungin-cnnnewsnw18-samsungin",
    "https://amg01448-samsungin-abpananda-samsungin-ad-pw.amagi.tv/ts-ap-s1-n1/playlist/amg01448-samsungin-abpananda-samsungin",
    "https://amg01412-xiaomiasia-zee24ghantaa-xiaomi-cvo5n.amagi.tv/playlist/amg01412-xiaomiasia-zee24ghantaa-xiaomi",
    "https://d35j504z0x2vu2.cloudfront.net/v1/master/0bc8e8376bd8417a1b6761138aa41c26c7309312/euronews",
    "https://d35j504z0x2vu2.cloudfront.net/v1/master/0bc8e8376bd8417a1b6761138aa41c26c7309312/mastiii",
    "https://amg01448-samsungin-news18bangla-samsungin-ad-qy.amagi.tv",
    "http://mdstrm.com/live-stream-playlist/57b4dc126338448314449d0c",
    "https://amg01448-samsungin-tv9bangla-samsungin-9lgnh.amagi.tv",
    "https://amg13643-amg13643c1-amgplt0016.playout.now3.amagi.tv",
    "https://yupptvcatchupire.yuppcdn.net/preview/colorsbanglahd",
    "https://livehub-voidnet.onrender.com/cluster/streamcore/in",
    "https://vg-republictvlive.akamaized.net/v1/master",
    "https://premierleagpl23.akamaized.net",
    "https://indiatodaylive.akamaized.net",
    "http://103.73.107.122:3255/TSportsHD",
    "https://streams.spacetoon.com",
    "https://owrcovcrpy.gpcdn.net",
    "http://al.hls.huya.com/src",
    "https://feeds.intoday.in",
    "http://103.230.105.252",
    "http://cdn01.palki.tv",
    "http://103.182.170.32",
    "http://live.iill.top",
]

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def is_excluded(channel_name: str) -> bool:
    return any(skip.lower() in channel_name.lower() for skip in EXCLUDE_LIST)


def is_whitelisted(url: str) -> bool:
    return any(domain in (url or "") for domain in WHITELIST_DOMAINS)


def ffmpeg_header_arg(extra_cookie: str = "") -> list:
    """Build FFmpeg header-related CLI args from HEADERS dict + optional cookies."""
    ua = HEADERS.get("User-Agent")
    header_lines = []
    for k, v in HEADERS.items():
        if k.lower() == "user-agent":
            continue
        header_lines.append(f"{k}: {v}")
    if extra_cookie:
        header_lines.append(f"Cookie: {extra_cookie}")
    headers_blob = "\r\n".join(header_lines)

    args = []
    if ua:
        args += ["-user_agent", ua]
    if headers_blob:
        args += ["-headers", headers_blob]
    return args


def mpv_header_args(cookies: str = "") -> list:
    """Build MPV header-related CLI args from HEADERS dict."""
    args = []
    if HEADERS.get("User-Agent"):
        args += [f"--http-header-fields=User-Agent: {HEADERS['User-Agent']}"]
    if HEADERS.get("Referer"):
        args += [f"--http-header-fields=Referer: {HEADERS['Referer']}"]
    if HEADERS.get("Origin"):
        args += [f"--http-header-fields=Origin: {HEADERS['Origin']}"]
    args += ["--http-header-fields=Accept: */*"]
    if cookies:
        args += [f"--http-header-fields=Cookie: {cookies}"]
    return args


def resolve_url(url: str) -> Tuple[str, str]:
    """Follow redirects and gather cookies for header injection in ffmpeg/mpv."""
    try:
        with requests.Session() as session:
            with session.get(url, headers=HEADERS, allow_redirects=True, timeout=20, stream=True) as r:
                cookies = r.cookies.get_dict()
                final_url = r.url
        cookie_header = "; ".join([f"{k}={v}" for k, v in cookies.items()])
        return final_url, cookie_header
    except Exception:
        return url, ""


def _is_valid_content_type(ct: str) -> bool:
    ct = (ct or "").lower()
    if any(ic in ct for ic in INVALID_CONTENT):
        return False
    if any(v in ct for v in VALID_CONTENT):
        return True
    return False


def head_pass(url: str) -> Tuple[bool, Optional[str]]:
    """HEAD (then light GET) probe. Return (ok, reason_if_any)."""
    last_error = None
    for _ in range(HEAD_RETRIES):
        try:
            r = requests.head(url, headers=HEADERS, allow_redirects=True, timeout=HEAD_TIMEOUT)
            ct = r.headers.get("Content-Type", "")
            if _is_valid_content_type(ct):
                return True, None
            last_error = f"HEAD content-type={ct or 'n/a'}"
        except Exception as e_head:
            last_error = f"HEAD error: {e_head}"
        try:
            r2 = requests.get(url, headers=HEADERS, allow_redirects=True, stream=True, timeout=HEAD_TIMEOUT)
            ct2 = r2.headers.get("Content-Type", "")
            r2.close()
            if _is_valid_content_type(ct2):
                return True, None
            last_error = f"GET content-type={ct2 or 'n/a'}"
        except Exception as e_get:
            last_error = f"GET error: {e_get}"
        time.sleep(0.6)

    # If it's an m3u8, still allow deeper probing
    if str(url).lower().endswith(".m3u8"):
        return True, last_error
    return False, last_error


def mpv_check(url: str, cookies: str = "", end_secs: int = 10) -> Tuple[bool, Optional[str]]:
    # ✅ Early guard: skip cleanly if mpv isn't installed/available in PATH
    if not HAS_MPV:
        return False, "MPV not available on PATH"

    cmd = [
        MPV_EXECUTABLE,
        "--no-config",             # deterministic in CI
        "--no-video",
        "--vo=null",
        "--ao=null",
        "--mute=yes",
        "--really-quiet",
        "--idle=no",
        "--cache=yes",
        "--cache-secs=2",
        "--demuxer-readahead-secs=2",
        "--network-timeout=10",
        f"--end={end_secs}",       # stop after N seconds
        *mpv_header_args(cookies),
        url,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=MPV_TIMEOUT)
        if result.returncode == 0:
            return True, None
        last = (result.stderr or "").strip().splitlines()[-1] if result.stderr else ""
        return False, f"MPV rc={result.returncode}" + (f" | {last}" if last else "")
    except subprocess.TimeoutExpired:
        return False, f"MPV timeout >{MPV_TIMEOUT}s"
    except FileNotFoundError:
        return False, f"MPV not found ('{MPV_EXECUTABLE}'). Install mpv or set MPV_PATH."
    except Exception as e:
        return False, f"MPV error: {e}"


def ffmpeg_check(url: str) -> Tuple[str, float, Optional[str]]:
    """
    Run FFmpeg probe. Returns (status, duration, note)
    status: 'online' | 'slow' | 'offline' | 'mpv_online' | 'mpv_offline'
    duration: time for the backend that actually ran (FFmpeg OR MPV), seconds
    """
    final_url, cookies = resolve_url(url)

    base = [
        "ffmpeg",
        *ffmpeg_header_arg(cookies),
        "-rw_timeout", "10000000",         # 10s read timeout (microseconds)
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "2",
        "-loglevel", "error",
        "-i", final_url,
        "-t", str(FFMPEG_TEST_DURATION),
        "-f", "null", "-",
    ]

    if FAST_MODE:
        base = [
            "ffmpeg",
            *ffmpeg_header_arg(cookies),
            "-probesize", str(FFMPEG_PROBESIZE // 2),
            "-analyzeduration", str(FFMPEG_ANALYZE // 2),
            "-rw_timeout", "10000000",
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "2",
            "-loglevel", "error",
            "-i", final_url,
            "-t", "1",
            "-f", "null", "-",
        ]

    last_stderr = ""
    for _ in range(RETRIES + 1):
        try:
            start = time.time()
            result = subprocess.run(base, capture_output=True, text=True, timeout=FFMPEG_TIMEOUT)
            dur = time.time() - start
            stderr = (result.stderr or "").lower()
            last_stderr = stderr

            if result.returncode == 0:
                if dur >= MAX_ALLOWED_DURATION:
                    return "slow", dur, None
                return "online", dur, None

            # Non-zero rc; inspect stderr for fatal patterns → MPV quick try (TIMED)
            if any((p in stderr) for p in FATAL_PATTERNS):
                t1 = time.time()
                ok, note = mpv_check(final_url, cookies, end_secs=FFMPEG_TEST_DURATION)
                dur_mpv = time.time() - t1
                return ("mpv_online" if ok else "mpv_offline"), dur_mpv, note
            else:
                # Unknown error; treat as offline (retry loop may try again)
                pass
        except subprocess.TimeoutExpired:
            # FFmpeg hung → try MPV (TIMED)
            t1 = time.time()
            ok, note = mpv_check(final_url, cookies, end_secs=FFMPEG_TEST_DURATION)
            dur_mpv = time.time() - t1
            return ("mpv_online" if ok else "mpv_offline"), dur_mpv, note
        except Exception as e:
            last_stderr = f"ffmpeg error: {e}"
        time.sleep(0.7)

    # After retries, give MPV one last shot (TIMED)
    t1 = time.time()
    ok, note = mpv_check(final_url, cookies, end_secs=FFMPEG_TEST_DURATION)
    dur_mpv = time.time() - t1
    return ("mpv_online" if ok else "mpv_offline"), dur_mpv, note or last_stderr

# -----------------------------------------------------------------------------
# File outputs preserved from your script
# -----------------------------------------------------------------------------

def export_excluded_whitelisted(channels: Dict[str, Dict]):
    """Export EXCLUDED + WHITELISTED channels into obsolete/excluded_whitelisted.m3u"""
    folder = "obsolete"
    os.makedirs(folder, exist_ok=True)  # ✅ create folder if missing

    output_file = os.path.join(folder, "excluded_whitelisted.m3u")

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")

    for channel_name, info in channels.items():
        for link in info.get("links", []):
            url = link.get("url")
            if not url:
                continue

            if is_excluded(channel_name) or is_whitelisted(url):
                with open(output_file, "a", encoding="utf-8") as f:
                    f.write(f'#EXTINF:-1 group-title="{info.get("group", "Other")}",{channel_name}\n{url}\n')

    print(f"✅ Exported excluded + whitelisted channels to {output_file}")


def export_offline(channels: Dict[str, Dict]):
    """
    Export OFFLINE channels to obsolete/offline.m3u
    Display format for the name: "Channel Name (offline days)"
    Only writes entries that still have a URL.
    """
    folder = "obsolete"
    os.makedirs(folder, exist_ok=True)

    output_file = os.path.join(folder, "offline.m3u")
    today = date.today()
    count = 0

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for channel_name, info in channels.items():
            group = info.get("group", "Other")
            for link in info.get("links", []):
                if not isinstance(link, dict):
                    continue
                if link.get("status") != "offline":
                    continue

                url = link.get("url") or ""
                if not url.strip():
                    # URL has been reset for long-offline entries; skip emitting empty URLs
                    continue

                last_offline = link.get("last_offline")
                days_str = "unknown"
                if last_offline:
                    try:
                        days = (today - datetime.fromisoformat(last_offline).date()).days
                        days_str = f"{days}d"
                    except Exception:
                        days_str = "unknown"

                display_name = f"{channel_name} ({days_str})"
                f.write(f'#EXTINF:-1 group-title="{group}",{display_name}\n{url}\n')
                count += 1

    print(f"✅ Exported {count} offline channel link(s) to {output_file}")

# -----------------------------------------------------------------------------
# JSON traversal + status update (parallel)
# -----------------------------------------------------------------------------

def update_status_parallel(channels: Dict[str, Dict]):
    """Update status of all links with HEAD → FFmpeg → MPV pipeline."""

    def task(channel_name: str, link_entry: Dict):
        """Returns (url, status, note, dur_seconds, via)"""
        # Small random jitter to avoid thundering-herd
        time.sleep(random.uniform(0, 0.2))

        url = link_entry.get("url")
        if not url:
            return "", "missing", "no url", None, "missing"

        # Skip excluded channels
        if is_excluded(channel_name):
            print(f"[SKIPPED] {channel_name}")
            return url, "online", "excluded", None, "excluded"

        # Whitelist domains → trust online without probing
        if is_whitelisted(url):
            print(f"➡️ (WHITELISTED) {channel_name} -> {url}")
            return url, "online", "whitelisted", None, "whitelist"

        ok_head, reason = head_pass(url)
        if not ok_head:
            print(f"🔴 (HEAD-FAIL) {channel_name} | {reason or 'no reason'} -> {url}")
            return url, "offline", "head", None, "head_fail"

        status, dur, note = ffmpeg_check(url)

        if status in ("online", "slow"):
            print(f"🟢 (FFMPEG) {dur:.1f}s    {channel_name}") # can add this -> {url}
            return url, "online", note or "ffmpeg", dur, "ffmpeg"
        elif status == "mpv_online":
            print(f"🟢 (MPV)    {dur:.1f}s    {channel_name}")  # can add this -> {url}
            return url, "online", note or "mpv", dur, "mpv"
        else:
            print(f"🔴 {channel_name} -> {url}")
            return url, "offline", status, dur, ("mpv" if status.startswith("mpv_") else "ffmpeg")

    # Ensure structure is sane and collect futures
    futures = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for channel_name, info in channels.items():
            # Ensure 'links' exists and is a list
            if "links" not in info or not isinstance(info["links"], list):
                info["links"] = []

            for i, link_entry in enumerate(info["links"]):
                if not link_entry:
                    info["links"][i] = {"url": None, "status": "missing", "first_online": None, "last_offline": None}
                    continue

                if isinstance(link_entry, str):
                    info["links"][i] = {"url": link_entry, "status": "unknown", "first_online": None, "last_offline": None}
                    link_entry = info["links"][i]

                link_entry.setdefault("first_online", None)
                link_entry.setdefault("last_offline", None)

                futures.append((executor.submit(task, channel_name, link_entry), channel_name, i))

        # Collect results and update JSON in-place
        today = date.today().isoformat()
        for future, ch_name, idx in futures:
            url, status, note, dur, via = future.result()
            link_entry = channels[ch_name]["links"][idx]

            link_entry["status"] = status
            # NEW: speed & timing & via
            link_entry["probe_time_s"] = round(dur, 3) if dur is not None else None
            if dur and dur > 0:
                link_entry["speed"] = round(FFMPEG_TEST_DURATION / dur, 3)
            else:
                link_entry["speed"] = 0.0
            link_entry["passed_via"] = via

            # Dates
            if status == "online":
                if link_entry.get("first_online") is None:
                    link_entry["first_online"] = today
                link_entry["last_online"] = today
                link_entry["last_offline"] = None
            elif status == "offline":
                if link_entry.get("last_offline") is None:
                    link_entry["last_offline"] = today

# -----------------------------------------------------------------------------
# Sorting, summarize, maintenance
# -----------------------------------------------------------------------------

def categorize_link(channel_name: str, url: Optional[str], status: str) -> str:
    if status == "missing":
        return "MISSING"
    if status == "offline":
        return "OFFLINE"
    if is_excluded(channel_name):
        return "EXCLUDED"
    if is_whitelisted(url or ""):
        return "WHITELISTED"
    return "ONLINE"


def summarize(channels: Dict[str, Dict], start_time: float):
    today = date.today()
    entries = []

    online_links = offline_links = missing_links = excluded_links = whitelist_links = 0

    for channel_name, info in channels.items():
        for link in info.get("links", []):
            url = link.get("url")
            status = link.get("status", "unknown")

            category = categorize_link(channel_name, url, status)

            if category == "MISSING":
                missing_links += 1
            elif category == "OFFLINE":
                offline_links += 1
            elif category == "EXCLUDED":
                excluded_links += 1
            elif category == "WHITELISTED":
                whitelist_links += 1
            elif category == "ONLINE":
                online_links += 1

            entries.append({
                "category": category,
                "channel": channel_name,
                "url": url,
                "last_offline": link.get("last_offline"),
            })

    category_order = {"MISSING": 0, "OFFLINE": 1, "EXCLUDED": 2, "WHITELISTED": 3}
    entries.sort(key=lambda x: (category_order.get(x["category"], 4), str(x["url"])) )

    print("\n=== SUMMARY ===")
    for e in entries:
        if e["category"] == "MISSING":
            continue
        elif e["category"] == "OFFLINE":
            days_offline = "unknown duration"
            if e["last_offline"]:
                days_offline = f"{(today - datetime.fromisoformat(e['last_offline']).date()).days:>5} day(s)"
            print(f"[OFFLINE] {e['channel']:<30} | Offline for {days_offline} -> {e['url']}")
        elif e["category"] == "EXCLUDED":
            print(f"[EXCLUDED] {e['channel']} -> {e['url']}")
        elif e["category"] == "WHITELISTED":
            print(f"[WHITELISTED] {e['channel']} -> {e['url']}")

    elapsed = time.time() - start_time
    m, s = divmod(int(elapsed + 0.5), 60)
    separator = "=" * 50
    print(f"\n{separator}")
    print(f"{'Total channels':<20}: {len(channels)}")
    print(f"{'Total online links':<20}: {online_links}")
    print(f"{'Total offline links':<20}: {offline_links}")
    print(f"{'Total missing links':<20}: {missing_links}")
    print(f"{'Excluded links':<20}: {excluded_links}")
    print(f"{'Whitelisted links':<20}: {whitelist_links}")
    print(f"{'Total runtime':<20}: {m}m {s}s")
    print(f"{separator}\n")


def sort_channels(channels: Dict[str, Dict]) -> Dict[str, Dict]:
    return dict(
        sorted(
            channels.items(),
            key=lambda item: (
                item[1].get("group", "").lower(),
                item[0].lower(),
            )
        )
    )


def mark_old_offline_links(channels: Dict[str, Dict], days_threshold: int = 10):
    today = date.today()
    for channel_name, info in channels.items():
        for link in info.get("links", []):
            status = link.get("status", "unknown")
            last_offline = link.get("last_offline")
            if status == "offline" and last_offline:
                last_offline_date = datetime.fromisoformat(last_offline).date()
                offline_days = (today - last_offline_date).days
                if offline_days >= days_threshold:
                    print(f"[RESET URL] {channel_name} -> Offline for {offline_days} day(s) -> {link.get('url')}")
                    link["url"] = ""


def reorder_links(channels: Dict[str, Dict]) -> None:
    """
    Reorder each channel's links:
      1) ONLINE: non-whitelisted fastest first, prefer ffmpeg on ties
      2) ONLINE: whitelisted
      3) OFFLINE
      4) MISSING
    """
    def key_fn(link: Dict):
        url = (link.get("url") or "")
        status = (link.get("status") or "unknown").lower()
        is_wl = is_whitelisted(url)
        spd = float(link.get("speed") or 0.0)  # higher is better
        via = (link.get("passed_via") or "").lower()

        # Primary: ONLINE(0) → OFFLINE(1) → MISSING(2)
        bucket_status = 0 if status == "online" else (1 if status == "offline" else 2)
        # Within ONLINE: non-whitelist(0) → whitelist(1). For non-ONLINE, keep 0 so status dominates
        bucket_wl = (1 if is_wl else 0) if bucket_status == 0 else 0

        # prefer ffmpeg slightly on ties (subtract a tiny epsilon from MPV when sorting)
        mpv_penalty = 0.01 if via == "mpv" else 0.0

        # Sort ascending; invert speed to get fastest first
        return (bucket_status, bucket_wl, -(spd - mpv_penalty))

    for info in channels.values():
        links = info.get("links")
        if isinstance(links, list) and links:
            links.sort(key=key_fn)

# -----------------------------------------------------------------------------
# I/O helpers
# -----------------------------------------------------------------------------

def _atomic_write_json(path: str, payload: Dict):
    dir_ = os.path.dirname(path) or "."
    with tempfile.NamedTemporaryFile("w", dir=dir_, delete=False, encoding="utf-8") as tmp:
        json.dump(payload, tmp, ensure_ascii=False, indent=2)
        tmp.flush()
        os.fsync(tmp.fileno())
    os.replace(tmp.name, path)

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main():
    start_time = time.time()

    # Load JSON
    try:
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            channels = json.load(f)
    except FileNotFoundError:
        print(f"❌ {JSON_FILE} not found")
        return
    except json.JSONDecodeError as e:
        print(f"❌ Malformed JSON in {JSON_FILE}: {e}")
        return

    # Update status in parallel with HEAD→FFmpeg→MPV
    update_status_parallel(channels)

    # Sort channels by group then name
    channels_sorted = sort_channels(channels)

    # Mark links offline for 10+ days by emptying URL
    mark_old_offline_links(channels_sorted, days_threshold=10)

    # 🔝 Reorder links (fastest online first; whitelists last within ONLINE)
    reorder_links(channels_sorted)

    # Save updated and sorted JSON atomically
    _atomic_write_json(JSON_FILE, channels_sorted)
    print(f"\n✅ Updated {JSON_FILE} with head/ffmpeg/mpv checks, speed metrics, pass backend, "
          f"reset URLs for old offline links, and sorted by group/name with per-channel link reordering.\n")

    # Print summary
    summarize(channels_sorted, start_time)

    # ✅ Export excluded + whitelisted playlist
    export_excluded_whitelisted(channels_sorted)

    # ✅ Export offline playlist (name includes offline duration)
    export_offline(channels_sorted)

if __name__ == "__main__":
    main()
