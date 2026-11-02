import json
from app.services.llm_client import ask_llm

def score_candidate(parsed, vacancy):
    prompt = f"""
Оцени кандидата по шкале 0-10.

Верни JSON:

{{
 "scores": {{
   "hard_skills": {{ "value": 0, "rationale": "", "evidence_segments": [] }},
   "communication": {{ "value": 0, "rationale": "", "evidence_segments": [] }},
   "culture_fit": {{ "value": 0, "rationale": "", "evidence_segments": [] }},
   "risk_flags": []
 }},
 "recommendation": {{
   "decision": "",
   "next_steps": []
 }},
 "uncertainty": []
}}

Правило:
- нет evidence → не утверждай

Данные:
{json.dumps(parsed, ensure_ascii=False)}
"""

    response = ask_llm(prompt)
    return json.loads(response)