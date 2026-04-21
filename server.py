#!/usr/bin/env python3
"""Local server for YT Downloader Chrome extension.

Runs yt-dlp with Chrome cookies so members-only content works.

Usage:
    python server.py
"""

import json
import os
import platform
import subprocess
import sys
import threading
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

PORT = 9876
DOWNLOAD_DIR = os.path.expanduser("~/Downloads/YouTube")

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# In-memory task tracker
_tasks = {}


class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/status":
            task_id = params.get("id", [""])[0]
            info = _tasks.get(task_id, {})
            self._respond(200, info if info else {"status": "unknown"})

        elif path == "/open-folder":
            if platform.system() == "Darwin":
                subprocess.Popen(["open", DOWNLOAD_DIR])
            elif platform.system() == "Windows":
                subprocess.Popen(["explorer", DOWNLOAD_DIR])
            else:
                subprocess.Popen(["xdg-open", DOWNLOAD_DIR])
            self._respond(200, {"ok": True})

        else:
            self._respond(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/download":
            self._respond(404, {"ok": False, "error": "not found"})
            return

        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        url = body.get("url", "")
        mode = body.get("mode", "audio")
        fmt = body.get("format", "mp3")

        if "youtube.com" not in url and "youtu.be" not in url:
            self._respond(400, {"ok": False, "error": "not a youtube url"})
            return

        cmd = [
            "yt-dlp",
            "--no-playlist",
            "--cookies-from-browser", "chrome",
            "-o", os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
        ]

        if mode == "audio":
            cmd += ["-x", "--audio-format", fmt]
        else:
            cmd += ["-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"]

        cmd.append(url)

        task_id = uuid.uuid4().hex[:8]
        _tasks[task_id] = {"status": "downloading", "mode": mode, "url": url}

        print(f"[yt-dlp] {task_id} {mode} | {url}")

        def _run():
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode == 0:
                _tasks[task_id] = {"status": "done", "mode": mode}
                print(f"[yt-dlp] {task_id} done")
            else:
                err = proc.stderr[-300:] if proc.stderr else "unknown error"
                _tasks[task_id] = {"status": "error", "error": err}
                print(f"[yt-dlp] {task_id} error: {err}")

        threading.Thread(target=_run, daemon=True).start()
        self._respond(200, {"ok": True, "task_id": task_id})

    def _respond(self, code, data):
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, format, *args):
        print(f"[server] {args[0]}")


if __name__ == "__main__":
    print(f"YT Downloader server on http://localhost:{PORT}")
    print(f"Downloads go to: {DOWNLOAD_DIR}")
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
