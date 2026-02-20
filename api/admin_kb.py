# api/admin_kb.py
import os
import sys
import secrets
from pathlib import Path
from typing import List
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from dotenv import load_dotenv
import subprocess

load_dotenv()

router = APIRouter(prefix="/admin/api", tags=["Admin KB"])
security = HTTPBasic()

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
DATA_DIR = Path("data/clean")

# --- Auth ---
def verify_admin(credentials: HTTPBasicCredentials = Depends(security)):
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
    # Security: prevent path traversal
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
    """Create a new knowledge file"""
    # Security: validate filename
    if ".." in req.name or "/" in req.name or "\\" in req.name:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not req.name.endswith(".txt"):
        raise HTTPException(status_code=400, detail="Only .txt files allowed")
    
    file_path = DATA_DIR / req.name
    if file_path.exists():
        raise HTTPException(status_code=409, detail="File already exists")
    
    try:
        file_path.write_text(req.content, encoding="utf-8")
        return {"message": "File created successfully", "name": req.name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/files/{filename}")
def update_file(filename: str, req: UpdateFileReq, username: str = Depends(verify_admin)):
    """Update an existing file"""
    # Security: prevent path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    file_path = DATA_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        file_path.write_text(req.content, encoding="utf-8")
        return {"message": "File updated successfully", "name": filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/files/{filename}")
def delete_file(filename: str, username: str = Depends(verify_admin)):
    """Delete a knowledge file"""
    # Security: prevent path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    file_path = DATA_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        file_path.unlink()
        return {"message": "File deleted successfully", "name": filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reingest")
async def reingest_knowledge(username: str = Depends(verify_admin)):
    """Trigger re-ingestion with real-time progress updates"""
    from fastapi.responses import StreamingResponse
    import asyncio
    
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
            
            yield f"data: {{\"status\": \"started\", \"message\": \"Starting re-ingestion...\"}}\n\n"
            
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    line = line.strip()
                    # Escape quotes and backslashes for JSON
                    safe_line = line.replace('\\', '\\\\').replace('"', '')
                    yield f"data: {{\"status\": \"progress\", \"message\": \"{safe_line}\"}}\n\n"
                await asyncio.sleep(0.1)
            
            stderr = process.stderr.read()
            if process.returncode == 0:
                yield f"data: {{\"status\": \"success\", \"message\": \"Re-ingestion completed successfully!\"}}\n\n"
            else:
                error_msg = stderr.replace('"', '').replace('\n', ' ')[:500]
                yield f"data: {{\"status\": \"error\", \"message\": \"Re-ingestion failed: {error_msg}\"}}\n\n"
        except Exception as e:
            yield f"data: {{\"status\": \"error\", \"message\": \"Error: {str(e).replace('"', '')}\"}}\n\n"
    
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
