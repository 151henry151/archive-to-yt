/* Archive to YouTube - Web UI */

const API = "api";

let authStatus = false;
let previewData = null;
let currentJobId = null;
let chosenPrivacy = "private";

// Elements
const landing = document.getElementById("landing");
const preview = document.getElementById("preview");
const editSection = document.getElementById("edit");
const processing = document.getElementById("processing");
const review = document.getElementById("review");
const complete = document.getElementById("complete");

const urlInput = document.getElementById("url");
const landingError = document.getElementById("landing-error");
const btnSignin = document.getElementById("btn-signin");
const signedIn = document.getElementById("signed-in");
const btnPreview = document.getElementById("btn-preview");
const previewLoading = document.getElementById("preview-loading");
const previewLoadingStatus = document.getElementById("preview-loading-status");
const previewLoadingProgress = document.getElementById("preview-loading-progress");
const previewTitle = document.getElementById("preview-title");
const previewMeta = document.getElementById("preview-meta");
const previewPlaylist = document.getElementById("preview-playlist");
const previewTracks = document.getElementById("preview-tracks");
const previewTotal = document.getElementById("preview-total");
const btnBack = document.getElementById("btn-back");
const btnEdit = document.getElementById("btn-edit");
const btnEditBack = document.getElementById("btn-edit-back");
const editPlaylistTitle = document.getElementById("edit-playlist-title");
const editPlaylistDescription = document.getElementById("edit-playlist-description");
const editTracksContainer = document.getElementById("edit-tracks");
const btnProceed = document.getElementById("btn-proceed");
const progressFill = document.getElementById("progress-fill");
const progressIndeterminate = document.getElementById("progress-indeterminate");
const progressText = document.getElementById("progress-text");
const playlistLink = document.getElementById("playlist-link");
const btnMakePublic = document.getElementById("btn-make-public");
const publicPlaylistLink = document.getElementById("public-playlist-link");
const btnStartOver = document.getElementById("btn-start-over");

function show(section) {
  [landing, previewLoading, preview, editSection, processing, review, complete].forEach((el) => {
    if (el) el.classList.add("hidden");
  });
  if (section) section.classList.remove("hidden");
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
  show(previewLoading);
  if (previewLoadingStatus) previewLoadingStatus.textContent = "Starting...";
  if (previewLoadingProgress) previewLoadingProgress.style.width = "0%";

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
    const { job_id } = await res.json();
    await pollPreviewJob(job_id);
  } catch (e) {
    show(landing);
    showError(landingError, e.message);
  }
}

async function pollPreviewJob(jobId) {
  const res = await fetch(`${API}/preview/job/${jobId}`, { credentials: "include" });
  if (!res.ok) {
    show(landing);
    showError(landingError, "Failed to get preview status");
    return;
  }
  const data = await res.json();
  const prog = data.progress || {};
  const msg = prog.message || data.status;
  const current = prog.current ?? 0;
  const total = prog.total ?? 0;

  if (previewLoadingStatus) previewLoadingStatus.textContent = msg;
  if (previewLoadingProgress && total > 0) {
    previewLoadingProgress.style.width = `${Math.min(98, Math.round(100 * current / total))}%`;
  }

  if (data.status === "complete" && data.result) {
    if (previewLoadingProgress) previewLoadingProgress.style.width = "100%";
    previewData = data.result;
    renderPreview();
    show(preview);
    return;
  }
  if (data.status === "failed") {
    show(landing);
    showError(landingError, data.error || "Preview failed");
    return;
  }
  setTimeout(() => pollPreviewJob(jobId), 800);
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

function showEditFromPreview() {
  if (!previewData) return;
  const { playlist, tracks } = previewData;
  if (editPlaylistTitle) editPlaylistTitle.value = playlist.title || "";
  if (editPlaylistDescription) editPlaylistDescription.value = playlist.description || "";
  if (editTracksContainer) {
    editTracksContainer.innerHTML = tracks
      .map(
        (t) =>
          `<div class="edit-track" data-number="${t.number}">
            <label>Track ${t.number}: ${escapeHtml(t.name)}</label>
            <input type="text" class="edit-video-title full-width" value="${escapeHtml(t.video_title || "")}" placeholder="Video title">
            <textarea class="edit-video-description full-width" rows="2" placeholder="Description">${escapeHtml(t.description_preview || "")}</textarea>
          </div>`
      )
      .join("");
  }
  show(editSection);
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

async function handleProceed() {
  if (!authStatus) {
    alert("Please sign in with YouTube first.");
    return;
  }
  const payload = { url: urlInput.value.trim(), privacy_status: chosenPrivacy };
  const editPayload = editSection && !editSection.classList.contains("hidden") ? getEditPayload() : null;
  if (editPayload) {
    payload.privacy_status = editPayload.privacy_status;
    chosenPrivacy = editPayload.privacy_status;
    payload.playlist_title = editPayload.playlist_title || undefined;
    payload.playlist_description = editPayload.playlist_description || undefined;
    payload.tracks = editPayload.tracks;
  }
  try {
    const res = await fetch(`${API}/process`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
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

function getEditPayload() {
  const playlist_title = editPlaylistTitle ? editPlaylistTitle.value.trim() : "";
  const playlist_description = editPlaylistDescription ? editPlaylistDescription.value.trim() : "";
  const privacyRadios = document.querySelectorAll('input[name="privacy"]:checked');
  const privacy_status = privacyRadios.length ? privacyRadios[0].value : "private";
  const tracks = [];
  if (editTracksContainer) {
    editTracksContainer.querySelectorAll(".edit-track").forEach((el) => {
      const number = parseInt(el.dataset.number, 10);
      const titleInput = el.querySelector(".edit-video-title");
      const descInput = el.querySelector(".edit-video-description");
      tracks.push({
        number,
        video_title: (titleInput && titleInput.value) ? titleInput.value.trim() : "",
        video_description: (descInput && descInput.value) ? descInput.value.trim() : "",
      });
    });
  }
  return { playlist_title, playlist_description, tracks, privacy_status };
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
if (btnBack) btnBack.addEventListener("click", () => show(landing));
if (btnEdit) btnEdit.addEventListener("click", showEditFromPreview);
if (btnEditBack) btnEditBack.addEventListener("click", () => show(preview));
btnProceed.addEventListener("click", handleProceed);
btnMakePublic.addEventListener("click", handleMakePublic);
btnStartOver.addEventListener("click", handleStartOver);

// Init
checkAuth();
