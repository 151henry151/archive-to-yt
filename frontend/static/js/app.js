/* Archive to YouTube - Web UI */

const API = "/api";

let authStatus = false;
let previewData = null;
let currentJobId = null;

// Elements
const landing = document.getElementById("landing");
const preview = document.getElementById("preview");
const processing = document.getElementById("processing");
const review = document.getElementById("review");
const complete = document.getElementById("complete");

const urlInput = document.getElementById("url");
const landingError = document.getElementById("landing-error");
const btnSignin = document.getElementById("btn-signin");
const signedIn = document.getElementById("signed-in");
const btnPreview = document.getElementById("btn-preview");
const previewLoading = document.getElementById("preview-loading");
const previewTitle = document.getElementById("preview-title");
const previewMeta = document.getElementById("preview-meta");
const previewPlaylist = document.getElementById("preview-playlist");
const previewTracks = document.getElementById("preview-tracks");
const previewTotal = document.getElementById("preview-total");
const btnBack = document.getElementById("btn-back");
const btnProceed = document.getElementById("btn-proceed");
const progressFill = document.getElementById("progress-fill");
const progressIndeterminate = document.getElementById("progress-indeterminate");
const progressText = document.getElementById("progress-text");
const playlistLink = document.getElementById("playlist-link");
const btnMakePublic = document.getElementById("btn-make-public");
const publicPlaylistLink = document.getElementById("public-playlist-link");
const btnStartOver = document.getElementById("btn-start-over");

function show(section) {
  [landing, preview, processing, review, complete].forEach((el) => el.classList.add("hidden"));
  section.classList.remove("hidden");
}

function showError(el, msg) {
  el.textContent = msg || "";
  el.classList.toggle("hidden", !msg);
}

async function checkAuth() {
  const res = await fetch(`${API}/auth/status`, { credentials: "include" });
  const data = await res.json();
  authStatus = data.authenticated;
  signedIn.classList.toggle("hidden", !authStatus);
  btnSignin.textContent = authStatus ? "Sign out" : "Sign in with YouTube";
  return authStatus;
}

async function handleSignIn() {
  if (authStatus) {
    await fetch(`${API}/auth/logout`, { method: "POST", credentials: "include" });
    authStatus = false;
    signedIn.classList.add("hidden");
    btnSignin.textContent = "Sign in with YouTube";
    return;
  }
  const res = await fetch(`${API}/auth/youtube/url`, { credentials: "include" });
  const data = await res.json();
  if (data.url) window.location.href = data.url;
}

async function handlePreview() {
  const url = urlInput.value.trim();
  if (!url) {
    showError(landingError, "Enter an archive.org URL");
    return;
  }
  if (!url.includes("archive.org/details/")) {
    showError(landingError, "Invalid archive.org URL");
    return;
  }
  showError(landingError, "");
  btnPreview.disabled = true;
  previewLoading.classList.remove("hidden");
  try {
    const res = await fetch(`${API}/preview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
      credentials: "include",
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || res.statusText);
    }
    previewData = await res.json();
    renderPreview();
    show(preview);
  } catch (e) {
    showError(landingError, e.message);
  } finally {
    btnPreview.disabled = false;
    previewLoading.classList.add("hidden");
  }
}

function renderPreview() {
  const { metadata, playlist, tracks, total_duration_seconds } = previewData;
  previewTitle.textContent = metadata.title;
  previewMeta.textContent = `${metadata.performer} • ${metadata.venue} • ${metadata.date}`;
  previewPlaylist.textContent = `Playlist: ${playlist.title} (${playlist.track_count} tracks)`;
  previewTracks.innerHTML = tracks
    .map(
      (t) =>
        `<tr><td>${t.number}</td><td>${t.name}</td><td>${t.video_title}</td><td>${formatDuration(t.duration_seconds)}</td></tr>`
    )
    .join("");
  previewTotal.textContent = `Total duration: ${formatDuration(total_duration_seconds)}`;
}

function formatDuration(sec) {
  if (sec == null) return "?";
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

async function handleProceed() {
  if (!authStatus) {
    alert("Please sign in with YouTube first.");
    return;
  }
  try {
    const res = await fetch(`${API}/process`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: urlInput.value.trim() }),
      credentials: "include",
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || res.statusText);
    }
    const data = await res.json();
    currentJobId = data.job_id;
    show(processing);
    progressFill.style.width = "0%";
    progressFill.classList.remove("hidden");
    progressIndeterminate.classList.add("hidden");
    progressText.textContent = "Starting...";
    pollJob();
  } catch (e) {
    alert(e.message);
  }
}

async function pollJob() {
  const res = await fetch(`${API}/job/${currentJobId}`, { credentials: "include" });
  const data = await res.json();
  const msg = data.progress?.message || data.status;
  const current = data.progress?.current ?? 0;
  const total = data.progress?.total ?? 0;

  progressText.textContent = msg;

  if (total > 0) {
    progressIndeterminate.classList.add("hidden");
    progressFill.classList.remove("hidden");
    const pct = Math.min(98, Math.round(100 * current / total));
    progressFill.style.width = `${pct}%`;
  } else {
    progressFill.classList.add("hidden");
    progressIndeterminate.classList.remove("hidden");
  }

  if (data.status === "complete") {
    progressIndeterminate.classList.add("hidden");
    progressFill.classList.remove("hidden");
    progressFill.style.width = "100%";
    progressText.textContent = "Complete!";
    playlistLink.href = data.playlist_url;
    playlistLink.textContent = data.playlist_url;
    show(review);
    return;
  }
  if (data.status === "failed") {
    progressIndeterminate.classList.add("hidden");
    progressFill.classList.remove("hidden");
    progressText.textContent = "Failed: " + (data.error || "Unknown error");
    return;
  }
  setTimeout(pollJob, 800);
}

async function handleMakePublic() {
  try {
    const res = await fetch(`${API}/job/${currentJobId}/publish`, {
      method: "POST",
      credentials: "include",
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || res.statusText);
    }
    const data = await res.json();
    publicPlaylistLink.href = data.playlist_url;
    publicPlaylistLink.textContent = data.playlist_url;
    show(complete);
  } catch (e) {
    alert(e.message);
  }
}

function handleStartOver() {
  previewData = null;
  currentJobId = null;
  urlInput.value = "";
  show(landing);
}

// Parse URL params for auth callback
(function () {
  const q = new URLSearchParams(window.location.search);
  if (q.get("error")) {
    showError(landingError, q.get("error") === "auth_denied" ? "Sign-in was cancelled." : q.get("error"));
  }
  if (q.get("signed_in")) {
    window.history.replaceState({}, document.title, window.location.pathname);
  }
})();

// Event listeners
btnSignin.addEventListener("click", handleSignIn);
btnPreview.addEventListener("click", handlePreview);
btnBack.addEventListener("click", () => show(landing));
btnProceed.addEventListener("click", handleProceed);
btnMakePublic.addEventListener("click", handleMakePublic);
btnStartOver.addEventListener("click", handleStartOver);

// Init
checkAuth();
