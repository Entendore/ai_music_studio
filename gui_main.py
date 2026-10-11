"""Main application window with minimalist styling."""
import sys
import os
import logging
from typing import Optional
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QSpinBox, QPushButton, QTextEdit,
    QSplitter, QMessageBox, QProgressBar, QComboBox, QScrollArea, QFrame
)
from PySide6.QtCore import Qt, QThread, Slot, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtGui import QFont

from core import PluginManager
from gui_components import (
    SettingsDialog, build_settings_widgets, clear_layout,
    apply_global_styles, STYLES, SettingWidget, create_reset_button
)
from gui_workers import Worker, LogEmitter, QtLogHandler
from config import save_config
from backend import BackendMetadata

logger = logging.getLogger(__name__)

class MusicStudioApp(QMainWindow):
    def __init__(self, manager: PluginManager, config: dict):
        super().__init__()
        self.manager = manager
        self.config = config
        self.thread = None
        self.worker = None
        self.settings_widgets: dict[str, SettingWidget] = {}
        self._backend_metadata: dict = manager.get_backend_metadata()
        self.last_saved_path = None

        self.setWindowTitle("AI Music Studio")
        self.resize(900, 650)

        central = QWidget()
        self.setCentralWidget(central)
        self.splitter = QSplitter(Qt.Horizontal)
        root = QHBoxLayout(central)
        root.setContentsMargins(6, 6, 6, 6)
        root.addWidget(self.splitter)

        self.control_scroll = QScrollArea()
        self.control_scroll.setWidgetResizable(True)
        self.control_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.control_panel = QWidget()
        self.control_layout = QVBoxLayout(self.control_panel)
        self.control_layout.setContentsMargins(4, 4, 4, 4)
        self.control_scroll.setWidget(self.control_panel)
        self.splitter.addWidget(self.control_scroll)

        self.log_panel = QWidget()
        self.log_layout = QVBoxLayout(self.log_panel)
        self.log_layout.setContentsMargins(0, 0, 0, 0)
        self.splitter.addWidget(self.log_panel)
        self.splitter.setSizes([350, 550])

        self._build_ui()
        self._setup_logging()
        
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.player.playbackStateChanged.connect(self._update_playback_state)

        if not self.config.get('plugins', {}).get('active_plugin'):
            backends = self.manager.discover_available_backends()
            if backends:
                self.config['plugins']['active_plugin'] = backends[0]
        self.load_backend()

    def _build_ui(self):
        title = QLabel("AI Music Studio")
        title.setFont(QFont("Segoe UI", 13, QFont.Bold))
        title.setStyleSheet("color: #666; padding: 2px;")
        self.control_layout.addWidget(title)
        self._build_backend_selector()
        self._build_input_section()
        self._build_settings_section()
        self._build_controls_section()
        self._build_playback_section()
        self.control_layout.addStretch()
        self._build_log_section()

    def _build_backend_selector(self):
        self.backend_combo = QComboBox()
        for backend_id in self.manager.discover_available_backends():
            info: BackendMetadata = self._backend_metadata.get(backend_id, {})
            self.backend_combo.addItem(f"{info.get('icon', '📦')} {info.get('name', backend_id)}", backend_id)
        
        current_plugin = self.config.get('plugins', {}).get('active_plugin', '')
        for i in range(self.backend_combo.count()):
            if self.backend_combo.itemData(i) == current_plugin:
                self.backend_combo.setCurrentIndex(i); break
        
        self.backend_combo.currentIndexChanged.connect(self._on_backend_selection_changed)
        self.control_layout.addWidget(self.backend_combo)

        self.backend_status_label = QLabel("")
        self.backend_status_label.setStyleSheet("font-size: 10px; color: #555; padding: 2px;")
        self.control_layout.addWidget(self.backend_status_label)

    def _on_backend_selection_changed(self, index: int):
        backend_name = self.backend_combo.itemData(index)
        if not backend_name: return

        if self.thread and self.thread.isRunning():
            QMessageBox.warning(self, "Cannot Switch", "A generation is currently running.")
            return

        if self.manager.active_backend: self.manager.active_backend.unload()
        self.config['plugins']['active_plugin'] = backend_name
        save_config(self.config)
        self.load_backend()

    def _build_input_section(self):
        self.prompt_group = QFrame()
        layout = QVBoxLayout(self.prompt_group)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.prompt_desc_label = QLabel()
        self.prompt_desc_label.setWordWrap(True)
        self.prompt_desc_label.setStyleSheet("color: #555; font-size: 10px;")
        layout.addWidget(self.prompt_desc_label)

        self.prompt_input = QTextEdit()
        self.prompt_input.setMinimumHeight(80); self.prompt_input.setMaximumHeight(150)
        layout.addWidget(self.prompt_input)

        row = QHBoxLayout()
        row.addWidget(QLabel("Duration:"))
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(5, 300); self.duration_spin.setValue(30); self.duration_spin.setSuffix("s")
        self.duration_spin.setStyleSheet(STYLES['spinbox']); self.duration_spin.setMaximumWidth(80)
        row.addWidget(self.duration_spin); row.addStretch()
        layout.addLayout(row)
        self.control_layout.addWidget(self.prompt_group)

    def _configure_prompt_section(self, prompt_schema: Optional[dict]):
        if not prompt_schema or not prompt_schema.get('required', True):
            self.prompt_group.hide(); return
        self.prompt_group.show()
        self.prompt_desc_label.setText(prompt_schema.get('description', ''))
        self.prompt_input.setPlaceholderText(prompt_schema.get('placeholder', ''))

    def _build_settings_section(self):
        self.settings_group = QFrame()
        outer_layout = QVBoxLayout(self.settings_group)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        
        self.settings_scroll = QScrollArea()
        self.settings_scroll.setWidgetResizable(True); self.settings_scroll.setMaximumHeight(250)
        self.settings_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        container = QWidget()
        self.settings_layout = QVBoxLayout(container)
        self.settings_layout.setContentsMargins(0, 0, 0, 0)
        self.settings_scroll.setWidget(container)
        outer_layout.addWidget(self.settings_scroll)
        self.control_layout.addWidget(self.settings_group)

    def _build_controls_section(self):
        layout = QVBoxLayout()
        self.btn_generate = QPushButton("Generate")
        self.btn_generate.setStyleSheet(STYLES['button_primary'])
        self.btn_generate.clicked.connect(self.start_generation)
        layout.addWidget(self.btn_generate)

        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet(STYLES['button_danger'])
        self.btn_stop.clicked.connect(self.stop_generation)
        layout.addWidget(self.btn_stop)

        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet(STYLES['progress_bar'])
        layout.addWidget(self.progress_bar)

        row = QHBoxLayout()
        self.btn_reload = QPushButton("Reload")
        self.btn_reload.setStyleSheet(STYLES['button_secondary'])
        self.btn_reload.clicked.connect(self.reload_backend)
        row.addWidget(self.btn_reload)
        
        self.btn_settings = QPushButton("Paths")
        self.btn_settings.setStyleSheet(STYLES['button_secondary'])
        self.btn_settings.clicked.connect(self.open_settings)
        row.addWidget(self.btn_settings)
        layout.addLayout(row)
        self.control_layout.addLayout(layout)

    def _build_playback_section(self):
        layout = QVBoxLayout()
        self.lbl_now_playing = QLabel("No audio")
        self.lbl_now_playing.setStyleSheet("color: #555; font-size: 10px;")
        layout.addWidget(self.lbl_now_playing)

        row = QHBoxLayout()
        self.btn_play = QPushButton("Play"); self.btn_play.setEnabled(False)
        self.btn_play.setStyleSheet(STYLES['button_primary'])
        self.btn_play.clicked.connect(self.play_audio)
        row.addWidget(self.btn_play)

        self.btn_stop_play = QPushButton("Stop"); self.btn_stop_play.setEnabled(False)
        self.btn_stop_play.setStyleSheet(STYLES['button_secondary'])
        self.btn_stop_play.clicked.connect(self.stop_audio)
        row.addWidget(self.btn_stop_play)
        layout.addLayout(row)
        self.control_layout.addLayout(layout)

    def _build_log_section(self):
        header = QLabel("Console")
        header.setStyleSheet("color: #555; padding: 2px;")
        self.log_layout.addWidget(header)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("QTextEdit { background-color: #0a0a0a; color: #666; font-family: 'Consolas', monospace; font-size: 10px; border: 1px solid #222; border-radius: 2px; padding: 6px; }")
        self.log_layout.addWidget(self.log_text)

    def _setup_logging(self):
        self.log_emitter = LogEmitter()
        self.log_emitter.log_message.connect(self.append_log)
        handler = QtLogHandler(self.log_emitter)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', datefmt='%H:%M:%S'))
        logging.getLogger().addHandler(handler)

    def open_settings(self): SettingsDialog(self.config, self).exec()

    def populate_settings(self):
        clear_layout(self.settings_layout)
        self.settings_widgets = {}
        if not self.manager.active_backend:
            empty_label = QLabel("No backend loaded")
            empty_label.setStyleSheet("color: #444; padding: 10px;")
            self.settings_layout.addWidget(empty_label)
            self._configure_prompt_section(None); return
        
        prompt_schema = self.manager.active_backend.__class__.get_prompt_schema()
        self._configure_prompt_section(prompt_schema)

        schema = self.manager.active_backend.__class__.get_settings_schema()
        backend_name = self.config.get('plugins', {}).get('active_plugin', '')
        saved_settings = self.config.get('backend_settings', {}).get(backend_name, {})
        
        build_settings_widgets(schema, self.settings_layout, self.settings_widgets, saved_settings)
        create_reset_button(self.settings_widgets, self.settings_layout)

    def save_backend_settings(self):
        if not self.settings_widgets: return
        backend_name = self.config.get('plugins', {}).get('active_plugin', '')
        if not backend_name: return
        
        self.config.setdefault('backend_settings', {}).setdefault(backend_name, {})
        for key, widget in self.settings_widgets.items():
            value = widget.get_value()
            if value is not None: self.config['backend_settings'][backend_name][key] = value
        save_config(self.config)

    def load_backend(self):
        plugin_name = self.config['plugins']['active_plugin']
        info = self._backend_metadata.get(plugin_name, {})
        try:
            self.manager.load_plugin(plugin_name, self.config)
            self.populate_settings()
            self.btn_generate.setEnabled(True)
            self.backend_status_label.setText(f"✓ {info.get('name', plugin_name)} loaded")
        except Exception as e:
            logging.error(f"Failed to load: {e}")
            self.btn_generate.setEnabled(False)
            self.backend_status_label.setText(f"✗ {info.get('name', plugin_name)} failed")

    def reload_backend(self):
        if self.manager.active_backend: self.manager.active_backend.unload()
        self.load_backend()

    def start_generation(self):
        if self.thread and self.thread.isRunning(): return
        self.stop_audio(); self.save_backend_settings()

        params = {k: w.get_value() for k, w in self.settings_widgets.items() if w.get_value() is not None}
        prompt = self.prompt_input.toPlainText()

        if self.manager.active_backend:
            prompt_schema = self.manager.active_backend.__class__.get_prompt_schema()
            if prompt_schema.get('required', True) and not prompt.strip():
                QMessageBox.warning(self, "Empty Prompt", "Prompt is required for this backend.")
                return

        self.thread = QThread()
        self.worker = Worker(self.manager.active_backend, prompt, self.duration_spin.value(), params, self.config)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run_generation)
        self.worker.finished.connect(self.on_finished)
        self.worker.success.connect(self.on_success)
        self.worker.error.connect(self.on_error)
        self.worker.progress.connect(self.update_progress)

        self.thread.start()
        self.btn_generate.setEnabled(False); self.btn_generate.setText("Generating...")
        self.btn_stop.setEnabled(True); self.progress_bar.setValue(0)

    def stop_generation(self):
        if self.worker: self.worker.stop()

    def play_audio(self):
        if self.last_saved_path:
            self.player.setSource(QUrl.fromLocalFile(self.last_saved_path))
            self.player.play()

    def stop_audio(self): self.player.stop()

    def _update_playback_state(self, state):
        is_playing = state == QMediaPlayer.PlaybackState.PlayingState
        has_audio = self.last_saved_path is not None
        self.btn_play.setEnabled(not is_playing and has_audio)
        self.btn_stop_play.setEnabled(is_playing)
        if is_playing:
            self.lbl_now_playing.setText(f"▶ {os.path.basename(self.last_saved_path)}")
        elif has_audio:
            self.lbl_now_playing.setText("Paused")
        else:
            self.lbl_now_playing.setText("No audio")

    @Slot(str)
    def append_log(self, message):
        color = "#888"
        if "[ERROR]" in message: color = "#663333"
        elif "[WARNING]" in message: color = "#665533"
        elif "[SUCCESS]" in message or "✓" in message: color = "#336633"
        self.log_text.append(f'<span style="color: {color};">{message}</span>')

    @Slot(int)
    def update_progress(self, value): self.progress_bar.setValue(value)

    @Slot(dict, str)
    def on_success(self, result, filename):
        output_dir = self.config.get('settings', {}).get('output_dir', 'output')
        try:
            path = self.manager.save_audio(result, filename, output_dir)
            self.last_saved_path = path
            self.btn_play.setEnabled(True)
            self.append_log(f"✓ Saved to: {path}")
            self.play_audio()
        except Exception as e: logging.error(f"Save error: {e}")

    @Slot(str)
    def on_error(self, err_msg): QMessageBox.critical(self, "Error", f"Generation failed:\n\n{err_msg}")

    @Slot()
    def on_finished(self):
        if self.thread:
            self.thread.quit(); self.thread.wait()
            self.thread.deleteLater(); self.worker.deleteLater()
            self.thread = None; self.worker = None
        self.btn_generate.setEnabled(True); self.btn_generate.setText("Generate")
        self.btn_stop.setEnabled(False)

    def closeEvent(self, event):
        self.save_backend_settings(); self.stop_audio()
        if self.thread and self.thread.isRunning():
            self.worker.stop(); self.thread.quit(); self.thread.wait()
        event.accept()

def launch_gui(manager: PluginManager, config: dict):
    app = QApplication(sys.argv)
    apply_global_styles(app)
    window = MusicStudioApp(manager, config)
    window.show()
    sys.exit(app.exec())
