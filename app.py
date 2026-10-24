import asyncio, json, os, time
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response
from fastapi.responses import HTMLResponse, PlainTextResponse
from pdf_export import build_lecture_pdf

SRC = os.environ.get("NOTES_FILE", "test10_notes.json")
SPEED = float(os.environ.get("SPEED", "30"))  # 30 = 1 lecture minute per 2 real seconds

chunks = json.load(open(SRC))
released, marks, clients = [], [], set()
t0 = None

def lecture_time():
    return 0 if t0 is None else (time.time() - t0) * SPEED

async def replay():
    global t0
    t0 = time.time()
    for c in chunks:
        while lecture_time() < c["end"]:
            await asyncio.sleep(0.2)
        c = {**c, "important": any(c["start"] <= m <= c["end"] for m in marks)}
        # Ensure default values if older json files are loaded
        c.setdefault("importance", "Core")
        c.setdefault("difficulty", "Intermediate")
        c.setdefault("study_resources", [])
        released.append(c)
        for ws in list(clients):
            try:
                await ws.send_text(json.dumps(c))
            except Exception:
                clients.discard(ws)

@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(replay())
    yield
    task.cancel()

app = FastAPI(lifespan=lifespan)

@app.get("/")
def index():
    return HTMLResponse(open("index.html").read())

@app.post("/mark")
def mark():
    marks.append(lecture_time())
    return {"at": lecture_time()}

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    for c in released:
        await ws.send_text(json.dumps(c))
    clients.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        clients.discard(ws)

@app.get("/export.pdf")
def export_pdf():
    # If no chunks released yet, return an empty digest or the first chunks
    target_chunks = released if released else chunks
    pdf_bytes = build_lecture_pdf(target_chunks)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="lecture_summary.pdf"'}
    )

@app.get("/export.md", response_class=PlainTextResponse)
def export():
    target_chunks = released if released else chunks
    out = ["# Lecture Notes\n"]
    for c in target_chunks:
        imp = c.get("importance", "Core")
        diff = c.get("difficulty", "Intermediate")
        out.append(f"## {c['topic']} ({c['start'] // 60}:{c['start'] % 60:02d}){' *' if c.get('important') else ''}")
        out.append(f"**Importance:** {imp} | **Difficulty:** {diff}\n")
        out += [f"- {n}" for n in c["notes"]]
        if c.get("concepts"):
            out.append("\n**Concepts**")
            out += [f"- {x['term']}: {x['definition']}" for x in c["concepts"]]
        if c.get("questions"):
            out.append("\n**Questions**")
            out += [f"{i}. {q['question']} (Answer: {q['answer']})" for i, q in enumerate(c["questions"], 1)]
        if c.get("study_resources"):
            out.append("\n**Recommended Study Resources**")
            out += [f"- {r}" for r in c["study_resources"]]
        if c.get("action_items"):
            out.append("\n**Action Items**")
            out += [f"- {a}" for a in c["action_items"]]
        out.append("")
    return "\n".join(out)
