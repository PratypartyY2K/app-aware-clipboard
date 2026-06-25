import os
from clipboard_manager.gui import SettingsDialog
from clipboard_manager import settings

pytest_plugins = ['pytestqt.qtbot']


def test_settings_dialog_apply(qtbot):
    tmp = os.environ.get('XDG_CONFIG_HOME')
    os.environ['XDG_CONFIG_HOME'] = os.path.join(os.getcwd(), 'tmp_test_config')
    try:
        settings.load_settings('CopyPasteTool')
        dlg = SettingsDialog()
        qtbot.addWidget(dlg)
        dlg.show()
        qtbot.waitExposed(dlg)
        dlg.pause_spin.setValue(1111)
        dlg.secret_safe_chk.setChecked(False)
        dlg._on_apply()
        s = settings.load_settings()
        assert int(s['pause_after_set_ms']) == 1111
        ss = s.get('secret_safe_mode')
        assert ss in (False, 'False', 0, '0') or bool(ss) is False
    finally:
        if tmp is not None:
            os.environ['XDG_CONFIG_HOME'] = tmp
        else:
            try:
                del os.environ['XDG_CONFIG_HOME']
            except KeyError:
                pass
