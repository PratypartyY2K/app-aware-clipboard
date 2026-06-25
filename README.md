# Copy Paste Tool

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![CI](https://github.com/PratypartyY2K/copy-paste-tool/actions/workflows/ci.yml/badge.svg)](https://github.com/PratypartyY2K/copy-paste-tool/actions)
[![Codecov](https://codecov.io/gh/PratypartyY2K/copy-paste-tool/branch/main/graph/badge.svg)](https://codecov.io/gh/PratypartyY2K/copy-paste-tool)

Your clipboard keeps one value. Copy again and the previous value is gone.

This app keeps a history of copied text, but the hard part is not storing strings in a list. The hard part is deciding when a clipboard change is real, which app caused it, and when not to store it at all.

**Copy Paste Tool** is a macOS clipboard manager built with PyQt6. It tracks copied text by source app, avoids re-capturing its own writes, and defaults to not keeping obvious secrets longer than needed.

## Why This Exists

I wanted clipboard history, but most clipboard apps gloss over the parts that actually go wrong on desktop systems:

- The app itself writes to the clipboard and can easily create loops.
- Frontmost-app attribution on macOS depends on timing and permissions.
- Password managers and token-like values should not be treated like normal notes.
- Desktop apps are easy to demo manually and easy to leave untested.
- Extra features stop being useful when they make capture less predictable.

This repo is the result of treating clipboard history like a state-management problem instead of just a UI problem.

## What Makes It Different

- **Event-driven capture**: listens to Qt clipboard events instead of polling. That keeps idle CPU use down and avoids a whole class of timing bugs.
- **Per-app history**: every saved clip is tagged with the app that most likely produced it.
- **Secret-safe defaults**: clips from password-manager/authenticator apps are skipped, and JWT-like or long token-like values are marked temporary.
- **Loop protection**: when the app writes back to the clipboard, capture pauses for a short window so the write does not come back in as a new item.
- **Stable UI actions**: list rows store item IDs, so pin/copy actions still hit the right record if history changes while the menu is open.
- **Tight module boundaries**: watcher, history, persistence, and UI are separate enough to test without dragging the whole app through every case.
- **Less feature churn**: Boards was removed when it kept misclassifying clips and complicated persistence.

## Project Snapshot

- **Platform**: macOS-first
- **Language**: Python 3.11
- **GUI**: PyQt6
- **Persistence**: SQLite with WAL mode
- **Testing**: pytest, pytest-qt, GitHub Actions, Codecov

## Demo

Screenshots and a short GIF still need to be added. Right now the code tells the story better than the visuals.

## Features

### Core workflow

- Save copied text into per-app history.
- Filter the list by source app.
- Search within the selected app history.
- Copy any saved item back to the clipboard.

### Privacy and safety

- **Secret-safe mode** skips capture from common password-manager and authenticator apps.
- **Token heuristics** treat JWTs and long token-like strings as temporary and remove them after a timeout.
- **Persistence is opt-in**. By default the app stays in memory unless you point it at a SQLite file.
- **Per-app capture control** lets you turn capture off for one app without touching the global blocklist.

### Productivity

- Pin frequently used items to the top of an app’s history.
- Context menu actions:
  - Trim whitespace
  - Copy as one line
  - Extract URLs
  - JSON-escape text
  - Convert to `camelCase`
  - Convert to `snake_case`

## Architecture

The code is split by failure boundary, not by framework convention.

- `clipboard_manager/watcher.py`
  Watches clipboard changes, samples recent foreground apps, and emits capture events.
- `clipboard_manager/history.py`
  Owns dedupe, secret filtering, temporary-item cleanup, pins, and in-memory state.
- `clipboard_manager/storage.py`
  Handles optional SQLite persistence and settings reads/writes.
- `clipboard_manager/gui.py`
  Renders the main window, filters items, and wires context-menu actions.
- `clipboard_manager/clipboard_item.py`
  Defines the clipboard item model and stable item IDs.

## Why This Is Hard

These are the parts that mattered during implementation and debugging:

- **Clipboard feedback loops**: copying from the app back into the system clipboard will re-trigger capture unless the watcher ignores that write for a bounded window.
- **Source attribution**: macOS does not hand you a clean “this app copied this text” event. The app samples foreground state and uses short lookback windows because attribution gets worse if you wait too long.
- **Secret handling**: keeping everything forever is the easiest implementation and the wrong default. Secret-safe mode adds false positives, but the tradeoff is deliberate.
- **Cleanup and persistence**: temporary items expire in the background while the UI and SQLite state are still live.
- **GUI testing**: clipboard flows are stateful and timing-sensitive, so the repo includes automated tests instead of relying only on local manual checks.

## Design Decisions

### Boards were removed on purpose

An older version tried to auto-route clips into Boards such as Links, Code, Commands, Notes, and Other.

That feature is deprecated because it was wrong too often. Misclassification made the UI noisier, complicated persistence, and added logic that was hard to trust. I would rather have a smaller feature set with predictable behavior.

The old implementation is still in `archive/boards_reference.py` if I want to revisit rules-based routing later, but it is not part of the active app path.

## Quick Start

### Prerequisites

- macOS
- Python 3.11
- Virtualenv recommended

### Install

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install PyQt6
```

If you want the better attribution path that uses PyObjC:

```bash
python -m pip install pyobjc-framework-ApplicationServices
```

### Run

```bash
python clipboard_manager/main.py
```

If you already have a local venv:

```bash
.venv/bin/python clipboard_manager/main.py
```

### Current install status

This is still a developer install. There is no polished standalone macOS build here yet.

## Usage

### Main controls

- **Pause (ms)**: how long capture stays paused after the app writes to the clipboard.
- **App dropdown**: picks which app history you are looking at.
- **Search box**: filters the current app history.
- **Secret-safe mode**: turns secret filtering on or off.
- **Edit Blocklist**: edits the app substring blocklist used by secret-safe mode.
- **Per-app capture toggle**: turns capture on or off for the selected app.
- **Context menu**: copy, transform, pin, and unpin items.

### Hotkey

The default shortcut is an **in-app** hotkey, `Ctrl+\``, which opens the window and focuses search. It is not a global hotkey.

## Privacy and Security

### Defaults

- Secret-safe mode starts enabled.
- Persistence starts disabled.
- Common password-manager, authenticator, and keychain-like apps are in the default blocklist.

### Accessibility note

Accurate frontmost-app attribution may require Accessibility permission on macOS. If you keep seeing `Unknown App` or `Python`, grant permission to the Python interpreter or packaged app under:

`System Settings -> Privacy & Security -> Accessibility`

Then restart the app. If attribution is still off, run with debug logging and adjust the timing knobs.

### Threat-model caveat

Secret-safe mode is heuristic-based. It helps with the common cases, but it is not encrypted storage and it will miss some things. If the machine or database is in your threat model, leave persistence off or add encryption yourself.

## Persistence

Persistence is optional and uses SQLite.

To enable it:

```bash
export CLIP_PERSISTENCE_DB=./.local/persistence.db
python clipboard_manager/main.py
```

Notes:

- The database file is created if it does not exist.
- SQLite runs in WAL mode because the app updates history while the UI is live.
- Settings such as Secret-safe mode and the blocklist are stored there.
- Clips are saved on capture and on pin/unpin updates.
- Temporary secret-like clips are deleted after their timeout.

## Configuration

Most tunables live in `clipboard_manager/history.py` and in watcher env vars.

### History tunables

- `MAX_RECENT_HASHES`: size of the recent-hash LRU used for dedupe
- `APP_DEDUPE_SECONDS`: suppresses repeated copies of the same content from the same app for a short window
- `TEMPORARY_TOKEN_SECONDS`: lifetime for token-like clips

### Debugging and attribution env vars

- `CLIP_DEBUG=1`: concise debug logs
- `CLIP_DEBUG=2`: verbose sampling logs
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

If you are upgrading from an older build that still stored a `board` column, use the migration helper.

Dry run:

```bash
PYTHONPATH=. python scripts/drop_board_column.py --db ./.local/persistence.db
```

Apply:

```bash
PYTHONPATH=. python scripts/drop_board_column.py --db ./.local/persistence.db --apply
```

The script writes a backup before it changes the database.

## Testing and CI

The repo has automated coverage for the logic that tends to break:

- GitHub Actions runs the test suite.
- Coverage is enforced in CI.
- Codecov publishes coverage reports.
- Tests cover dedupe, secret-safe behavior, persistence, pins, settings, and GUI interactions.

### Run tests locally

```bash
python3 -m pip install -r requirements-ci.txt
pytest -q -m "not gui" --cov=clipboard_manager --cov-report=term-missing
```

### Run GUI tests

On macOS, run them directly. On headless Linux, use Xvfb.

```bash
xvfb-run -s "-screen 0 1920x1080x24" pytest -q
```

## Troubleshooting

### `ModuleNotFoundError: No module named 'PyQt6'`

Install PyQt6 into the same interpreter you are using to run the app.

### Source app shows as `Unknown App`

This usually means attribution permissions are missing or the automation probe is getting blocked. Check Accessibility settings first.

### Items disappear unexpectedly

If Secret-safe mode is on, token-like content may be treated as temporary and deleted after its timeout.

## Building a macOS App

Local packaging helpers are included for experiments, but this repo does not publish official signed builds.

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

Treat that as a developer packaging path, not an end-user install flow.
