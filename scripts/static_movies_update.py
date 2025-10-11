import json
import subprocess
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

JSON_FILE = "static_movies.json"
WORKERS = 100
OFFLINE_EXPIRY_DAYS = 10

def check_ffmpeg(url):
    """
    Check if a media URL is playable using FFmpeg.
    Returns "online" if playable, "offline" otherwise.
    """
    try:
        cmd = [
            "ffmpeg",
            "-v", "error",
            "-i", url,
            "-t", "1",
            "-f", "null",
            "-"
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        return "online" if result.returncode == 0 else "offline"
    except Exception:
        return "offline"

def update_links(movie_data):
    """
    Update all movie links concurrently using FFmpeg.
    Remove links offline for more than OFFLINE_EXPIRY_DAYS.
    """
    now = datetime.utcnow()
    futures = []

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        for movie_name, movie in movie_data.items():
            for link in movie["links"]:
                futures.append((movie_name, link, executor.submit(check_ffmpeg, link["url"])))

        for movie_name, link, future in futures:
            status = future.result()
            link["status"] = status

            if status == "online":
                link["last_online"] = now.isoformat()
                if not link.get("first_online"):
                    link["first_online"] = now.isoformat()
                print(f"[ONLINE] {movie_name} → {link['url']}")
            else:
                link["last_offline"] = now.isoformat()
                print(f"[OFFLINE] {movie_name} → {link['url']}")

    # Remove links offline for more than OFFLINE_EXPIRY_DAYS
    expiry_time = now - timedelta(days=OFFLINE_EXPIRY_DAYS)
    for movie in movie_data.values():
        movie["links"] = [
            link for link in movie["links"]
            if not (link["status"] == "offline" and datetime.fromisoformat(link["last_offline"]) < expiry_time)
        ]

def sort_movies(movie_data):
    """
    Sort movies by group, year (latest first), then name.
    """
    return dict(sorted(
        movie_data.items(),
        key=lambda item: (
            item[1]["group"],
            -item[1]["year"],
            item[0].lower()
        )
    ))

def print_summary(movie_data):
    """
    Print a summary of total movies and link statuses.
    """
    total_movies = len(movie_data)
    total_links = sum(len(movie["links"]) for movie in movie_data.values())
    online_links = sum(
        1 for movie in movie_data.values() for link in movie["links"] if link["status"] == "online"
    )
    offline_links = total_links - online_links

    print("\n--- Summary ---")
    print(f"Total movies: {total_movies}")
    print(f"Total links: {total_links}")
    print(f"Online links: {online_links}")
    print(f"Offline links: {offline_links}")

def main():
    # Load JSON
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        movie_data = json.load(f)

    # Update links
    update_links(movie_data)

    # Sort movies
    movie_data = sort_movies(movie_data)

    # Write back to file
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(movie_data, f, ensure_ascii=False, indent=2)

    print_summary(movie_data)
    print(f"Updated and sorted {len(movie_data)} movies.")

if __name__ == "__main__":
    main()
