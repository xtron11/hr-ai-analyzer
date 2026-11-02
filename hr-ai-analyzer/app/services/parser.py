from app.services.llm_client import ask_llm
import json

def load_prompt():
    with open("app/prompts/parser_prompt.txt", "r", encoding="utf-8") as f:
        return f.read()

def parse_transcript(transcript: str):
    prompt_template = load_prompt()
    prompt = prompt_template.replace("{{transcript}}", transcript)

    response = ask_llm(prompt)

    return json.loads(response)  # 🔥 теперь это работает стабильно