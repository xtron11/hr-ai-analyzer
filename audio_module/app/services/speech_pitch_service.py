import numpy as np
import parselmouth


class SpeechPitchService:

    def analyze(self, waveform: np.ndarray, sample_rate: int):

        sound = parselmouth.Sound(waveform, sampling_frequency=sample_rate)

        pitch = sound.to_pitch(time_step=0.01)
        freq = pitch.selected_array["frequency"]

        total_frames = len(freq)
        voiced = freq[freq > 0]

        if len(voiced) == 0 or total_frames == 0:
            return {
                "avg_pitch": 0.0,
                "min_pitch": 0.0,
                "max_pitch": 0.0,
                "std_pitch": 0.0,
                "pitch_range": 0.0,
                "voiced_ratio": 0.0
            }

        avg_pitch = np.mean(voiced)
        min_pitch = np.min(voiced)
        max_pitch = np.max(voiced)
        std_pitch = np.std(voiced)
        pitch_range = max_pitch - min_pitch
        voiced_ratio = len(voiced) / total_frames

        return {
            "avg_pitch": round(float(avg_pitch), 2),
            "min_pitch": round(float(min_pitch), 2),
            "max_pitch": round(float(max_pitch), 2),
            "std_pitch": round(float(std_pitch), 2),
            "pitch_range": round(float(pitch_range), 2),
            "voiced_ratio": round(float(voiced_ratio), 3)
        }


speech_pitch_service = SpeechPitchService()
