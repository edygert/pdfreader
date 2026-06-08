# pdfreader

A fast, minimal, keyboard-driven PDF reader. Single-page view, instant scaling,
remembers where you left off. Built with Tkinter + Pillow + pypdfium2.

Tkinter renders over X11/XWayland, which keeps it stable on ChromeOS (Crostini),
where the Sommelier Wayland proxy mishandles native dialogs and extra surfaces.
File opening uses a built-in in-window browser, not a native file dialog, for the
same reason.

## Run (development)

```bash
uv sync                              # create the 3.12 venv, install deps
uv run python -m pdfreader           # restores last file, or shows Open prompt
uv run python -m pdfreader file.pdf  # open a specific file
```

## Keyboard shortcuts

| Action            | Keys                     |
| ----------------- | ------------------------ |
| Open file         | `o`                      |
| Go to page        | `:`                      |
| Next page         | `Ctrl f`, `Ctrl →`, `Space`, `PageDown` |
| Previous page     | `Ctrl b`, `Ctrl ←`, `PageUp` |
| First page        | `gg`, `Home`             |
| Last page         | `G`, `End`               |
| Zoom page in/out  | `+` / `=` , `-`          |
| Fit to width      | `Shift W`                |
| Fit to height     | `Shift H`                |
| Custom scale (%)  | `f`                      |
| Rotate cw / ccw   | `r` / `Shift+R`          |
| Page color (white / off-white / dark) | `t`          |
| UI text size      | `Ctrl +` / `Ctrl -` / `Ctrl 0` |
| Pan the page      | `h` `j` `k` `l`, Arrow keys |
| Help              | `?` / `F1`               |
| Quit              | `q`                      |

Press `?` or `F1` in the app for the same list.

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
