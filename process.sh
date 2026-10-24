#!/usr/bin/env bash
set -e

# Load environment variables if present
set -a
[ -f .env ] && source .env
set +a

# Configure CUDA library path for faster-whisper (ctranslate2)
export LD_LIBRARY_PATH="$(echo "$PWD"/.venv/lib/python3.12/site-packages/nvidia/*/lib | tr ' ' ':'):$LD_LIBRARY_PATH"

if [ -z "$1" ]; then
    echo "================================================================="
    echo "  EchoNotes — Automated Lecture Assistant"
    echo "================================================================="
    echo "Usage:   ./process.sh <YOUTUBE_URL_OR_FILE> [OPTIONS]"
    echo ""
    echo "Example: ./process.sh 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'"
    echo ""
    echo "Options:"
    echo "  --speed SPEED        Replay speed multiplier (default: 30; 1 = real-time)"
    echo "  --port PORT          Web server port (default: 8000)"
    echo "  --course TITLE       Course or lecture name context"
    echo "  --whisper-model SIZE Whisper size: tiny, base, small, medium (default: small)"
    echo "  --backend NAME       LLM backend: ollama or gemini"
    echo "  --no-browser         Do not auto-open browser"
    echo "================================================================="
    exit 1
fi

exec uv run python process.py "$@"
