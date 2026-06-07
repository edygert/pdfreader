"""Application entry point: build the Tk root, parse args, restore last session."""

from __future__ import annotations

import argparse
import sys
import tkinter as tk
from pathlib import Path

from . import fonts
from . import state as state_mod
from .viewer import Viewer


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pdfreader", description="A fast, minimal PDF reader."
    )
    parser.add_argument("file", nargs="?", help="PDF file to open")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    state = state_mod.load()
    root = tk.Tk()
    # Create the scalable named fonts before any widget references them; the
    # per-file text scale is applied later when a file opens.
    fonts.init_fonts(root)
    fonts.apply_scale(1.0)
    viewer = Viewer(root, state)

    # Render once the window has a real size; open_path/_render needs it.
    def _startup() -> None:
        if args.file:
            viewer.open_path(args.file)
        elif state.last_file and Path(state.last_file).is_file():
            # Auto-restore the previous file at its saved page and scale.
            viewer.open_path(state.last_file)

    root.after(50, _startup)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
