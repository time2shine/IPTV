import json
import os
import subprocess
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Tuple

JSON_FILE = "static_movies.json"
WORKERS = 64  # tuned down a bit; auto-capped below
FFMPEG_BIN = os.environ.get("FFMPEG_BIN", "ffmpeg")
FFMPEG_TIMEOUT = 30  # seconds
RW_TIMEOUT_US = 15_000_000  # 15s socket timeout for ffmpeg, in microseconds

def _to_int_year(v) -> int:
    try:
        return int(str(v).strip())
    except Exception:
        return 0

def _to_date(d: str) -> datetime:
    # Accept YYYY-MM-DD; fallback to very old date if unparsable
    try:
        return datetime.fromisoformat(d.strip())
    except Exception:
        return datetime(1970, 1, 1)

def check_ffmpeg(url: str, headers: Dict[str, str] = None) -> str:
    """
    Try to open the media briefly with FFmpeg.
    Returns "online" if exit code == 0, else "offline".
    """
    try:
        cmd = [
            FFMPEG_BIN,
            "-nostdin",
            "-v", "error",
        ]

        # Optional HTTP headers if ever added to JSON links as {"headers": {...}}
        if headers:
            # FFmpeg expects CRLF-separated header lines
            header_blob = "".join(f"{k}: {v}\r\n" for k, v in headers.items())
            cmd += ["-headers", header_blob]

        # rw_timeout works for many network protocols (in microseconds)
        cmd += [
            "-rw_timeout", str(RW_TIMEOUT_US),
            "-i", url,
            "-t", "1",
            "-f", "null", "-"
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=FFMPEG_TIMEOUT,
            stdin=subprocess.DEVNULL,
        )
        return "online" if result.returncode == 0 else "offline"
    except Exception:
        return "offline"

def primary_language_for_movie(movie: Dict[str, Any]) -> str:
    """
    Choose the movie's primary language as the language of the newest 'added' link.
    This aligns 'language → newest year → name' grouping with the most recent update.
    """
    links = [l for l in movie.get("links", []) if isinstance(l, dict)]
    if not links:
        return ""
    newest = max(links, key=lambda l: _to_date(l.get("added", "")))
    return (newest.get("language") or "").lower()

def update_links(movie_data: Dict[str, Any]) -> None:
    """
    For each link, run a quick FFmpeg probe and rebuild the link dict with
    a stable key order: status → added → language → url
    (If a link contains extra fields like 'headers', they’re ignored in output.)
    """
    # Prepare worklist
    jobs: List[Tuple[str, int, str, Dict[str, str]]] = []
    for movie_name, movie in movie_data.items():
        for idx, link in enumerate(movie.get("links", [])):
            if not isinstance(link, dict):
                continue
            url = link.get("url", "")
            if not url:
                continue
            headers = link.get("headers") if isinstance(link.get("headers"), dict) else None
            jobs.append((movie_name, idx, url, headers))

    max_workers = min(WORKERS, max(1, len(jobs)))
    if max_workers < 1:
        return

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        future_map = {
            ex.submit(check_ffmpeg, url, headers): (movie_name, idx, url)
            for (movie_name, idx, url, headers) in jobs
        }
        for fut in as_completed(future_map):
            movie_name, idx, url = future_map[fut]
            status = "offline"
            try:
                status = fut.result()
            except Exception:
                pass

            # Rebuild link dict in desired key order
            old_link = movie_data[movie_name]["links"][idx]
            new_link = {
                "status": status,                                 # 1
                "added": old_link.get("added", ""),               # 2
                "language": old_link.get("language", ""),         # 3
                "url": old_link.get("url", ""),                   # 4
            }
            movie_data[movie_name]["links"][idx] = new_link

            tag = "ONLINE" if status == "online" else "OFFLINE"
            print(f"[{tag}] {movie_name} → {url}")

def sort_movies(movie_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Order: language (of newest link) → year (newest first) → name (A→Z)
    """
    def key(item):
        name, data = item
        lang = primary_language_for_movie(data)
        year = _to_int_year(data.get("year"))
        return (lang, -year, name.lower())

    # dict preserves insertion order, so make a new one from sorted items
    return dict(sorted(movie_data.items(), key=key))

def print_summary(movie_data: Dict[str, Any]) -> None:
    total_movies = len(movie_data)
    total_links = sum(len(m.get("links", [])) for m in movie_data.values())
    online = sum(1 for m in movie_data.values() for l in m.get("links", []) if l.get("status") == "online")
    offline = total_links - online

    # Per-language breakdown (by newest link’s language)
    by_lang: Dict[str, int] = {}
    for movie in movie_data.values():
        lang = primary_language_for_movie(movie) or "(unknown)"
        by_lang[lang] = by_lang.get(lang, 0) + 1

    print("\n--- Summary ---")
    print(f"Total movies: {total_movies}")
    print(f"Total links:  {total_links}")
    print(f"Online:       {online}")
    print(f"Offline:      {offline}")
    print("By language:  " + ", ".join(f"{k}: {v}" for k, v in sorted(by_lang.items())))

def atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    tmp.replace(path)

def main():
    json_path = Path(JSON_FILE)
    with json_path.open("r", encoding="utf-8") as f:
        movie_data = json.load(f)

    update_links(movie_data)
    movie_data = sort_movies(movie_data)
    atomic_write_json(json_path, movie_data)

    print_summary(movie_data)
    print(f"\nUpdated and sorted {len(movie_data)} movies.")

if __name__ == "__main__":
    main()
