# 📺 IPTV

A simple yet powerful IPTV playlist & EPG manager. This project was created as a **coding hobby** and to maintain a working IPTV setup for personal use.

---

## 🚀 Features

- ✅ **Playlist Aggregation** – Combines multiple `combined.m3u` playlists into one.
- ✅ **Static Channel Updates** – Automatically check working channel static channels from `static_channels.json`.
- ✅ **EPG Scraper** – Generates or updates `epg.xml` for TV guide support.
- ✅ **YouTube Playlist Support** – Automatically save live channels from YouTube in `YT_playlist.m3u`.
- ✅ **Fully Automated** – CI/CD workflows can regenerate playlists and guides.

---

## 🗂 Project Structure

```
IPTV/
├── .github/workflows/         # CI/CD pipelines for automation
├── YT_channels.py             # YouTube channels list
├── YT_get_YouTube_link.py     # Get m3u8 links from YouTube
├── combine_playlists.py       # Combines YouTube and static channels playlist into one
├── epg_scraper.py             # Scrapes and generates EPG (XML format)
├── static_channels_update.py  # Updates static channels status automatically
├── static_channels.json       # Predefined static channels (outpot)
├── YT_playlist.m3u            # Playlist generated from Youtube (output)
├── combined.m3u               # Final generated playlist (output)
└── epg.xml                    # Final generated TV guide (output)
```

---

## 📊 Workflow Diagram

```mermaid
---
config:
  layout: dagre
---
flowchart TD
    A2["YT_get_YouTube_link.py"] -- <br> --> A3["YT_playlist.m3u"]
    A3 --> A5["combine_playlists.py"]
    A4["static_channels.json"] -- </br> --> A5
    A5 --> A6["combined.m3u"]
    B1["epg_scraper.py"] -- Scrap Sites for EPG --> B2["epg.xml"]
    C1["static_channels_update.py"] -- checks/updates --> A4
    n1["YT_channels.py<br>"] -- <br> --> A3
    n1@{ shape: rect}

```

---

## ⚙️ Installation & Usage

1. **Clone the repository:**
   ```bash
   git clone https://github.com/time2shine/IPTV.git
   cd IPTV
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Generate Playlist & EPG:**
   ```bash
   python main.py
   ```

4. **Find outputs:**
   - `combined.m3u` → your IPTV playlist
   - `epg.xml` → your TV guide

---

## 🖼 Example Output

**Sample combined.m3u:**
```m3u
#EXTM3U
#EXTINF:-1 tvg-id="BBCWORLD" group-title="News",BBC World News
http://example.com/stream/bbcworld
```

---

## 🛠 For Developers

- Add new channels by editing `static_channels.json`.
- Modify playlist combination rules in `combine_playlists.py`.
- Extend EPG scraping logic in `epg_scraper.py` for custom sources.

---

## 🤝 Contributing

Contributions are welcome! Fork the repo, make your changes, and submit a PR.

---

## 📜 License

MIT License – free to use, modify, and share.

---

## ❤️ Maintainer Notes

This project is maintained as a **hobby** and for family use. It's a fun way to keep learning Python while keeping IPTV streams organized for daily use.

