import sys
import os
import pathlib

project_root = pathlib.Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from PyQt6.QtWidgets import QApplication
from clipboard_manager.gui import MainWindow
from clipboard_manager import settings

try:
    settings.load_settings()
except Exception:
    pass

NO_GUI = os.environ.get('CLIP_NO_GUI') == '1' or '--no-gui' in sys.argv

def _resolve_persistence():
    db_path = os.environ.get('CLIP_PERSISTENCE_DB')
    if not db_path:
        try:
            if settings.get('persistence_enabled'):
                db_path = settings.get('persistence_path') or os.path.expanduser('~/.local/persistence.db')
        except Exception:
            db_path = None

    if not db_path:
        return None

    try:
        from clipboard_manager.storage import Persistence
        return Persistence(db_path)
    except Exception:
        return None


def main():
    if NO_GUI:
        print('NO_GUI')
        return 0

    app = QApplication(sys.argv)
    persistence = _resolve_persistence()
    try:
        if persistence:
            from clipboard_manager.history import History
            history = History(persistence=persistence)
            window = MainWindow(history=history)
        else:
            window = MainWindow()
        window.show()
        return app.exec()
    finally:
        try:
            if persistence:
                persistence.close()
        except Exception:
            pass


if __name__ == '__main__':
    sys.exit(main())
