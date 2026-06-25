#!/usr/bin/env python3
import os
import sys
import time
from collections import deque

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from clipboard_manager.watcher import ClipboardWatcher  # noqa: E402

out = []

w = ClipboardWatcher.__new__(ClipboardWatcher)
w._app_history = deque()
w._last_sampled_app = None
w._ignore_until = 0.0

now = time.time()
entries = [
    ('PyCharm', now-20), ('Python', now-19), ('Notes', now-17), ('Python', now-16),
    ('Notes', now-14), ('Python', now-12), ('Brave Browser', now-10), ('PyCharm', now-9),
    ('Brave Browser', now-8), ('Python', now-7), ('Discord', now-5), ('Visual Studio Code', now-4),
    ('PyCharm', now-3), ('Discord', now-2), ('Python', now-1)
]
for name, ts in entries:
    w._app_history.append((ts, name))

out.append('history_len=%d' % len(w._app_history))

picked = w._pick_recent_source_app(now, allow_ide=True, code_like=False)
out.append('picked_recent=' + repr(picked))

url = 'https://calendar.google.com/calendar/u/2/r'
code = '    def my_function():\n        pass'

out.append('score_brave_url=%d' % w.score_owner('Brave Browser', url.lower(), True, False))
out.append('score_discord_url=%d' % w.score_owner('Discord', url.lower(), True, False))

out.append('score_pycharm_code=%d' % w.score_owner('PyCharm', code.lower(), True, True))
out.append('score_vscode_code=%d' % w.score_owner('Visual Studio Code', code.lower(), True, True))

out.append('event1=' + repr(w._pick_recent_source_app(now, allow_ide=True, code_like=False)))
lang_py = 'python'
out.append('event2=' + repr(w._pick_recent_source_app(now, allow_ide=True, code_like=True, language_hint=lang_py)))
lang_js = 'javascript'
out.append('event3=' + repr(w._pick_recent_source_app(now, allow_ide=True, code_like=True, language_hint=lang_js)))

p = '/tmp/attribution_output.txt'
with open(p, 'w') as f:
    f.write('\n'.join(out))
print('wrote', p)
