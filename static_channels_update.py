import json
import time
import requests
import functools
import subprocess
import os, shutil
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
RETRIES = 2                    # Retries for FFmpeg attempts
FAST_MODE = False              # True = faster/lighter FFmpeg probe
MAX_WORKERS = 100              # Parallel workers for link checks
JSON_FILE = "static_channels.json"

# HTTP header probe
HEAD_RETRIES = 3
HEAD_TIMEOUT = 5               # seconds per attempt

# FFmpeg probe
FFMPEG_TIMEOUT = 20            # subprocess timeout (seconds)
FFMPEG_TEST_DURATION = 2       # seconds of demuxing work
MAX_ALLOWED_DURATION = 12      # classify above this as "slow" (still online)
FFMPEG_ANALYZE = 1_000_000     # reduced when FAST_MODE
FFMPEG_PROBESIZE = 1_000_000   # reduced when FAST_MODE

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
    "Connection": "keep-alive",
}

# Content-type heuristics
INVALID_CONTENT = []
VALID_CONTENT = [
    "application/vnd.apple.mpegurl",
    "application/x-mpegurl",
    "application/mpegurl",
    "audio/x-mpegurl",
    "audio/mpegurl",
    "video/mp2t",
    "video/mp4",
    "video",
]

# Fatal patterns to detect in ffmpeg stderr
FATAL_PATTERNS = [
    # HTTP / network errors
    r"404 not found", r"403 forbidden", r"400 bad request", r"401 unauthorized",
    r"402 payment required", r"405 method not allowed", r"406 not acceptable",
    r"407 proxy authentication required", r"408 request timeout", r"409 conflict",
    r"410 gone", r"411 length required", r"412 precondition failed",
    r"413 payload too large", r"414 uri too long", r"415 unsupported media type",
    r"416 range not satisfiable", r"417 expectation failed",
    r"500 internal server error", r"501 not implemented", r"502 bad gateway",
    r"503 service unavailable", r"504 gateway timeout",
    r"505 http version not supported", r"connection refused", r"connection failed",
    r"network error", r"http error", r"timed out", r"failed to resolve",
    r"server returned 403", r"server returned 404", r"temporary failure",
    r"cannot connect",
    # Codec / format errors
    r"invalid data found", r"could not find codec parameters", r"no stream",
    r"empty packet", r"no timestamps", r"invalid nal unit", r"non-monotonous dts",
    r"corrupt", r"moov atom not found", r"unknown format", r"codec not found",
    r"unsupported codec", r"cannot decode", r"missing sample", r"invalid pts",
    r"invalid frame", r"cannot open input", r"cannot open output",
    # Streaming / playlist issues
    r"empty playlist", r"invalid m3u8", r"missing segment", r"segment not found",
    r"failed to open segment", r"unable to parse", r"stream error",
    r"protocol not found", r"unexpected eof", r"playlist parsing error",
    r"could not connect to server", r"discontinuity", r"fragment not found",
    r"key frame not found",
    # DRM / encryption / access control
    r"drm", r"encrypted", r"encryption", r"decryption", r"no key", r"sample-aes",
    r"fairplay", r"skd://", r"crypto", r"#ext-x-session-key", r"#ext-x-key",
    r"license server", r"unauthorized", r"permission denied", r"auth failed",
    r"access denied",
    # Generic / fallback
    r"error", r"failed", r"unable to", r"invalid", r"stall", r"buffer",
    r"packet loss", r"timeout", r"connection reset", r"connection closed",
    r"reset by peer", r"refused", r"broken pipe",
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
    "https://amg00721-amg00721c6-freelivesports-emea-9595.playouts.now.amagi.tv/ts-eu-w1-n2/playlist/amg00721-inverleigh-unbtn3row-freelivesportsemea",
    "https://d35j504z0x2vu2.cloudfront.net/v1/master/0bc8e8376bd8417a1b6761138aa41c26c7309312/euronews",
    "https://d35j504z0x2vu2.cloudfront.net/v1/master/0bc8e8376bd8417a1b6761138aa41c26c7309312/mastiii",
    "https://amg01448-samsungin-news18bangla-samsungin-ad-qy.amagi.tv",
    "http://mdstrm.com/live-stream-playlist/57b4dc126338448314449d0c",
    "https://yupptvcatchupire.yuppcdn.net/preview/colorsbanglahd",
    "https://vg-republictvlive.akamaized.net/v1/master",
    "https://indiatodaylive.akamaized.net",
    "http://103.73.107.122:3255/TSportsHD",
    "http://116.90.120.149:8000/play",
    "https://streams.spacetoon.com",
    "https://live.dinesh29.com",
    "https://feeds.intoday.in",
    "http://mtv.sunplex.live",
    "http://185.236.230.212",
    "http://cdn01.palki.tv",
    "http://103.182.170.32",
    "http://103.78.255.178",
]

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def is_excluded(channel_name: str) -> bool:
    return any(skip.lower() in channel_name.lower() for skip in EXCLUDE_LIST)


def is_whitelisted(url: str) -> bool:
    return any(domain in (url or "") for domain in WHITELIST_DOMAINS)


def ffmpeg_header_arg() -> list:
    """Build FFmpeg header-related CLI args from HEADERS dict."""
    ua = HEADERS.get("User-Agent")
    header_lines = []
    for k, v in HEADERS.items():
        if k.lower() == "user-agent":
            continue
        header_lines.append(f"{k}: {v}")
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
    if cookies:
        args += [f"--http-header-fields=Cookie: {cookies}"]
    return args


def resolve_url(url: str) -> Tuple[str, str]:
    """Follow redirects and gather cookies for header injection in ffmpeg/mpv."""
    session = requests.Session()
    try:
        r = session.get(url, headers=HEADERS, allow_redirects=True, timeout=20, stream=True)
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

    # Build ffmpeg command
    base = [
        "ffmpeg",
        *ffmpeg_header_arg(),
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "2",
        "-loglevel", "error",
        "-i", final_url,
        "-t", str(FFMPEG_TEST_DURATION),
        "-f", "null", "-",
    ]

    if FAST_MODE:
        # lighter demuxing parameters
        base = [
            "ffmpeg",
            *ffmpeg_header_arg(),
            "-probesize", str(FFMPEG_PROBESIZE // 2),
            "-analyzeduration", str(FFMPEG_ANALYZE // 2),
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

# -----------------------------------------------------------------------------
# JSON traversal + status update (parallel)
# -----------------------------------------------------------------------------

def update_status_parallel(channels: Dict[str, Dict]):
    """Update status of all links with HEAD → FFmpeg → MPV pipeline."""

    def task(channel_name: str, link_entry: Dict):
        """Returns (url, status, note, dur_seconds, via)"""
        url = link_entry.get("url")
        if not url:
            return "", "missing", "no url", None, "missing"

        # Skip excluded channels
        if is_excluded(channel_name):
            print(f"[SKIPPED] {channel_name}")
            return url, "online", "excluded", None, "excluded"

        # Whitelist domains → trust online without probing
        if is_whitelisted(url):
            print(f"[WHITELISTED] {channel_name} -> {url}")
            return url, "online", "whitelisted", None, "whitelist"

        ok_head, reason = head_pass(url)
        if not ok_head:
            print(f"[HEAD-FAIL] {channel_name} | {reason or 'no reason'} -> {url}")
            return url, "offline", "head", None, "head_fail"

        status, dur, note = ffmpeg_check(url)

        if status in ("online", "slow"):
            print(f"🟢 {channel_name} (ffmpeg) {dur:.1f}s -> {url}")
            return url, "online", note or "ffmpeg", dur, "ffmpeg"
        elif status == "mpv_online":
            print(f"🟢 {channel_name} (mpv) {dur:.1f}s -> {url}")
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
# Sorting, summarize, maintenance (mostly unchanged)
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
      1) non-whitelisted ONLINE links, sorted by speed DESC (fastest first)
         (tiny tie-breaker: prefer ffmpeg over mpv)
      2) WHITELISTED ONLINE
      3) OFFLINE
      4) MISSING
    """
    def key_fn(link: Dict):
        url = (link.get("url") or "")
        status = link.get("status", "unknown")
        is_wl = is_whitelisted(url)
        spd = float(link.get("speed") or 0.0)  # higher is better
        via = (link.get("passed_via") or "").lower()

        # buckets
        bucket_wl   = 1 if is_wl else 0
        bucket_off  = 1 if status == "offline" else 0
        bucket_miss = 1 if status == "missing" else 0

        # prefer ffmpeg slightly on ties (subtract a tiny epsilon from MPV when sorting)
        mpv_penalty = 0.01 if via == "mpv" else 0.0

        # We sort ascending, so invert speed (negate) and add penalty
        return (bucket_wl, bucket_off, bucket_miss, -(spd - mpv_penalty))

    for info in channels.values():
        links = info.get("links")
        if isinstance(links, list) and links:
            links.sort(key=key_fn)

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main():
    start_time = time.time()

    # Load JSON
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        channels = json.load(f)

    # Update status in parallel with HEAD→FFmpeg→MPV
    update_status_parallel(channels)

    # Sort channels by group then name
    channels_sorted = sort_channels(channels)

    # Mark links offline for 10+ days by emptying URL
    mark_old_offline_links(channels_sorted, days_threshold=10)

    # 🔝 Reorder links by speed (fastest first), whitelists last
    reorder_links(channels_sorted)

    # Save updated and sorted JSON
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(channels_sorted, f, ensure_ascii=False, indent=2)
    print("\n")
    print("\n")
    print(f"\n✅ Updated {JSON_FILE} with head/ffmpeg/mpv checks, speed metrics, pass backend, "
          f"reset URLs for old offline links, and sorted by group/name with per-channel link reordering.")
    print("\n")
    print("\n")

    # Print summary
    summarize(channels_sorted, start_time)

    # ✅ Export excluded + whitelisted playlist
    export_excluded_whitelisted(channels_sorted)


if __name__ == "__main__":
    main()
