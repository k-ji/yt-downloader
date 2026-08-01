const SERVER = "http://127.0.0.1:9876";

let currentUrl = "";
let serverReady = false;
let hasFfmpeg = false;

chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
  currentUrl = tabs[0]?.url || "";
  document.getElementById("url").textContent = currentUrl;

  const isYT = currentUrl.includes("youtube.com/") || currentUrl.includes("youtu.be/");
  if (!isYT) {
    showStatus("Not a YouTube page", "err");
    disableButtons();
    return;
  }

  checkServer();
});

document.getElementById("dlAudio").addEventListener("click", () => download("audio"));
document.getElementById("dlVideo").addEventListener("click", () => download("video"));
document.getElementById("dlTranscript").addEventListener("click", () => download("transcript"));
document.getElementById("openFolder").addEventListener("click", openFolder);

async function download(mode) {
  const fmt = document.getElementById("audioFmt").value;
  showStatus(mode === "transcript" ? "Checking transcript..." : "Sending to yt-dlp...", "wait");
  disableButtons();

  try {
    const resp = await fetch(`${SERVER}/download`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: currentUrl, mode, format: fmt }),
    });
    const data = await resp.json();
    if (resp.ok && data.ok) {
      showStatus(mode === "transcript" ? "Downloading transcript..." : "Downloading...", "wait");
      pollStatus(data.task_id);
    } else {
      const error = data.error || "download failed";
      showStatus(mode === "transcript" ? error : `Error: ${error}`, "err");
      restoreButtons();
    }
  } catch (e) {
    serverReady = false;
    hasFfmpeg = false;
    showStatus("Server not running. Start: python server.py", "err");
    disableButtons();
  }
}

async function checkServer() {
  try {
    const resp = await fetch(`${SERVER}/health`, { cache: "no-store" });
    const data = await resp.json();
    if (!resp.ok || !data.ok) throw new Error(data.error || `HTTP ${resp.status}`);
    if (!data.yt_dlp) {
      serverReady = false;
      hasFfmpeg = false;
      showStatus("yt-dlp not found", "err");
      disableButtons();
    } else if (!data.ffmpeg) {
      serverReady = true;
      hasFfmpeg = false;
      showStatus("ffmpeg not found; transcript only", "wait");
      restoreButtons();
    } else {
      serverReady = true;
      hasFfmpeg = true;
      showStatus("Server ready", "ok");
      restoreButtons();
    }
  } catch (e) {
    serverReady = false;
    hasFfmpeg = false;
    showStatus("Server not running. Start: python server.py", "err");
    disableButtons();
  }
}

function pollStatus(taskId) {
  const interval = setInterval(async () => {
    try {
      const resp = await fetch(`${SERVER}/status?id=${taskId}`);
      const data = await resp.json();
      if (data.status === "done") {
        clearInterval(interval);
        showStatus("Finished!", "ok");
        document.getElementById("openFolder").style.display = "block";
        restoreButtons();
      } else if (data.status === "error") {
        clearInterval(interval);
        showStatus(`Error: ${data.error || "download failed"}`, "err");
        restoreButtons();
      }
    } catch (e) {
      // server might be busy, keep polling
    }
  }, 2000);
}

async function openFolder() {
  try {
    await fetch(`${SERVER}/open-folder`);
  } catch (e) {
    // ignore
  }
}

function disableButtons() {
  document.getElementById("dlAudio").disabled = true;
  document.getElementById("dlVideo").disabled = true;
  document.getElementById("dlTranscript").disabled = true;
}

function restoreButtons() {
  document.getElementById("dlAudio").disabled = !(serverReady && hasFfmpeg);
  document.getElementById("dlVideo").disabled = !(serverReady && hasFfmpeg);
  document.getElementById("dlTranscript").disabled = !serverReady;
}

function showStatus(msg, type) {
  const el = document.getElementById("status");
  el.textContent = msg;
  el.className = `status-${type}`;
  el.style.display = "block";
}
