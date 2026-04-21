const SERVER = "http://localhost:9876";

let currentUrl = "";

chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
  currentUrl = tabs[0]?.url || "";
  document.getElementById("url").textContent = currentUrl;

  const isYT = currentUrl.includes("youtube.com/") || currentUrl.includes("youtu.be/");
  if (!isYT) {
    showStatus("Not a YouTube page", "err");
    document.getElementById("dlAudio").disabled = true;
    document.getElementById("dlVideo").disabled = true;
  }
});

document.getElementById("dlAudio").addEventListener("click", () => download("audio"));
document.getElementById("dlVideo").addEventListener("click", () => download("video"));
document.getElementById("openFolder").addEventListener("click", openFolder);

async function download(mode) {
  const fmt = document.getElementById("audioFmt").value;
  showStatus("Sending to yt-dlp...", "wait");
  document.getElementById("dlAudio").disabled = true;
  document.getElementById("dlVideo").disabled = true;

  try {
    const resp = await fetch(`${SERVER}/download`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: currentUrl, mode, format: fmt }),
    });
    const data = await resp.json();
    if (data.ok) {
      showStatus("Downloading...", "wait");
      pollStatus(data.task_id);
    } else {
      showStatus(`Error: ${data.error}`, "err");
      enableButtons();
    }
  } catch (e) {
    showStatus("Server not running. Start: python server.py", "err");
    enableButtons();
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
        enableButtons();
      } else if (data.status === "error") {
        clearInterval(interval);
        showStatus(`Error: ${data.error || "download failed"}`, "err");
        enableButtons();
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

function enableButtons() {
  document.getElementById("dlAudio").disabled = false;
  document.getElementById("dlVideo").disabled = false;
}

function showStatus(msg, type) {
  const el = document.getElementById("status");
  el.textContent = msg;
  el.className = `status-${type}`;
  el.style.display = "block";
}
