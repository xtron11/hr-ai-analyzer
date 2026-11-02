import torch
import gc
import soundfile as sf
# SpeechBrain 1.x: EncoderClassifier lives here (older 0.x used speechbrain.pretrained)
from speechbrain.inference.classifiers import EncoderClassifier

class EmotionRecognitionService:
    def __init__(self):
        try:
            self.classifier = EncoderClassifier.from_hparams(
                source="speechbrain/emotion-recognition-wav2vec2-IEMOCAP",
                savedir="pretrained_models/emotion_model",
                run_opts={"device":"cpu"}
            )
        except Exception as e:
            raise RuntimeError(
                "SpeechBrain SER model failed to load. "
                "Install a compatible speechbrain version and retry. "
                f"Original error: {e}"
            ) from e

    @staticmethod
    def _normalize_label(label: str) -> str:
        l = (label or "").lower().strip()
        # normalize to short labels used in existing JSON
        if l in {"neutral", "neu"}:
            return "neu"
        if l in {"happy", "happiness", "joy", "hap"}:
            return "hap"
        if l in {"sad", "sadness"}:
            return "sad"
        if l in {"anger", "angry"}:
            return "ang"
        return l or "neutral"

    def analyze_file(self, file_path: str):
        segment_duration = 5  # Анализируем по 5 секунд
        timeline = []
        all_emotions = []

        with sf.SoundFile(file_path) as f:
            sample_rate = f.samplerate
            chunk_samples = int(segment_duration * sample_rate)
            
            while f.tell() < len(f):
                chunk = f.read(chunk_samples)
                if len(chunk) < sample_rate:
                    break

                # Конвертация стерео в моно (если нужно)
                # soundfile возвращает [samples, channels] для стерео
                if len(chunk.shape) > 1:
                    chunk = chunk.mean(axis=1)

                with torch.no_grad():
                    try:
                        # Подготовка тензора [Batch=1, Time]
                        waveform_tensor = torch.from_numpy(chunk).float().unsqueeze(0)
                        # Конвейер Wav2Vec2
                        feats = self.classifier.mods.wav2vec2(waveform_tensor)
                        if feats.ndim == 4:
                            feats = feats.squeeze(1)
                        embedded = self.classifier.mods.avg_pool(feats)
                        outputs = self.classifier.mods.output_mlp(embedded)
                        logits = outputs.view(outputs.shape[0], -1)
                        p_out = torch.nn.functional.softmax(logits, dim=-1)
                        score, index = torch.max(p_out, dim=-1)
                        label = self.classifier.hparams.label_encoder.decode_torch(index)[0]
                        label = self._normalize_label(label)
                        confidence = round(float(score[0]), 4)
                        del waveform_tensor
                        
                        curr_sec = f.tell() / sample_rate
                        timeline.append({
                            "start_sec": round(curr_sec - (len(chunk)/sample_rate), 2),
                            "end_sec": round(curr_sec, 2),
                            "emotion": label,
                            "confidence": confidence
                        })
                        all_emotions.append(label)

                    except Exception as e:
                        print(f"Error in segment at {f.tell()/sample_rate}s: {e}")
                    gc.collect()

        if all_emotions:
            final_emotion = max(set(all_emotions), key=all_emotions.count)
            avg_conf = sum([t["confidence"] for t in timeline]) / len(timeline)
        else:
            final_emotion, avg_conf = "neutral", 0.0

        return {
            "emotion": final_emotion,
            "confidence": round(avg_conf, 4),
            "emotions_timeline": timeline,
            "method": "speechbrain_iemocap",
        }

emotion_recognition_service = EmotionRecognitionService()