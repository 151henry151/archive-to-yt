"""
FastAPI application for archive-to-yt web UI.
"""

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import FileResponse

# Port for internal binding (override via PORT env)
PORT = int(os.environ.get("PORT", "18765"))

# Paths relative to project root
ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT / "frontend"
STATIC_DIR = FRONTEND_DIR / "static"

app = FastAPI(
    title="Archive to YouTube",
    description="Upload archive.org audio tracks to YouTube as videos",
    version="1.1.0",
)

# Session secret (required for session cookies)
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")

# When BASE_URL is set (path-based deployment), scope session cookie to app path
# so it's sent correctly after OAuth redirects. Use Secure when served over HTTPS.
_session_path = "/"
_base_url = os.environ.get("BASE_URL", "")
if _base_url and _base_url.startswith("https://"):
    from urllib.parse import urlparse
    _parsed = urlparse(_base_url)
    if _parsed.path:
        _session_path = _parsed.path.rstrip("/") or "/"
    _https_only = True
else:
    _https_only = False

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    max_age=86400 * 7,  # 7 days
    path=_session_path,
    same_site="lax",
    https_only=_https_only,
)

# CORS for local dev (relaxed; tighten for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    """Health check for load balancers and monitoring."""
    return {"status": "ok", "version": "1.1.0"}


# Mount static files if directory exists
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/terms")
def terms():
    """Serve Terms of Service page."""
    path = FRONTEND_DIR / "terms.html"
    if path.exists():
        return FileResponse(path)
    raise HTTPException(status_code=404, detail="Not found")


@app.get("/privacy")
def privacy():
    """Serve Privacy Policy page."""
    path = FRONTEND_DIR / "privacy.html"
    if path.exists():
        return FileResponse(path)
    raise HTTPException(status_code=404, detail="Not found")


@app.get("/")
@app.get("/preview")
@app.get("/edit")
@app.get("/process")
@app.get("/review")
@app.get("/complete")
def index():
    """Serve the SPA; all routes fall through to index.html."""
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "Frontend not found. Create frontend/index.html."}


# Include API routers
from backend.api.auth import router as auth_router
from backend.api.preview import router as preview_router
from backend.api.process import router as process_router

app.include_router(auth_router, prefix="/api", tags=["auth"])
app.include_router(preview_router, prefix="/api", tags=["preview"])
app.include_router(process_router, prefix="/api", tags=["process"])


