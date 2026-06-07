"""Application entry point: bootstrap Qt, parse args, restore last session."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from . import state as state_mod
from .viewer import MainWindow


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pdfreader", description="A fast, minimal PDF reader."
    )
    parser.add_argument("file", nargs="?", help="PDF file to open")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    app = QApplication(sys.argv)
    app.setOrganizationName("pdfreader")
    app.setApplicationName("pdfreader")

    state = state_mod.load()
    window = MainWindow(state)
    window.show()

    # open_path always restores the target file's own saved page and scale.
    if args.file:
        window.open_path(args.file)
    elif state.last_file and Path(state.last_file).is_file():
        window.open_path(state.last_file)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
