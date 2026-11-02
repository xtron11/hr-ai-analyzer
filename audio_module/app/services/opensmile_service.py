from typing import Dict, List

import numpy as np


class OpenSmileService:
    """
    openSMILE feature extraction for affective proxy signals.

    Uses eGeMAPSv02 functionals on 5-second windows.
    """

    def __init__(self):
        self._smile = None
        self._disabled = False

    def _ensure_smile(self):
        if self._disabled:
            return
        if self._smile is not None:
            return
        try:
            import opensmile

            self._smile = opensmile.Smile(
                feature_set=opensmile.FeatureSet.eGeMAPSv02,
                feature_level=opensmile.FeatureLevel.Functionals,
            )
        except Exception as e:
            print(f"[opensmile] disabled: {e}")
            self._disabled = True
            self._smile = None

    @staticmethod
    def _pick_float(row, key: str, default: float = 0.0) -> float:
        try:
            if key in row:
                return float(row[key])
        except Exception:
            pass
        return default

    def _extract_window(self, segment: np.ndarray, sample_rate: int) -> Dict[str, float]:
        self._ensure_smile()
        if self._smile is None:
            return {
                "f0_mean_hz": 0.0,
                "f0_std_hz": 0.0,
                "loudness_mean": 0.0,
                "jitter_local": 0.0,
                "shimmer_local_db": 0.0,
                "hnr_db": 0.0,
                "confidence": 0.0,
            }

        try:
            df = self._smile.process_signal(segment.astype(np.float32), sample_rate)
            if df is None or df.empty:
                return {
                    "f0_mean_hz": 0.0,
                    "f0_std_hz": 0.0,
                    "loudness_mean": 0.0,
                    "jitter_local": 0.0,
                    "shimmer_local_db": 0.0,
                    "hnr_db": 0.0,
                    "confidence": 0.0,
                }
            row = df.iloc[0]

            # Common eGeMAPS names. We keep fallback-friendly extraction.
            f0_mean = self._pick_float(row, "F0semitoneFrom27.5Hz_sma3nz_amean", 0.0)
            f0_std = self._pick_float(row, "F0semitoneFrom27.5Hz_sma3nz_stddevNorm", 0.0)
            loudness = self._pick_float(row, "loudness_sma3_amean", 0.0)
            jitter = self._pick_float(row, "jitterLocal_sma3nz_amean", 0.0)
            shimmer = self._pick_float(row, "shimmerLocaldB_sma3nz_amean", 0.0)
            hnr = self._pick_float(row, "HNRdBACF_sma3nz_amean", 0.0)

            # Confidence proxy: if all selected features are near zero, likely unusable.
            nonzero = sum(1 for v in [abs(f0_mean), abs(f0_std), abs(loudness), abs(hnr)] if v > 1e-5)
            conf = 1.0 if nonzero >= 2 else 0.2

            return {
                "f0_mean_hz": float(f0_mean),
                "f0_std_hz": float(f0_std),
                "loudness_mean": float(loudness),
                "jitter_local": float(jitter),
                "shimmer_local_db": float(shimmer),
                "hnr_db": float(hnr),
                "confidence": float(conf),
            }
        except Exception as e:
            print(f"[opensmile] extraction failed: {e}")
            return {
                "f0_mean_hz": 0.0,
                "f0_std_hz": 0.0,
                "loudness_mean": 0.0,
                "jitter_local": 0.0,
                "shimmer_local_db": 0.0,
                "hnr_db": 0.0,
                "confidence": 0.0,
            }

    def analyze(
        self,
        waveform: np.ndarray,
        sample_rate: int,
        duration_sec: float,
        segment_sec: float = 5.0,
        hop_sec: float = 5.0,
    ) -> dict:
        if duration_sec <= 0:
            return {
                "features": {
                    "f0_mean_hz": 0.0,
                    "f0_std_hz": 0.0,
                    "loudness_mean": 0.0,
                    "jitter_local": 0.0,
                    "shimmer_local_db": 0.0,
                    "hnr_db": 0.0,
                },
                "confidence": 0.0,
                "emotions_timeline": [],
                "method": "opensmile_egemaps_v02",
            }

        wav = waveform
        if wav.ndim > 1:
            wav = np.mean(wav, axis=0)
        wav = wav.astype(np.float32)

        seg_samples = int(segment_sec * sample_rate)
        hop_samples = int(hop_sec * sample_rate)
        total_samples = int(duration_sec * sample_rate)

        timeline: List[dict] = []
        start = 0
        while start < total_samples:
            end = start + seg_samples
            seg = wav[start:min(end, len(wav))]
            if len(seg) == 0:
                break
            if len(seg) < seg_samples:
                seg = np.pad(seg, (0, seg_samples - len(seg)), mode="constant", constant_values=0.0)

            feat = self._extract_window(seg, sample_rate)
            timeline.append(
                {
                    "start_sec": round(start / sample_rate, 2),
                    "end_sec": round(min(duration_sec, end / sample_rate), 2),
                    "features": {
                        "f0_mean_hz": round(float(feat["f0_mean_hz"]), 4),
                        "f0_std_hz": round(float(feat["f0_std_hz"]), 4),
                        "loudness_mean": round(float(feat["loudness_mean"]), 4),
                        "jitter_local": round(float(feat["jitter_local"]), 6),
                        "shimmer_local_db": round(float(feat["shimmer_local_db"]), 6),
                        "hnr_db": round(float(feat["hnr_db"]), 4),
                    },
                    "confidence": round(float(feat["confidence"]), 4),
                }
            )
            start += hop_samples

        if not timeline:
            return {
                "features": {
                    "f0_mean_hz": 0.0,
                    "f0_std_hz": 0.0,
                    "loudness_mean": 0.0,
                    "jitter_local": 0.0,
                    "shimmer_local_db": 0.0,
                    "hnr_db": 0.0,
                },
                "confidence": 0.0,
                "emotions_timeline": [],
                "method": "opensmile_egemaps_v02",
            }

        keys = ["f0_mean_hz", "f0_std_hz", "loudness_mean", "jitter_local", "shimmer_local_db", "hnr_db"]
        agg = {k: 0.0 for k in keys}
        for w in timeline:
            for k in keys:
                agg[k] += float(w["features"][k])
        for k in keys:
            agg[k] = round(agg[k] / len(timeline), 6 if "jitter" in k or "shimmer" in k else 4)
        conf = round(sum(float(w["confidence"]) for w in timeline) / len(timeline), 4)

        return {
            "features": agg,
            "confidence": conf,
            "emotions_timeline": timeline,
            "method": "opensmile_egemaps_v02",
        }


opensmile_service = OpenSmileService()

