# EchoNotes — Lecture Assistant

An end-to-end automated pipeline that converts any YouTube lecture (or local audio/video file) into structured, timestamped study material with a professional web dashboard.

Paste a YouTube URL, and EchoNotes will download the audio, transcribe it with Whisper, chunk the transcript into logical segments, run each chunk through an LLM to extract structured notes, and serve the results in a real-time web interface — all in a single terminal command.

---

## Team
 
**AADHAR CARD**, Electronics and Telecommunication, built for Tech Elevate 2026.
 
| Name |
|---|
| Prabhat Ranjan |
| Rishita |
| Sumit Kumar |
| Tanish Singhroha |


## How It Works

The system is a five-stage pipeline. Each stage is a standalone Python script that reads the output of the previous stage and writes its own output to disk.

```
YouTube URL / Audio File
        |
        v
  +-----------------+
  |  1. DOWNLOAD     |   yt-dlp + ffmpeg
  |  (process.py)    |   Extracts audio, converts to 16 kHz mono WAV
  +-----------------+
        |
        v
  +-----------------+
  |  2. TRANSCRIBE   |   faster-whisper (CTranslate2 + CUDA)
  |  (transcribe.py) |   Speech-to-text with timestamps
  +-----------------+
        |  lecture.json  (timestamped sentence segments)
        v
  +-----------------+
  |  3. CHUNK        |   Sliding window algorithm
  |  (chunker.py)    |   Groups sentences into 3-min overlapping windows
  +-----------------+
        |  lecture_chunks.json  (text blocks with start/end times)
        v
  +-----------------+
  |  4. LLM NOTES    |   Ollama (local) or Google Gemini (cloud)
  |  (notes.py)      |   Structured extraction per chunk
  +-----------------+
        |  lecture_notes.json  (structured JSON with all fields)
        v
  +-----------------+
  |  5. WEB UI       |   FastAPI + WebSocket + ReportLab
  |  (app.py)        |   Real-time dashboard with PDF/Markdown export
  +-----------------+
        |
        v
  http://localhost:8000
```

### Stage 1 — Audio Download (`process.py`)

When given a YouTube URL, the orchestrator script uses `yt-dlp` to extract audio and `ffmpeg` to convert it into a 16 kHz, single-channel, 16-bit PCM WAV file (the exact format Whisper expects). If a local file is provided instead, it is used directly (with automatic format conversion if needed).

The video title is auto-detected from YouTube metadata and passed downstream as the course/lecture context for the LLM.

### Stage 2 — Speech-to-Text Transcription (`transcribe.py`)

The WAV file is loaded into memory and transcribed using [faster-whisper](https://github.com/SYSTRAN/faster-whisper), a CTranslate2-optimized implementation of OpenAI's Whisper model.

- **Model**: Configurable (`tiny`, `base`, `small`, `medium`, `large-v3`). Default is `small`.
- **Device**: Automatically uses CUDA GPU if available, otherwise falls back to CPU.
- **VAD filtering**: Silero VAD is enabled to skip silent regions and reduce hallucinations.
- **Beam search**: Uses beam size 5 for improved accuracy.

Output: a JSON array of `{start, end, text}` sentence-level segments with precise timestamps.

### Stage 3 — Transcript Chunking (`chunker.py`)

Raw Whisper segments are short (typically a single sentence). The chunker groups them into larger 3-minute windows with 20-second overlaps using a sliding-window algorithm. This produces text blocks that are long enough for the LLM to reason over coherent topics, while the overlap ensures no concept is split across chunk boundaries.

Output: a JSON array where each element has `{id, start, end, text}` — the concatenated transcript text for that time window.

### Stage 4 — LLM Structured Note Generation (`notes.py`)

Each chunk is sent to an LLM (either a local Ollama model or Google Gemini) with a detailed system prompt. The LLM is instructed to return structured JSON conforming to a Pydantic schema. The output per chunk includes:

| Field | Description |
|---|---|
| **topic** | A specific 4–8 word academic title for the segment (never generic). |
| **importance** | `Core`, `High`, or `Moderate` — conceptual weight for exams. |
| **difficulty** | `Introductory`, `Intermediate`, or `Advanced`. |
| **notes** | 5–8 self-contained bullet points summarizing the key takeaways. |
| **concepts** | Technical terms the lecturer explicitly defined, with definitions. |
| **questions** | 2–3 conceptual MCQ/short-answer review questions with answers. |
| **action_items** | Explicit deadlines, problem sets, or readings (if any). |
| **study_resources** | 2–3 recommended textbook chapters or references for further study. |

The prompt enforces strict rules: no generic titles, no information outside the transcript, no repeated concepts across chunks, and plausible MCQ distractors. Pydantic validation with up to 3 retries ensures valid JSON output.

Previously covered terms are tracked and passed to each subsequent chunk to avoid redundancy.

### Stage 5 — Web Dashboard (`app.py` + `index.html`)

A FastAPI server loads the generated notes JSON and replays chunks over WebSocket in accelerated time (default 30x, configurable). The single-page frontend connects via WebSocket and renders each chunk as it arrives.

**Dashboard tabs:**

- **Lecture Notes** — Timestamped bullet points with importance/difficulty badges and inline study resource tags.
- **Key Concepts** — Term-definition cards for every concept the lecturer introduced.
- **Review Questions** — MCQs with lettered options and interactive "Reveal Answer" toggles.
- **Study Resources** — Dedicated view of all recommended textbooks and references per segment.
- **Action Items** — Explicit assignments, deadlines, or readings.

**Additional features:**

- **Mark Section** — Flag the current live timestamp as important (the chunk is highlighted in the UI).
- **Download PDF** — Generates and downloads a publication-grade PDF summary report via ReportLab, including all notes, concepts, questions, difficulty ratings, and study references with page numbering and headers.
- **Export Markdown** — Downloads a structured Markdown document of all notes.
- **Search & Filter** — Full-text search across notes, concepts, and resources. Toggle to show only important/flagged sections.

---

## One-Command Usage

```bash
./process.sh "https://www.youtube.com/watch?v=VIDEO_ID"
```

This single command runs all five stages and opens the dashboard in your default browser.

### Options

```bash
# Specify course context for the LLM
./process.sh "https://youtube.com/watch?v=..." --course "MIT 6.006: Introduction to Algorithms"

# Choose Whisper model size (tiny/base/small/medium/large-v3)
./process.sh "https://youtube.com/watch?v=..." --whisper-model medium

# Set replay speed (1 = real-time, 30 = fast, 9999 = instant)
./process.sh "https://youtube.com/watch?v=..." --speed 9999

# Use Gemini instead of Ollama for note generation
./process.sh "https://youtube.com/watch?v=..." --backend gemini

# Custom port, no auto-open browser
./process.sh "https://youtube.com/watch?v=..." --port 8080 --no-browser

# Process a local file
./process.sh ./recording.mp4
```

### Replay Existing Notes

If you have already processed a lecture and just want to view the notes again:

```bash
NOTES_FILE=lecture_notes.json ./run.sh uvicorn app:app --reload
```

Then open `http://localhost:8000`.

---

## Project Structure

```
lecture-assistant/
  process.sh          One-command entry point (shell wrapper)
  process.py          Pipeline orchestrator (download, transcribe, chunk, notes, serve)
  transcribe.py       Whisper speech-to-text with automatic format conversion
  chunker.py          Sliding-window transcript segmentation (3 min, 20 sec overlap)
  notes.py            LLM structured note extraction (Ollama / Gemini)
  app.py              FastAPI server with WebSocket streaming and export endpoints
  index.html          Single-page web dashboard (vanilla HTML/CSS/JS)
  pdf_export.py       ReportLab PDF report generator
  run.sh              Helper script (loads .env, sets CUDA library paths)
  pyproject.toml      Python project config and dependencies
  .env                API keys and backend configuration
```

---

## Prerequisites

- **Python 3.12+** managed via [uv](https://docs.astral.sh/uv/)
- **ffmpeg** — for audio conversion
- **yt-dlp** — for YouTube downloads
- **NVIDIA GPU + CUDA** — for GPU-accelerated Whisper transcription (falls back to CPU)
- **Ollama** with a model pulled (e.g. `ollama pull qwen2.5:7b`), or a **Gemini API key** in `.env`

### Install Dependencies

```bash
uv sync
```

---

## Configuration (`.env`)

```env
# LLM backend: "ollama" (local) or "gemini" (cloud)
BACKEND=ollama

# Ollama model
OLLAMA_MODEL=qwen2.5:7b

# Gemini credentials (if using BACKEND=gemini)
GEMINI_API_KEY=your-key-here
GEMINI_MODEL=gemini-2.5-flash
```

| Variable | Default | Description |
|---|---|---|
| `BACKEND` | `gemini` | LLM backend for note generation. |
| `OLLAMA_MODEL` | `qwen2.5:7b` | Local Ollama model name. |
| `GEMINI_API_KEY` | — | Google AI API key (required if using Gemini). |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model identifier. |
| `NOTES_FILE` | `test10_notes.json` | Pre-generated notes JSON to load in the web server. |
| `SPEED` | `30` | Replay speed multiplier (30 = 1 lecture minute per 2 real seconds). |
| `WHISPER_MODEL` | `small` | Whisper model size for transcription. |
| `COURSE` | `MIT 8.02: E&M` | Course context string passed to the LLM prompt. |

## Acknowledgements
 
[faster-whisper](https://github.com/SYSTRAN/faster-whisper), [OpenAI Whisper](https://arxiv.org/abs/2212.04356), [Ollama](https://ollama.com), [Qwen2.5](https://github.com/QwenLM/Qwen2.5), [FastAPI](https://fastapi.tiangolo.com), [uv](https://docs.astral.sh/uv/), the Arduino-ESP32 core, and the Adafruit and WebSockets libraries.

