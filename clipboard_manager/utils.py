import time
import subprocess
import importlib
import os
import sys
from typing import List, Optional
from datetime import datetime, timezone

_has_pyobjc = False
_AppKit = None
_Quartz = None


def _try_load_pyobjc():
    global _has_pyobjc, _AppKit, _Quartz
    if _has_pyobjc:
        return True
    try:
        _AppKit = importlib.import_module('AppKit')
        _Quartz = importlib.import_module('Quartz')
        _has_pyobjc = True
        return True
    except Exception:
        _has_pyobjc = False
        _AppKit = None
        _Quartz = None
        return False


def is_pyobjc_available() -> bool:
    return _try_load_pyobjc()


def is_ax_trusted(prompt: bool = False) -> bool:
    if not _try_load_pyobjc():
        return False
    try:
        import ApplicationServices as AS
        return bool(AS.AXIsProcessTrustedWithOptions(
            {"AXTrustedCheckOptionPrompt": bool(prompt)}
        ))
    except Exception:
        AXIsProcessTrusted = getattr(_Quartz, "AXIsProcessTrusted", None)
        return bool(AXIsProcessTrusted()) if AXIsProcessTrusted else False


def _get_app_from_ax() -> Optional[str]:
    try:
        if not _has_pyobjc:
            return None
        AXIsProcessTrusted = getattr(_Quartz, 'AXIsProcessTrusted', None)
        if not AXIsProcessTrusted or not AXIsProcessTrusted():
            return None
        AXUIElementCreateSystemWide = getattr(_Quartz, 'AXUIElementCreateSystemWide', None)
        AXUIElementCopyAttributeValue = getattr(_Quartz, 'AXUIElementCopyAttributeValue', None)
        kAXFocusedApplicationAttribute = getattr(_Quartz, 'kAXFocusedApplicationAttribute', None)
        AXUIElementGetPid = getattr(_Quartz, 'AXUIElementGetPid', None)
        if not (AXUIElementCreateSystemWide and AXUIElementCopyAttributeValue and kAXFocusedApplicationAttribute and AXUIElementGetPid):
            return None
        sys_wide = AXUIElementCreateSystemWide()
        try:
            focused_ref = AXUIElementCopyAttributeValue(sys_wide, kAXFocusedApplicationAttribute)
        except TypeError:
            focused_ref = AXUIElementCopyAttributeValue(sys_wide, kAXFocusedApplicationAttribute, None)
        if focused_ref is None:
            return None
        try:
            pid = AXUIElementGetPid(focused_ref)
        except Exception:
            return None
        if not pid:
            return None
        try:
            ra = getattr(_AppKit.NSRunningApplication, 'runningApplicationWithProcessIdentifier_')(pid)
            if ra is None:
                return None
            name = getattr(ra, 'localizedName')()
            return str(name) if name else None
        except Exception:
            return None
    except Exception:
        return None


def _get_app_from_appkit() -> Optional[str]:
    try:
        if not _has_pyobjc:
            return None
        ws = getattr(_AppKit, 'NSWorkspace').sharedWorkspace()
        active = getattr(ws, 'frontmostApplication')()
        if active is None:
            return None
        name = getattr(active, 'localizedName')()
        return str(name) if name else None
    except Exception:
        return None


def _get_app_from_mouse_window() -> Optional[str]:
    try:
        if not _has_pyobjc:
            return None
        CGEventGetLocation = getattr(_Quartz, 'CGEventGetLocation', None)
        CGWindowListCopyWindowInfo = getattr(_Quartz, 'CGWindowListCopyWindowInfo', None)
        kCGWindowListOptionOnScreenOnly = getattr(_Quartz, 'kCGWindowListOptionOnScreenOnly', None)
        kCGNullWindowID = getattr(_Quartz, 'kCGNullWindowID', None)
        if not (CGEventGetLocation and CGWindowListCopyWindowInfo and kCGWindowListOptionOnScreenOnly is not None and kCGNullWindowID is not None):
            return None
        pt = CGEventGetLocation(None)
        mx = float(getattr(pt, 'x', 0))
        my = float(getattr(pt, 'y', 0))
        wins = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
        for w in wins:
            try:
                bounds = w.get('kCGWindowBounds') or {}
                x = float(bounds.get('X', bounds.get('x', 0)))
                y = float(bounds.get('Y', bounds.get('y', 0)))
                w_w = float(bounds.get('Width', bounds.get('width', 0)))
                w_h = float(bounds.get('Height', bounds.get('height', 0)))
                if mx >= x and mx <= x + w_w and my >= y and my <= y + w_h:
                    owner = w.get('kCGWindowOwnerName') or None
                    if owner:
                        return str(owner)
            except Exception:
                continue
        return None
    except Exception:
        return None


def find_window_owner_by_content(snippet: str) -> Optional[str]:
    """Best-effort lookup for a visible window title containing the snippet."""
    try:
        if not snippet:
            return None
        if not _has_pyobjc:
            return None
        txt = snippet.strip()
        if not txt:
            return None
        CGWindowListCopyWindowInfo = getattr(_Quartz, 'CGWindowListCopyWindowInfo', None)
        kCGWindowListOptionOnScreenOnly = getattr(_Quartz, 'kCGWindowListOptionOnScreenOnly', None)
        kCGNullWindowID = getattr(_Quartz, 'kCGNullWindowID', None)
        if not (CGWindowListCopyWindowInfo and kCGWindowListOptionOnScreenOnly is not None and kCGNullWindowID is not None):
            return None
        wins = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
        for w in wins:
            try:
                title = (w.get('kCGWindowName') or '')
                owner = (w.get('kCGWindowOwnerName') or '')
                if not title:
                    title = owner
                if not title:
                    continue
                if txt.lower() in str(title).lower():
                    return owner or None
            except Exception:
                continue
        return None
    except Exception:
        return None


def get_frontmost_app(content_snippet: Optional[str] = None) -> str:
    cl_debug = int(os.environ.get('CLIP_DEBUG', '0') or '0')


    try:
        probe_works = False
        hard_exceptions = 0
        attempts = int(os.environ.get('EARLY_PROBE_ATTEMPTS', '3'))
        for _ in range(attempts):
            try:
                _ = subprocess.run(
                    ['osascript', '-e', 'tell application "System Events" to get name of first application process whose frontmost is true'],
                    capture_output=True, text=True, timeout=0.12
                )
                probe_works = True
                break
            except subprocess.TimeoutExpired:
                continue
            except Exception:
                hard_exceptions += 1
                continue
        if not probe_works and hard_exceptions >= attempts:
            if cl_debug >= 1:
                print("[clip-debug] %s method='early-osascript-check' failed (hard exceptions); returning 'Unknown App'" % (datetime.now(timezone.utc).isoformat(),))
            return 'Unknown App'
    except Exception:
        pass

    def usable(name: Optional[str]):
        if not name:
            return False
        try:
            nl = name.lower()
        except Exception:
            nl = str(name).lower()
        if 'python' in nl or nl.strip() == '':
            return False
        return True

    if _try_load_pyobjc():
        appkit_samples = []
        appkit_attempts = int(os.environ.get('APPKIT_SAMPLES', '5'))
        appkit_delay = float(os.environ.get('APPKIT_DELAY', '0.02'))
        for _ in range(appkit_attempts):
            try:
                a = _get_app_from_appkit()
            except Exception:
                a = None
            appkit_samples.append(a)
            time.sleep(appkit_delay)
        freq = {}
        for v in appkit_samples:
            if usable(v):
                freq[v] = freq.get(v, 0) + 1
        if freq:
            sorted_items = sorted(freq.items(), key=lambda x: (-x[1], x[0]))
            candidate, count = sorted_items[0]
            if count >= int(os.environ.get('APPKIT_MIN_COUNT', '2')):
                if cl_debug >= 1:
                    print("[clip-debug] %s method='appkit-sampled' result='%s' count=%d preview='%s'" % (datetime.now(timezone.utc).isoformat(), candidate, count, (content_snippet or '')[:120]))
                return candidate
    try:
        if _try_load_pyobjc() and is_ax_trusted():
            ax_samples = []
            ax_attempts = int(os.environ.get('AX_SAMPLES', '5'))
            ax_delay = float(os.environ.get('AX_DELAY', '0.02'))
            for _ in range(ax_attempts):
                try:
                    a = _get_app_from_ax()
                except Exception:
                    a = None
                ax_samples.append(a)
                time.sleep(ax_delay)
            freq = {}
            for v in ax_samples:
                if usable(v):
                    freq[v] = freq.get(v, 0) + 1
            if freq:
                sorted_items = sorted(freq.items(), key=lambda x: (-x[1], x[0]))
                candidate, count = sorted_items[0]
                if count >= int(os.environ.get('AX_MIN_COUNT', '2')):
                    if cl_debug >= 1:
                        print("[clip-debug] %s method='ax-sampled' result='%s' count=%d preview='%s'" % (datetime.now(timezone.utc).isoformat(), candidate, count, (content_snippet or '')[:120]))
                    return candidate
    except Exception:
        pass

    interpreter_names = {os.path.basename(sys.executable).lower(), os.path.splitext(os.path.basename(sys.argv[0]))[0].lower(), 'python', 'python3'}
    samples = []
    raw_samples = []
    max_attempts = int(os.environ.get('OSASCRIPT_SAMPLES', '25'))
    consecutive_needed = int(os.environ.get('OSASCRIPT_CONSECUTE', '4'))
    sample_delay = float(os.environ.get('OSASCRIPT_DELAY', '0.02'))
    last_val = None
    consecutive = 0
    for _ in range(max_attempts):
        try:
            res = subprocess.run(
                ['osascript', '-e', 'tell application "System Events" to get name of first application process whose frontmost is true'],
                capture_output=True, text=True, timeout=0.6
            )
            val = (res.stdout or '').strip() or None
        except Exception:
            val = None
        raw_samples.append(val)
        norm = val.lower().strip() if val else None
        if norm and norm in interpreter_names:
            norm = None
        samples.append(norm)
        if norm and last_val and norm == last_val:
            consecutive += 1
        elif norm:
            consecutive = 1
            last_val = norm
        else:
            consecutive = 0
            last_val = None
        if consecutive >= consecutive_needed and usable(last_val):
            final = last_val
            break
        time.sleep(sample_delay)
    else:
        freq = {}
        for s in samples:
            if not s:
                continue
            if usable(s):
                freq[s] = freq.get(s, 0) + 1
        if freq:
            sorted_items = sorted(freq.items(), key=lambda x: (-x[1], x[0]))
            choice, count = sorted_items[0]
            if count >= int(os.environ.get('OSASCRIPT_MIN_COUNT', '3')):
                final = choice
            else:
                final = None
        else:
            final = None

    resolved = final or 'Unknown App'

    if cl_debug >= 2:
        dbg = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'appkit_samples': appkit_samples if 'appkit_samples' in locals() else None,
            'ax_samples': ax_samples if 'ax_samples' in locals() else None,
            'raw_osascript_samples': raw_samples,
            'normalized_samples': samples,
            'final_resolved': resolved,
            'preview': (content_snippet or '')[:200]
        }
        print('\n--- clip-debug-verbose ---')
        for k, v in dbg.items():
            print("%s: %s" % (k, v))
        print('--- end ---')
    elif cl_debug >= 1:
        print("[clip-debug] %s method='osascript' osascript='%s' resolved='%s' preview='%s'" % (datetime.now(timezone.utc).isoformat(), (raw_samples[0] if raw_samples else None), resolved, (content_snippet or '')[:120]))

    return resolved


def get_top_window_owners(n: int = 10) -> List[str]:
    """Return visible window owners from front to back, up to ``n`` entries."""
    out = []
    try:
        if not _has_pyobjc:
            return out
        CGWindowListCopyWindowInfo = getattr(_Quartz, 'CGWindowListCopyWindowInfo', None)
        kCGWindowListOptionOnScreenOnly = getattr(_Quartz, 'kCGWindowListOptionOnScreenOnly', None)
        kCGNullWindowID = getattr(_Quartz, 'kCGNullWindowID', None)
        if not (CGWindowListCopyWindowInfo and kCGWindowListOptionOnScreenOnly is not None and kCGNullWindowID is not None):
            return out
        wins = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
        for w in wins[:n]:
            try:
                owner = w.get('kCGWindowOwnerName') or ''
                if owner:
                    out.append(str(owner))
            except Exception:
                continue
    except Exception:
        pass
    return out


def probe_frontmost_methods(content_snippet: Optional[str] = None) -> dict:
    """Collect raw attribution probe outputs for debugging."""
    result = {}
    try:
        res = subprocess.run(
            ['osascript', '-e', 'tell application "System Events" to get name of first application process whose frontmost is true'],
            capture_output=True, text=True, timeout=0.6
        )
        single = (res.stdout or '').strip() or None
    except Exception:
        single = None
    result['osascript_single'] = single

    samples = []
    for _ in range(7):
        try:
            r = subprocess.run(
                ['osascript', '-e', 'tell application "System Events" to get name of first application process whose frontmost is true'],
                capture_output=True, text=True, timeout=0.6
            )
            val = (r.stdout or '').strip() or None
        except Exception:
            val = None
        samples.append(val)
        time.sleep(0.02)
    result['osascript_samples'] = samples

    try:
        appkit_name = _get_app_from_appkit()
    except Exception:
        appkit_name = None
    result['appkit'] = appkit_name

    try:
        ax_name = _get_app_from_ax()
    except Exception:
        ax_name = None
    result['ax'] = ax_name

    try:
        mouse_owner = _get_app_from_mouse_window()
    except Exception:
        mouse_owner = None
    result['mouse_window_owner'] = mouse_owner

    try:
        by_content = find_window_owner_by_content((content_snippet or '')[:200])
    except Exception:
        by_content = None
    result['by_content'] = by_content

    return result


def trim_whitespace(s: str) -> str:
    return s.strip()


def copy_one_line(s: str) -> str:
    import re
    return re.sub(r"\s+", " ", s).strip()


def extract_urls(text: str):
    import re
    if not text:
        return []
    pattern = re.compile(r"(https?://[^\s,;]+|www\.[^\s,;]+)")
    matches = pattern.findall(text)
    seen = set()
    out = []
    for m in matches:
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


def extract_urls_text(text: str) -> str:
    urls = extract_urls(text)
    return urls[0] if urls else ''


def json_escape(text: str) -> str:
    import json
    return json.dumps(text)


def to_camel_case(text: str) -> str:
    import re
    parts = [p for p in re.split(r'[^0-9a-zA-Z]+', text) if p]
    if not parts:
        return ''
    first = parts[0].lower()
    rest = ''.join(p.capitalize() for p in parts[1:])
    return first + rest


def to_snake_case(text: str) -> str:
    import re
    parts = [p for p in re.split(r'[^0-9a-zA-Z]+', text) if p]
    return '_'.join(p.lower() for p in parts)


def fuzzy_score(text: str, query: str) -> int:
    import difflib
    if not query:
        return 100
    s = str(text)
    q = str(query)
    if q.lower() in s.lower():
        return 100
    ratio = difflib.SequenceMatcher(a=s.lower(), b=q.lower()).ratio()
    return int(ratio * 100)


def highlight_match(text: str, query: str) -> str:
    import html
    if not query:
        return html.escape(text)
    s = text
    q = query
    low = s.lower()
    qlow = q.lower()
    idx = low.find(qlow)
    if idx == -1:
        return html.escape(text)
    before = html.escape(s[:idx])
    match = html.escape(s[idx:idx+len(q)])
    after = html.escape(s[idx+len(q):])
    return before + '<b>' + match + '</b>' + after


def timeline_probes(duration_sec: float = 3.0, interval_sec: float = 0.05) -> List[dict]:
    """Sample attribution probes over time and return timestamped snapshots."""
    out = []
    end = time.time() + float(duration_sec)
    while time.time() < end:
        ts = datetime.now(timezone.utc).isoformat()
        try:
            osa = None
            try:
                r = subprocess.run(
                    ['osascript', '-e', 'tell application "System Events" to get name of first application process whose frontmost is true'],
                    capture_output=True, text=True, timeout=0.5
                )
                osa = (r.stdout or '').strip() or None
            except Exception:
                osa = None
            try:
                ak = _get_app_from_appkit()
            except Exception:
                ak = None
            try:
                ax = _get_app_from_ax()
            except Exception:
                ax = None
            try:
                mw = _get_app_from_mouse_window()
            except Exception:
                mw = None
        except Exception:
            ak = ax = osa = mw = None
        out.append({'ts': ts, 'osascript': osa, 'appkit': ak, 'ax': ax, 'mouse_window_owner': mw})
        time.sleep(interval_sec)
    return out
