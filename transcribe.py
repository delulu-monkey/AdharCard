import json, os, subprocess, sys, time, wave
import numpy as np
import ctranslate2
from faster_whisper import WhisperModel

audio_path = sys.argv[1] if len(sys.argv) > 1 else "test10.wav"

def ensure_16k_mono_wav(src_path: str) -> str:
    """Ensure audio is 16 kHz, mono, 16-bit PCM WAV. Convert via ffmpeg if needed."""
    try:
        with wave.open(src_path, "rb") as w:
            if w.getframerate() == 16000 and w.getnchannels() == 1 and w.getsampwidth() == 2:
                return src_path
    except Exception:
        pass

    converted_path = src_path.rsplit(".", 1)[0] + "_16k.wav"
    print(f"Converting {src_path} to 16 kHz mono 16-bit WAV via ffmpeg...")
    subprocess.run([
        "ffmpeg", "-y", "-i", src_path,
        "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
        converted_path
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return converted_path

wav_file = ensure_16k_mono_wav(audio_path)

with wave.open(wav_file, "rb") as w:
    audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0

device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
compute_type = "int8_float16" if device == "cuda" else "int8"
whisper_model_name = os.environ.get("WHISPER_MODEL", "small")

print(f"Loading Whisper '{whisper_model_name}' on {device} ({compute_type})...")
model = WhisperModel(whisper_model_name, device=device, compute_type=compute_type)

initial_prompt = os.environ.get(
    "INITIAL_PROMPT",
    "University lecture notes. Clear academic terminology, concepts, and definitions."
)

t0 = time.time()
print(f"Transcribing {len(audio) / 16000:.1f}s of audio...")
segments, info = model.transcribe(
    audio,
    language="en",
    vad_filter=True,
    beam_size=5,
    initial_prompt=initial_prompt
)

out = []
for s in segments:
    text = s.text.strip()
    out.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": text})
    print(f"[{s.start:7.1f}s] {text}")

out_path = audio_path.rsplit(".", 1)[0] + ".json"
with open(out_path, "w") as f:
    json.dump(out, f, indent=2)

print(f"Transcription complete: {len(audio) / 16000:.0f}s of audio transcribed in {time.time() - t0:.1f}s -> saved to {out_path}")
