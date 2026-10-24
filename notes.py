import json, os, sys, time
from typing import Literal, Optional
from pydantic import BaseModel, Field

class Concept(BaseModel):
    term: str = Field(description="Precise technical or physical term defined or explained in this lecture segment.")
    definition: str = Field(description="Clear, concise, accurate definition based directly on the lecture context.")

class Question(BaseModel):
    type: Literal["mcq", "short"] = Field(description="Question type: multiple choice (mcq) or short-answer.")
    question: str = Field(description="Conceptual question testing understanding of mechanisms, physical laws, or 'why/how'.")
    options: Optional[list[str]] = Field(default=None, description="4 plausible answer choices for MCQ, or None for short answer.")
    answer: str = Field(description="The exact answer and brief conceptual rationale derived strictly from the transcript.")

class LectureNotes(BaseModel):
    topic: str = Field(
        description="A specific, descriptive academic title (4-8 words) reflecting the exact physical concepts discussed in this timestamp segment. NEVER use generic course titles like 'Electricity and Magnetism' or 'Physics' or 'Introduction'. For example: 'Atomic Structure & Subatomic Charge Distribution' or 'Benjamin Franklin's Convention & Conservation of Charge' or 'Electrostatic Induction & Force in Conductors'."
    )
    importance: Literal["Core", "High", "Moderate"] = Field(
        description="'Core' for foundational physical laws/definitions; 'High' for key mechanisms or problem-solving methods; 'Moderate' for background, historical anecdotes, or motivating demonstrations."
    )
    difficulty: Literal["Introductory", "Intermediate", "Advanced"] = Field(
        description="Conceptual and mathematical difficulty: 'Introductory' for basic qualitative concepts and definitions; 'Intermediate' for multi-step reasoning and charge distribution; 'Advanced' for mathematical field analysis."
    )
    notes: list[str] = Field(description="5 to 8 bullet points, each a complete, self-contained, grammatically clear sentence.")
    concepts: list[Concept] = Field(description="Only terms the lecturer actually defines or explains in this segment.")
    questions: list[Question] = Field(description="2 to 3 conceptual questions testing understanding of mechanisms.")
    action_items: list[str] = Field(description="Explicit assignments, problem set deadlines, or reading instructions, or [].")
    study_resources: list[str] = Field(
        description="2 to 3 recommended study resources, standard university textbook chapters, or open-access references where a student can study this topic (e.g. 'Halliday & Resnick: Fundamentals of Physics, Chapter 21', 'Purcell & Morin: Electricity and Magnetism, Chapter 1', 'Feynman Lectures on Physics Vol. II, Chapter 1', 'MIT 8.02 Online Course Notes: Section 1.2')."
    )

PROMPT = """You are an expert university lecture-notes assistant for undergraduate students.
Subject / Context: {course_context}
From the transcript segment below, return ONLY valid JSON matching the schema.

Strict Guidelines:
1. TOPIC TITLE: Provide a distinct, highly specific academic title (4-8 words) uniquely identifying the exact subject matter covered in this timestamp segment.
   - CRITICAL: NEVER output generic titles like "Lecture", "Course Introduction", "Lecture Notes", or the broad course name.
   - The title must capture the specific discussion (e.g., "Atomic Model and Subatomic Particle Charges", "Hash Table Collision Resolution Algorithms", "Mitochondrial Electron Transport Chain").
2. IMPORTANCE: Rate this segment as "Core", "High", or "Moderate" based on its conceptual weight and relevance for examinations.
3. DIFFICULTY: Rate this segment as "Introductory", "Intermediate", or "Advanced".
4. NOTES: 5 to 8 bullet points, each a self-contained, informative sentence. Prioritize definitions, physical laws, formulas with their physical meaning, and explanations of causality (why phenomena happen). Skip greetings, logistical banter, and jokes unless they contain an explicit deadline.
5. CONCEPTS: Include terms the lecturer explicitly defines or explains.
6. QUESTIONS: 2 to 3 conceptual questions testing understanding of mechanisms, not trivia. For MCQs, provide 4 plausible options with the exact correct answer.
7. ACTION ITEMS: Explicit deadlines, problem sets, or assigned readings stated in the transcript, otherwise [].
8. STUDY RESOURCES: Recommend 2 to 3 specific textbooks, chapters, or authoritative academic references where a student can study and master the specific topics covered in this segment (e.g. Halliday, Resnick & Walker; Purcell & Morin; Griffiths; Feynman Lectures Vol II; or MIT 8.02 Course Notes).

Already covered earlier (do not repeat these concepts): {prior_terms}

Transcript Segment:
{text}"""

BACKEND = os.environ.get("BACKEND", "gemini")
MODEL = os.environ.get("GEMINI_MODEL")

if BACKEND == "gemini":
    from google import genai
    from google.genai import types
    client = genai.Client()
else:
    client = None

import ollama

def generate_notes_local(text: str, prior_terms: list[str]) -> LectureNotes:
    course_ctx = os.environ.get("COURSE", "MIT 8.02: Electricity and Magnetism")
    prompt = PROMPT.format(course_context=course_ctx, prior_terms=", ".join(prior_terms) or "nothing yet", text=text)
    for attempt in range(3):
        r = ollama.chat(
            model=os.environ.get("OLLAMA_MODEL", "qwen2.5:7b"),
            messages=[{"role": "user", "content": prompt}],
            format=LectureNotes.model_json_schema(),
            options={"temperature": 0.2, "num_ctx": 4096},
        )
        try:
            return LectureNotes.model_validate_json(r.message.content)
        except Exception as e:
            print(f"retry {attempt + 1}: {e}")
    raise RuntimeError("model kept returning invalid JSON")

def generate_notes(text: str, prior_terms: list[str]) -> LectureNotes:
    course_ctx = os.environ.get("COURSE", "MIT 8.02: Electricity and Magnetism")
    prompt = PROMPT.format(course_context=course_ctx, prior_terms=", ".join(prior_terms) or "nothing yet", text=text)
    r = client.models.generate_content(
        model=MODEL or "gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=LectureNotes,
            temperature=0.2,
        ),
    )
    return LectureNotes.model_validate_json(r.text)

if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "test10_chunks.json"
    chunks = json.load(open(src))
    results, seen = [], []
    gen = generate_notes_local if BACKEND == "ollama" else generate_notes
    for c in chunks:
        n = gen(c["text"], seen)
        seen += [x.term for x in n.concepts]
        results.append({"start": c["start"], "end": c["end"], **n.model_dump()})
        print(f"chunk {c['id']}: [{n.importance} | {n.difficulty}] {n.topic}")
        time.sleep(4 if BACKEND == "gemini" else 0)  # stay under the requests-per-minute limit
    json.dump(results, open(src.replace("_chunks", "_notes"), "w"), indent=2)
