import sqlite3
import os
from typing import Dict, Any, List

SCHEMA = '''
CREATE TABLE IF NOT EXISTS items (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    source_app TEXT,
    timestamp TEXT,
    is_temporary INTEGER DEFAULT 0,
    expire_at REAL NULL,
    pinned INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS metadata (
    k TEXT PRIMARY KEY,
    v TEXT
);
'''

class Persistence:
    def __init__(self, db_path: str):
        self.db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(self.db_path) or '.', exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._apply_pragmas()
        self._ensure_schema()

    def _apply_pragmas(self):
        cur = self.conn.cursor()
        try:
            cur.execute('PRAGMA journal_mode=WAL;')
        except Exception:
            pass
        try:
            cur.execute('PRAGMA synchronous=NORMAL;')
        except Exception:
            pass
        try:
            cur.execute('PRAGMA foreign_keys=ON;')
        except Exception:
            pass
        try:
            cur.execute('PRAGMA temp_store=MEMORY;')
        except Exception:
            pass
        self.conn.commit()

    def _ensure_schema(self):
        cur = self.conn.cursor()
        cur.executescript(SCHEMA)
        self.conn.commit()

    def load_items(self) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute('SELECT * FROM items ORDER BY pinned DESC, timestamp DESC')
        rows = cur.fetchall()
        items = []
        for r in rows:
            items.append({
                'id': r['id'],
                'content': r['content'],
                'source_app': r['source_app'],
                'timestamp': r['timestamp'],
                'board': None,
                'is_temporary': bool(r['is_temporary']),
                'expire_at': r['expire_at'],
                'pinned': bool(r['pinned']),
            })
        return items

    def save_item(self, item) -> None:
        cur = self.conn.cursor()
        cur.execute('''
            INSERT OR REPLACE INTO items (id, content, source_app, timestamp, is_temporary, expire_at, pinned)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            item.id,
            item.content,
            item.source_app,
            item.timestamp.isoformat() if hasattr(item.timestamp, 'isoformat') else str(item.timestamp),
            1 if item.is_temporary else 0,
            item.expire_at,
            1 if item.pinned else 0,
        ))
        self.conn.commit()

    def delete_item(self, item_id: str) -> None:
        cur = self.conn.cursor()
        cur.execute('DELETE FROM items WHERE id=?', (item_id,))
        self.conn.commit()

    def update_item(self, item) -> None:
        self.save_item(item)

    def load_settings(self) -> Dict[str, str]:
        cur = self.conn.cursor()
        cur.execute('SELECT key, value FROM settings')
        return {r['key']: r['value'] for r in cur.fetchall()}

    def save_setting(self, key: str, value: str) -> None:
        cur = self.conn.cursor()
        cur.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))
        self.conn.commit()

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass
