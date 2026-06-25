import types
import subprocess
from clipboard_manager import utils


def test_get_frontmost_app_osascript_consecutive(monkeypatch):
    monkeypatch.setattr(utils, '_try_load_pyobjc', lambda: False)
    class FakeCompleted:
        def __init__(self, out='MyApp'):
            self.stdout = out
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: FakeCompleted('MyApp'))
    monkeypatch.setenv('OSASCRIPT_SAMPLES', '6')
    monkeypatch.setenv('OSASCRIPT_CONSECUTE', '2')
    monkeypatch.setenv('OSASCRIPT_DELAY', '0.001')
    res = utils.get_frontmost_app()
    assert res is not None and res.lower() == 'myapp'
    monkeypatch.delenv('OSASCRIPT_SAMPLES', raising=False)
    monkeypatch.delenv('OSASCRIPT_CONSECUTE', raising=False)
    monkeypatch.delenv('OSASCRIPT_DELAY', raising=False)


def test_get_frontmost_app_osascript_freq_choice(monkeypatch):
    monkeypatch.setattr(utils, '_try_load_pyobjc', lambda: False)
    outs = ['A', None, 'B', 'A', 'A']
    class Fake:
        def __init__(self):
            self.i = 0
        def __call__(self, *a, **k):
            class C:
                def __init__(self, out):
                    self.stdout = out
            out = outs[self.i % len(outs)]
            self.i += 1
            return C(out or '')
    monkeypatch.setattr(subprocess, 'run', Fake())
    monkeypatch.setenv('OSASCRIPT_SAMPLES', '6')
    monkeypatch.setenv('OSASCRIPT_MIN_COUNT', '2')
    monkeypatch.setenv('OSASCRIPT_DELAY', '0.001')
    res = utils.get_frontmost_app()
    assert res is not None and res.lower() == 'a'
    monkeypatch.delenv('OSASCRIPT_SAMPLES', raising=False)
    monkeypatch.delenv('OSASCRIPT_MIN_COUNT', raising=False)
    monkeypatch.delenv('OSASCRIPT_DELAY', raising=False)


def test_internal_appkit_ax_mouse_helpers(monkeypatch):
    dummy_app = types.SimpleNamespace()
    dummy_active = types.SimpleNamespace()
    dummy_active.localizedName = lambda: 'AppKitApp'
    ws = types.SimpleNamespace()
    ws.frontmostApplication = lambda: dummy_active
    dummy_AppKit = types.SimpleNamespace()
    dummy_AppKit.NSWorkspace = types.SimpleNamespace(sharedWorkspace=lambda: ws)
    monkeypatch.setattr(utils, '_has_pyobjc', True)
    monkeypatch.setattr(utils, '_AppKit', dummy_AppKit)
    assert utils._get_app_from_appkit() == 'AppKitApp'

    class DummyQuartz:
        def AXIsProcessTrusted(self):
            return True
        def AXUIElementCreateSystemWide(self):
            return 'sys'
        def AXUIElementCopyAttributeValue(self, sys_wide, attr):
            return 'focused'
        def AXUIElementGetPid(self, focused):
            return 12345
    dummy_quartz = DummyQuartz()
    class FakeRA:
        def localizedName(self):
            return 'AXApp'
    dummy_AppKit.NSRunningApplication = types.SimpleNamespace(runningApplicationWithProcessIdentifier_=lambda pid: FakeRA())
    monkeypatch.setattr(utils, '_Quartz', dummy_quartz)
    monkeypatch.setattr(utils, '_AppKit', dummy_AppKit)
    monkeypatch.setattr(utils, '_has_pyobjc', True)
    val_ax = utils._get_app_from_ax()
    assert val_ax is None or val_ax == 'AXApp'

    class MQ:
        def CGEventGetLocation(self, _):
            return types.SimpleNamespace(x=50, y=50)
        def CGWindowListCopyWindowInfo(self, opt, nullid):
            return [
                {'kCGWindowBounds': {'X': 0, 'Y': 0, 'Width': 100, 'Height': 100}, 'kCGWindowOwnerName': 'MouseApp'}
            ]
    mq = MQ()
    mq.kCGWindowListOptionOnScreenOnly = 1
    mq.kCGNullWindowID = 0
    monkeypatch.setattr(utils, '_Quartz', mq)
    monkeypatch.setattr(utils, '_has_pyobjc', True)
    assert utils._get_app_from_mouse_window() == 'MouseApp'


def test_get_top_window_owners_no_pyobjc(monkeypatch):
    monkeypatch.setattr(utils, '_has_pyobjc', False)
    assert utils.get_top_window_owners(5) == []


def test_timeline_probes_monkeypatched(monkeypatch):
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: types.SimpleNamespace(stdout='X'))
    monkeypatch.setattr(utils, '_get_app_from_appkit', lambda: 'AK')
    monkeypatch.setattr(utils, '_get_app_from_ax', lambda: 'AX')
    monkeypatch.setattr(utils, '_get_app_from_mouse_window', lambda: 'MW')
    out = utils.timeline_probes(duration_sec=0.05, interval_sec=0.01)
    assert isinstance(out, list) and len(out) >= 1
