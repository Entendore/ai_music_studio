"""Math & Noise Synthesizer Backend."""
import numpy as np
import logging
import time
from typing import Optional
from backend import MusicBackend, GenerationResult, ProgressCallback, StopCheck

logger = logging.getLogger(__name__)

class Plugin(MusicBackend):
    def __init__(self):
        self.model = None

    @classmethod
    def get_metadata(cls):
        return {
            'name': 'MathSynth',
            'description': 'Math waveform synthesizer',
            'details': 'Sine, Sawtooth, Square, FM Synth, White/Brown noise.',
            'icon': '📊',
            'requirements': 'No additional requirements',
        }

    @classmethod
    def get_prompt_schema(cls):
        return {'required': False, 'title': None, 'description': None, 'placeholder': None}

    @classmethod
    def get_settings_schema(cls):
        return [
            {'id': 'waveform_type', 'type': 'dropdown', 
             'options': ['Sine', 'White Noise', 'Brown Noise', 'Sawtooth', 'Square', 'FM Synth'], 
             'default': 'Sine', 'category': 'Waveform', 'label': '🎛 Waveform Type',
             'description': 'Choose the synthesis algorithm.'},
            {'id': 'frequency', 'type': 'slider', 'min': 20.0, 'max': 2000.0,
             'default': 440.0, 'step': 1.0, 'category': 'Pitch', 'label': '〰 Frequency (Hz)',
             'description': 'Base pitch. 440Hz = Concert A.'},
            {'id': 'amplitude', 'type': 'slider', 'min': 0.0, 'max': 1.0,
             'default': 0.8, 'step': 0.05, 'category': 'Output', 'label': '📊 Volume',
             'description': 'Output level. 0.0 = silence, 1.0 = maximum before clipping.'}
        ]

    def load_model(self, config: dict) -> None:
        logger.info("[MathSynth] Initializing Synthesizer Backend...")
        time.sleep(0.2)
        self.model = "MathSynthEngine"
        logger.info("[MathSynth] Ready.")

    def _apply_envelope(self, audio: np.ndarray, sample_rate: int, fade_ms: int = 50) -> np.ndarray:
        fade_len = int(sample_rate * fade_ms / 1000)
        if fade_len > 0 and len(audio) > 2 * fade_len:
            audio[:fade_len] *= np.linspace(0, 1, fade_len)
            audio[-fade_len:] *= np.linspace(1, 0, fade_len)
        return audio

    def generate(self, prompt: str, duration: int, params: dict,
                 progress_callback: Optional[ProgressCallback] = None,
                 stop_check: Optional[StopCheck] = None) -> Optional[GenerationResult]:
        
        waveform = params.get('waveform_type', 'Sine')
        freq = float(params.get('frequency', 440.0))
        amp = float(params.get('amplitude', 0.8))
        sample_rate = 44100
        n_samples = int(sample_rate * duration)
        
        audio = np.zeros(n_samples, dtype=np.float32)
        chunks = 10
        chunk_size = n_samples // chunks

        for i in range(chunks):
            if stop_check and stop_check():
                logger.warning("[MathSynth] Generation cancelled by user.")
                return None

            time.sleep(0.05)
            start = i * chunk_size
            end = n_samples if i == chunks - 1 else start + chunk_size

            t = np.linspace(start / sample_rate, end / sample_rate, end - start, endpoint=False)
            chunk_audio = np.zeros(end - start, dtype=np.float32)

            if waveform == 'Sine':
                chunk_audio = np.sin(2 * np.pi * freq * t)
            elif waveform == 'White Noise':
                chunk_audio = np.random.uniform(-1, 1, len(t))
            elif waveform == 'Brown Noise':
                white = np.random.uniform(-1, 1, len(t))
                chunk_audio = np.cumsum(white) / 50.0
                max_val = np.max(np.abs(chunk_audio))
                if max_val > 0: chunk_audio = chunk_audio / max_val
            elif waveform == 'Sawtooth':
                chunk_audio = 2 * (freq * t % 1) - 1
            elif waveform == 'Square':
                chunk_audio = np.sign(np.sin(2 * np.pi * freq * t))
            elif waveform == 'FM Synth':
                mod_index = 5.0
                mod_freq = freq * 1.5
                chunk_audio = np.sin(2 * np.pi * freq * t + mod_index * np.sin(2 * np.pi * mod_freq * t))
                max_val = np.max(np.abs(chunk_audio))
                if max_val > 0: chunk_audio = chunk_audio / max_val

            audio[start:end] = chunk_audio * amp
            if progress_callback:
                progress_callback(int((i + 1) / chunks * 100))

        audio = self._apply_envelope(audio, sample_rate)
        return {'audio': audio, 'sample_rate': sample_rate}

    def unload(self) -> None:
        logger.info("[MathSynth] Unloading model...")
        self.model = None
