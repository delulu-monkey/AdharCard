from google import genai

client = genai.Client()
for m in client.models.list():
    if "generateContent" in (m.supported_actions or []):
        print(m.name)
