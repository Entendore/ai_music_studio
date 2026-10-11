"""Abstract base class and public data contracts for music-generation backends."""
import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, List, Optional, TypedDict

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int], None]
StopCheck = Callable[[], bool]

class BackendError(RuntimeError):
    """Base class for all errors originating inside a backend."""

class SettingItem(TypedDict, total=False):
    id: str
    type: str
    label: str
    description: str
    category: str
    default: Any
    min: float
    max: float
    step: float
    options: List[str]
    placeholder: str

class PromptSchema(TypedDict, total=False):
    required: bool
    title: Optional[str]
    description: Optional[str]
    placeholder: Optional[str]

class BackendMetadata(TypedDict, total=False):
    name: str
    description: str
    details: str
    icon: str
    requirements: str

class GenerationResult(TypedDict):
    audio: Any
    sample_rate: int

class MusicBackend(ABC):
    @abstractmethod
    def load_model(self, config: dict) -> None: ...
    
    @abstractmethod
    def generate(
        self,
        prompt: str,
        duration: int,
        params: dict,
        progress_callback: Optional[ProgressCallback] = None,
        stop_check: Optional[StopCheck] = None,
    ) -> Optional[GenerationResult]: ...

    @abstractmethod
    def unload(self) -> None: ...

    @classmethod
    def get_settings_schema(cls) -> List[SettingItem]:
        return []

    @classmethod
    def get_prompt_schema(cls) -> PromptSchema:
        return {
            'required': True,
            'title': '📝 Prompt',
            'description': 'Enter a text prompt for generation.',
            'placeholder': 'Enter your prompt here...',
        }

    @classmethod
    def get_metadata(cls) -> BackendMetadata:
        return {
            'name': cls.__name__,
            'description': '',
            'details': '',
            'icon': '📦',
            'requirements': '',
        }

    @property
    def display_name(self) -> str:
        return str(self.get_metadata().get('name') or type(self).__name__)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.get_metadata.__func__ is MusicBackend.get_metadata.__func__:
            logger.warning("Backend %s does not override get_metadata()", cls.__name__)
