import time
from clipboard_manager.storage import Persistence
from clipboard_manager.history import History


def test_persistence_save_and_load(tmp_path):
    db = tmp_path / 'persistence.db'
    p = Persistence(str(db))
    h = History(persistence=p)
    now = time.time()
    it = h.add_item('persist test ' + str(now), source_app='Tester', timestamp=now)
    assert it is not None
    p2 = Persistence(str(db))
    items = p2.load_items()
    assert any(r['id'] == it.id for r in items)
    p.close()
    p2.close()

