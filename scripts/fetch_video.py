"""Selects a local background video for normal YouTube videos and keeps live streams in the iframe."""
import json
import os
from pathlib import Path

import yt_dlp

VIDEO_URL = "https://www.youtube.com/watch?v=o4qjk8_5gmU"
VIDEO_ID = "o4qjk8_5gmU"
MANIFEST = Path("data/video.json")
VIDEO_FILE = Path("data/background.mp4")


def main():
    MANIFEST.parent.mkdir(exist_ok=True)
    inspect_opts = {"quiet": True, "no_warnings": True, "noplaylist": True}
    with yt_dlp.YoutubeDL(inspect_opts) as ydl:
        info = ydl.extract_info(VIDEO_URL, download=False)

    is_live = info.get("is_live") or info.get("live_status") in {"is_live", "is_upcoming"}
    if is_live:
        MANIFEST.write_text(json.dumps({"mode": "youtube", "video": VIDEO_ID}))
        print("Live stream detected; keeping the YouTube iframe")
        return

    download_opts = {
        "format": "best[ext=mp4][height<=720]/best[ext=mp4]/best",
        "outtmpl": str(VIDEO_FILE),
        "merge_output_format": "mp4",
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(download_opts) as ydl:
        ydl.download([VIDEO_URL])
    MANIFEST.write_text(json.dumps({"mode": "local", "src": str(VIDEO_FILE)}))
    print(f"Downloaded normal video to {VIDEO_FILE}")


if __name__ == "__main__":
    main()
