import math
from typing import Dict, List, Optional

import numpy as np
import torch
import torchaudio


class AffectDimensionsService:
    """
    Variant C helper: audEERING dimensional affect (Valence/Arousal/Dominance).

    Model: audeering/wav2vec2-large-robust-12-ft-emotion-msp-dim
    Output: dims -> [valence, arousal, dominance] in roughly [0..1]
    """

    def __init__(
        self,
        model_id: str = "audeering/wav2vec2-large-robust-12-ft-emotion-msp-dim",
        device: str = "cpu",
        target_sample_rate: int = 16000,
    ):
        self.model_id = model_id
        self.device = device
        self.target_sample_rate = target_sample_rate

        self._model = None
        self._processor = None
        self._debug_error_count = 0
        self._debug_error_limit = 3

    def _log_debug(self, msg: str):
        if self._debug_error_count < self._debug_error_limit:
            print(msg)
            self._debug_error_count += 1

    def _ensure_loaded(self):
        if self._model is not None and self._processor is not None:
            return

        
        from transformers import AutoModelForAudioClassification, AutoProcessor

        self._processor = AutoProcessor.from_pretrained(self.model_id)
        # trust_remote_code needed for some audio models in Transformers
        self._model = AutoModelForAudioClassification.from_pretrained(
            self.model_id, trust_remote_code=True
        ).to(self.device)
        self._model.eval()

    def _predict_dims(self, waveform_1d: np.ndarray) -> Dict[str, float]:
        """
        Returns {valence, arousal, dominance, confidence}
        """
        try:
            self._ensure_loaded()
        except Exception as e:
            self._log_debug(f"[affect_dimensions] failed to load model: {e}")
            return {"valence": 0.5, "arousal": 0.5, "dominance": 0.5, "confidence": 0.0}

        # Processor expects 1D float array.
        wav = waveform_1d.astype(np.float32)
        try:
            inputs = self._processor(
                wav,
                sampling_rate=self.target_sample_rate,
                return_tensors="pt",
            )
        except Exception as e:
            self._log_debug(f"[affect_dimensions] processor failed: {e}")
            return {"valence": 0.5, "arousal": 0.5, "dominance": 0.5, "confidence": 0.0}
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        try:
            with torch.inference_mode():
                out = self._model(**inputs)
        except Exception as e:
            self._log_debug(f"[affect_dimensions] forward failed: {e}")
            return {"valence": 0.5, "arousal": 0.5, "dominance": 0.5, "confidence": 0.0}

        # out can be dict-like or have attributes depending on model code
        if isinstance(out, dict):
            logits = out.get("logits")
            dims = out.get("dims")
        else:
            logits = getattr(out, "logits", None)
            dims = getattr(out, "dims", None)

        if dims is None and logits is not None:
            # Some implementations return only 'logits' for dims.
            try:
                logits_np = logits.detach().cpu().numpy()
                if logits_np.ndim >= 2 and logits_np.shape[-1] == 3:
                    raw = logits_np[0]
                    # Heuristic: if already in [0,1], use directly; else apply sigmoid.
                    if float(raw.min()) >= 0.0 and float(raw.max()) <= 1.0:
                        dims_np = raw
                    else:
                        dims_np = 1.0 / (1.0 + np.exp(-raw))
                    dims = torch.tensor(dims_np, dtype=torch.float32)
                elif logits_np.ndim == 1 and logits_np.shape[0] == 3:
                    raw = logits_np
                    if float(raw.min()) >= 0.0 and float(raw.max()) <= 1.0:
                        dims_np = raw
                    else:
                        dims_np = 1.0 / (1.0 + np.exp(-raw))
                    dims = torch.tensor(dims_np, dtype=torch.float32)
            except Exception as e:
                dims = None
                self._log_debug(f"[affect_dimensions] dims extraction failed: {e}")

        if dims is None:
            self._log_debug(f"[affect_dimensions] no dims in model output; using fallback neutrals")
            return {"valence": 0.5, "arousal": 0.5, "dominance": 0.5, "confidence": 0.0}

        dims_np = dims.detach().cpu().numpy()
        # Expect shape [3] or [1,3]
        if dims_np.ndim == 2:
            valence = float(dims_np[0][0])
            arousal = float(dims_np[0][1])
            dominance = float(dims_np[0][2])
        else:
            valence = float(dims_np[0])
            arousal = float(dims_np[1])
            dominance = float(dims_np[2])

        # Weak confidence proxy: distance from neutral (0.5)
        confidence = float(min(1.0, (abs(valence - 0.5) + abs(arousal - 0.5) + abs(dominance - 0.5)) * 1.2))

        return {
            "valence": valence,
            "arousal": arousal,
            "dominance": dominance,
            "confidence": confidence,
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
                "valence": 0.5,
                "arousal": 0.5,
                "dominance": 0.5,
                "dimensions": {"valence": 0.5, "arousal": 0.5, "dominance": 0.5},
                "confidence": 0.0,
                "dimensions_timeline": [],
                "emotions_timeline": [],
                "method": "audeering_dims_v1",
            }

        # Ensure mono 1D
        if waveform.ndim > 1:
            waveform = np.mean(waveform, axis=0)
        wav = waveform.astype(np.float32)

        # Resample if needed
        if sample_rate != self.target_sample_rate:
            wav_t = torch.tensor(wav).unsqueeze(0)
            resampler = torchaudio.transforms.Resample(
                orig_freq=sample_rate, new_freq=self.target_sample_rate
            )
            wav_t = resampler(wav_t)
            wav = wav_t.squeeze(0).detach().cpu().numpy()

        sr = self.target_sample_rate
        segment_samples = int(segment_sec * sr)
        hop_samples = int(hop_sec * sr)

        dimensions_timeline: List[dict] = []
        start_sample = 0
        total_samples = int(duration_sec * sr)

        # Include the last (possibly shorter) window, same idea as emotions_recognition.
        while start_sample < total_samples:
            end_sample = start_sample + segment_samples
            seg = wav[start_sample:min(end_sample, len(wav))]
            if len(seg) == 0:
                break
            if len(seg) < segment_samples:
                seg = np.pad(
                    seg,
                    (0, segment_samples - len(seg)),
                    mode="constant",
                    constant_values=0.0,
                )

            start_sec = start_sample / sr
            end_sec = min(duration_sec, end_sample / sr)

            pred = self._predict_dims(seg)
            dimensions_timeline.append(
                {
                    "start_sec": round(start_sec, 2),
                    "end_sec": round(end_sec, 2),
                    "valence": float(round(pred["valence"], 4)),
                    "arousal": float(round(pred["arousal"], 4)),
                    "dominance": float(round(pred["dominance"], 4)),
                    "confidence": float(round(pred["confidence"], 4)),
                }
            )

            start_sample += hop_samples

        # Aggregate
        if not dimensions_timeline:
            return {
                "valence": 0.5,
                "arousal": 0.5,
                "dominance": 0.5,
                "confidence": 0.0,
                "dimensions_timeline": [],
                "emotions_timeline": [],
                "method": "audeering_dims_v1",
            }

        valence_avg = sum(x["valence"] for x in dimensions_timeline) / len(dimensions_timeline)
        arousal_avg = sum(x["arousal"] for x in dimensions_timeline) / len(dimensions_timeline)
        dominance_avg = sum(x["dominance"] for x in dimensions_timeline) / len(dimensions_timeline)
        conf_avg = sum(x.get("confidence", 0.0) for x in dimensions_timeline) / len(dimensions_timeline)

        return {
            "valence": float(round(valence_avg, 4)),
            "arousal": float(round(arousal_avg, 4)),
            "dominance": float(round(dominance_avg, 4)),
            "dimensions": {
                "valence": float(round(valence_avg, 4)),
                "arousal": float(round(arousal_avg, 4)),
                "dominance": float(round(dominance_avg, 4)),
            },
            "confidence": float(round(conf_avg, 4)),
            "dimensions_timeline": dimensions_timeline,
            "emotions_timeline": dimensions_timeline,
            "method": "audeering_dims_v1",
        }


affect_dimensions_service = AffectDimensionsService()

