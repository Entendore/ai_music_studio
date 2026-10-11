"""Background worker thread and Qt logging bridge components."""
import datetime
import logging
from typing import Optional
from PySide6.QtCore import QObject, Signal, Slot
from backend import MusicBackend, GenerationResult

class LogEmitter(QObject):
    log_message = Signal(str)

class QtLogHandler(logging.Handler):
    def __init__(self, emitter: LogEmitter):
        super().__init__()
        self.emitter = emitter

    def emit(self, record):
        self.emitter.log_message.emit(self.format(record))

class Worker(QObject):
    finished = Signal()
    error = Signal(str)
    success = Signal(dict, str)
    progress = Signal(int)

    def __init__(self, backend: MusicBackend, prompt: str, duration: int, params: dict, config: dict):
        super().__init__()
        self.backend = backend
        self.prompt = prompt
        self.duration = duration
        self.params = params
        self.config = config
        self._is_cancelled = False

    def stop(self):
        self._is_cancelled = True

    @Slot()
    def run_generation(self):
        try:
            result = self.backend.generate(
                self.prompt, self.duration, self.params,
                progress_callback=self.progress.emit,
                stop_check=lambda: self._is_cancelled,
            )
            if result is not None:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_prompt = "".join(c if c.isalnum() else "_" for c in self.prompt)[:20]
                self.success.emit(result, f"{timestamp}_{safe_prompt}")
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()
