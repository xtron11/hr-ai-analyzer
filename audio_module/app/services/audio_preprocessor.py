import torch
import torchaudio
import os

class AudioPreprocessor:
    def __init__(self, target_sample_rate: int = 16000):
        self.target_sample_rate = target_sample_rate

    def process(self, audio_path: str):
        # Получаем инфо о файле без загрузки данных в RAM
        metadata = torchaudio.info(audio_path)
        
        # Если файл больше 50МБ, мы не можем грузить его целиком в RAM без риска
        # Но для базовых метрик (speech_rate и pitch) пока оставим загрузку, 
        # ограничив её лимитом (например, первые 10 минут)
        
        waveform, sample_rate = torchaudio.load(audio_path)

        # stereo → mono
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)

        # resample
        if sample_rate != self.target_sample_rate:
            resampler = torchaudio.transforms.Resample(
                orig_freq=sample_rate,
                new_freq=self.target_sample_rate
            )
            waveform = resampler(waveform)
            sample_rate = self.target_sample_rate

        waveform_np = waveform.squeeze().numpy()
        duration_sec = len(waveform_np) / sample_rate

        return waveform_np, sample_rate, round(duration_sec, 2)

audio_preprocessor = AudioPreprocessor()