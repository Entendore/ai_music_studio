"""HeartMuLa Music Generation Backend."""
import numpy as np
import logging
import os
import tempfile
import subprocess
import threading
import time
import soundfile as sf
import torch
from typing import Optional
from backend import MusicBackend, GenerationResult, ProgressCallback, StopCheck

logger = logging.getLogger(__name__)

class Plugin(MusicBackend):
    def __init__(self):
        self.device = "cpu"
        self.model_path = ""
        self.repo_path = ""

    @classmethod
    def get_metadata(cls):
        return {
            'name': 'HeartMuLa',
            'description': 'Lyrics to song with vocals',
            'details': 'Supports 3B/7B models, GTX 1080 optimization.',
            'icon': '🎤',
            'requirements': 'Requires checkpoints and git repo'
        }

    @classmethod
    def get_prompt_schema(cls):
        return {
            'required': True,
            'title': '📝 Lyrics Input',
            'description': 'Write structured lyrics. Style is controlled by Tags.',
            'placeholder': "[Intro]\nSoft piano melody...\n\n[Verse 1]\nWalking through..."
        }

    @classmethod
    def get_settings_schema(cls):
        return [
            {'id': 'tags', 'type': 'text', 'default': 'piano,happy,wedding,synthesizer,romantic',
             'category': 'Music Style', 'label': '🎵 Style Tags', 'description': 'Comma-separated tags.'},
            {'id': 'temperature', 'type': 'slider', 'min': 0.1, 'max': 2.0, 'default': 1.0, 'step': 0.1,
             'category': 'Sampling', 'label': '🌡 Temperature', 'description': 'Controls randomness.'},
            {'id': 'topk', 'type': 'slider', 'min': 1, 'max': 200, 'default': 50, 'step': 1,
             'category': 'Sampling', 'label': '🎯 Top-K', 'description': 'Limits sampling to K tokens.'},
            {'id': 'cfg_scale', 'type': 'slider', 'min': 1.0, 'max': 5.0, 'default': 1.5, 'step': 0.1,
             'category': 'Sampling', 'label': '⚖ CFG Scale', 'description': 'Guidance strength.'},
            {'id': 'version', 'type': 'dropdown', 'options': ['3B', '7B'], 'default': '3B',
             'category': 'Model', 'label': '📦 Model Size', 'description': '3B: 8GB VRAM. 7B: 24GB+ VRAM.'},
            {'id': 'lazy_load', 'type': 'dropdown', 'options': ['true', 'false'], 'default': 'true',
             'category': 'Performance (VRAM)', 'label': '⚡ Lazy Load', 'description': 'Reduce peak VRAM.'},
            {'id': 'mula_dtype', 'type': 'dropdown', 'options': ['float16', 'bfloat16', 'float32'], 'default': 'float16',
             'category': 'Performance (VRAM)', 'label': '🔢 Model Precision', 'description': 'Halves VRAM usage.'},
            {'id': 'codec_dtype', 'type': 'dropdown', 'options': ['float32', 'float16'], 'default': 'float32',
             'category': 'Performance (VRAM)', 'label': '🎵 Codec Precision', 'description': 'Use float32 to avoid artifacts.'}
        ]

    def load_model(self, config: dict) -> None:
        self.device = config['hardware'].get('device', 'cuda')
        self.model_path = config.get('system', {}).get('ckpt_dir', '')
        self.repo_path = config.get('system', {}).get('heartlib_repo_dir', '')

        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"HeartMuLa checkpoints not found at {self.model_path}")

        self.script_path = os.path.join(self.repo_path, "examples", "run_music_generation.py")
        if not os.path.exists(self.script_path):
            raise FileNotFoundError(f"Script not found at {self.script_path}")

        if self.device == 'cuda':
            total_mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            logger.info(f"GPU Detected: {torch.cuda.get_device_name(0)} ({total_mem:.1f} GB VRAM)")
            if total_mem <= 9.0:
                logger.warning("⚠️ 8GB VRAM GPU Detected: Ensure Lazy Load is TRUE and Precision is FLOAT16!")

    def generate(self, prompt: str, duration: int, params: dict,
                 progress_callback: Optional[ProgressCallback] = None,
                 stop_check: Optional[StopCheck] = None) -> Optional[GenerationResult]:
        
        cmd = [
            "python", self.script_path,
            "--model_path", self.model_path,
            "--lyrics", "lyrics.txt", 
            "--tags", "tags.txt",
            "--save_path", "output.wav",
            "--max_audio_length_ms", str(duration * 1000),
            "--topk", str(int(params.get('topk', 50))),
            "--temperature", str(params.get('temperature', 1.0)),
            "--cfg_scale", str(params.get('cfg_scale', 1.5)),
            "--version", params.get('version', '3B'),
            "--mula_device", self.device,
            "--codec_device", self.device,
            "--lazy_load", params.get('lazy_load', 'true'),
            "--mula_dtype", params.get('mula_dtype', 'float16'),
            "--codec_dtype", params.get('codec_dtype', 'float32')
        ]

        if progress_callback: progress_callback(5)

        with tempfile.TemporaryDirectory() as temp_dir:
            with open(os.path.join(temp_dir, "lyrics.txt"), 'w', encoding='utf-8') as f: f.write(prompt)
            with open(os.path.join(temp_dir, "tags.txt"), 'w', encoding='utf-8') as f: f.write(params.get('tags', 'pop'))
            
            cmd[cmd.index("lyrics.txt")] = os.path.join(temp_dir, "lyrics.txt")
            cmd[cmd.index("tags.txt")] = os.path.join(temp_dir, "tags.txt")
            output_path = os.path.join(temp_dir, "output.wav")
            cmd[cmd.index("output.wav")] = output_path

            logger.info("Executing HeartMuLa CLI...")
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            def drain_pipe(pipe, level):
                for line in pipe:
                    logger.log(level, f"[CLI] {line.strip()}")
            
            t_out = threading.Thread(target=drain_pipe, args=(process.stdout, logging.INFO), daemon=True)
            t_err = threading.Thread(target=drain_pipe, args=(process.stderr, logging.ERROR), daemon=True)
            t_out.start()
            t_err.start()

            while process.poll() is None:
                if stop_check and stop_check():
                    process.terminate()
                    logger.warning("HeartMuLa CLI terminated by user.")
                    return None
                time.sleep(0.5)

            t_out.join(timeout=1)
            t_err.join(timeout=1)

            if process.returncode != 0:
                return None
            if progress_callback: progress_callback(90)

            if not os.path.exists(output_path):
                logger.error("Generation finished but output file was not created.")
                return None

            try:
                audio_data, sample_rate = sf.read(output_path, dtype='float32')
                if len(audio_data.shape) > 1: audio_data = audio_data[:, 0]
                if progress_callback: progress_callback(100)
                return {'audio': audio_data, 'sample_rate': sample_rate}
            except Exception as e:
                logger.error(f"Failed to read generated audio: {e}")
                return None

    def unload(self) -> None:
        logger.info("HeartMuLa subprocess backend unloaded.")
