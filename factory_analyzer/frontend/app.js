// app.js - Frontend interactions and API calls

// ── DOM Elements ─────────────────────────────────────────────────────────────
const dropZone = document.getElementById("drop-zone");
const fileInput = document.getElementById("file-input");
const fileList = document.getElementById("file-list");

const mapInput = document.getElementById("map-input");
const mapFileName = document.getElementById("map-file-name");

const btnAnalyze = document.getElementById("btn-analyze");
const btnDownload = document.getElementById("btn-download");
const errorBanner = document.getElementById("error-banner");

const progressLog = document.getElementById("progress-log");
const logParse = document.getElementById("log-parse");
const logScore = document.getElementById("log-score");
const logAgent = document.getElementById("log-agent");
const logDone = document.getElementById("log-done");

const resultsSection = document.getElementById("results-section");
const workerTbody = document.getElementById("worker-tbody");

// Stats
const statTotal = document.getElementById("stat-total");
const statAvg = document.getElementById("stat-avg");
const statRed = document.getElementById("stat-red");
const statAmber = document.getElementById("stat-amber");
const statGreen = document.getElementById("stat-green");

const API_BASE = "http://localhost:8000";

let uploadedFiles = [];
let currentSessionId = null;

// ── Event Listeners ──────────────────────────────────────────────────────────

// Drop Zone
dropZone.addEventListener("click", () => fileInput.click());

dropZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropZone.classList.add("dragover");
});

dropZone.addEventListener("dragleave", () => {
  dropZone.classList.remove("dragover");
});

dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZone.classList.remove("dragover");
  if (e.dataTransfer.files.length > 0) {
    handleFiles(e.dataTransfer.files);
  }
});

fileInput.addEventListener("change", (e) => {
  if (e.target.files.length > 0) {
    handleFiles(e.target.files);
  }
});

// Map Input
mapInput.addEventListener("change", (e) => {
  if (e.target.files.length > 0) {
    mapFileName.textContent = e.target.files[0].name;
  } else {
    mapFileName.textContent = "No map selected";
  }
});

// Action Buttons
btnAnalyze.addEventListener("click", doAnalysisFlow);
btnDownload.addEventListener("click", doDownloadReport);

// ── File Handling ────────────────────────────────────────────────────────────

function handleFiles(files) {
  uploadedFiles = Array.from(files).filter(f => f.name.endsWith(".txt"));
  
  if (uploadedFiles.length === 0) {
    showError("No valid .txt files found.");
    fileList.classList.add("hidden");
    return;
  }

  fileList.innerHTML = "";
  uploadedFiles.forEach(f => {
    const div = document.createElement("div");
    div.className = "file-item";
    div.innerHTML = `<span>${f.name}</span> <span style="color:#666">${(f.size/1024).toFixed(1)} KB</span>`;
    fileList.appendChild(div);
  });
  fileList.classList.remove("hidden");
  hideError();
}

function showError(msg) {
  errorBanner.textContent = msg;
  errorBanner.classList.remove("hidden");
}
function hideError() {
  errorBanner.classList.add("hidden");
}

function setLogState(el, state) {
  el.classList.remove("hidden", "active", "done");
  if (state === "active") {
    el.classList.add("active");
  } else if (state === "done") {
    el.classList.add("done");
    el.innerHTML = el.innerHTML.replace("[ ]", "[✓]").replace('<span class="spinner">⟳</span>', "");
  }
}

// ── API Flow ─────────────────────────────────────────────────────────────────

async function doAnalysisFlow() {
  if (uploadedFiles.length === 0) {
    btnAnalyze.classList.remove("shake");
    void btnAnalyze.offsetWidth; // trigger reflow
    btnAnalyze.classList.add("shake");
    return;
  }

  hideError();
  btnAnalyze.disabled = true;
  btnAnalyze.textContent = "PROCESSING...";
  resultsSection.classList.add("hidden");
  progressLog.classList.remove("hidden");

  // Reset logs
  [logParse, logScore, logAgent, logDone].forEach(el => {
    el.classList.add("hidden");
    el.innerHTML = el.innerHTML.replace("[✓]", "[ ]");
  });

  try {
    // 1. Upload & Parse
    setLogState(logParse, "active");
    const formData = new FormData();
    uploadedFiles.forEach(f => formData.append("files", f));
    if (mapInput.files.length > 0) {
      formData.append("device_map", mapInput.files[0]);
    }

    let res = await fetch(`${API_BASE}/upload`, {
      method: "POST",
      body: formData
    });
    if (!res.ok) throw new Error(await getErrorMsg(res));
    let data = await res.json();
    currentSessionId = data.session_id;

    setLogState(logParse, "done");
    setLogState(logScore, "done"); // DB parsing incorporates scoring

    // 2. Analyze (Agent)
    setLogState(logAgent, "active");
    logAgent.innerHTML = `[ ] Generating AI insights... <span class="spinner">⟳</span>`;
    logAgent.classList.remove("hidden");

    res = await fetch(`${API_BASE}/analyze`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({session_id: currentSessionId})
    });
    if (!res.ok) throw new Error(await getErrorMsg(res));
    data = await res.json();

    setLogState(logAgent, "done");
    setLogState(logDone, "done");

    // 3. Render Results
    renderResults(data.workers);

  } catch (err) {
    showError(err.message);
    progressLog.classList.add("hidden");
  } finally {
    btnAnalyze.disabled = false;
    btnAnalyze.textContent = "ANALYZE & GENERATE REPORT";
  }
}

async function doDownloadReport() {
  if (!currentSessionId) return;

  btnDownload.disabled = true;
  const originalText = btnDownload.innerText;
  btnDownload.innerText = "GENERATING...";

  try {
    const res = await fetch(`${API_BASE}/generate-report`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({session_id: currentSessionId})
    });
    
    if (!res.ok) throw new Error(await getErrorMsg(res));

    // trigger download
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "scorecard.xlsx";
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    a.remove();

    btnDownload.classList.add("success");
    btnDownload.innerText = "✓ DOWNLOADED scorecard.xlsx";
    setTimeout(() => {
      btnDownload.classList.remove("success");
      btnDownload.innerText = originalText;
      btnDownload.disabled = false;
    }, 3000);

  } catch (err) {
    showError("Download failed: " + err.message);
    btnDownload.disabled = false;
    btnDownload.innerText = originalText;
  }
}

async function getErrorMsg(res) {
  try {
    const d = await res.json();
    return d.detail || res.statusText;
  } catch {
    return res.statusText;
  }
}

function renderResults(workers) {
  // Stats
  statTotal.textContent = workers.length;
  if(workers.length > 0) {
    const avg = workers.reduce((sum, w) => sum + w.score, 0) / workers.length;
    statAvg.textContent = avg.toFixed(1);
  } else {
    statAvg.textContent = "0.0";
  }

  const red = workers.filter(w => w.status === "RED").length;
  const amber = workers.filter(w => w.status === "AMBER").length;
  const green = workers.filter(w => w.status === "GREEN").length;

  statRed.textContent = red;
  statAmber.textContent = amber;
  statGreen.textContent = green;

  // Table
  workerTbody.innerHTML = "";
  workers.forEach(w => {
    const tr = document.createElement("tr");
    tr.className = `status-${w.status.toLowerCase()}`;
    
    tr.innerHTML = `
      <td>${w.worker_id}</td>
      <td class="score-col">${w.score.toFixed(1)}</td>
      <td class="rank-col">#${w.rank}</td>
      <td><span class="status-badge">${w.status}</span></td>
      <td class="notes-col">${w.narrative}</td>
    `;
    workerTbody.appendChild(tr);
  });

  resultsSection.classList.remove("hidden");
  // scroll to results
  resultsSection.scrollIntoView({behavior: "smooth", block: "start"});
}
