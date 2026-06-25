import os
from clipboard_manager.storage import Persistence
from clipboard_manager.history import History


def test_persistence_roundtrip(tmp_path):
    db = os.path.join(str(tmp_path), 'persistence.db')
    p = Persistence(db)

    h = History(persistence=p)
    assert h.get_apps() == []

    item = h.add_item('hello world', source_app='TestApp')
    assert item is not None
    pid = item.id
    h2 = History(persistence=p)
    found = h2.get_item_by_id(pid)
    assert found is not None
    assert found.content == 'hello world'

    h.set_secret_safe_enabled(False)
    h3 = History(persistence=p)
    assert h3.get_secret_safe_enabled() is False
