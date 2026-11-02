import json
from datetime import datetime
from app.services.llm_client import ask_llm

def generate_report(parsed, scoring, vacancy):
    prompt = f"""
Сформируй финальный отчет.

Верни JSON:

{{
 "final_score": 0,
 "summary": {{
   "short": "",
   "detailed": ""
 }},
 "strengths": [],
 "risks": [],
 "follow_up_questions": []
}}

Данные:
{json.dumps(parsed, ensure_ascii=False)}
{json.dumps(scoring, ensure_ascii=False)}
"""

    response = ask_llm(prompt)
    result = json.loads(response)

    result["generated_at"] = datetime.utcnow().isoformat()
    return result