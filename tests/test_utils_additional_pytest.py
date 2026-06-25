import types
import subprocess
from clipboard_manager import utils


def test_probe_frontmost_methods_monkeypatched(monkeypatch):
    class FakeCompleted:
        def __init__(self, out='OSA'):
            self.stdout = out
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: FakeCompleted('OSA'))

    monkeypatch.setattr(utils, '_get_app_from_appkit', lambda: 'AK')
    monkeypatch.setattr(utils, '_get_app_from_ax', lambda: 'AX')
    monkeypatch.setattr(utils, '_get_app_from_mouse_window', lambda: 'MW')
    monkeypatch.setattr(utils, 'find_window_owner_by_content', lambda s: 'OwnerX')

    out = utils.probe_frontmost_methods('snippet')
    assert isinstance(out, dict)
    assert out['osascript_single'] in (None, 'OSA')
    assert isinstance(out['osascript_samples'], list)
    assert out['appkit'] == 'AK'
    assert out['ax'] == 'AX'
    assert out['mouse_window_owner'] == 'MW'
    assert out['by_content'] == 'OwnerX'


def test_get_top_window_owners_monkeypatched(monkeypatch):
    dummy_quartz = types.SimpleNamespace()
    def fake_CGWindowListCopyWindowInfo(opt, nullid):
        return [
            {'kCGWindowOwnerName': 'AppOne'},
            {'kCGWindowOwnerName': 'AppTwo'},
            {'kCGWindowOwnerName': ''},
        ]
    dummy_quartz.CGWindowListCopyWindowInfo = fake_CGWindowListCopyWindowInfo
    dummy_quartz.kCGWindowListOptionOnScreenOnly = 1
    dummy_quartz.kCGNullWindowID = 0
    monkeypatch.setattr(utils, '_has_pyobjc', True)
    monkeypatch.setattr(utils, '_Quartz', dummy_quartz)
    out = utils.get_top_window_owners(n=5)
    assert isinstance(out, list)
    assert 'AppOne' in out and 'AppTwo' in out


def test_find_window_owner_by_content_with_pyobjc(monkeypatch):
    dummy_quartz = types.SimpleNamespace()
    def fake_CGWindowListCopyWindowInfo(opt, nullid):
        return [
            {'kCGWindowName': 'Title one', 'kCGWindowOwnerName': 'Owner1'},
            {'kCGWindowName': 'Some Snippet Here', 'kCGWindowOwnerName': 'Owner2'},
        ]
    dummy_quartz.CGWindowListCopyWindowInfo = fake_CGWindowListCopyWindowInfo
    dummy_quartz.kCGWindowListOptionOnScreenOnly = 1
    dummy_quartz.kCGNullWindowID = 0
    monkeypatch.setattr(utils, '_has_pyobjc', True)
    monkeypatch.setattr(utils, '_Quartz', dummy_quartz)
    res = utils.find_window_owner_by_content('Snippet')
    assert res == 'Owner2'


def test_probe_frontmost_methods_handles_errors(monkeypatch):
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('fail')))
    monkeypatch.setattr(utils, '_get_app_from_appkit', lambda: None)
    monkeypatch.setattr(utils, '_get_app_from_ax', lambda: None)
    monkeypatch.setattr(utils, '_get_app_from_mouse_window', lambda: None)
    out = utils.probe_frontmost_methods(None)
    assert isinstance(out, dict)
    assert out['osascript_single'] is None
    assert isinstance(out['osascript_samples'], list)
    assert out['appkit'] is None and out['ax'] is None and out['mouse_window_owner'] is None


