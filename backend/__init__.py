"""Music-generation backend package."""
from .base import (
    MusicBackend, SettingItem, PromptSchema, BackendMetadata, 
    GenerationResult, ProgressCallback, StopCheck, BackendError
)

__all__ = [
    'MusicBackend', 'SettingItem', 'PromptSchema', 'BackendMetadata',
    'GenerationResult', 'ProgressCallback', 'StopCheck', 'BackendError'
]
