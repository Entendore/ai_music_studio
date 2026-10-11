"""Configuration loading, saving, and environment variable setup."""
import yaml
import os

DEFAULT_CONFIG = {
    'system': {
        'cache_dir': os.path.join(os.path.expanduser('~'), '.aimusic', 'cache'),
        'ckpt_dir': os.path.join(os.path.expanduser('~'), '.aimusic', 'ckpt'),
    },
    'hardware': {'device': 'cuda'},
    'plugins': {'active_plugin': ''},
    'settings': {'output_dir': 'output'},
    'backend_settings': {}
}

def load_config(config_path="config.yaml"):
    if not os.path.exists(config_path):
        save_config(DEFAULT_CONFIG, config_path)
        return DEFAULT_CONFIG
    try:
        with open(config_path, "r") as f:
            cfg = yaml.safe_load(f)
            # Deep merge defaults to ensure missing keys exist
            for k, v in DEFAULT_CONFIG.items():
                if k not in cfg: cfg[k] = v
            return cfg
    except Exception:
        return DEFAULT_CONFIG

def save_config(config, config_path="config.yaml"):
    with open(config_path, "w") as f: 
        yaml.dump(config, f, default_flow_style=False)

def setup_environment(config):
    cache_path = os.path.abspath(config.get('system', {}).get('cache_dir', 'cache'))
    os.makedirs(cache_path, exist_ok=True)
    os.environ['HF_HOME'] = cache_path
    os.environ['TORCH_HOME'] = cache_path
    os.environ['XDG_CACHE_HOME'] = cache_path
