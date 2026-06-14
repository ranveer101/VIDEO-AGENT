# Video Mind

Video Mind is an AI video intelligence dashboard that turns YouTube links or uploaded audio/video files into transcripts, summaries, structured insights, and transcript-grounded chat.

## Features

- Email signup/login with protected user history
- YouTube URL and local audio/video upload support
- Audio extraction, WAV conversion, and chunking
- English transcription with local Whisper
- Hinglish transcription/translation with Sarvam AI
- Meeting summaries, action items, decisions, and open questions
- General video summaries, key points, takeaways, and highlights
- RAG chat over the current transcript using LangChain and ChromaDB
- Live job progress with recent analysis history

## Tech Stack

- Backend: FastAPI, SQLite
- Frontend: HTML, CSS, vanilla JavaScript
- AI/LLM: Mistral AI, LangChain
- Speech: Whisper, Sarvam AI
- Vector DB: ChromaDB
- Media: yt-dlp, pydub, FFmpeg

## Project Structure

```text
backend.py              FastAPI app and API routes
main.py                 End-to-end analysis pipeline
storage.py              SQLite auth and analysis history helpers
core/                   Transcription, summarization, extraction, RAG, vector store
utils/                  Audio download/conversion/chunking helpers
static/                 Dashboard frontend
```

## Setup

1. Create and activate a Python virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Install FFmpeg and make sure it is available on your PATH.
4. Copy `.env.example` to `.env` and fill in your API keys.
5. Start the FastAPI app:

```bash
python -m uvicorn backend:app --host 127.0.0.1 --port 8000

         python -m uvicorn backend:app --host 127.0.0.1 --port 8005 --reload
```

6. Open:

```text
http://127.0.0.1:8000/
```

## Environment Variables

```text
MISTRAL_API_KEY      Required for summaries, insights, and chat
MISTRAL_MODEL        Optional; defaults to mistral-small-latest
SARVAM_API_KEY       Required for Hinglish transcription
SARVAM_STT_MODEL     Optional Sarvam model name
WHISPER_MODEL        Optional Whisper model name, for example tiny or small
CORS_ORIGINS         Optional comma-separated allowed browser origins
```

## Deploy on Render

1. Push this repo to GitHub (do not commit `.env`).
2. On [Render](https://render.com), create a **New Web Service** and connect the repo.
3. Choose **Docker** as the runtime (uses the repo `Dockerfile`).
4. Set **Health Check Path** to `/api/health`.
5. Add environment variables in the Render dashboard:
   - `MISTRAL_API_KEY` (required)
   - `SARVAM_API_KEY` (only if you use Hinglish)
   - `CORS_ORIGINS` = your Render URL, e.g. `https://video-mind.onrender.com`
   - `WHISPER_MODEL` = `tiny` (recommended on small instances)
6. Deploy. First build may take 15–30+ minutes (PyTorch + Whisper).

Alternatively, use **Blueprint**: New → Blueprint → point at this repo (`render.yaml` is included).

**Important:** Free tier has limited RAM; Whisper + PyTorch often needs at least the **Starter** plan. SQLite and `vector_db/` live on ephemeral disk and reset when the service redeploys unless you add a Render persistent disk.

## Notes

- Use English mode for local Whisper transcription.
- Use Hinglish mode only after adding a valid `SARVAM_API_KEY`.
- Local runtime files such as `.env`, databases, vector stores, downloads, logs, and caches are intentionally ignored by Git.

## Resume Summary

Built a full-stack AI video intelligence platform using FastAPI, Whisper/Sarvam, Mistral, LangChain, ChromaDB, and SQLite to transcribe videos, generate structured insights, and provide authenticated transcript-grounded RAG chat.
