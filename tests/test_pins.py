import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from clipboard_manager.history import HistoryStore


def test_pin_unpin_ordering():
    hs = HistoryStore()
    hs.add_item('first', source_app='App')
    b = hs.add_item('second', source_app='App')
    hs.add_item('third', source_app='App')
    ids_before = [it.content for it in hs.items]
    assert ids_before[0] == 'third'
    hs.pin_item(b.id)
    assert hs.items[0].id == b.id
    hs.unpin_item(b.id)
    assert hs.items[0].content == 'third'

if __name__ == '__main__':
    test_pin_unpin_ordering()
    print('PINS_TEST_OK')
