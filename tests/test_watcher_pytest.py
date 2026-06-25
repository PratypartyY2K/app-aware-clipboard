from PyQt6.QtWidgets import QApplication
from clipboard_manager.watcher import ClipboardWatcher


def test_watcher_signal(monkeypatch, qtbot):
    QApplication.instance() or QApplication([])
    watcher = ClipboardWatcher()
    received = []
    def on_change(text, source_app, ts):
        received.append((text, source_app))
    watcher.clipboard_changed.connect(on_change)
    class FakeClipboard:
        def __init__(self):
            self._text = 'abc'
        def text(self):
            return self._text
        def dataChanged(self):
            return None
        def setText(self, t):
            self._text = t
    fake = FakeClipboard()
    monkeypatch.setattr(watcher, 'clipboard', fake)
    monkeypatch.setattr('clipboard_manager.utils.get_frontmost_app', lambda: 'TestApp')
    watcher._on_clipboard_change()
    assert received and received[0][0] == 'abc'


def test_set_text_pause(monkeypatch):
    watcher = ClipboardWatcher()
    class FakeClipboard:
        def __init__(self):
            self._text = ''
        def text(self):
            return self._text
        def setText(self, t):
            self._text = t
    fake = FakeClipboard()
    monkeypatch.setattr(watcher, 'clipboard', fake)
    watcher.set_text('new', pause_ms=200)
    assert fake.text() == 'new'
    watcher._ignore = True
    fake.setText('other')
    watcher._on_clipboard_change()
    watcher._ignore = False
