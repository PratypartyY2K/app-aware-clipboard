from clipboard_manager.clipboard_item import ClipboardItem
from collections import OrderedDict
import hashlib
import time
from datetime import datetime
import threading
import re
import os
from clipboard_manager import settings

MAX_RECENT_HASHES = 200
APP_DEDUPE_SECONDS = 30
TEMPORARY_TOKEN_SECONDS = 30
BLOCKLIST_DEFAULTS = {
    '1password', '1password 8', 'lastpass', 'bitwarden', 'dashlane', 'keepassxc', 'keepass', 'google authenticator', 'authy', 'keychain', 'password manager'
}

_JWT_RE = re.compile(r"^[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+$")
_LONG_BASE64_RE = re.compile(r"^[A-Za-z0-9-_]{40,}$")

class HistoryStore:
    def __init__(self, persistence=None):
        self.items = []
        self._recent_hashes = OrderedDict()
        self._last_seen_by_app = {}
        self._items_by_id = {}
        self._lock = threading.RLock()
        self._cleanup_thread = None
        self._cleanup_event = threading.Event()
        self.secret_safe_enabled = True
        self.blocklist_apps = set(BLOCKLIST_DEFAULTS)
        self._app_capture_enabled = {}
        self._change_listeners = []
        self._persistence = persistence
        if self._persistence:
            try:
                self._load_from_persistence()
            except Exception:
                pass

        try:
            settings.register_callback(self._on_setting_changed)
        except Exception:
            pass

    def _on_setting_changed(self, key, value):
        try:
            if key == 'secret_safe_mode':
                self.set_secret_safe_enabled(bool(value))
            if key == 'blocklist_apps':
                if isinstance(value, (list, tuple)):
                    entries = value
                elif isinstance(value, str):
                    entries = [s.strip() for s in value.split('\n') if s.strip()]
                else:
                    entries = []
                self.set_blocklist(entries)
        except Exception:
            pass

    def _load_from_persistence(self):
        persisted_settings = self._persistence.load_settings()
        if persisted_settings.get('secret_safe_enabled') in ('0', 'False', 'false', None):
            self.secret_safe_enabled = False
        elif persisted_settings.get('secret_safe_enabled') in ('1', 'True', 'true'):
            self.secret_safe_enabled = True
        persisted_blocklist = persisted_settings.get('blocklist_apps')
        if persisted_blocklist:
            try:
                self.blocklist_apps = set(entry.strip().lower() for entry in persisted_blocklist.split('\n') if entry.strip())
            except Exception:
                pass

        persisted_items = self._persistence.load_items()
        for row in persisted_items:
            try:
                stored_app = row.get('source_app') or 'Unknown App'
                item = ClipboardItem(row['content'], source_app=self._normalize_source_app(stored_app))
                item.id = row.get('id') or item.id
                try:
                    item.timestamp = datetime.fromisoformat(row.get('timestamp'))
                except Exception:
                    pass
                try:
                    stored_board = row.get('board')
                    item._legacy_board = stored_board if stored_board else None
                except Exception:
                    item._legacy_board = None
                item.board = None
                item.is_temporary = bool(row.get('is_temporary'))
                item.expire_at = row.get('expire_at')
                item.pinned = bool(row.get('pinned'))
                self.items.append(item)
                self._items_by_id[item.id] = item
            except Exception:
                pass

    def add_change_listener(self, listener):
        if not callable(listener):
            return
        with self._lock:
            if listener not in self._change_listeners:
                self._change_listeners.append(listener)

    def remove_change_listener(self, listener):
        with self._lock:
            try:
                self._change_listeners.remove(listener)
            except ValueError:
                pass

    def _notify_change(self):
        with self._lock:
            listeners = list(self._change_listeners)
        for listener in listeners:
            try:
                listener()
            except Exception:
                pass

    def get_blocklist(self):
        with self._lock:
            return sorted(self.blocklist_apps)

    def set_blocklist(self, entries):
        with self._lock:
            self.blocklist_apps = set(e.strip().lower() for e in entries if e and e.strip())
        if self._persistence:
            try:
                self._persistence.save_setting('blocklist_apps', '\n'.join(sorted(self.blocklist_apps)))
            except Exception:
                pass
        self._notify_change()

    def set_app_capture_enabled(self, app_name: str, enabled: bool):
        with self._lock:
            if app_name:
                self._app_capture_enabled[app_name] = bool(enabled)
        self._notify_change()

    def is_app_capture_enabled(self, app_name: str) -> bool:
        with self._lock:
            if not app_name:
                return True
            return self._app_capture_enabled.get(app_name, True)

    def set_secret_safe_enabled(self, enabled: bool):
        with self._lock:
            self.secret_safe_enabled = bool(enabled)
        if self._persistence:
            try:
                self._persistence.save_setting('secret_safe_enabled', '1' if self.secret_safe_enabled else '0')
            except Exception:
                pass
        self._notify_change()

    def get_secret_safe_enabled(self) -> bool:
        with self._lock:
            return bool(self.secret_safe_enabled)

    def _start_cleanup_thread(self):
        if self._cleanup_thread is not None and self._cleanup_thread.is_alive():
            return
        self._cleanup_event.clear()
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()

    def _cleanup_loop(self):
        while not self._cleanup_event.wait(timeout=0.5):
            now = time.time()
            removed = False
            with self._lock:
                new_items = []
                # Rebuild once so expiry cleanup does not mutate the active list while iterating.
                for item in self.items:
                    if getattr(item, 'is_temporary', False) and getattr(item, 'expire_at', None) is not None:
                        if now >= item.expire_at:
                            try:
                                del self._items_by_id[item.id]
                            except Exception:
                                pass
                            if self._persistence:
                                try:
                                    self._persistence.delete_item(item.id)
                                except Exception:
                                    pass
                            removed = True
                            continue
                    new_items.append(item)
                if removed:
                    self.items = new_items
            if removed:
                self._notify_change()

    def stop_cleanup(self):
        self._cleanup_event.set()
        if self._cleanup_thread is not None:
            self._cleanup_thread.join(timeout=1.0)

    def _looks_like_token(self, text: str) -> bool:
        if not text:
            return False
        stripped = text.strip()
        return bool(_JWT_RE.match(stripped) or _LONG_BASE64_RE.match(stripped))

    def _is_blocked_app(self, app_name: str) -> bool:
        if not app_name:
            return False
        if not bool(self.secret_safe_enabled):
            return False
        n = app_name.lower()
        for bad in self.blocklist_apps:
            if bad in n:
                return True
        return False

    def _first_unpinned_index(self):
        insert_at = 0
        while insert_at < len(self.items) and getattr(self.items[insert_at], 'pinned', False):
            insert_at += 1
        return insert_at

    def add_item(self, content, source_app="Unknown App", timestamp=None):
        if not content:
            return None

        if not self.is_app_capture_enabled(source_app):
            if int(os.environ.get('CLIP_DEBUG', '0') or '0') >= 2:
                print('[clip-debug] history.add_item: capture disabled for app=%s' % (source_app,))
            return None

        if self._is_blocked_app(source_app):
            if int(os.environ.get('CLIP_DEBUG', '0') or '0') >= 2:
                print('[clip-debug] history.add_item: blocked app=%s (secret-safe)' % (source_app,))
            return None

        source_app = self._normalize_source_app(source_app)

        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        now = time.time()

        with self._lock:
            if content_hash in self._recent_hashes:
                for existing_item in self.items:
                    if existing_item.content == content and existing_item.source_app == source_app:
                        try:
                            self._recent_hashes.move_to_end(content_hash, last=False)
                        except Exception:
                            pass
                        if int(os.environ.get('CLIP_DEBUG', '0') or '0') >= 2:
                            print('[clip-debug] history.add_item: deduped per-app app=%s' % (source_app,))
                        return existing_item
                if int(os.environ.get('CLIP_DEBUG', '0') or '0') >= 2:
                    print('[clip-debug] history.add_item: seen content global but no per-app match; will add new item (app=%s)' % (source_app,))

            last_seen = self._last_seen_by_app.get((source_app, content_hash))
            if last_seen is not None and (now - last_seen) <= APP_DEDUPE_SECONDS:
                for existing_item in self.items:
                    if existing_item.content == content and existing_item.source_app == source_app:
                        self._last_seen_by_app[(source_app, content_hash)] = now
                        if int(os.environ.get('CLIP_DEBUG', '0') or '0') >= 2:
                            print('[clip-debug] history.add_item: suppressed duplicate within APP_DEDUPE_SECONDS for app=%s' % (source_app,))
                        return existing_item
                self._last_seen_by_app[(source_app, content_hash)] = now
                if int(os.environ.get('CLIP_DEBUG', '0') or '0') >= 2:
                    print('[clip-debug] history.add_item: recent same-app copy seen (no existing item), will add new item for app=%s' % (source_app,))

            is_temp = False
            expire_at = None

            if bool(self.secret_safe_enabled) and self._looks_like_token(content):
                is_temp = True
                expire_at = now + TEMPORARY_TOKEN_SECONDS

            item = ClipboardItem(content, source_app, is_temporary=is_temp, expire_at=expire_at)

            if timestamp is not None:
                try:
                    item.timestamp = datetime.fromtimestamp(timestamp)
                except Exception:
                    pass

            insert_at = self._first_unpinned_index()
            self.items.insert(insert_at, item)
            try:
                self._items_by_id[item.id] = item
            except Exception:
                pass

            try:
                if content_hash in self._recent_hashes:
                    del self._recent_hashes[content_hash]
                self._recent_hashes[content_hash] = now
                while len(self._recent_hashes) > MAX_RECENT_HASHES:
                    self._recent_hashes.popitem(last=False)
            except Exception:
                pass

            self._last_seen_by_app[(source_app, content_hash)] = now

            if is_temp:
                self._start_cleanup_thread()

            if self._persistence:
                try:
                    self._persistence.save_item(item)
                except Exception:
                    pass

        if int(os.environ.get('CLIP_DEBUG', '0') or '0') >= 2:
            print('[clip-debug] history.add_item: added item id=%s app=%s preview="%s"' % (item.id, source_app, (content or '')[:80].replace('\n','\\n')))
        self._notify_change()
        return item

    def get_item_by_id(self, item_id):
        with self._lock:
            return self._items_by_id.get(item_id)

    def get_apps(self):
        with self._lock:
            return sorted(set(item.source_app for item in self.items))

    def get_items_by_app(self, app_name):
        with self._lock:
            return [item for item in self.items if item.source_app == app_name]

    def pin_item(self, item_id):
        with self._lock:
            item = self._items_by_id.get(item_id)
            if not item:
                return False
            item.pinned = True
            try:
                self.items = [i for i in self.items if i.id != item_id]
                insert_at = self._first_unpinned_index()
                self.items.insert(insert_at, item)
                if self._persistence:
                    try:
                        self._persistence.update_item(item)
                    except Exception:
                        pass
                self._notify_change()
                return True
            except Exception:
                return False

    def unpin_item(self, item_id):
        with self._lock:
            item = self._items_by_id.get(item_id)
            if not item:
                return False
            item.pinned = False
            try:
                self.items = [i for i in self.items if i.id != item_id]
                insert_at = self._first_unpinned_index()
                while insert_at < len(self.items) and self.items[insert_at].timestamp > item.timestamp:
                    insert_at += 1
                self.items.insert(insert_at, item)
                if self._persistence:
                    try:
                        self._persistence.update_item(item)
                    except Exception:
                        pass
                self._notify_change()
                return True
            except Exception:
                return False

    def _normalize_source_app(self, name: str) -> str:
        if not name:
            return 'Unknown App'
        return name.strip()


History = HistoryStore
