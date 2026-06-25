import json
import os
from pathlib import Path
from typing import Any, Callable, Dict

DEFAULTS = {
    "version": 1,
    "capture_enabled": True,
    "pause_after_set_ms": 500,
    "secret_safe_mode": True,
    "persistence_enabled": False,
    "persistence_path": "",
    "max_history_items": 500,
    "dedupe_strategy": "lru",
    "dedupe_lru_size": 200,
    "dedupe_per_app_window_s": 30,
    "blocklist_apps": ["1password", "bitwarden", "lastpass", "authenticator", "keychain"],
    "per_app_capture_toggle": {},
    "pause_indicator_enabled": True,
    "debug_level": 0,
}

_callbacks = []
_settings: Dict[str, Any] = {}
_save_timer = None


def get_config_dir(app_name: str = "CopyPasteTool") -> Path:
    if os.name == "nt":
        base = os.getenv("APPDATA", str(Path.home() / "AppData" / "Roaming"))
    else:
        base = os.getenv("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    config_dir = Path(base) / app_name
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_path(app_name: str = "CopyPasteTool") -> Path:
    return get_config_dir(app_name) / "settings.json"


def _write_settings_file(path: Path) -> None:
    tmp_path = path.with_suffix(".tmp")
    try:
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(_settings or DEFAULTS, handle, indent=2, ensure_ascii=False)
        tmp_path.replace(path)
    except Exception:
        pass


def save_settings(app_name: str = "CopyPasteTool") -> None:
    _write_settings_file(get_config_path(app_name))


def save_debounced(delay: float = 0.5, app_name: str = "CopyPasteTool") -> None:
    global _save_timer
    try:
        if _save_timer is not None:
            try:
                _save_timer.cancel()
            except Exception:
                pass
        path = get_config_path(app_name)
        import threading
        _save_timer = threading.Timer(delay, _write_settings_file, args=(path,))
        _save_timer.daemon = True
        _save_timer.start()
    except Exception:
        save_settings(app_name)


def get(key: str, default: Any = None) -> Any:
    return _settings.get(key, DEFAULTS.get(key, default))


def set_(key: str, value: Any) -> None:
    _settings[key] = value
    for cb in list(_callbacks):
        try:
            cb(key, value)
        except Exception:
            pass


def register_callback(cb: Callable[[str, Any], None]) -> None:
    if cb not in _callbacks:
        _callbacks.append(cb)


def unregister_callback(cb: Callable[[str, Any], None]) -> None:
    try:
        _callbacks.remove(cb)
    except ValueError:
        pass


def load_settings(app_name: str = "CopyPasteTool") -> Dict[str, Any]:
    global _settings
    merged_settings = DEFAULTS.copy()
    path = get_config_path(app_name)
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if isinstance(loaded, dict):
                merged_settings.update(loaded)
        except Exception:
            try:
                broken_copy = path.with_suffix('.broken.json')
                path.replace(broken_copy)
            except Exception:
                pass
    _settings = merged_settings
    return _settings
