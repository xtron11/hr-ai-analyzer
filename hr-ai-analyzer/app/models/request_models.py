from pydantic import BaseModel
from typing import List, Dict

class Segment(BaseModel):
    segment_id: str
    start_ms: int
    end_ms: int
    speaker: str
    text: str

class Transcript(BaseModel):
    language: str
    text: str
    segments: List[Segment]

class AnalyzeRequest(BaseModel):
    interview_id: str
    vacancy: Dict
    transcript: Transcript