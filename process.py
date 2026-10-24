#!/usr/bin/env python3
"""
EchoNotes Automated Pipeline
End-to-end automation:
YouTube URL / Audio File -> Download -> Whisper Transcription -> Chunking -> LLM Structured Notes -> Web UI
"""

import argparse
import os
import re
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

def sanitize_filename(name: str) -> str:
    """Convert title to a filesystem-friendly string."""
    clean = re.sub(r'[^\w\s-]', '', name).strip().lower()
    return re.sub(r'[-\s]+', '_', clean)[:50]

def run_step(step_name: str, cmd: list[str], env: dict = None):
    print(f"\n{'='*60}")
    print(f"STEP: {step_name}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*60}")
    t0 = time.time()
    res = subprocess.run(cmd, env=env)
    if res.returncode != 0:
        print(f"\nError: Step '{step_name}' failed with exit code {res.returncode}", file=sys.stderr)
        sys.exit(res.returncode)
    print(f"Finished '{step_name}' in {time.time() - t0:.1f}s")

def get_youtube_title(url: str) -> str:
    try:
        res = subprocess.run(
            ["yt-dlp", "--print", "%(title)s", url],
            capture_output=True,
            text=True,
            check=True
        )
        title = res.stdout.strip()
        if title:
            return title
    except Exception as e:
        print(f"Warning: Could not extract title from YouTube URL ({e}). Using default.")
    return "YouTube Lecture"

def main():
    parser = argparse.ArgumentParser(
        description="Automated EchoNotes Pipeline: Download YouTube Lecture, Transcribe, Generate Structured Notes, and Launch Web UI."
    )
    parser.add_argument(
        "input",
        help="YouTube URL (e.g. https://www.youtube.com/watch?v=...) or path to local audio/video file."
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=30.0,
        help="Web UI replay speed multiplier (default: 30 = 1 lecture minute per 2 real seconds; use 1 for real-time)."
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for the FastAPI web server (default: 8000)."
    )
    parser.add_argument(
        "--course",
        type=str,
        default=None,
        help="Course or lecture title context for the LLM (default: auto-detected from video title)."
    )
    parser.add_argument(
        "--whisper-model",
        type=str,
        default="small",
        help="Whisper model size: tiny, base, small, medium, large-v3 (default: small)."
    )
    parser.add_argument(
        "--backend",
        type=str,
        choices=["ollama", "gemini"],
        default=None,
        help="LLM backend override (default: configured in .env)."
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not automatically open the web browser."
    )
    parser.add_argument(
        "--skip-transcribe",
        action="store_true",
        help="Skip transcription if JSON already exists for the audio file."
    )

    args = parser.parse_args()

    # Environment setup
    env = os.environ.copy()
    if args.backend:
        env["BACKEND"] = args.backend
    if args.whisper_model:
        env["WHISPER_MODEL"] = args.whisper_model

    root_dir = Path(__file__).resolve().parent

    # Stage 1: Download or locate audio
    is_url = args.input.startswith("http://") or args.input.startswith("https://")
    if is_url:
        print(f"\n[1/5] Fetching video information for: {args.input}")
        video_title = get_youtube_title(args.input)
        if not args.course:
            args.course = video_title
        slug = sanitize_filename(video_title)
        wav_path = root_dir / f"{slug}.wav"

        print(f"Video Title: {video_title}")
        print(f"Target WAV:  {wav_path}")

        if wav_path.exists():
            print(f"Audio file {wav_path} already exists. Skipping download.")
        else:
            download_cmd = [
                "yt-dlp",
                "-x",
                "--audio-format", "wav",
                "--postprocessor-args", "ffmpeg:-ar 16000 -ac 1 -c:a pcm_s16le",
                "-o", str(wav_path),
                args.input
            ]
            run_step("Download YouTube Audio (16 kHz mono WAV)", download_cmd)
    else:
        src_path = Path(args.input).resolve()
        if not src_path.exists():
            print(f"Error: Local file '{src_path}' not found.", file=sys.stderr)
            sys.exit(1)
        wav_path = src_path
        if not args.course:
            args.course = src_path.stem.replace("_", " ").title()

    base_name = str(wav_path).rsplit(".", 1)[0]
    json_path = f"{base_name}.json"
    chunks_path = f"{base_name}_chunks.json"
    notes_path = f"{base_name}_notes.json"

    env["COURSE"] = args.course
    print(f"\nLecture Context: {args.course}")

    # Stage 2: Transcribe
    if args.skip_transcribe and Path(json_path).exists():
        print(f"\n[2/5] Transcript {json_path} exists. Skipping Whisper transcription.")
    else:
        run_step(
            "Whisper Transcription",
            [sys.executable, str(root_dir / "transcribe.py"), str(wav_path)],
            env=env
        )

    # Stage 3: Chunker
    run_step(
        "Transcript Chunking (3-minute overlapping windows)",
        [sys.executable, str(root_dir / "chunker.py"), json_path],
        env=env
    )

    # Stage 4: Structured Notes Generation
    run_step(
        "LLM Notes & Concepts Generation",
        [sys.executable, str(root_dir / "notes.py"), chunks_path],
        env=env
    )

    if not Path(notes_path).exists():
        print(f"Error: Expected notes file {notes_path} was not created.", file=sys.stderr)
        sys.exit(1)

    # Stage 5: Launch Web Dashboard
    print(f"\n{'='*60}")
    print("PIPELINE COMPLETED SUCCESSFULLY!")
    print(f"Notes file: {notes_path}")
    print(f"Dashboard URL: http://localhost:{args.port}")
    print(f"{'='*60}\n")

    env["NOTES_FILE"] = notes_path
    env["SPEED"] = str(args.speed)

    dashboard_url = f"http://localhost:{args.port}"
    if not args.no_browser:
        def open_browser():
            time.sleep(1.2)
            print(f"Opening browser at {dashboard_url} ...")
            webbrowser.open(dashboard_url)
        import threading
        threading.Thread(target=open_browser, daemon=True).start()

    server_cmd = [
        "uvicorn",
        "app:app",
        "--host", "127.0.0.1",
        "--port", str(args.port)
    ]
    subprocess.run(server_cmd, env=env)

if __name__ == "__main__":
    main()
