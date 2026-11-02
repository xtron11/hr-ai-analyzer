import json

def safe_json_loads(text: str):
    try:
        return json.loads(text)
    except:
        return {
            "error": "invalid_json",
            "raw": text
        }