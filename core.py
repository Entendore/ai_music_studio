"""Core plugin management and audio file utilities."""
import logging
import os
import pkgutil
import soundfile as sf
import importlib
from backend import MusicBackend, BackendError

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

class PluginManager:
    def __init__(self):
        self.active_backend: MusicBackend = None

    @staticmethod
    def discover_available_backends() -> list:
        available = []
        try:
            import backend as _pkg
            pkg_path = os.path.dirname(_pkg.__file__)
            for _, modname, _ in pkgutil.iter_modules([pkg_path]):
                if modname == 'base': continue
                try:
                    module = importlib.import_module(f"backend.{modname}")
                    cls = getattr(module, "Plugin", None)
                    if cls and issubclass(cls, MusicBackend) and cls is not MusicBackend:
                        available.append(modname)
                except Exception as exc:
                    logger.debug(f"Skipping backend '{modname}': {exc}")
        except ImportError:
            pass
        return sorted(available)

    @staticmethod
    def get_backend_metadata() -> dict:
        metadata = {}
        try:
            import backend as _pkg
            pkg_path = os.path.dirname(_pkg.__file__)
            for _, modname, _ in pkgutil.iter_modules([pkg_path]):
                if modname == 'base': continue
                try:
                    module = importlib.import_module(f"backend.{modname}")
                    cls = getattr(module, "Plugin", None)
                    if cls and issubclass(cls, MusicBackend) and cls is not MusicBackend:
                        metadata[modname] = cls.get_metadata()
                except Exception:
                    pass
        except ImportError:
            pass
        return metadata

    def load_plugin(self, plugin_name: str, config: dict):
        try:
            module = importlib.import_module(f"backend.{plugin_name}")
            backend = module.Plugin()
            logger.info(f"Loading plugin: {plugin_name}...")
            backend.load_model(config)
            self.active_backend = backend
            return backend
        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_name}: {e}")
            raise BackendError(str(e))

    def save_audio(self, audio_data: dict, filename: str, output_dir: str):
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.abspath(os.path.join(output_dir, f"{filename}.wav"))
        sf.write(path, audio_data['audio'], audio_data['sample_rate'])
        logger.info(f"Saved audio to: {path}")
        return path
