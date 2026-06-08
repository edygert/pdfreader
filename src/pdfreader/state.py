"""Persist and restore reading position — page and scale — per file."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Scale modes persisted in state and used by the viewer.
FIT_WIDTH = "fit_width"
FIT_HEIGHT = "fit_height"
CUSTOM = "custom"

# Cap how many files we remember so state.json can't grow without bound.
# Least-recently-opened entries are dropped first.
_MAX_FILES = 500


@dataclass
class FileState:
    """The remembered reading position for a single PDF."""

    page: int = 0
    scale_mode: str = FIT_WIDTH
    custom_factor: float = 1.0
    ui_scale: float = 1.0  # chrome/text size for this file (page scale is separate)
    rotation: int = 0  # degrees clockwise: 0 / 90 / 180 / 270


@dataclass
class State:
    last_file: str | None = None
    page_theme: str = "white"  # global: white / off-white / dark
    files: dict[str, FileState] = field(default_factory=dict)

    def for_file(self, path: str) -> FileState:
        """Return the record for ``path``, creating a default one if new.

        Re-inserts the key so dict order reflects most-recently-opened last,
        which is what the size cap trims against.
        """
        record = self.files.pop(path, None) or FileState()
        self.files[path] = record
        return record


def _config_dir() -> Path:
    """Platform-appropriate per-user config directory for the app."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:  # Linux / Crostian / other Unix
        base = os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")
    return Path(base) / "pdfreader"


def _state_path() -> Path:
    return _config_dir() / "state.json"


def load() -> State:
    path = _state_path()
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError, json.JSONDecodeError):
        return State()

    files: dict[str, FileState] = {}
    for fpath, rec in (data.get("files") or {}).items():
        try:
            files[fpath] = FileState(
                page=int(rec.get("page", 0)),
                scale_mode=rec.get("scale_mode", FIT_WIDTH),
                custom_factor=float(rec.get("custom_factor", 1.0)),
                ui_scale=float(rec.get("ui_scale", 1.0)),
                rotation=int(rec.get("rotation", 0)),
            )
        except (ValueError, AttributeError):
            continue
    return State(
        last_file=data.get("last_file"),
        page_theme=data.get("page_theme", "white"),
        files=files,
    )


def save(state: State) -> None:
    path = _state_path()
    # Trim to the most-recently-opened entries (dict preserves insertion order).
    if len(state.files) > _MAX_FILES:
        for stale in list(state.files)[: len(state.files) - _MAX_FILES]:
            del state.files[stale]
    payload = {
        "last_file": state.last_file,
        "page_theme": state.page_theme,
        "files": {p: asdict(r) for p, r in state.files.items()},
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2))
    except OSError:
        # Persistence is best-effort; never crash the app over it.
        pass
