"""Application entry point — configures paths, environment, and launches the GUI."""
import os
import sys

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_aimusic_dir = os.path.dirname(os.path.abspath(__file__))

for _p in (_project_root, _aimusic_dir):
    if _p not in sys.path: sys.path.insert(0, _p)

from config import load_config, setup_environment
from core import PluginManager
from gui_main import launch_gui

def main():
    config = load_config()
    setup_environment(config)
    manager = PluginManager()
    launch_gui(manager, config)

if __name__ == "__main__":
    main()
