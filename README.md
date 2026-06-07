# pdfreader

A fast, minimal, keyboard-driven PDF reader. Single-page view, instant scaling,
remembers where you left off. Built with PySide6 + pypdfium2.

## Run (development)

```bash
uv sync                              # create the 3.12 venv, install deps
uv run python -m pdfreader           # restores last file, or shows Open prompt
uv run python -m pdfreader file.pdf  # open a specific file
```

## Keyboard shortcuts

| Action            | Vim-like        | Conventional        |
| ----------------- | --------------- | ------------------- |
| Open file         | `O`             | `Ctrl+O`            |
| Go to page        | `G`             | `Ctrl+G`            |
| Next page         | `J`, `Space`    | `PgDown`            |
| Previous page     | `K`, `⇧Space`   | `PgUp`              |
| First page        | `Home`          | `Ctrl+Home`         |
| Last page         | `End`           | `Ctrl+End`          |
| Zoom in           | `+` / `=`       | `Ctrl++`            |
| Zoom out          | `-`             | `Ctrl+-`            |
| Fit to width      | `W`             | View menu           |
| Fit to height     | `H`             | View menu           |
| Custom scale (%)  | `F`             | View menu           |
| Help              | `?`             | `F1`                |
| Quit              | `Q`             | `Ctrl+Q`            |

Arrow keys pan the page when it is zoomed larger than the window.

## Session memory

Page and scale are remembered **per file** in `state.json` in your platform
config dir (`~/.config/pdfreader` on Linux). Reopening any file — whether by
launching with no argument (which reopens the most recent file) or opening it
explicitly — restores that file's own last page and scale. Up to 500 files are
remembered (least-recently-opened dropped first).

## Build a standalone executable

PyInstaller is not a cross-compiler — build on each target OS:

```bash
uv run pyinstaller build/pdfreader.spec
./dist/pdfreader            # runs with no Python/uv installed
```

## Tests

```bash
uv run pytest
```
