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
    """Return a platform-appropriate config directory path."""
    if os.name == "nt":
        base = os.getenv("APPDATA", str(Path.home() / "AppData" / "Roaming"))
    else:
        base = os.getenv("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    p = Path(base) / app_name
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_config_path(app_name: str = "CopyPasteTool") -> Path:
    return get_config_dir(app_name) / "settings.json"


def _do_save(path: Path):
    tmp = path.with_suffix(".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(_settings or DEFAULTS, f, indent=2, ensure_ascii=False)
        tmp.replace(path)
    except Exception:
        pass


def save_settings(app_name: str = "CopyPasteTool") -> None:
    """Immediately write settings to disk."""
    path = get_config_path(app_name)
    _do_save(path)


def save_debounced(delay: float = 0.5, app_name: str = "CopyPasteTool") -> None:
    """Schedule a debounced save after `delay` seconds. Multiple calls reset the timer."""
    global _save_timer
    try:
        if _save_timer is not None:
            try:
                _save_timer.cancel()
            except Exception:
                pass
        path = get_config_path(app_name)
        import threading
        _save_timer = threading.Timer(delay, _do_save, args=(path,))
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
    cfg = DEFAULTS.copy()
    path = get_config_path(app_name)
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                cfg.update(loaded)
        except Exception:
            try:
                backup = path.with_suffix('.broken.json')
                path.replace(backup)
            except Exception:
                pass
    _settings = cfg
    return _settings
