# Copy Paste Tool

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![CI](https://github.com/PratypartyY2K/copy-paste-tool/actions/workflows/ci.yml/badge.svg)](https://github.com/PratypartyY2K/copy-paste-tool/actions)
[![Codecov](https://codecov.io/gh/PratypartyY2K/copy-paste-tool/branch/main/graph/badge.svg)](https://codecov.io/gh/PratypartyY2K/copy-paste-tool)

Your clipboard remembers one thing.
Copy something else, and the last thing is gone.

Clipboard managers fix that, but many treat the problem like a UI exercise. This project treats it like a systems problem: capture reliably, attribute clips to the right app, avoid duplicate feedback loops, and handle sensitive content conservatively.

**Copy Paste Tool** is a privacy-first, app-aware clipboard manager for macOS built with PyQt6. It is designed around correctness, low-overhead event handling, and real-world failure modes rather than feature bloat.

## Why This Exists

This project started from a simple product need, but the interesting part is not "store copied text in a list." The hard part is making clipboard history behave predictably on an actual desktop:

- Clipboard updates can be triggered by the app itself, causing feedback loops.
- App attribution on macOS is imperfect and permission-sensitive.
- Sensitive content should not be treated like normal text.
- GUI-heavy apps are easy to demo badly and harder to test well.
- Extra features become noise if they reduce correctness.

The result is a small desktop app with a stronger engineering focus than most clipboard projects.

## What Makes It Different

- **Event-driven clipboard capture**: uses Qt clipboard signals for clipboard changes instead of polling, which keeps CPU usage low and behavior responsive.
- **App-aware history**: each clip is attributed to the frontmost source app at capture time using macOS-focused attribution heuristics.
- **Privacy-first defaults**: Secret-safe mode is enabled by default, with app blocklists and token/JWT heuristics for sensitive content.
- **Correctness protections**: watcher pause logic prevents programmatic copy actions from being re-captured as new history entries.
- **Deterministic UI actions**: list rows carry stable item IDs so context-menu actions target the intended record even if history updates mid-interaction.
- **Testable architecture**: capture, history, persistence, and UI are separated into distinct modules with CI and coverage reporting.
- **Scope discipline**: the earlier Boards feature was intentionally deprecated because it added ambiguity and misclassification without enough reliability.

## Project Snapshot

- **Platform**: macOS-first
- **Language**: Python 3.11
- **GUI**: PyQt6
- **Persistence**: SQLite with WAL mode
- **Testing**: pytest, pytest-qt, coverage, GitHub Actions, Codecov

## Demo

Screenshots and a short GIF are the next README upgrade. The current repo is stronger technically than it is visually documented, so this section is intentionally called out as missing rather than ignored.

## Features

### Core workflow

- Capture copied text into per-app history.
- Filter history by source application.
- Search within the currently selected app history.
- Re-copy any saved item from the UI.

### Privacy and safety

- **Secret-safe mode** blocks capture from common password-manager and authenticator apps.
- **Token heuristics** detect JWTs and long token-like strings, then mark them temporary and auto-remove them after a configurable timeout.
- **Persistence is opt-in**. By default, the app runs in memory unless you explicitly configure a SQLite database path.
- **Per-app capture control** lets you disable capture for a selected app without changing the global blocklist.

### Productivity

- Pin frequently used items so they stay at the top of their app history.
- Use clip actions from the context menu:
  - Trim whitespace
  - Copy as one line
  - Extract URLs
  - JSON-escape text
  - Convert to `camelCase`
  - Convert to `snake_case`

## Architecture

The codebase is intentionally split so the risky parts stay isolated and testable.

- `clipboard_manager/watcher.py`
  Clipboard event handling, pause/resume logic, source-app attribution, and capture signaling.
- `clipboard_manager/history.py`
  Dedupe, blocklist enforcement, temporary secret cleanup, pinning, and in-memory item management.
- `clipboard_manager/storage.py`
  Optional SQLite persistence and settings storage.
- `clipboard_manager/gui.py`
  Main window, filtering, search, and context-menu actions.
- `clipboard_manager/clipboard_item.py`
  Item model with stable IDs and metadata.

## Why This Is Hard

This is the section I would talk through in an interview, because these are the parts that make the project more than CRUD with a GUI.

- **Clipboard feedback loops**: copying from the app back into the system clipboard can accidentally create duplicate captures unless the watcher is paused carefully.
- **Source attribution**: identifying the real originating app on macOS depends on permissions, timing, and heuristics. The repo includes tunable attribution windows for debugging and calibration.
- **Secret handling**: once you decide privacy matters, "store everything forever" stops being acceptable. Secret-safe mode changes both app filtering and token retention behavior.
- **Concurrency and persistence**: history updates, cleanup of temporary items, and SQLite persistence need to coexist without corrupting state or making the UI unpredictable.
- **GUI testing in CI**: desktop apps are easy to leave untested. This repo includes automated tests and headless CI coverage instead of relying only on manual verification.

## Design Decisions

### Boards were removed on purpose

An earlier version included automatic Boards such as Links, Code, Commands, Notes, and Other. That feature is now deprecated and archived.

It was removed because it introduced unreliable classification and ambiguity in real-world usage. Keeping it would have made the app look more feature-rich while making behavior less trustworthy. Removing it was a deliberate choice to prioritize correctness over feature bloat.

The archived reference implementation remains in `archive/boards_reference.py` for future experimentation, but it is not part of the active runtime path.

## Quick Start

### Prerequisites

- macOS
- Python 3.11
- A virtual environment is recommended

### Install

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install PyQt6
```

If you want the stronger macOS attribution path backed by PyObjC, install the macOS extras used by the project as well:

```bash
python -m pip install pyobjc-framework-ApplicationServices
```

### Run

```bash
python clipboard_manager/main.py
```

If you already have a repo-local environment:

```bash
.venv/bin/python clipboard_manager/main.py
```

### Current install status

This is currently a **developer-focused install**. Packaged standalone macOS distribution is still in progress, and this README does not pretend otherwise.

## Usage

### Main controls

- **Pause (ms)**: sets how long capture is paused after the app writes back to the clipboard.
- **App dropdown**: selects the source application whose history you want to inspect.
- **Search box**: filters the current app's history.
- **Secret-safe mode**: enables or disables privacy heuristics.
- **Edit Blocklist**: changes the app substring blocklist used by Secret-safe mode.
- **Per-app capture toggle**: disables or enables capture for the selected app.
- **Context menu**: copy, transform, pin, and unpin items.

### Hotkey

The default shortcut is an **in-app** hotkey, `Ctrl+\``, which shows the window and focuses search. It is not a global system hotkey.

## Privacy and Security

### Defaults

- Secret-safe mode is enabled by default.
- Persistence is disabled by default.
- Common password-manager, authenticator, and keychain-like apps are pre-populated in the blocklist.

### Accessibility note

For more accurate frontmost-app attribution on macOS, the app may require Accessibility permission. If attribution frequently falls back to `Unknown App` or `Python`, grant Accessibility access to the Python interpreter or packaged app in:

`System Settings -> Privacy & Security -> Accessibility`

Then restart the app and, if needed, run with verbose debug logging.

### Threat-model caveat

Secret-safe mode improves behavior, but it is still heuristic-based. It does not replace encrypted storage or a stronger secret-management model. If your threat model is strict, leave persistence disabled or add encryption around persisted data.

## Persistence

Persistence is optional and uses SQLite.

To enable it:

```bash
export CLIP_PERSISTENCE_DB=./.local/persistence.db
python clipboard_manager/main.py
```

Notes:

- The database is created automatically if needed.
- SQLite runs with WAL mode enabled for better reliability.
- Settings such as Secret-safe state and blocklist are saved.
- Clipboard items are saved on capture and update.
- Temporary secret-like items are removed after their configured lifetime.

## Configuration

The main tunables live in `clipboard_manager/history.py` and environment variables used by the watcher.

### History tunables

- `MAX_RECENT_HASHES`: LRU size for dedupe tracking
- `APP_DEDUPE_SECONDS`: suppresses repeat copies of the same content per app within a short window
- `TEMPORARY_TOKEN_SECONDS`: lifetime for token-like clipboard entries

### Debugging and attribution env vars

- `CLIP_DEBUG=1`: concise debug logs
- `CLIP_DEBUG=2`: verbose attribution and sampling logs
- `CP_PRE_MARGIN_MS`
- `CP_POST_MARGIN_MS`
- `CP_LOOKBACK_SECONDS`
- `CP_FREQ_LOOKBACK_SECONDS`
- `APPKIT_SAMPLES`, `APPKIT_DELAY`, `APPKIT_MIN_COUNT`
- `AX_SAMPLES`, `AX_DELAY`, `AX_MIN_COUNT`
- `OSASCRIPT_SAMPLES`, `OSASCRIPT_DELAY`, `OSASCRIPT_MIN_COUNT`, `OSASCRIPT_CONSECUTE`

Example:

```bash
export CP_POST_MARGIN_MS=100
export CLIP_DEBUG=2
PYTHONPATH=. python3 -m clipboard_manager.main
```

## Data Migration

If you are upgrading from an older version that persisted a `board` column, a helper migration is included.

Dry run:

```bash
PYTHONPATH=. python scripts/drop_board_column.py --db ./.local/persistence.db
```

Apply:

```bash
PYTHONPATH=. python scripts/drop_board_column.py --db ./.local/persistence.db --apply
```

The script creates a backup automatically before modifying the database.

## Testing and CI

This repo is not just manually demoed. It includes automated testing and CI for both core logic and GUI-related behavior.

- GitHub Actions runs the test suite.
- Coverage is enforced in CI.
- Codecov publishes coverage reports.
- The test suite covers utilities, dedupe behavior, secret-safe handling, persistence, pins, settings, and GUI interactions.

### Run tests locally

```bash
python3 -m pip install -r requirements-ci.txt
pytest -q -m "not gui" --cov=clipboard_manager --cov-report=term-missing
```

### Run GUI tests

On macOS, run them directly. On Linux/headless environments, use Xvfb.

```bash
xvfb-run -s "-screen 0 1920x1080x24" pytest -q
```

## Troubleshooting

### `ModuleNotFoundError: No module named 'PyQt6'`

Install dependencies into the same interpreter you use to run the app.

### Source app shows as `Unknown App`

This usually means attribution permissions or automation calls are restricted. Check Accessibility permissions first.

### Items disappear unexpectedly

If Secret-safe mode is enabled, token-like content may be intentionally treated as temporary and removed after its timeout.

## Building a macOS App

Local packaging helpers are included for experimentation, but this repository is not currently publishing official signed builds.

Available helpers:

- `scripts/build_dmg.sh`
- `scripts/make_icns.sh`
- `CopyPasteTool.spec`

Example local packaging flow:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller
./scripts/build_dmg.sh
```

This should be treated as a developer workflow, not an end-user distribution path.
