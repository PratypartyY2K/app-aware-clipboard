from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtWidgets import QApplication
from clipboard_manager.utils import get_frontmost_app, get_top_window_owners, is_pyobjc_available
from clipboard_manager import settings
import time
from datetime import datetime
import os
from collections import deque

def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except Exception:
        return default

def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except Exception:
        return default

DEFAULT_LOOKBACK = _env_float('CP_LOOKBACK_SECONDS', 2.5)
DEFAULT_FREQ_LOOKBACK = _env_float('CP_FREQ_LOOKBACK_SECONDS', 5.0)
OWNER_MIN_SCORE = _env_int('CP_MIN_OWNER_SCORE', 0)
OWNER_WEIGHT_BROWSER = _env_int('CP_WEIGHT_BROWSER', 50)
OWNER_WEIGHT_COMM = _env_int('CP_WEIGHT_COMM', 30)
OWNER_WEIGHT_IDE = _env_int('CP_WEIGHT_IDE', 20)
OWNER_CONTENT_BOOST = _env_int('CP_WEIGHT_CONTENT_BOOST', 25)
OWNER_CODE_BOOST = _env_int('CP_WEIGHT_CODE_BOOST', 30)

class ClipboardWatcher(QObject):
    clipboard_changed = pyqtSignal(str, str, float)

    def __init__(self, parent=None):
        super(ClipboardWatcher, self).__init__(parent)
        self.clipboard = QApplication.clipboard()
        self.clipboard.dataChanged.connect(self._on_clipboard_change)
        self._ignore_until = 0.0
        try:
            self._default_pause_ms = int(settings.get('pause_after_set_ms', 500))
        except Exception:
            self._default_pause_ms = 500
        try:
            settings.register_callback(self._on_setting_changed)
        except Exception:
            pass

        try:
            import sys
            self._self_names = {os.path.basename(sys.executable).lower(),
                                os.path.splitext(os.path.basename(sys.argv[0]))[0].lower(), 'python', 'python3',
                                'clipboard'}
        except Exception:
            self._self_names = {'python', 'python3', 'clipboard'}

        self._app_history = deque(maxlen=80)
        self._last_sampled_app = None

        self._use_appkit_notifications = False
        try:
            if is_pyobjc_available():
                try:
                    from AppKit import NSWorkspace, NSWorkspaceDidActivateApplicationNotification
                    from Foundation import NSObject
                    import objc

                    class _AppkitObserver(NSObject):
                        def initWithWatcher_(self, watcher):
                            self = objc.super(_AppkitObserver, self).init()
                            if self is None:
                                return None
                            self._watcher = watcher
                            return self

                        def appActivated_(self, notification):
                            try:
                                info = notification.userInfo()
                                app = info.get('NSWorkspaceApplicationKey') if info else None
                                if app is not None:
                                    try:
                                        name = app.localizedName()
                                    except Exception:
                                        name = None
                                    if name:
                                        self._watcher._record_app_activation(str(name))
                            except Exception:
                                pass

                    self._appkit_observer = _AppkitObserver.alloc().initWithWatcher_(self)
                    nc = NSWorkspace.sharedWorkspace().notificationCenter()
                    nc.addObserver_selector_name_object_(self._appkit_observer, 'appActivated:', NSWorkspaceDidActivateApplicationNotification, None)
                    self._use_appkit_notifications = True
                except Exception:
                    self._use_appkit_notifications = False
        except Exception:
            self._use_appkit_notifications = False

        if not self._use_appkit_notifications:
            self._app_timer = QTimer(self)
            self._app_timer.timeout.connect(self._sample_active_app)
            self._app_timer.start(150)

        try:
            try:
                initial = get_frontmost_app()
            except Exception:
                initial = None
            if initial and 'python' not in initial.lower():
                norm_initial = self._normalize_app_name(initial)
                nl_init = norm_initial.lower() if norm_initial else ''
                if norm_initial and nl_init.strip() and not any(sn in nl_init for sn in self._self_names) and not any(ign in nl_init for ign in self._IGNORED_OWNERS):
                    self._app_history.append((time.time(), norm_initial))
                    self._last_sampled_app = norm_initial
        except Exception:
            pass


    def _record_app_activation(self, app_name: str):
        try:
            if not app_name:
                return
            if time.time() < self._ignore_until:
                return
            norm = self._normalize_app_name(app_name)
            nl = norm.lower() if norm else ''
            if not norm or nl.strip() == '':
                return
            if any(sn in nl for sn in self._self_names):
                return
            if any(ign in nl for ign in self._IGNORED_OWNERS):
                return
            if norm != self._last_sampled_app:
                self._last_sampled_app = norm
                self._app_history.append((time.time(), norm))
        except Exception:
            pass


    def _sample_active_app(self):
        try:
            app = get_frontmost_app()
        except Exception:
            app = None
        if not app:
            return
        norm = self._normalize_app_name(app)
        nl = norm.lower() if norm else ''
        if not norm or nl.strip() == '':
            return
        if any(sn in nl for sn in self._self_names):
            return
        if any(ign in nl for ign in self._IGNORED_OWNERS):
            return
        if norm != self._last_sampled_app:
            self._last_sampled_app = norm
            self._app_history.append((time.time(), norm))

    _NORMALIZE_MAP = [
        ("visual studio code", "Visual Studio Code"),
        ("code -", "Visual Studio Code"),
        ("code", "Visual Studio Code"),
        ("pycharm", "PyCharm"),
        ("brave", "Brave Browser"),
        ("chrome", "Chrome"),
        ("safari", "Safari"),
        ("firefox", "Firefox"),
        ("discord", "Discord"),
        ("notion", "Notion"),
        ("outlook", "Microsoft Outlook"),
        ("whatsapp", "WhatsApp"),
        ("slack", "Slack"),
        ("teams", "Microsoft Teams"),
    ]

    _IGNORED_OWNERS = [
        'window server', 'grace', 'displaylink', 'display link', 'control center', 'grizzly', 'grap', 'grm', 'gr', 'dock',
        'fontd', 'kernel_task'
    ]

    def _normalize_app_name(self, name: str) -> str:
        if not name:
            return name
        normalized = name.strip()
        name_lower = normalized.lower()
        for alias, canonical_name in self._NORMALIZE_MAP:
            if alias in name_lower:
                return canonical_name
        return normalized

    def score_owner(self, owner_name: str, text_lower: str, allow_ide: bool, code_like: bool) -> int:
        if not owner_name:
            return -999
        owner_lower = owner_name.lower()
        if any(name in owner_lower for name in ('clipboard', 'copy-paste-tool', 'python', 'python3', 'terminal', 'iterm')):
            return -999
        if any(ignored in owner_lower for ignored in self._IGNORED_OWNERS):
            return -999
        score = 0
        if any(name in owner_lower for name in ('brave', 'chrome', 'safari', 'firefox', 'edge', 'opera')):
            score += OWNER_WEIGHT_BROWSER
        if any(name in owner_lower for name in ('discord', 'slack', 'teams')):
            score += OWNER_WEIGHT_COMM
        if any(name in owner_lower for name in ('pycharm', 'intellij', 'vscode', 'sublime', 'atom', 'webstorm', 'visual studio code')):
            score += OWNER_WEIGHT_IDE
        score += 1
        if text_lower:
            if any(token in text_lower for token in ('http://', 'https://', 'www.')) and any(name in owner_lower for name in ('brave', 'chrome', 'safari', 'firefox', 'edge', 'opera')):
                score += OWNER_CONTENT_BOOST
            if code_like and any(name in owner_lower for name in ('pycharm', 'intellij', 'vscode', 'sublime')):
                score += OWNER_CODE_BOOST
            try:
                for part in text_lower.split():
                    if part and part in owner_lower:
                        score += 2
            except Exception:
                pass
        return score

    def _pick_recent_source_app(self, ts: float, *, allow_ide: bool, code_like: bool = False, language_hint: str | None = None) -> str | None:
        lookback_window = DEFAULT_LOOKBACK

        def is_ide(app_name: str) -> bool:
            name_lower = app_name.lower()
            return any(name in name_lower for name in ('pycharm', 'intellij', 'idea', 'webstorm', 'goland', 'clion', 'rider', 'vscode', 'visual studio code', 'sublime', 'atom'))

        def is_self(app_name: str) -> bool:
            name_lower = app_name.lower()
            return any(name in name_lower for name in ('clipboard', 'copy-paste-tool', 'python', 'python3', 'terminal', 'iterm'))

        if not self._app_history:
            return None

        cutoff = ts - lookback_window
        if code_like:
            preferred_ides_by_language = {
                'python': ('pycharm', 'intellij'),
                'javascript': ('vscode', 'visual studio code', 'webstorm'),
                'js': ('vscode', 'visual studio code', 'webstorm'),
            }
            preferred_ides = ()
            if language_hint and language_hint in preferred_ides_by_language:
                preferred_ides = preferred_ides_by_language[language_hint]
            if language_hint:
                preferred_apps_by_language = {
                    'python': 'PyCharm',
                    'javascript': 'Visual Studio Code',
                    'js': 'Visual Studio Code',
                }
                target_app = preferred_apps_by_language.get(language_hint)
                if target_app:
                    freq_cutoff = ts - DEFAULT_FREQ_LOOKBACK
                    for seen_at, app_name in reversed(self._app_history):
                        if seen_at < freq_cutoff:
                            break
                        if not app_name:
                            continue
                        if is_self(app_name):
                            continue
                        if any(ignored in app_name.lower() for ignored in self._IGNORED_OWNERS):
                            continue
                        if target_app.lower() in app_name.lower():
                            return self._normalize_app_name(app_name)
            if preferred_ides:
                for seen_at, app_name in reversed(self._app_history):
                    if seen_at < cutoff:
                        break
                    if not app_name:
                        continue
                    if is_self(app_name):
                        continue
                    if any(ignored in app_name.lower() for ignored in self._IGNORED_OWNERS):
                        continue
                    app_name_lower = app_name.lower()
                    if any(ide_name in app_name_lower for ide_name in preferred_ides):
                        return self._normalize_app_name(app_name)
            for seen_at, app_name in reversed(self._app_history):
                if seen_at < cutoff:
                    break
                if not app_name:
                    continue
                if is_self(app_name):
                    continue
                if any(ignored in app_name.lower() for ignored in self._IGNORED_OWNERS):
                    continue
                if is_ide(app_name):
                    return self._normalize_app_name(app_name)

        recent_counts = {}
        last_seen = {}
        for seen_at, app_name in self._app_history:
            if not app_name:
                continue
            if seen_at < cutoff:
                continue
            name_lower = app_name.lower()
            if is_self(app_name):
                continue
            if any(ignored in name_lower for ignored in self._IGNORED_OWNERS):
                continue
            canonical_name = self._normalize_app_name(app_name)
            recent_counts[canonical_name] = recent_counts.get(canonical_name, 0) + 1
            last_seen[canonical_name] = max(last_seen.get(canonical_name, 0), seen_at)

        if not recent_counts:
            return None

        if language_hint:
            preferred_apps_by_language = {
                'python': 'PyCharm',
                'javascript': 'Visual Studio Code',
                'js': 'Visual Studio Code',
            }
            target_app = preferred_apps_by_language.get(language_hint)
            if target_app:
                for app_name in recent_counts.keys():
                    if target_app.lower() in app_name.lower() or app_name.lower() in target_app.lower():
                        return target_app

        for seen_at, app_name in reversed(self._app_history):
            if seen_at < cutoff:
                break
            if not app_name:
                continue
            if is_self(app_name):
                continue
            if any(ignored in app_name.lower() for ignored in self._IGNORED_OWNERS):
                continue
            if not is_ide(app_name):
                return self._normalize_app_name(app_name)

        best = None
        best_score = -1.0
        now = ts
        total = sum(recent_counts.values())
        for app_name, count in recent_counts.items():
            recency = now - last_seen.get(app_name, now)
            recency_score = 1.0 / (1.0 + recency)
            score = recency_score * 0.7 + (count / max(1, total)) * 0.3
            if is_ide(app_name) and allow_ide:
                score += 0.15 + (0.6 if code_like else 0.0)
            if score > best_score:
                best_score = score
                best = app_name

        return best

    def _on_clipboard_change(self):
        try:
            now = time.time()
            if now < self._ignore_until:
                return
        except RuntimeError:
            if os.environ.get('CLIP_DEBUG') == '2':
                print('[clip-debug] _on_clipboard_change called on uninitialized watcher; ignoring')
            return
        except Exception:
            return

        text = self.clipboard.text()
        if not text:
            return
        ts = now

        try:
            if os.environ.get('CLIP_DEBUG') == '2':
                print('--- clip-debug-verbose ---')
                print('timestamp:', datetime.fromtimestamp(ts).isoformat())
                print('frontmost_probe: <skipped in debug to avoid blocking>')
                print('last_sampled_app:', self._last_sampled_app)
                try:
                    owners_preview = get_top_window_owners(6)
                except Exception:
                    owners_preview = []
                try:
                    history_preview = list(self._app_history)[-6:]
                except Exception:
                    history_preview = []
                print('owners_preview:', owners_preview)
                print('history_preview:', history_preview)
                print('emitting placeholder: Unknown App')
                print('--- end ---')
        except Exception:
            pass

        pre_ms = int(os.environ.get('CP_PRE_MARGIN_MS', '500') or '500')
        post_ms = int(os.environ.get('CP_POST_MARGIN_MS', '50') or '50')
        pre_margin = float(pre_ms) / 1000.0
        post_margin = float(post_ms) / 1000.0
        likely_app = None
        try:
            candidates = []
            for seen_at, app_name in self._app_history:
                try:
                    if not app_name or not app_name.strip():
                        continue
                    if seen_at >= (ts - pre_margin) and seen_at <= (ts + post_margin):
                        candidates.append((seen_at, app_name))
                except Exception:
                    continue
            if candidates:
                def type_weight(app_name):
                    name_lower = app_name.lower()
                    # Browsers tend to be the real source for copied links and snippets, so
                    # we bias them slightly when multiple focus events land in the same window.
                    if any(name in name_lower for name in ('brave', 'chrome', 'safari', 'firefox', 'edge', 'opera')):
                        return 0.6
                    if any(name in name_lower for name in ('pycharm', 'intellij', 'vscode', 'visual studio code', 'sublime', 'atom', 'webstorm')):
                        return 0.4
                    if any(name in name_lower for name in ('discord', 'slack', 'teams', 'whatsapp')):
                        return 0.1
                    return 0.2

                best_score = None
                best_candidate = None
                for seen_at, app_name in candidates:
                    try:
                        dt = abs(seen_at - ts)
                        recency_score = 1.0 / (1.0 + dt)
                        weight = type_weight(app_name)
                        score = recency_score + weight
                        if best_score is None or score > best_score:
                            best_score = score
                            best_candidate = app_name
                    except Exception:
                        continue
                likely_app = best_candidate
        except Exception:
            pass

        self._ignore_until = ts + 0.1
        if likely_app:
            source_app = self._normalize_app_name(likely_app)
        elif self._last_sampled_app:
            source_app = self._normalize_app_name(self._last_sampled_app)
        else:
            source_app = 'Unknown App'

        if os.environ.get('CLIP_DEBUG') == '2':
            print("[clip-debug] %s final_emit app=%s" % (datetime.fromtimestamp(ts).isoformat(), source_app))

        if os.environ.get('CLIP_DEBUG') == '2':
            try:
                preview = (text or '')[:200].replace('\n', '\\n')
            except Exception:
                preview = ''
            print("[clip-debug] emitting text_preview=\"%s\" app=%s ts=%s" % (preview, source_app, datetime.fromtimestamp(ts).isoformat()))

        try:
            self.clipboard_changed.emit(text, source_app, ts)
        except Exception:
            pass

    def pause(self, ms=None):
        if ms is None:
            try:
                ms = int(getattr(self, '_default_pause_ms', settings.get('pause_after_set_ms', 500)))
            except Exception:
                return
        try:
            ms = float(ms)
        except Exception:
            return
        self._ignore_until = time.time() + (ms / 1000.0)

    def set_text(self, text: str, pause_ms: int = None):
        try:
            clipboard = getattr(self, 'clipboard', None) or QApplication.clipboard()
            clipboard.setText(str(text))
        except Exception:
            pass
        try:
            if pause_ms is None:
                try:
                    pause_ms = int(getattr(self, '_default_pause_ms', settings.get('pause_after_set_ms', 500)))
                except Exception:
                    pause_ms = 500
            self.pause(pause_ms)
            if os.environ.get('CLIP_DEBUG') == '2':
                print("[clip-debug] set_text called; paused for %d ms" % (pause_ms,))
        except Exception:
            pass

    def _on_setting_changed(self, key, value):
        try:
            if key == 'pause_after_set_ms':
                self._default_pause_ms = int(value)
        except Exception:
            pass
