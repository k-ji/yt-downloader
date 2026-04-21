# YT Downloader

Chrome extension + local server for downloading YouTube audio/video using yt-dlp. Uses Chrome cookies for authentication, so members-only content works.

## Requirements

- Python 3.8+
- [yt-dlp](https://github.com/yt-dlp/yt-dlp): `brew install yt-dlp` or `pip install yt-dlp`
- [ffmpeg](https://ffmpeg.org/): `brew install ffmpeg`
- Google Chrome (for cookie-based auth)

## Setup

### 1. Start the server

```bash
python server.py
```

Server runs on `http://localhost:9876`. Downloads go to `~/Downloads/YouTube/`.

### 2. Install the Chrome extension

1. Open `chrome://extensions/`
2. Enable **Developer mode** (top right)
3. Click **Load unpacked**
4. Select the `extension/` folder

## Usage

1. Navigate to any YouTube video in Chrome
2. Click the YT Downloader extension icon
3. Choose audio format (MP3/M4A/WAV) or video
4. Click Download

## Features

- Audio download with format selection (MP3, M4A, WAV)
- Video download (best quality MP4)
- Members-only content support (via Chrome cookies)
- Async downloads with status polling
- Open downloads folder from popup
