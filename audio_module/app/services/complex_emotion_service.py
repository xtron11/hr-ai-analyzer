import math
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple


_HESITATION_RE = re.compile(
    r"\b(ээ+|эм+|мм+|ну+|как бы|типа|короче|в смысле|не знаю|не уверен|сложно сказать|затрудняюсь)\b",
    re.IGNORECASE,
)

_IRRITATION_RE = re.compile(
    r"\b(бесит|раздража(ет|етс?я)|достал(о|а|и)?|надоело|сколько можно|это же очевидно|давай(те)? быстрее|блин|чёрт)\b",
    re.IGNORECASE,
)

_ENGAGEMENT_RE = re.compile(
    r"\b(интересно|давайте|хочу|могу|сделаю|попробую|важно|например|смотрите|смотри|уточню|правильно понимаю)\b",
    re.IGNORECASE,
)


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def _token_count(text: str) -> int:
    t = re.findall(r"[A-Za-zА-Яа-яЁё0-9']+", text)
    return len(t)


def _window_text(transcript_segments: List[dict], start_sec: float, end_sec: float) -> str:
    parts = []
    for seg in transcript_segments:
        s0 = float(seg.get("start_sec", 0.0))
        s1 = float(seg.get("end_sec", 0.0))
        if s1 <= start_sec or s0 >= end_sec:
            continue
        txt = (seg.get("text") or "").strip()
        if txt:
            parts.append(txt)
    return " ".join(parts).strip()


def _overlap_fraction(seg_start: float, seg_end: float, win_start: float, win_end: float) -> float:
    seg_dur = max(1e-6, float(seg_end - seg_start))
    ov = max(0.0, min(seg_end, win_end) - max(seg_start, win_start))
    return float(ov / seg_dur)


def _window_weighted_features(transcript_segments: List[dict], start_sec: float, end_sec: float) -> Tuple[float, float, float, float]:
    """
    Returns weighted counts scaled by overlap between ASR segment and window.
    This prevents long ASR segments from being counted fully in multiple windows.
    """
    words = 0.0
    hes = 0.0
    irr = 0.0
    eng = 0.0

    for seg in transcript_segments:
        s0 = float(seg.get("start_sec", 0.0))
        s1 = float(seg.get("end_sec", 0.0))
        if s1 <= start_sec or s0 >= end_sec:
            continue

        frac = _overlap_fraction(s0, s1, start_sec, end_sec)
        txt = (seg.get("text") or "").strip()
        if not txt:
            continue

        words += _token_count(txt) * frac
        hes += len(_HESITATION_RE.findall(txt)) * frac
        irr += len(_IRRITATION_RE.findall(txt)) * frac
        eng += len(_ENGAGEMENT_RE.findall(txt)) * frac

    return words, hes, irr, eng


def _window_silence_sec(transcript_segments: List[dict], start_sec: float, end_sec: float) -> float:
    """
    Proxy for pauses based on ASR segment gaps.
    Works even without VAD timestamps.
    """
    # collect segments that overlap, then compute gaps between them clipped to window
    segs: List[Tuple[float, float]] = []
    for seg in transcript_segments:
        s0 = float(seg.get("start_sec", 0.0))
        s1 = float(seg.get("end_sec", 0.0))
        if s1 <= start_sec or s0 >= end_sec:
            continue
        segs.append((max(s0, start_sec), min(s1, end_sec)))
    if not segs:
        return float(end_sec - start_sec)
    segs.sort()
    silence = 0.0
    cur_end = start_sec
    for s0, s1 in segs:
        if s0 > cur_end:
            silence += s0 - cur_end
        cur_end = max(cur_end, s1)
    if cur_end < end_sec:
        silence += end_sec - cur_end
    return float(max(0.0, silence))


@dataclass(frozen=True)
class ComplexEmotionWindow:
    start_sec: float
    end_sec: float
    scores: Dict[str, float]
    top_emotion: str
    confidence: float


class ComplexEmotionService:
    """
    Variant C (no training): heuristic + multi-signal scoring.
    Uses:
    - Whisper transcript segments with timestamps
    - ASR-gap-based silence proxy
    - global pitch metrics (weak prior)
    - global speech rate (weak prior)
    """

    def analyze(
        self,
        transcript_segments: List[dict],
        duration_sec: float,
        speech_rate_wpm: float | None = None,
        pitch_metrics: dict | None = None,
        affect_dimensions: dict | None = None,
        opensmile_features: dict | None = None,
        segment_sec: float = 5.0,
        hop_sec: float = 5.0,
    ) -> dict:
        if duration_sec <= 0:
            return {
                "emotion": "unknown",
                "confidence": 0.0,
                "scores": {k: 0.0 for k in ("confusion", "tension", "engagement", "irritation")},
                "emotions_timeline": [],
                "method": "heuristic_v1",
            }

        avg_pitch = float((pitch_metrics or {}).get("avg_pitch") or 0.0)
        std_pitch = float((pitch_metrics or {}).get("std_pitch") or 0.0)
        voiced_ratio = float((pitch_metrics or {}).get("voiced_ratio") or 0.0)
        rate = float(speech_rate_wpm or 0.0)

        affect_timeline = (affect_dimensions or {}).get("dimensions_timeline") or None
        opensmile_timeline = (opensmile_features or {}).get("emotions_timeline") or None

        windows: List[ComplexEmotionWindow] = []
        t = 0.0
        window_idx = 0
        while t < duration_sec - 1e-6:
            w0 = t
            w1 = min(duration_sec, t + segment_sec)
            words, hes, irr, eng = _window_weighted_features(transcript_segments, w0, w1)
            silence = _window_silence_sec(transcript_segments, w0, w1)
            silence_ratio = silence / max(0.001, (w1 - w0))

            # Normalize rough signals
            words_norm = _clamp01(words / 20.0)  # 0..1 for ~0..20+ tokens per 5s
            hes_norm = _clamp01(hes / 3.0)
            irr_norm = _clamp01(irr / 2.0)
            eng_norm = _clamp01(eng / 2.0)

            # Pitch prior: higher std_pitch and higher voiced_ratio tends to correlate with activation
            pitch_activation = _clamp01((std_pitch / 80.0) * 0.7 + voiced_ratio * 0.3)
            # Speech rate prior: very low rate can correlate with confusion; higher rate can correlate with tension/irritation
            rate_norm = _clamp01(rate / 180.0)

            # VAD priors (optional): valence/arousal/dominance in ~[0..1]
            vad_win = None
            if affect_timeline is not None and window_idx < len(affect_timeline):
                vad_win = affect_timeline[window_idx]

            if vad_win is not None:
                valence_norm = _clamp01(float(vad_win.get("valence", 0.5)))
                arousal_norm = _clamp01(float(vad_win.get("arousal", 0.5)))
                dominance_norm = _clamp01(float(vad_win.get("dominance", 0.5)))
            else:
                valence_norm = 0.5
                arousal_norm = 0.5
                dominance_norm = 0.5

            # openSMILE priors (optional)
            smile_win = None
            if opensmile_timeline is not None and window_idx < len(opensmile_timeline):
                smile_win = opensmile_timeline[window_idx]

            if smile_win is not None:
                f = smile_win.get("features", {})
                loudness_norm = _clamp01(float(f.get("loudness_mean", 0.0)) / 10.0)
                jitter_norm = _clamp01(float(f.get("jitter_local", 0.0)) / 0.08)
                shimmer_norm = _clamp01(abs(float(f.get("shimmer_local_db", 0.0))) / 1.2)
                hnr_norm = _clamp01(float(f.get("hnr_db", 0.0)) / 30.0)
            else:
                loudness_norm = 0.5
                jitter_norm = 0.5
                shimmer_norm = 0.5
                hnr_norm = 0.5

            # Base raw scores (then softmax, so classes compete).
            confusion_base = (
                2.2 * hes_norm
                + 1.4 * silence_ratio
                + 0.8 * (1.0 - words_norm)
                + 0.6 * (1.0 - rate_norm)
                - 1.2 * irr_norm
            )

            irritation_base = (
                2.6 * irr_norm
                + 1.2 * pitch_activation
                + 0.8 * rate_norm
                - 1.0 * silence_ratio
                - 0.6 * hes_norm
            )

            engagement_base = (
                1.8 * words_norm
                + 1.2 * eng_norm
                + 0.8 * pitch_activation
                - 1.4 * silence_ratio
                - 0.8 * hes_norm
            )

            tension_base = (
                1.6 * pitch_activation
                + 1.1 * rate_norm
                + 0.7 * (1.0 - silence_ratio)
                - 0.6 * eng_norm
                + 0.2 * (1.0 if avg_pitch > 160.0 else 0.0)
            )

            # VAD adjustments: map dimensions to target states.
            # - confusion: low dominance + low arousal + uncertainty words/pause
            # - tension: high arousal + high dominance + negative valence
            # - engagement: positive valence + high dominance + controlled arousal
            # - irritation: high arousal + negative valence + reduced dominance
            confusion_raw = (
                confusion_base
                + 2.0 * (1.0 - dominance_norm)
                + 1.2 * (1.0 - arousal_norm)
                + 0.4 * abs(valence_norm - 0.5)
                + 0.8 * jitter_norm
                + 0.6 * shimmer_norm
            )
            tension_raw = (
                tension_base
                + 2.0 * arousal_norm
                + 1.3 * dominance_norm
                + 1.0 * (1.0 - valence_norm)
                + 1.0 * loudness_norm
                + 0.8 * shimmer_norm
            )
            engagement_raw = (
                engagement_base
                + 1.7 * valence_norm
                + 1.4 * dominance_norm
                - 0.9 * abs(arousal_norm - 0.6)
                + 0.7 * loudness_norm
                + 0.5 * hnr_norm
                - 0.5 * jitter_norm
            )
            irritation_raw = (
                irritation_base
                + 2.2 * arousal_norm
                + 1.6 * (1.0 - valence_norm)
                + 0.6 * (1.0 - dominance_norm)
                + 1.1 * loudness_norm
                + 0.9 * shimmer_norm
                - 0.5 * hnr_norm
            )

            raw = [confusion_raw, tension_raw, engagement_raw, irritation_raw]
            # Temperature keeps softmax from becoming too peaky.
            temperature = 1.5
            m = max(raw)
            exps = [math.exp((x - m) / temperature) for x in raw]
            s = sum(exps) + 1e-12
            scores = {
                "confusion": float(round(exps[0] / s, 4)),
                "tension": float(round(exps[1] / s, 4)),
                "engagement": float(round(exps[2] / s, 4)),
                "irritation": float(round(exps[3] / s, 4)),
            }
            top_emotion = max(scores, key=scores.get)
            conf = scores[top_emotion]
            windows.append(
                ComplexEmotionWindow(
                    start_sec=round(w0, 2),
                    end_sec=round(w1, 2),
                    scores=scores,
                    top_emotion=top_emotion,
                    confidence=conf,
                )
            )
            t += hop_sec
            window_idx += 1

        if not windows:
            agg = {k: 0.0 for k in ("confusion", "tension", "engagement", "irritation")}
            return {
                "emotion": "unknown",
                "confidence": 0.0,
                "scores": agg,
                "emotions_timeline": [],
                "method": "heuristic_v1",
            }

        # Aggregate by mean score
        agg: Dict[str, float] = {k: 0.0 for k in ("confusion", "tension", "engagement", "irritation")}
        for w in windows:
            for k, v in w.scores.items():
                agg[k] += v
        for k in agg:
            agg[k] = float(round(agg[k] / len(windows), 4))

        final = max(agg, key=agg.get)
        return {
            "emotion": final,
            "confidence": agg[final],
            "scores": agg,
            "emotions_timeline": [
                {
                    "start_sec": w.start_sec,
                    "end_sec": w.end_sec,
                    "emotion": w.top_emotion,
                    "confidence": w.confidence,
                    "scores": w.scores,
                }
                for w in windows
            ],
            "method": "heuristic_v1",
        }


complex_emotion_service = ComplexEmotionService()

