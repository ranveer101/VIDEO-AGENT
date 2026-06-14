import os
import re
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from core.rag_engine import ask_question, load_rag_chain
from main import run_pipeline
from storage import (
    create_token,
    create_user,
    delete_token,
    get_analysis,
    get_user_by_email,
    get_user_by_token,
    init_db,
    list_recent_analyses,
    save_analysis,
    verify_password,
)
from utils.audio_processor import cleanup_generated_files


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
MAX_HISTORY = 5
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DEFAULT_CORS_ORIGINS = "http://127.0.0.1:8000,http://localhost:8000"


def _cors_origins() -> list[str]:
    origins = os.getenv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS)
    return [origin.strip() for origin in origins.split(",") if origin.strip()]

app = FastAPI(title="Video Mind API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
init_db()

executor = ThreadPoolExecutor(max_workers=2)
jobs = {}
sessions = {}


class ChatRequest(BaseModel):
    session_id: str
    question: str


class AuthRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(AuthRequest):
    name: str


def _now_label() -> str:
    return datetime.now().strftime("%d %b %Y, %I:%M %p")


def _public_user(user: dict) -> dict:
    return {"id": user["id"], "name": user["name"], "email": user["email"]}


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _validate_email(email: str) -> str:
    normalized = _normalize_email(email)
    if not EMAIL_PATTERN.match(normalized):
        raise HTTPException(status_code=400, detail="Enter a valid email address")
    return normalized


def _validate_password(password: str) -> str:
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    return password


def _auth_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Login required")
    user = get_user_by_token(authorization.replace("Bearer ", "", 1).strip())
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return user


def _set_job(job_id: str, stage: str, detail: str, percent: int, status: str = "running") -> None:
    jobs[job_id].update(
        {
            "stage": stage,
            "detail": detail,
            "percent": percent,
            "status": status,
            "updated_at": _now_label(),
        }
    )


def _clean_result(result: dict, session_id: str) -> dict:
    clean = {key: value for key, value in result.items() if key not in {"rag_chain", "generated_files"}}
    clean["session_id"] = session_id
    return clean


def _history_entry(job_id: str, user_id: int, result: dict, status: str, source: str, language: str, content_type: str) -> dict:
    return {
        "id": job_id,
        "user_id": user_id,
        "video_name": result.get("title") or Path(source).name or "Untitled analysis",
        "created_at": _now_label(),
        "status": status,
        "source": source,
        "language": language,
        "content_type": content_type,
        "session_id": result.get("session_id"),
        "chat_available": bool(result.get("session_id") in sessions),
        "result": result if status == "complete" else None,
    }


def _remember_history(entry: dict) -> None:
    save_analysis(entry)


def _run_job(job_id: str, user_id: int, input_source: str, language: str, content_type: str, temp_path: str | None) -> None:
    generated_files = []

    def progress(stage: str, detail: str, percent: int) -> None:
        _set_job(job_id, stage, detail, percent)

    try:
        progress("uploading", "Preparing video source for analysis.", 8)
        result = run_pipeline(
            input_source,
            language=language,
            content_type=content_type,
            progress_callback=progress,
        )
        generated_files = result.get("generated_files", [])
        session_id = str(uuid.uuid4())
        sessions[session_id] = {
            "rag_chain": result["rag_chain"],
            "content_type": content_type,
            "title": result["title"],
            "summary": result["summary"],
            "collection_name": result.get("collection_name"),
            "source": input_source,
        }
        clean = _clean_result(result, session_id)
        jobs[job_id]["result"] = clean
        _remember_history(_history_entry(job_id, user_id, clean, "complete", input_source, language, content_type))
        _set_job(job_id, "complete", "Analysis complete. Temporary files cleaned.", 100, "complete")
    except Exception as exc:
        jobs[job_id]["error"] = str(exc)
        _remember_history(
            _history_entry(
                job_id,
                user_id,
                {"title": Path(input_source).name or "Failed analysis"},
                "error",
                input_source,
                language,
                content_type,
            )
        )
        _set_job(job_id, "error", str(exc), 100, "error")
    finally:
        cleanup_generated_files(generated_files)
        if temp_path and os.path.exists(temp_path):
            cleanup_generated_files([temp_path])


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/auth/register")
def register(payload: RegisterRequest):
    name = payload.name.strip()
    email = _validate_email(payload.email)
    password = _validate_password(payload.password)

    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    if get_user_by_email(email):
        raise HTTPException(status_code=400, detail="Email is already registered")
    user = create_user(name, email, password)
    token = create_token(user["id"])
    return {"token": token, "user": _public_user(user)}


@app.post("/api/auth/login")
def login(payload: AuthRequest):
    email = _validate_email(payload.email)
    user = get_user_by_email(email)
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_token(user["id"])
    return {"token": token, "user": _public_user(user)}


@app.get("/api/auth/me")
def me(user: dict = Depends(_auth_user)):
    return {"user": _public_user(user)}


@app.post("/api/auth/logout")
def logout(authorization: str | None = Header(default=None)):
    if authorization and authorization.startswith("Bearer "):
        delete_token(authorization.replace("Bearer ", "", 1).strip())
    return {"ok": True}


@app.post("/api/analyze")
async def analyze(
    source: Optional[str] = Form(None),
    language: str = Form("english"),
    content_type: str = Form("meeting"),
    file: Optional[UploadFile] = File(None),
    user: dict = Depends(_auth_user),
):
    if content_type not in {"meeting", "general"}:
        raise HTTPException(status_code=400, detail="content_type must be meeting or general")
    if language not in {"english", "hinglish"}:
        raise HTTPException(status_code=400, detail="language must be english or hinglish")

    temp_path = None
    if file and file.filename:
        suffix = Path(file.filename).suffix or ".mp4"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(await file.read())
            temp_path = temp_file.name
        input_source = temp_path
        display_name = file.filename
    elif source and source.strip():
        input_source = source.strip()
        display_name = input_source
    else:
        raise HTTPException(status_code=400, detail="Provide a YouTube URL or upload a file")

    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "id": job_id,
        "user_id": user["id"],
        "status": "queued",
        "stage": "uploading",
        "detail": "Queued for analysis.",
        "percent": 3,
        "video_name": display_name,
        "created_at": _now_label(),
        "result": None,
        "error": None,
    }
    executor.submit(_run_job, job_id, user["id"], input_source, language, content_type, temp_path)
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str, user: dict = Depends(_auth_user)):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("user_id") and job["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/api/history")
def get_history(user: dict = Depends(_auth_user)):
    return list_recent_analyses(user["id"], MAX_HISTORY)


@app.get("/api/history/{history_id}")
def get_history_item(history_id: str, user: dict = Depends(_auth_user)):
    item = get_analysis(user["id"], history_id)
    if not item or not item.get("result"):
        raise HTTPException(status_code=404, detail="No completed result for this entry")
    result = dict(item["result"])
    session_id = result.get("session_id")
    collection_name = result.get("collection_name")
    if session_id and session_id not in sessions and collection_name:
        try:
            rag_chain = load_rag_chain(
                collection_name=collection_name,
                content_type=item["content_type"],
                title=result.get("title", ""),
                summary=result.get("summary", ""),
            )
            sessions[session_id] = {
                "rag_chain": rag_chain,
                "content_type": item["content_type"],
                "title": result.get("title", ""),
                "summary": result.get("summary", ""),
                "collection_name": collection_name,
                "source": item["source"],
            }
        except Exception as e:
            print(f"Error restoring RAG session: {e}")
            result["session_id"] = None
    if result.get("session_id") not in sessions:
        result["session_id"] = None
    return result


@app.post("/api/history/{history_id}/rerun")
def rerun_history(history_id: str, user: dict = Depends(_auth_user)):
    item = get_analysis(user["id"], history_id)
    if not item:
        raise HTTPException(status_code=404, detail="History entry not found")
    if item["source"].startswith(tempfile.gettempdir()):
        raise HTTPException(status_code=400, detail="Uploaded temp files cannot be rerun. Upload the file again.")
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "id": job_id,
        "user_id": user["id"],
        "status": "queued",
        "stage": "uploading",
        "detail": "Queued for rerun.",
        "percent": 3,
        "video_name": item["video_name"],
        "created_at": _now_label(),
        "result": None,
        "error": None,
    }
    executor.submit(_run_job, job_id, user["id"], item["source"], item["language"], item["content_type"], None)
    return {"job_id": job_id}


@app.post("/api/cleanup")
def manual_cleanup(user: dict = Depends(_auth_user)):
    deleted = 0
    for folder in [BASE_DIR / "downloads"]:
        if folder.exists():
            deleted += cleanup_generated_files([str(path) for path in folder.glob("*") if path.is_file()])
    return {"deleted": deleted}


@app.post("/api/chat")
def chat(payload: ChatRequest, user: dict = Depends(_auth_user)):
    session = sessions.get(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found. Analyze a video first.")
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    answer = ask_question(session["rag_chain"], payload.question.strip())
    return {"answer": answer}
