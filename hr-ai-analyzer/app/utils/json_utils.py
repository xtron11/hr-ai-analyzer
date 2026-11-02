import json
import re

def extract_json(response):
    if isinstance(response, dict):
        return response

    if not isinstance(response, str):
        return {"error": "invalid_json", "raw": response}

    cleaned = response.strip()

    # 🔥 убираем markdown
    cleaned = cleaned.replace("```json", "").replace("```", "").strip()

    # 🔥 убираем мусор до JSON
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        cleaned = match.group()

    # 🔥 фикс странных символов (ВАЖНО)
    cleaned = cleaned.replace("\xa0", " ")

    try:
        return json.loads(cleaned)
    except Exception as e:
        print("❌ FINAL FAIL:", e)
        print("RAW:", cleaned)

    return {
        "error": "invalid_json",
        "raw": cleaned
    }