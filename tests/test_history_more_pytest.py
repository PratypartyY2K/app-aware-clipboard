import time
from clipboard_manager.history import HistoryStore, MAX_RECENT_HASHES, APP_DEDUPE_SECONDS


def test_pin_unpin_ordering():
    hs = HistoryStore()
    hs.add_item('first', source_app='App')
    b = hs.add_item('second', source_app='App')
    hs.add_item('third', source_app='App')
    assert [it.content for it in hs.items][:3] == ['third', 'second', 'first']
    assert hs.pin_item(b.id)
    assert hs.items[0].id == b.id
    assert hs.unpin_item(b.id)
    assert hs.items[0].content == 'third'


def test_app_capture_toggle():
    hs = HistoryStore()
    hs.set_app_capture_enabled('NoCaptureApp', False)
    it = hs.add_item('hello', source_app='NoCaptureApp')
    assert it is None
    hs.set_app_capture_enabled('NoCaptureApp', True)
    it2 = hs.add_item('hello', source_app='NoCaptureApp')
    assert it2 is not None


def test_recent_hashes_lru_trim():
    hs = HistoryStore()
    for i in range(MAX_RECENT_HASHES + 5):
        hs.add_item(f'unique-{i}', source_app='App')
    assert len(hs._recent_hashes) <= MAX_RECENT_HASHES


def test_per_app_dedupe_window():
    hs = HistoryStore()
    content = 'dup-test'
    it1 = hs.add_item(content, source_app='AppX')
    assert it1 is not None
    it2 = hs.add_item(content, source_app='AppX')
    assert it2 is not None
    time.sleep(APP_DEDUPE_SECONDS + 0.5)
    it3 = hs.add_item(content, source_app='AppX')
    assert it3 is not None
