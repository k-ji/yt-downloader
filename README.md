# YT Downloader

Chrome extension + local server for downloading YouTube audio, video, and transcripts using yt-dlp. Uses Chrome cookies for authentication, so members-only content works.

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

For normal use on this Mac, install the LaunchAgent so the server starts automatically at login and restarts if it exits:

```bash
mkdir -p ~/Library/LaunchAgents ~/Data/Logs
cp launchd/com.kun.yt-downloader.plist ~/Library/LaunchAgents/
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.kun.yt-downloader.plist 2>/dev/null || true
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.kun.yt-downloader.plist
```

Check it:

```bash
curl http://127.0.0.1:9876/health
```

### 2. Install the Chrome extension

1. Open `chrome://extensions/`
2. Enable **Developer mode** (top right)
3. Click **Load unpacked**
4. Select the `extension/` folder
5. If the extension was already loaded, click its reload button after code changes

On the current Chrome profile, the loaded unpacked extension path is:

```text
/Users/kun/yt-downloader/extension
```

Keep that copy in sync with this repo's `extension/` folder, or remove it in `chrome://extensions/` and load this repo's folder instead.

## Usage

1. Navigate to any YouTube video in Chrome
2. Click the YT Downloader extension icon
3. Choose audio format (MP3/M4A/WAV), video, or transcript
4. Click Download

## Features

- Audio download with format selection (MP3, M4A, WAV)
- Video download (best quality MP4)
- Transcript download when manual or auto captions are available
- Members-only content support (via Chrome cookies)
- Async downloads with status polling
- Open downloads folder from popup
