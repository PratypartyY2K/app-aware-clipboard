import os
from clipboard_manager import settings

def test_load_defaults_and_save(tmp_path):
    app_name = 'TestApp'
    cfg_dir = tmp_path / app_name
    cfg_dir.mkdir()
    orig_home = os.environ.get('XDG_CONFIG_HOME')
    os.environ['XDG_CONFIG_HOME'] = str(tmp_path)
    try:
        path = settings.get_config_path(app_name)
        if path.exists():
            path.unlink()
        s = settings.load_settings(app_name)
        assert isinstance(s, dict)
        assert s['pause_after_set_ms'] == settings.DEFAULTS['pause_after_set_ms']
        settings.set_('pause_after_set_ms', 1234)
        settings.save_settings(app_name)
        loaded = settings.load_settings(app_name)
        assert loaded['pause_after_set_ms'] == 1234
    finally:
        if orig_home is not None:
            os.environ['XDG_CONFIG_HOME'] = orig_home
        else:
            del os.environ['XDG_CONFIG_HOME']


def test_corrupt_file_backup(tmp_path):
    app_name = 'TestApp2'
    os.environ['XDG_CONFIG_HOME'] = str(tmp_path)
    try:
        path = settings.get_config_path(app_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('w', encoding='utf-8') as f:
            f.write('{ not json')
        s = settings.load_settings(app_name)
        broken = path.with_suffix('.broken.json')
        assert broken.exists() or not path.exists()
        assert s['pause_after_set_ms'] == settings.DEFAULTS['pause_after_set_ms']
    finally:
        pass
