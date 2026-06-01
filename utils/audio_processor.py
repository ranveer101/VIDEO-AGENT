import os
from pathlib import Path

import yt_dlp
from pydub import AudioSegment


DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def _looks_like_dead_local_proxy(value: str) -> bool:
    return bool(value and ("127.0.0.1:9" in value or "localhost:9" in value))


def _clear_dead_proxy_env() -> None:
    for key in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]:
        if _looks_like_dead_local_proxy(os.environ.get(key, "")):
            os.environ.pop(key, None)


def download_youtube_audio(url: str) -> str:
    _clear_dead_proxy_env()
    output_path = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_path,
        "proxy": "",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192",
            }
        ],
        "quiet": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info).replace(".webm", ".wav").replace(".m4a", ".wav")
    return filename


def convert_to_wav(input_path: str) -> str:
    output_path = os.path.splitext(input_path)[0] + "_converted.wav"
    audio = AudioSegment.from_file(input_path)
    audio = audio.set_channels(1).set_frame_rate(16000)
    audio.export(output_path, format="wav")
    return output_path


def chunk_audio(wav_path: str, chunk_minutes: int = 10) -> list[str]:
    audio = AudioSegment.from_wav(wav_path)
    chunk_ms = chunk_minutes * 60 * 1000
    chunks = []

    for i, start in enumerate(range(0, len(audio), chunk_ms)):
        chunk = audio[start: start + chunk_ms]
        chunk_path = f"{wav_path}_chunk_{i}.wav"
        chunk.export(chunk_path, format="wav")
        chunks.append(chunk_path)

    return chunks


def process_input(source: str) -> tuple[list[str], list[str]]:
    generated_files = []

    if source.startswith("http://") or source.startswith("https://"):
        print("Detected YouTube URL. Downloading audio...")
        wav_path = download_youtube_audio(source)
    else:
        print("Detected local file. Converting to WAV...")
        wav_path = convert_to_wav(source)

    generated_files.append(wav_path)
    print("Chunking audio...")
    chunks = chunk_audio(wav_path)
    generated_files.extend(chunks)
    print(f"Audio ready - {len(chunks)} chunk(s) created.")
    return chunks, generated_files


def cleanup_generated_files(paths: list[str]) -> int:
    deleted = 0
    for path in paths:
        if not path:
            continue
        try:
            file_path = Path(path)
            if file_path.exists() and file_path.is_file():
                file_path.unlink()
                deleted += 1
        except OSError:
            pass
    return deleted
