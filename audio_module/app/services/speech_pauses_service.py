import torch
from silero_vad import load_silero_vad, get_speech_timestamps


class SpeechPausesService:
    def __init__(self, pause_threshold_sec: float = 1.5):
        self.model = load_silero_vad()
        self.pause_threshold_sec = pause_threshold_sec

    def analyze(self, waveform, sample_rate, duration_sec):

        speech_timestamps = get_speech_timestamps(
            waveform,
            self.model,
            sampling_rate=sample_rate
        )

        if len(speech_timestamps) < 2:
            return {
                "total_pauses": 0,
                "total_pause_time_sec": 0.0,
                "avg_pause_duration_sec": 0.0,
                "long_pauses_count": 0,
                "pause_rate_per_min": 0.0,
                "pause_threshold_sec": self.pause_threshold_sec
            }

        pauses = []

        for i in range(len(speech_timestamps) - 1):
            end_current = speech_timestamps[i]["end"] / sample_rate
            start_next = speech_timestamps[i + 1]["start"] / sample_rate

            pause_duration = start_next - end_current

            if pause_duration > 0:
                pauses.append(pause_duration)

        total_pauses = len(pauses)
        total_pause_time = sum(pauses)
        avg_pause = total_pause_time / total_pauses

        long_pauses = [p for p in pauses if p >= self.pause_threshold_sec]

        pause_rate_per_min = (
            total_pauses / (duration_sec / 60)
            if duration_sec > 0 else 0.0
        )

        return {
            "total_pauses": total_pauses,
            "total_pause_time_sec": round(total_pause_time, 3),
            "avg_pause_duration_sec": round(avg_pause, 3),
            "long_pauses_count": len(long_pauses),
            "pause_rate_per_min": round(pause_rate_per_min, 2),
            "pause_threshold_sec": self.pause_threshold_sec
        }


speech_pauses_service = SpeechPausesService()
