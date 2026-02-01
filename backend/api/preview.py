"""
Preview API - dry-run preview of what would be uploaded.
Runs as a background job with real progress updates.
"""

import re
import threading
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Import from project root
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.archive_scraper import ArchiveScraper
from src.audio_downloader import AudioDownloader
from src.metadata_formatter import MetadataFormatter

router = APIRouter()

ROOT = Path(__file__).resolve().parent.parent.parent
TEMP_DIR = ROOT / "temp"
TEMP_DIR.mkdir(exist_ok=True)

# In-memory preview job store (use Redis/DB for multi-worker in production)
preview_jobs: dict = {}


class PreviewRequest(BaseModel):
    url: str


def _run_preview_job(job_id: str, url: str):
    """Background task: generate preview and report progress."""
    job = preview_jobs.get(job_id)
    if not job or job["status"] != "pending":
        return

    def progress(step: str, message: str, current: int = 0, total: int = 0):
        if job_id in preview_jobs:
            preview_jobs[job_id]["progress"] = {
                "step": step,
                "message": message,
                "current": current,
                "total": total,
            }

    try:
        preview_jobs[job_id]["status"] = "running"
        progress("fetch_metadata", "Fetching metadata from archive.org...")

        scraper = ArchiveScraper(url)
        metadata = scraper.extract_metadata()
        tracks = metadata.get("tracks", [])
        if not tracks:
            raise ValueError("No tracks found on archive.org page")

        progress("find_audio", "Finding tracks and audio files...")
        track_audio = scraper.get_audio_file_urls()
        if not track_audio:
            raise ValueError("No audio files found for tracks")

        formatter = MetadataFormatter()
        audio_downloader = AudioDownloader(str(TEMP_DIR))
        playlist_title = formatter.format_playlist_title(metadata)
        playlist_description = formatter.format_playlist_description(metadata, tracks)

        preview_tracks = []
        total_duration = 0.0
        n = len(track_audio)

        for i, track_info in enumerate(track_audio):
            progress(
                "durations",
                f"Getting duration for track {i + 1} of {n}...",
                current=i + 1,
                total=n,
            )
            track_num = track_info["number"]
            track_name = track_info["name"]
            audio_url = track_info["url"]

            track_info_clean = track_info.copy()
            track_name_clean = str(track_info.get("name", "Unknown Track")).strip()
            track_name_clean = re.sub(r"<[^>]+>", "", track_name_clean)
            track_name_clean = track_name_clean.replace("&gt;", ">").replace("&lt;", "<").replace("&amp;", "&")
            track_name_clean = re.sub(r"\s+", " ", track_name_clean).strip()
            if len(track_name_clean) > 100 or "\n" in track_name_clean:
                track_name_clean = track_name_clean.split("\n")[0].strip()
            if not track_name_clean:
                track_name_clean = f"Track {track_num}"
            track_info_clean["name"] = track_name_clean

            video_title = formatter.format_video_title(track_info_clean, metadata)
            if not video_title or not video_title.strip():
                video_title = f"Track {track_num} - {track_name_clean}"

            duration = audio_downloader.get_audio_duration_from_url(audio_url)
            if duration:
                total_duration += duration

            video_description = formatter.format_track_description(track_info_clean, metadata)
            description_preview = video_description[:300] + "..." if len(video_description) > 300 else video_description

            preview_tracks.append({
                "number": track_num,
                "name": track_name,
                "video_title": video_title,
                "duration_seconds": round(duration, 1) if duration else None,
                "description_preview": description_preview,
                "audio_filename": track_info.get("filename", "unknown"),
            })

        progress("prepare", "Preparing preview...")
        result = {
            "metadata": {
                "title": metadata.get("title", "Unknown"),
                "performer": metadata.get("performer", "Unknown"),
                "venue": metadata.get("venue", "Unknown"),
                "date": metadata.get("date", "Unknown"),
                "url": metadata.get("url", url),
                "identifier": metadata.get("identifier", "unknown"),
            },
            "playlist": {
                "title": playlist_title,
                "description": playlist_description,
                "track_count": len(preview_tracks),
            },
            "tracks": preview_tracks,
            "total_duration_seconds": round(total_duration, 1),
        }

        preview_jobs[job_id]["status"] = "complete"
        preview_jobs[job_id]["result"] = result
        preview_jobs[job_id]["progress"] = {
            "step": "complete",
            "message": "Preview ready.",
            "current": n,
            "total": n,
        }
    except HTTPException as e:
        preview_jobs[job_id]["status"] = "failed"
        preview_jobs[job_id]["error"] = e.detail if hasattr(e, "detail") else str(e)
        preview_jobs[job_id]["progress"] = {"step": "error", "message": str(e), "current": 0, "total": 0}
    except ValueError as e:
        preview_jobs[job_id]["status"] = "failed"
        preview_jobs[job_id]["error"] = str(e)
        preview_jobs[job_id]["progress"] = {"step": "error", "message": str(e), "current": 0, "total": 0}
    except Exception as e:
        preview_jobs[job_id]["status"] = "failed"
        preview_jobs[job_id]["error"] = str(e)
        preview_jobs[job_id]["progress"] = {"step": "error", "message": str(e), "current": 0, "total": 0}


@router.post("/preview")
def preview_start(request: PreviewRequest):
    """
    Start a preview job. Returns job_id; poll GET /api/preview/job/{job_id} for progress and result.
    """
    url = request.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    if "archive.org/details/" not in url:
        raise HTTPException(status_code=400, detail="Invalid archive.org URL")

    job_id = str(uuid.uuid4())[:8]
    preview_jobs[job_id] = {
        "status": "pending",
        "url": url,
        "progress": {"step": "pending", "message": "Starting...", "current": 0, "total": 0},
        "result": None,
        "error": None,
    }

    thread = threading.Thread(target=_run_preview_job, args=(job_id, url))
    thread.daemon = True
    thread.start()

    return {"job_id": job_id}


@router.get("/preview/job/{job_id}")
def preview_job_status(job_id: str):
    """Get preview job status, progress, and result when complete."""
    if job_id not in preview_jobs:
        raise HTTPException(status_code=404, detail="Preview job not found")

    job = preview_jobs[job_id]
    resp = {
        "job_id": job_id,
        "status": job["status"],
        "progress": job["progress"],
    }
    if job["status"] == "complete" and job.get("result"):
        resp["result"] = job["result"]
    if job["status"] == "failed" and job.get("error"):
        resp["error"] = job["error"]
    return resp
