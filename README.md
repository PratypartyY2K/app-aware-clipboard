# App-Aware Clipboard Manager

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE) [![CI](https://github.com/PratypartyY2K/copy-paste-tool/actions/workflows/ci.yml/badge.svg)](https://github.com/PratypartyY2K/copy-paste-tool/actions) [![Codecov](https://codecov.io/gh/PratypartyY2K/copy-paste-tool/branch/main/graph/badge.svg)](https://codecov.io/gh/PratypartyY2K/copy-paste-tool)

A lightweight, macOS-focused clipboard manager built with PyQt6. It captures text copies, attributes them to the source application, and presents an app-aware UI with developer-friendly utilities.

This README covers: installation, key features (Secret-safe mode, Pins, Search, Clip Actions), usage, configuration, developer notes, and troubleshooting.

---

## Table of Contents
- [Project Overview](#project-overview)
- [Features](#features)
- [Quick Start (macOS)](#quick-start-macos)
- [UI Walkthrough](#ui-walkthrough)
- [Data migration](#data-migration-if-you-upgraded-from-an-older-version)
- [Security & Privacy](#security--privacy)
- [Configuration and Settings](#configuration-and-settings)
- [Developer Notes & Architecture](#developer-notes--architecture)
- [CI and Testing](#ci-and-testing)
- [Troubleshooting](#troubleshooting)
- [Building a macOS app and DMG](#building-a-macos-app-and-dmg)

---

## Project Overview

This tool watches the macOS clipboard and records copied text together with metadata: source application and capture timestamp. The design separates capture, storage/deduplication, and UI so functionality can be extended safely and tested.

### Design Goals
- **Correctness**: avoid re-capturing programmatic copies and attribute the frontmost application at capture time.
- **Efficiency**: use Qt clipboard signals (no polling) for accuracy and low CPU usage.
- **Security-aware**: provide a Secret-safe mode that avoids storing sensitive content from password/auth apps and token-like clipboard contents.
- **Productivity features**: search, pins, and developer-friendly clip actions.


## Features

### Boards (deprecated and archived)
- NOTE: the earlier "Boards" auto-routing feature (Links, Code, Commands, Notes, Other) is deprecated and no longer used by the running application or by default persistence. The DB column that previously contained board values can be removed with the migration helper (see "Data migration" below).

The legacy routing implementation is preserved for reference in `archive/boards_reference.py` if you wish to inspect or re-enable it. Keeping an archived copy lets you re-introduce a rules-based router safely in the future without relying on the deprecated on-disk `board` column.

> Why removed: boards were causing persistent misclassification and added complexity. The core manager still supports app attribution, pins, search, and clip actions.

### Secret-safe mode (trust)
- Blocklisted apps (password managers, authenticators, Keychain entries) are not stored when Secret-safe mode is enabled.
- Token/JWT heuristics: if clipboard content looks like a token (JWT or long base64-like string) it will be stored only temporarily and auto-removed after a configurable timeout.
- The Secret-safe toggle and blocklist editor are available in the UI.

### Pins
- Pin frequently used items; pinned items stay at the top of the list for the source app.
- Pin/Unpin is available from the context menu.

### Search
- A search box filters the visible history for the currently selected app.
- The window can be shown & search focused via an in-app hotkey (default: Ctrl+`). Note: this is an in-app hotkey, not a global system hotkey.

### Clip Actions (developer-friendly)
- Right-click an item to run transformations before copying to clipboard:
  - Trim whitespace
  - Copy as one-line
  - Extract URLs
  - JSON-escape (produce a JSON quoted/escaped string)
  - Convert to camelCase / snake_case

### Stable IDs & safe context menu actions
- The UI stores a stable `ClipboardItem.id` in each list row (UserRole) so context menu actions operate on the intended record even if the history updates while the menu is open.


## Quick Start (macOS)

### Prerequisites
- Python 3.11 (the codebase was developed and tested with Python 3.11 on macOS; newer 3.x versions should work but use caution)
- A Python virtual environment is recommended
- PyQt6 installed in the environment

### Create and activate a venv, then install PyQt6:

```bash
# from project root
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install PyQt6
```

### Run the GUI app:

```bash
# from project root, with venv active
python clipboard_manager/main.py
```

If you have an existing `.venv` in the repo, run the app using its Python binary:

```bash
.venv/bin/python clipboard_manager/main.py
```


## UI Walkthrough

### Main controls
- **Pause (ms)**: when the app programmatically copies text back to the clipboard, the watcher pauses capture for this duration (default 300 ms in the UI) to avoid re-capturing the same content.
- **App dropdown**: filter history by the source application. When no app is selected, the list is empty.
- **Search box**: filters the visible items for the selected app. It searches item content and (where available) legacy board metadata.
- **Secret-safe mode (checkbox)**: enable/disable the secret-safe heuristics.
- **Edit Blocklist**: opens a small editor where you can add/remove app name substrings to block from capture.
- **Per-app capture toggle**: enable or disable capture for the currently-selected app (useful to stop capturing from a specific app without blocking it globally).
- **Context menu (right-click on an item)**: copy, clip actions (trim, one-line, extract URLs, JSON-escape, camel/snake), Pin/Unpin.

### Hotkey
- An in-app hotkey (Ctrl+`) shows the window and focuses the search box; this is NOT a system-wide/global hotkey.


## Data migration (if you upgraded from an older version)
If your existing local persistence DB was created by a prior release that stored `board` values, you may want to remove that column to match the current schema.

A helper migration script is provided: `scripts/drop_board_column.py`.

Dry-run (recommended):

```bash
PYTHONPATH=. python scripts/drop_board_column.py --db ./.local/persistence.db
```

Apply the migration (the script automatically creates a backup at `./.local/persistence.db.bak`):

```bash
PYTHONPATH=. python scripts/drop_board_column.py --db ./.local/persistence.db --apply
```

After applying, you can inspect the DB with sqlite3:

```bash
sqlite3 ./.local/persistence.db "PRAGMA table_info(items);"
sqlite3 ./.local/persistence.db "SELECT COUNT(*) FROM items;"
```


## Security & Privacy

### Defaults
- Secret-safe mode is ON by default.
- Persistence is OFF by default (history, pins, and settings are stored in memory only unless you enable persistence explicitly by setting `CLIP_PERSISTENCE_DB`).
- Common sensitive apps are pre-populated into the blocklist (password managers, authenticators, keychain-like apps).

### Per-app controls
- The UI exposes a "Per-app capture" toggle which lets you enable or disable capturing for the currently-selected app without altering the global blocklist.

### Accessibility permission (macOS)
- For accurate frontmost-application attribution on macOS the app requires Accessibility privileges. If attribution shows as `Unknown App` or returns `Python` frequently, grant accessibility to either the Python interpreter used to run the app or to the packaged app binary: System Settings → Privacy & Security → Accessibility. After granting permission, restart the application and re-run with `CLIP_DEBUG=2` to verify attribution samples.

### Security notes
- Token/JWT heuristics attempt to detect likely secrets and keep them temporary when Secret-safe mode is enabled; heuristics are conservative and may not catch all secrets. If you need stronger guarantees, avoid enabling persistence or implement secure encrypted storage.
- If you enable persistence, consider encrypting persisted data or storing only metadata (timestamps, app names) depending on your threat model.


## Configuration and Settings

### Configuration constants in `clipboard_manager/history.py`:
- `MAX_RECENT_HASHES` — LRU size for dedupe (default 200)
- `APP_DEDUPE_SECONDS` — per-app dedupe window (default 30 seconds)
- `TEMPORARY_TOKEN_SECONDS` — how long token-like clips are kept before auto-deletion (default 30 seconds)

### Secret-safe blocklist
- Edit blocklist from the UI (Edit Blocklist) or programmatically via `History.set_blocklist(...)`.

### Persistence (optional)

You can enable on-disk persistence using a small SQLite database. Persistence stores clipboard items and a few settings (secret-safe toggle, blocklist) so your history survives restarts.

To enable persistence, set the `CLIP_PERSISTENCE_DB` environment variable to a path where the app can write a SQLite file. Example (macOS / Linux):

```bash
# from project root, enable persistence to a local ./.local/persistence.db file
export CLIP_PERSISTENCE_DB=./.local/persistence.db
python clipboard_manager/main.py
```

**Notes:**
- The persistence implementation is intentionally minimal and uses SQLite with WAL mode for reliability.
- Settings saved: `secret_safe_enabled` and `blocklist_apps`.
- Items are saved on capture and updates (pin/unpin) and temporary token items are auto-deleted after their configured lifetime.
- To disable persistence, unset `CLIP_PERSISTENCE_DB` or run the app normally.

### Persistence: quick test & monitor

You can run a tiny smoke test that writes an item through the normal `History` + `Persistence` flow and then prints the DB rows. A test script is included at `scripts/test_persistence_run.py`:

```bash
PYTHONPATH=. python3 scripts/test_persistence_run.py
```

To actively monitor the DB for new rows (handy while reproducing copy flows), you can run a small monitor script (see `scripts/monitor_db.py`). It polls the DB and prints newly-observed items. Example:

```bash
PYTHONPATH=. python3 scripts/monitor_db.py
```

### Tunable environment variables

The watcher and attribution logic expose several environment-backed tunables useful for debugging and adapting to different machines. These are safe to set in your shell before launching the app.

- `CP_PRE_MARGIN_MS` — pre-copy margin (ms) to consider recent focus history when attributing a clipboard event (default 500)
- `CP_POST_MARGIN_MS` — post-copy margin (ms) to include short delays after the clipboard event (default 50)
- `CP_LOOKBACK_SECONDS` — how many seconds of app-activation history to consult for attribution (default ~2.5)
- `CP_FREQ_LOOKBACK_SECONDS` — wider lookback for frequency-based heuristics (default ~5.0)
- `APPKIT_SAMPLES`, `APPKIT_DELAY`, `APPKIT_MIN_COUNT` — sampling knobs when using AppKit/pyobjc
- `AX_SAMPLES`, `AX_DELAY`, `AX_MIN_COUNT` — sampling knobs for Accessibility probe
- `OSASCRIPT_SAMPLES`, `OSASCRIPT_DELAY`, `OSASCRIPT_MIN_COUNT`, `OSASCRIPT_CONSECUTE` — osascript sampling settings

### Debug helpers

- `CLIP_DEBUG=1` prints concise attribution logs.
- `CLIP_DEBUG=2` prints verbose sampling/debug dumps (useful when tuning attribution and dedupe).

Example: run with more permissive post margin and verbose debug:

```bash
export CP_POST_MARGIN_MS=100
export CLIP_DEBUG=2
PYTHONPATH=. python3 -m clipboard_manager.main
```


## Developer Notes & Architecture

### Key modules
- `clipboard_manager/watcher.py` — `ClipboardWatcher` emits `clipboard_changed(content, source_app, timestamp)` and exposes `pause(ms)`, `resume()`, and `set_text(text, pause_ms)`.
- `clipboard_manager/history.py` — `HistoryStore` handles dedupe, blocklist, token heuristics, temporary-marking and pin management. Exported alias: `History`.
- `clipboard_manager/boards.py` — retained for reference only; board routing is no longer used for new persisted data.
- `clipboard_manager/gui.py` — `MainWindow` renders the UI and uses stable item IDs for list rows.
- `clipboard_manager/clipboard_item.py` — `ClipboardItem` model: id, content, source_app, timestamp, is_temporary, expire_at, pinned.

### Testing strategy
- Unit tests cover utilities and critical behavior (dedupe, secret-safe heuristics, pin/unpin ordering).
- A smoke test exercises `ClipboardWatcher` + `History` pause behavior without requiring a visible UI (`tests/smoke_pause_test.py`).

### Running tests (no pytest required)

The repo contains small test scripts that can be executed directly. Example:

```bash
python tests/test_utils.py
python tests/test_secret_safe.py
python tests/test_pins.py
python tests/smoke_pause_test.py
python tests/gui_startup.py  # non-blocking GUI startup check
```


## CI and Testing

This repository includes a GitHub Actions workflow that runs the test suite and enforces a minimum coverage threshold.

- **Workflow file**: `.github/workflows/ci.yml`
- **Coverage requirement**: the CI enforces a minimum coverage (default set to 70%). The workflow runs tests in a headless environment using `xvfb` so GUI tests (pytest-qt) run reliably.
- **Coverage reports** are uploaded to Codecov. See the Codecov badge at the top of this README for the latest project coverage.

### Run tests locally with coverage (recommended):

```bash
# install test deps from repo
python3 -m pip install -r requirements-ci.txt
# run pytest with coverage
pytest -q -m "not gui" --cov=clipboard_manager --cov-report=term-missing
```

If you want to run GUI tests locally in an environment without a display, use Xvfb (Linux) or run on macOS directly:

```bash
# on Linux with Xvfb
sudo apt-get install xvfb
xvfb-run -s "-screen 0 1920x1080x24" pytest -q
```

If the CI badge link in the README is incorrect, replace the `your-org/your-repo` path with the actual GitHub owner and repository name to enable the badge.


## Troubleshooting

**Q: `ModuleNotFoundError: No module named 'PyQt6'` when running tests or app**
- Ensure PyQt6 is installed into the Python interpreter you use (activate your venv and run `python -m pip install PyQt6`).

**Q: `Unknown App` is shown as the source app**
- The project uses an AppleScript call (`osascript`) to ask macOS which app is frontmost. If your environment restricts automation, this may fail and fallback to `Unknown App`.

**Q: Items disappear (temporary tokens)**
- Token/JWT-like content is removed automatically by design when Secret-safe mode is enabled (default 30 seconds). Disable Secret-safe mode to keep all clips.


## Building a macOS app and DMG

I included helper scripts and a PyInstaller spec so I (or another developer) can experiment locally; however, I am not publishing official signed builds from this repository right now. If I decide to publish a signed/notarized macOS build later, I'll document the release steps here.

If you are a developer and want to experiment locally (for testing only), the helper scripts remain in the `scripts/` folder:

```bash
# OPTIONAL local experiment (macOS only) — packaging is for developer experimentation
# create and activate a venv, install deps
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

# OPTIONAL: create an icns from the icon.iconset (macOS only)
# ./scripts/make_icns.sh

# build the app and dmg locally (not recommended for end-user distribution)
# ./scripts/build_dmg.sh
```

Notes:
- The scripts are intended for local experimentation by developers only. Do not check generated build artifacts (for example `.dmg` files) into the repository.
- If I later publish official, signed, and notarized releases, I will add those artifacts and explicit release notes.

Last updated: 2026-02-07
