# api/admin_kb.py
import os
import sys
import secrets
import base64
import requests
from pathlib import Path
from typing import List
from fastapi import APIRouter, HTTPException, Depends, status, Request
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from dotenv import load_dotenv
import subprocess

load_dotenv()

router = APIRouter(prefix="/admin/api", tags=["Admin KB"])
security = HTTPBasic(auto_error=False)

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
DATA_DIR = Path("data/clean")
DATA_DIR.mkdir(parents=True, exist_ok=True)

# GitHub config
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")   # e.g. "your-username/your-repo"
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")

ALLOWED_ORIGIN = "https://enatega-chatbot-knowledge-update.netlify.app"


# --- GitHub Sync ---
def _github_headers():
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }

def _get_file_sha(filename: str) -> str | None:
    """Get the SHA of an existing file in GitHub (needed for updates/deletes)."""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return None
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/data/clean/{filename}"
    resp = requests.get(url, headers=_github_headers(), params={"ref": GITHUB_BRANCH})
    if resp.status_code == 200:
        return resp.json().get("sha")
    return None

def github_upsert_file(filename: str, content: str, commit_message: str):
    """Create or update a file in GitHub."""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        print("GitHub sync skipped: GITHUB_TOKEN or GITHUB_REPO not set")
        return

    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/data/clean/{filename}"
    encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")

    payload = {
        "message": commit_message,
        "content": encoded,
        "branch": GITHUB_BRANCH,
    }

    # If file already exists in GitHub, we need its SHA to update it
    sha = _get_file_sha(filename)
    if sha:
        payload["sha"] = sha

    resp = requests.put(url, headers=_github_headers(), json=payload)
    if resp.status_code not in (200, 201):
        print(f"GitHub upsert failed for {filename}: {resp.status_code} {resp.text}")
    else:
        print(f"GitHub sync success: {commit_message}")

def github_delete_file(filename: str, commit_message: str):
    """Delete a file from GitHub."""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        print("GitHub sync skipped: GITHUB_TOKEN or GITHUB_REPO not set")
        return

    sha = _get_file_sha(filename)
    if not sha:
        print(f"GitHub delete skipped: {filename} not found in repo")
        return

    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/data/clean/{filename}"
    payload = {
        "message": commit_message,
        "sha": sha,
        "branch": GITHUB_BRANCH,
    }

    resp = requests.delete(url, headers=_github_headers(), json=payload)
    if resp.status_code != 200:
        print(f"GitHub delete failed for {filename}: {resp.status_code} {resp.text}")
    else:
        print(f"GitHub sync success: {commit_message}")


# --- Auth ---
def verify_admin(request: Request, credentials: HTTPBasicCredentials = Depends(security)):
    # Skip auth for preflight OPTIONS requests
    if request.method == "OPTIONS":
        return "preflight"

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    correct_username = secrets.compare_digest(credentials.username, ADMIN_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    return credentials.username


# --- Models ---
class FileItem(BaseModel):
    name: str
    size: int
    modified: str

class FileContent(BaseModel):
    name: str
    content: str

class CreateFileReq(BaseModel):
    name: str
    content: str

class UpdateFileReq(BaseModel):
    content: str


# --- Endpoints ---
@router.get("/files", response_model=List[FileItem])
def list_files(username: str = Depends(verify_admin)):
    """List all .txt files in data/clean/"""
    try:
        files = []
        for f in DATA_DIR.glob("*.txt"):
            stat = f.stat()
            files.append(FileItem(
                name=f.name,
                size=stat.st_size,
                modified=stat.st_mtime.__str__()
            ))
        return sorted(files, key=lambda x: x.name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/files/{filename}", response_model=FileContent)
def get_file(filename: str, username: str = Depends(verify_admin)):
    """Get content of a specific file"""
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    file_path = DATA_DIR / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    try:
        content = file_path.read_text(encoding="utf-8")
        return FileContent(name=filename, content=content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/files", status_code=201)
def create_file(req: CreateFileReq, username: str = Depends(verify_admin)):
    """Create a new knowledge file and sync to GitHub"""
    if ".." in req.name or "/" in req.name or "\\" in req.name:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not req.name.endswith(".txt"):
        raise HTTPException(status_code=400, detail="Only .txt files allowed")

    file_path = DATA_DIR / req.name
    if file_path.exists():
        raise HTTPException(status_code=409, detail="File already exists")

    try:
        file_path.write_text(req.content, encoding="utf-8")
        # Sync to GitHub
        github_upsert_file(
            filename=req.name,
            content=req.content,
            commit_message=f"[Admin] Create {req.name}",
        )
        return {"message": "File created successfully", "name": req.name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/files/{filename}")
def update_file(filename: str, req: UpdateFileReq, username: str = Depends(verify_admin)):
    """Update an existing file and sync to GitHub"""
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    file_path = DATA_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    try:
        file_path.write_text(req.content, encoding="utf-8")
        # Sync to GitHub
        github_upsert_file(
            filename=filename,
            content=req.content,
            commit_message=f"[Admin] Update {filename}",
        )
        return {"message": "File updated successfully", "name": filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/files/{filename}")
def delete_file(filename: str, username: str = Depends(verify_admin)):
    """Delete a knowledge file and sync to GitHub"""
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    file_path = DATA_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    try:
        file_path.unlink()
        # Sync to GitHub
        github_delete_file(
            filename=filename,
            commit_message=f"[Admin] Delete {filename}",
        )
        return {"message": "File deleted successfully", "name": filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reingest")
async def reingest_knowledge(username: str = Depends(verify_admin)):
    """Trigger re-ingestion with real-time progress updates"""
    import asyncio
    import json

    async def progress_stream():
        try:
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'

            process = subprocess.Popen(
                [sys.executable, "ingest_qdrant.py", "--recreate"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                encoding='utf-8',
                errors='replace',
                bufsize=1
            )

            msg = json.dumps({"status": "started", "message": "Starting re-ingestion..."})
            yield f"data: {msg}\n\n"

            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    line = line.strip()
                    msg = json.dumps({"status": "progress", "message": line})
                    yield f"data: {msg}\n\n"
                await asyncio.sleep(0.1)

            stderr = process.stderr.read()
            if process.returncode == 0:
                msg = json.dumps({"status": "success", "message": "Re-ingestion completed successfully!"})
                yield f"data: {msg}\n\n"
            else:
                error_msg = stderr[:500]
                msg = json.dumps({"status": "error", "message": f"Re-ingestion failed: {error_msg}"})
                yield f"data: {msg}\n\n"
        except Exception as e:
            error_message = str(e).replace('"', "'").replace('\n', ' ')
            msg = json.dumps({"status": "error", "message": f"Error: {error_message}"})
            yield f"data: {msg}\n\n"

    return StreamingResponse(progress_stream(), media_type="text/event-stream")

@router.get("/status")
def get_status(username: str = Depends(verify_admin)):
    """Get Qdrant collection status"""
    try:
        from qdrant_client import QdrantClient
        QDRANT_URL = os.getenv("QDRANT_URL")
        QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
        COLLECTION = os.getenv("COLLECTION_NAME")

        client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        count = client.count(collection_name=COLLECTION, exact=True).count

        return {
            "collection": COLLECTION,
            "chunks": count,
            "files": len(list(DATA_DIR.glob("*.txt")))
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/debug")
def debug_info(username: str = Depends(verify_admin)):
    """Debug: check filesystem state on Railway"""
    return {
        "cwd": os.getcwd(),
        "data_dir_absolute": str(DATA_DIR.absolute()),
        "data_dir_exists": DATA_DIR.exists(),
        "data_dir_is_dir": DATA_DIR.is_dir() if DATA_DIR.exists() else False,
        "files": [f.name for f in DATA_DIR.glob("*.txt")] if DATA_DIR.exists() else [],
        "parent_contents": [f.name for f in DATA_DIR.parent.iterdir()] if DATA_DIR.parent.exists() else [],
        "github_configured": bool(GITHUB_TOKEN and GITHUB_REPO),
        "github_repo": GITHUB_REPO or "not set",
        "github_branch": GITHUB_BRANCH,
    }