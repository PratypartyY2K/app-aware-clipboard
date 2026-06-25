#!/usr/bin/env python3
"""
Strip Python comments from .py files in the repository (in-place).
- Preserves shebangs (first-line starting with
- Preserves docstrings and '#' characters inside string literals.
- Removes full-line comments and trailing comments outside of strings.

Use with caution; this modifies files in-place. Run tests after running.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def strip_comments_from_line(line):
    if not line.strip():
        return line
    if line.startswith('#!'):
        return line
    i = 0
    n = len(line)
    out = []
    single = False
    double = False
    triple_single = False
    triple_double = False
    while i < n:
        ch = line[i]
        if ch == '\\':
            if i+1 < n:
                out.append(ch)
                out.append(line[i+1])
                i += 2
                continue
            else:
                out.append(ch)
                i += 1
                continue
        if not single and not double:
            if line.startswith('"""', i):
                triple_double = not triple_double
                out.append('"""')
                i += 3
                continue
            if line.startswith("'''", i):
                triple_single = not triple_single
                out.append("'''")
                i += 3
                continue
        if not triple_single and not triple_double:
            if ch == '"' and not single:
                double = not double
                out.append(ch)
                i += 1
                continue
            if ch == "'" and not double:
                single = not single
                out.append(ch)
                i += 1
                continue
        if ch == '#' and not (single or double or triple_single or triple_double):
            break
        out.append(ch)
        i += 1
    res = ''.join(out)
    if res.rstrip() =="":
        return '\n'
    return res.rstrip() + ("\n" if line.endswith('\n') else '')

def process_file(path: Path):
    data = path.read_text(encoding='utf8')
    new_lines = []
    for idx, line in enumerate(data.splitlines(True)):
        stripped = line.lstrip()
        if stripped.startswith('#') and not line.startswith('#!'):
            continue
        new_line = strip_comments_from_line(line)
        new_lines.append(new_line)
    new_data = ''.join(new_lines)
    if new_data != data:
        path.write_text(new_data, encoding='utf8')
        print('Updated', path)

def main():
    patterns = [
        'clipboard_manager/**/*.py',
        'scripts/**/*.py',
        'tests/**/*.py',
        '*.py'
    ]
    pyfiles = []
    for pat in patterns:
        pyfiles.extend(list(ROOT.glob(pat)))
    pyfiles = [p for p in pyfiles if '__pycache__' not in p.parts and '.venv' not in p.parts and 'site-packages' not in str(p)]
    for p in pyfiles:
        process_file(p)

if __name__ == '__main__':
    main()
