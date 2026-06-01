const stages = [
  ["uploading", "Uploading Video"],
  ["extracting", "Extracting Audio"],
  ["transcribing", "Transcribing Content"],
  ["analyzing", "Analyzing Transcript"],
  ["insights", "Generating Insights"],
  ["saving", "Saving Results"],
  ["complete", "Analysis Complete"],
];

const authScreen = document.querySelector("#authScreen");
const dashboardApp = document.querySelector("#dashboardApp");
const loginTab = document.querySelector("#loginTab");
const registerTab = document.querySelector("#registerTab");
const loginForm = document.querySelector("#loginForm");
const registerForm = document.querySelector("#registerForm");
const authMessage = document.querySelector("#authMessage");
const userBadge = document.querySelector("#userBadge");
const logoutBtn = document.querySelector("#logoutBtn");
const form = document.querySelector("#analyzeForm");
const fileInput = document.querySelector("#file");
const fileName = document.querySelector("#fileName");
const analyzeBtn = document.querySelector("#analyzeBtn");
const cleanupBtn = document.querySelector("#cleanupBtn");
const statusTitle = document.querySelector("#statusTitle");
const statusBadge = document.querySelector("#statusBadge");
const statusText = document.querySelector("#statusText");
const progressPanel = document.querySelector("#progressPanel");
const progressPercent = document.querySelector("#progressPercent");
const stageList = document.querySelector("#stageList");
const historyList = document.querySelector("#historyList");
const emptyState = document.querySelector("#emptyState");
const results = document.querySelector("#results");
const titleEl = document.querySelector("#title");
const summaryEl = document.querySelector("#summary");
const transcriptEl = document.querySelector("#transcript");
const transcriptPanel = document.querySelector("#transcriptPanel");
const toggleTranscript = document.querySelector("#toggleTranscript");
const insightGrid = document.querySelector("#insightGrid");
const resultType = document.querySelector("#resultType");
const chatForm = document.querySelector("#chatForm");
const questionInput = document.querySelector("#question");
const chatLog = document.querySelector("#chatLog");

let activeSessionId = null;
let pollTimer = null;
let authToken = localStorage.getItem("videoMindToken");

renderStages("idle");
bootAuth();

loginTab.addEventListener("click", () => setAuthMode("login"));
registerTab.addEventListener("click", () => setAuthMode("register"));

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await submitAuth("/api/auth/login", {
    email: document.querySelector("#loginEmail").value,
    password: document.querySelector("#loginPassword").value,
  });
});

registerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await submitAuth("/api/auth/register", {
    name: document.querySelector("#registerName").value,
    email: document.querySelector("#registerEmail").value,
    password: document.querySelector("#registerPassword").value,
  });
});

logoutBtn.addEventListener("click", async () => {
  await authFetch("/api/auth/logout", { method: "POST" }).catch(() => {});
  forceLogout();
});

fileInput.addEventListener("change", () => {
  fileName.textContent = fileInput.files[0]?.name || "MP4, MOV, MP3, WAV";
});

toggleTranscript.addEventListener("click", () => {
  transcriptPanel.classList.toggle("hidden");
});

cleanupBtn.addEventListener("click", async () => {
  const response = await authFetch("/api/cleanup", { method: "POST" });
  const payload = await response.json();
  setProgressState("Cleanup", `Removed ${payload.deleted || 0} generated file(s).`, 0, "idle", "Idle");
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const source = document.querySelector("#source").value.trim();
  const file = fileInput.files[0];

  if (!source && !file) {
    setProgressState("Input needed", "Add a video URL or choose a local file first.", 0, "error", "Error");
    return;
  }

  const data = new FormData(form);
  if (!file) {
    data.delete("file");
  }

  setLoading(true);
  setProgressState("Queued", "Preparing analysis job.", 3, "running", "Running");

  try {
    const response = await authFetch("/api/analyze", { method: "POST", body: data });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Analysis failed");
    }
    pollJob(payload.job_id);
  } catch (error) {
    setLoading(false);
    setProgressState("Error", friendlyError(error.message), 100, "error", "Error");
  }
});

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = questionInput.value.trim();

  if (!activeSessionId || !question) {
    return;
  }

  addMessage(question, "user");
  questionInput.value = "";

  try {
    const response = await authFetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: activeSessionId, question }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Chat failed");
    }
    addMessage(payload.answer, "assistant");
  } catch (error) {
    addMessage(error.message, "assistant");
  }
});

async function pollJob(jobId) {
  clearInterval(pollTimer);

  const tick = async () => {
    try {
      const response = await authFetch(`/api/jobs/${jobId}`);
      const job = await response.json();
      if (!response.ok) {
        throw new Error(job.detail || "Job not found");
      }

      setProgressState(titleForStage(job.stage), job.detail, job.percent, job.status, labelForStatus(job.status));
      renderStages(job.stage);

      if (job.status === "complete") {
        clearInterval(pollTimer);
        setLoading(false);
        renderResults(job.result);
        loadHistory();
      }

      if (job.status === "error") {
        clearInterval(pollTimer);
        setLoading(false);
        setProgressState("Analysis failed", friendlyError(job.error || job.detail), 100, "error", "Error");
        loadHistory();
      }
    } catch (error) {
      clearInterval(pollTimer);
      setLoading(false);
      setProgressState("Connection issue", error.message, 100, "error", "Error");
    }
  };

  await tick();
  pollTimer = setInterval(tick, 1400);
}

async function loadHistory() {
  try {
    const response = await authFetch("/api/history");
    const items = await response.json();
    historyList.innerHTML = items.length
      ? items.map(renderHistoryItem).join("")
      : `<div class="history-item"><strong>No analyses yet</strong><span class="history-meta">Your last five runs will appear here.</span></div>`;
  } catch {
    historyList.innerHTML = `<div class="history-item"><strong>History unavailable</strong></div>`;
  }
}

window.quickView = async (id) => {
  const response = await authFetch(`/api/history/${id}`);
  const payload = await response.json();
  if (!response.ok) {
    setProgressState("Unavailable", payload.detail || "Could not load history item.", 0, "error", "Error");
    return;
  }
  renderResults(payload);
  setProgressState("Quick View", "Loaded saved analysis from history.", 100, "complete", "Complete");
  renderStages("complete");
};

window.rerunAnalysis = async (id) => {
  const response = await authFetch(`/api/history/${id}/rerun`, { method: "POST" });
  const payload = await response.json();
  if (!response.ok) {
    setProgressState("Rerun unavailable", payload.detail || "Could not rerun analysis.", 0, "error", "Error");
    return;
  }
  setLoading(true);
  pollJob(payload.job_id);
};

function renderResults(payload) {
  activeSessionId = payload.session_id || null;
  emptyState.classList.add("hidden");
  results.classList.remove("hidden");
  chatLog.innerHTML = "";
  if (!activeSessionId) {
    addMessage("This saved result can be viewed, but chat is available only for analyses from the current server session.", "assistant");
  }

  titleEl.textContent = payload.title || "Video Analysis";
  resultType.textContent = payload.content_type === "meeting" ? "Meeting Intelligence Brief" : "Video Intelligence Brief";
  summaryEl.innerHTML = formatRichText(payload.summary || "");
  transcriptEl.textContent = payload.transcript || "";
  transcriptPanel.classList.add("hidden");

  const cards = payload.content_type === "meeting"
    ? [
        ["Action Items", payload.action_items],
        ["Key Decisions", payload.key_decisions],
        ["Open Questions", payload.open_questions],
      ]
    : [
        ["Key Points", payload.key_points],
        ["Takeaways", payload.takeaways],
        ["Highlights", payload.highlights],
      ];

  insightGrid.innerHTML = cards.map(([heading, body]) => `
    <article class="glass-card insight-card">
      <p class="eyebrow">${escapeHtml(heading)}</p>
      <div class="rich-text">${formatRichText(body || "No data found.")}</div>
    </article>
  `).join("");
}

function renderHistoryItem(item) {
  const canView = item.status === "complete";
  return `
    <article class="history-item">
      <strong>${escapeHtml(item.video_name || "Untitled")}</strong>
      <div class="history-meta">
        <span>${escapeHtml(item.created_at)}</span>
        <span>${escapeHtml(item.status)}</span>
      </div>
      <div class="history-actions">
        <button class="mini-btn" ${canView ? `onclick="quickView('${item.id}')"` : "disabled"}>Quick View</button>
        <button class="mini-btn" onclick="rerunAnalysis('${item.id}')">Re-run</button>
      </div>
    </article>
  `;
}

function renderStages(activeStage) {
  const activeIndex = stages.findIndex(([key]) => key === activeStage);
  stageList.innerHTML = stages.map(([key, label], index) => {
    const state = activeStage === "idle" ? "" : index < activeIndex ? "done" : index === activeIndex ? "active" : "";
    return `
      <div class="stage ${state}">
        <span class="stage-dot"></span>
        <div><strong>${label}</strong><span>${stageDescription(key)}</span></div>
      </div>
    `;
  }).join("");
}

function setProgressState(title, detail, percent, status, badge) {
  const safePercent = Math.max(0, Math.min(100, Number(percent) || 0));
  statusTitle.textContent = title;
  statusText.textContent = detail || "";
  progressPercent.textContent = `${safePercent}%`;
  progressPanel.style.setProperty("--progress", `${safePercent}%`);
  statusBadge.textContent = badge;
  statusBadge.className = `status-badge ${status === "error" ? "error" : status === "idle" ? "idle" : ""}`;
}

function setLoading(isLoading) {
  analyzeBtn.disabled = isLoading;
  analyzeBtn.textContent = isLoading ? "Analyzing..." : "Run Analysis";
}

function addMessage(text, role) {
  const message = document.createElement("div");
  message.className = `message ${role}`;
  message.textContent = text;
  chatLog.appendChild(message);
  chatLog.scrollTop = chatLog.scrollHeight;
}

function titleForStage(stage) {
  return stages.find(([key]) => key === stage)?.[1] || "Processing";
}

function labelForStatus(status) {
  if (status === "complete") return "Complete";
  if (status === "error") return "Error";
  if (status === "queued") return "Queued";
  return "Running";
}

function stageDescription(stage) {
  return {
    uploading: "Source is being prepared.",
    extracting: "Audio is converted and chunked.",
    transcribing: "Speech is becoming text.",
    analyzing: "Transcript context is being understood.",
    insights: "Structured sections are being generated.",
    saving: "RAG memory is being prepared.",
    complete: "Results are ready.",
  }[stage] || "";
}

function friendlyError(message = "") {
  if (message.includes("127.0.0.1") && message.toLowerCase().includes("proxy")) {
    return "YouTube download failed because a local proxy setting is blocking yt-dlp. The backend now ignores that broken proxy; try again.";
  }
  if (message.toLowerCase().includes("unable to download")) {
    return "The video could not be downloaded. Check that the URL is public and reachable, then try again.";
  }
  return message || "Something went wrong.";
}

function formatRichText(value) {
  const text = escapeHtml(value);
  return text
    .replace(/^### (.*)$/gm, "<h3>$1</h3>")
    .replace(/^## (.*)$/gm, "<h3>$1</h3>")
    .replace(/^\d+\.\s+(.*)$/gm, "<div class=\"brief-line\"><span></span><p>$1</p></div>")
    .replace(/^-\s+(.*)$/gm, "<div class=\"brief-line\"><span></span><p>$1</p></div>")
    .replace(/\n{2,}/g, "<br><br>")
    .replace(/\n/g, "<br>");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function bootAuth() {
  if (!authToken) {
    authScreen.classList.remove("hidden");
    dashboardApp.classList.add("hidden");
    return;
  }

  try {
    const response = await authFetch("/api/auth/me");
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Login required");
    }
    showDashboard(payload.user);
  } catch {
    localStorage.removeItem("videoMindToken");
    authToken = null;
    authScreen.classList.remove("hidden");
    dashboardApp.classList.add("hidden");
  }
}

async function submitAuth(url, body) {
  authMessage.textContent = "";
  const email = String(body.email || "").trim().toLowerCase();
  const password = String(body.password || "");

  if (!email || !email.includes("@")) {
    authMessage.textContent = "Enter a valid email address.";
    return;
  }
  if (password.length < 6) {
    authMessage.textContent = "Password must be at least 6 characters.";
    return;
  }
  if ("name" in body && !String(body.name || "").trim()) {
    authMessage.textContent = "Name is required.";
    return;
  }

  const activeForm = url.includes("register") ? registerForm : loginForm;
  const submitButton = activeForm.querySelector("button[type=\"submit\"]");
  submitButton.disabled = true;
  submitButton.textContent = url.includes("register") ? "Creating..." : "Logging in...";

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...body, email }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Authentication failed");
    }
    authToken = payload.token;
    localStorage.setItem("videoMindToken", authToken);
    showDashboard(payload.user);
  } catch (error) {
    authMessage.textContent = error.message;
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = url.includes("register") ? "Create Account" : "Login";
  }
}

function showDashboard(user) {
  authScreen.classList.add("hidden");
  dashboardApp.classList.remove("hidden");
  userBadge.textContent = user?.name ? `Signed in as ${user.name}` : "Signed in";
  authMessage.textContent = "";
  loadHistory();
}

function setAuthMode(mode) {
  const isLogin = mode === "login";
  loginTab.classList.toggle("active", isLogin);
  registerTab.classList.toggle("active", !isLogin);
  loginForm.classList.toggle("hidden", !isLogin);
  registerForm.classList.toggle("hidden", isLogin);
  authMessage.textContent = "";
}

function forceLogout(message = "") {
  localStorage.removeItem("videoMindToken");
  authToken = null;
  dashboardApp.classList.add("hidden");
  authScreen.classList.remove("hidden");
  setAuthMode("login");
  authMessage.textContent = message;
  clearInterval(pollTimer);
  setLoading(false);
}

async function authFetch(url, options = {}) {
  const headers = new Headers(options.headers || {});
  if (authToken) {
    headers.set("Authorization", `Bearer ${authToken}`);
  }
  const response = await fetch(url, { ...options, headers });
  if (response.status === 401) {
    forceLogout("Your session expired. Please login again.");
  }
  return response;
}