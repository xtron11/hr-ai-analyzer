import numpy as np
from faster_whisper import WhisperModel


def format_time(seconds: float) -> str:
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02}:{secs:02}"


class SpeechRateService:
    def __init__(self):
        self.model = WhisperModel("base", device="cpu", compute_type="int8")

    def analyze(self, waveform, sample_rate, duration_sec):

        audio_np = waveform.astype(np.float32)


        segments, info = self.model.transcribe(
            audio_np,
            beam_size=5,
            
        )

        word_count = 0
        transcript_segments = []

        for segment in segments:
            text = segment.text.strip()
            word_count += len(text.split())

            transcript_segments.append({
                "start_sec": round(segment.start, 2),
                "end_sec": round(segment.end, 2),
                "start_time": format_time(segment.start),
                "end_time": format_time(segment.end),
                "text": text
            })

        if duration_sec > 0:
            speech_rate = word_count / (duration_sec / 60)
        else:
            speech_rate = 0.0

        return {
            "speech_rate_wpm": round(speech_rate, 2),
            "speech_rate_method": "asr_words",
            "word_count": word_count,
            "duration_sec": duration_sec,
            "transcript_segments": transcript_segments,
            "detected_language": info.language
        }


speech_rate_service = SpeechRateService()
