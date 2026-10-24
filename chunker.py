import json, sys

src = sys.argv[1] if len(sys.argv) > 1 else "test10.json"
WINDOW, OVERLAP = 180, 20  # seconds

segs = json.load(open(src))
end_time = segs[-1]["end"]

chunks, start = [], 0.0
while start < end_time:
    stop = start + WINDOW
    part = [s for s in segs if s["end"] > start and s["start"] < stop]
    if part:
        chunks.append({
            "id": len(chunks),
            "start": round(start),
            "end": round(min(stop, end_time)),
            "text": " ".join(s["text"] for s in part),
        })
    start = stop - OVERLAP

json.dump(chunks, open(src.replace(".json", "_chunks.json"), "w"), indent=2)
print(f"{len(chunks)} chunks, avg {sum(len(c['text'].split()) for c in chunks) // len(chunks)} words each")
