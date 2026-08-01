#!/usr/bin/env python3
"""Local server for YT Downloader Chrome extension.

Runs yt-dlp with Chrome cookies so members-only content works.

Usage:
    python server.py
"""

import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from html import unescape
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

PORT = 9876
DOWNLOAD_DIR = os.path.expanduser("~/Downloads/YouTube")
BIN_PATHS = [
    "/opt/homebrew/bin",
    "/usr/local/bin",
    os.path.expanduser("~/.local/bin"),
]
PREFERRED_TRANSCRIPT_LANG_PREFIXES = ("en", "en-")

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# In-memory task tracker
_tasks = {}


class Handler(BaseHTTPRequestHandler):
    def _read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            length = 0
        if length <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except json.JSONDecodeError:
            return None

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

        elif path == "/health":
            self._respond(200, {
                "ok": True,
                "yt_dlp": _find_binary("yt-dlp"),
                "ffmpeg": _find_binary("ffmpeg"),
                "download_dir": DOWNLOAD_DIR,
            })

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

        body = self._read_json()
        if body is None:
            self._respond(400, {"ok": False, "error": "invalid json"})
            return
        url = body.get("url", "")
        mode = body.get("mode", "audio")
        fmt = body.get("format", "mp3")

        if "youtube.com" not in url and "youtu.be" not in url:
            self._respond(400, {"ok": False, "error": "not a youtube url"})
            return
        if mode not in {"audio", "video", "transcript"}:
            self._respond(400, {"ok": False, "error": "mode must be audio, video, or transcript"})
            return
        if fmt not in {"mp3", "m4a", "wav"}:
            self._respond(400, {"ok": False, "error": "unsupported audio format"})
            return

        yt_dlp = _find_binary("yt-dlp")
        ffmpeg = _find_binary("ffmpeg")
        if not yt_dlp:
            self._respond(500, {"ok": False, "error": "yt-dlp not found"})
            return
        if mode in {"audio", "video"} and not ffmpeg:
            self._respond(500, {"ok": False, "error": "ffmpeg not found"})
            return

        transcript = None
        transcript_work_dir = ""
        output_template = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")
        if mode == "transcript":
            transcript = _select_transcript(yt_dlp, url)
            if not transcript:
                self._respond(404, {"ok": False, "error": "Transcript isn't available"})
                return
            transcript_work_dir = tempfile.mkdtemp(prefix="yt-downloader-transcript-")
            output_template = os.path.join(transcript_work_dir, "%(title)s.%(ext)s")

        task_id = uuid.uuid4().hex[:8]
        cmd = [
            yt_dlp,
            "--no-playlist",
            "--newline",
            "--no-update",
            "--cookies-from-browser", "chrome",
            "-o", output_template,
        ]

        if ffmpeg:
            cmd += ["--ffmpeg-location", os.path.dirname(ffmpeg)]

        if mode == "audio":
            cmd += ["-x", "--audio-format", fmt]
        elif mode == "video":
            cmd += ["-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"]
        else:
            cmd += [
                "--skip-download",
                "--sub-langs", transcript["lang"],
                "--sub-format", "vtt/srt/best",
            ]
            cmd.append("--write-subs" if transcript["kind"] == "manual" else "--write-auto-subs")

        cmd.append(url)

        _tasks[task_id] = {"status": "downloading", "mode": mode, "url": url, "download_dir": DOWNLOAD_DIR}

        print(f"[yt-dlp] {task_id} {mode} | {url}")

        def _run():
            started_at = time.time()
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True)
                if proc.returncode == 0:
                    result = {
                        "status": "done",
                        "mode": mode,
                        "download_dir": DOWNLOAD_DIR,
                        "output": _tail(proc.stdout, 1000),
                    }
                    if mode == "transcript":
                        transcript_path = _write_clean_transcript(
                            proc.stdout,
                            transcript["lang"],
                            started_at,
                            transcript_work_dir or DOWNLOAD_DIR,
                        )
                        if not transcript_path:
                            raise RuntimeError("transcript downloaded but could not be cleaned")
                        result["transcript_path"] = transcript_path
                        result["output"] = _tail(f"{proc.stdout}\nClean transcript: {transcript_path}", 1000)
                    _tasks[task_id] = result
                    print(f"[yt-dlp] {task_id} done")
                else:
                    err = _tail(proc.stderr or proc.stdout, 1200) or "unknown error"
                    _tasks[task_id] = {"status": "error", "mode": mode, "error": err}
                    print(f"[yt-dlp] {task_id} error: {err}")
            except Exception as exc:
                err = str(exc) or "unknown error"
                _tasks[task_id] = {"status": "error", "mode": mode, "error": err}
                print(f"[yt-dlp] {task_id} error: {err}")
            finally:
                if transcript_work_dir:
                    shutil.rmtree(transcript_work_dir, ignore_errors=True)

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


def _find_binary(name):
    found = shutil.which(name)
    if found:
        return found
    for folder in BIN_PATHS:
        candidate = os.path.join(folder, name)
        if os.path.exists(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return ""


def _select_transcript(yt_dlp, url):
    info = _load_video_info(yt_dlp, url)
    if not info:
        return None

    for kind, field in (("manual", "subtitles"), ("automatic", "automatic_captions")):
        lang = _choose_language(info.get(field) or {})
        if lang:
            return {"kind": kind, "lang": lang}
    return None


def _load_video_info(yt_dlp, url):
    cmd = [
        yt_dlp,
        "--no-playlist",
        "--no-update",
        "--cookies-from-browser", "chrome",
        "--skip-download",
        "--dump-single-json",
        url,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return None
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


def _choose_language(captions):
    if not captions:
        return ""

    languages = sorted(captions)
    for prefix in PREFERRED_TRANSCRIPT_LANG_PREFIXES:
        for lang in languages:
            if lang == prefix or lang.startswith(prefix):
                return lang
    return languages[0]


def _write_clean_transcript(output, lang, started_at, search_dir):
    subtitle_path = _find_subtitle_file(output, lang, started_at, search_dir)
    if not subtitle_path:
        return ""

    with open(subtitle_path, "r", encoding="utf-8-sig", errors="replace") as f:
        subtitle_text = f.read()

    lines = (
        _clean_srt_transcript(subtitle_text)
        if subtitle_path.lower().endswith(".srt")
        else _clean_vtt_transcript(subtitle_text)
    )
    if not lines:
        return ""

    transcript_name = os.path.basename(os.path.splitext(subtitle_path)[0] + ".txt")
    transcript_path = os.path.join(DOWNLOAD_DIR, transcript_name)
    with open(transcript_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")
    return transcript_path


def _find_subtitle_file(output, lang, started_at, search_dir):
    candidates = []
    for match in re.finditer(r"(?:Writing video subtitles to|Destination): (?P<path>.+?\.(?:vtt|srt))", output or ""):
        path = match.group("path").strip()
        if os.path.exists(path):
            candidates.append(path)

    if not candidates:
        suffixes = (f".{lang}.vtt", f".{lang}.srt", ".vtt", ".srt")
        for name in os.listdir(search_dir):
            path = os.path.join(search_dir, name)
            if not os.path.isfile(path):
                continue
            if not name.endswith(suffixes):
                continue
            if os.path.getmtime(path) >= started_at - 1:
                candidates.append(path)

    return max(candidates, key=os.path.getmtime) if candidates else ""


def _clean_vtt_transcript(text):
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line == "WEBVTT" or line.startswith(("Kind:", "Language:", "NOTE", "STYLE", "REGION")):
            continue
        if "-->" in line:
            continue
        cleaned = _clean_caption_line(line)
        if cleaned and cleaned not in lines:
            lines.append(cleaned)
    return _dedupe_rolling_caption_lines(lines)


def _clean_srt_transcript(text):
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.isdigit() or "-->" in line:
            continue
        cleaned = _clean_caption_line(line)
        if cleaned and cleaned not in lines:
            lines.append(cleaned)
    return _dedupe_rolling_caption_lines(lines)


def _clean_caption_line(line):
    line = re.sub(r"<\d{2}:\d{2}:\d{2}\.\d{3}>", "", line)
    line = re.sub(r"</?c(?:\.[^>]*)?>", "", line)
    line = re.sub(r"<[^>]+>", "", line)
    line = unescape(line)
    return re.sub(r"\s+", " ", line).strip()


def _dedupe_rolling_caption_lines(lines):
    cleaned = []
    for line in lines:
        if not cleaned:
            cleaned.append(line)
            continue
        previous = cleaned[-1]
        if line == previous:
            continue
        if line.startswith(previous):
            cleaned[-1] = line
            continue
        if previous.startswith(line):
            continue
        cleaned.append(line)
    return cleaned


def _tail(text, size):
    text = str(text or "")
    return text[-size:] if len(text) > size else text


if __name__ == "__main__":
    print(f"YT Downloader server on http://localhost:{PORT}")
    print(f"Downloads go to: {DOWNLOAD_DIR}")
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
