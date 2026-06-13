# pdfreader

A fast, minimal, keyboard-driven PDF reader. Single-page view, instant scaling,
vim-style navigation, per-file memory. Comes in two forms that share the same
keymap and behaviour:

- **Web app (PWA)** — `web/`. Plain JavaScript + [PDF.js], zero build step.
  Installable and offline-capable; runs in its own window from the app shelf.
  Best on ChromeOS. See **[web/README.md](web/README.md)**.
- **Standalone desktop app** — `src/pdfreader/`. Python (Tkinter + Pillow +
  [pypdfium2]). Runs via `uv`, or as a single self-contained executable built
  with PyInstaller.

Both render one page at a time on demand (fast, low memory), remember your place
per file, and are driven entirely from the keyboard.

## Features

- Open by file picker, drag-and-drop (PWA), or `Open with` file handler (PWA).
- Reopen one of the last 10 files from a popup (`Shift+O`).
- Go to page; first/last; next/prev — vim-style paging.
- Fit-to-width / fit-to-height / custom scale; zoom.
- Pan with `h j k l` / arrows / touchpad.
- Rotate pages (90° steps), remembered per file.
- Page color theme: white / warm off-white / dark (inverted), remembered globally.
- Adjustable UI text size, remembered per file.
- Per-file memory of page, scale, rotation, and text size.
- Help overlay (`?`) listing every shortcut.

## Keyboard shortcuts

| Action | Keys |
| --- | --- |
| Open file | `o` (PWA: also drag-drop / *Open with*) |
| Recent files (last 10) | `Shift+O` |
| Go to page | `:` |
| Table of contents | `c` |
| Next page | `Ctrl-f`, `Ctrl-→`, `Space`, `PageDown` |
| Previous page | `Ctrl-b`, `Ctrl-←`, `PageUp` |
| First / last page | `gg` / `G` (also `Home` / `End`) |
| Zoom page in / out | `+` `=` / `-` |
| Fit to width / height | `Shift+W` / `Shift+H` |
| Custom scale (%) | `f` |
| Rotate clockwise / counter | `r` / `Shift+R` |
| Page color (white / off-white / dark) | `t` |
| UI text size | `Ctrl +` / `Ctrl -` / `Ctrl 0` |
| Pan the page | `h` `j` `k` `l`, arrow keys |
| Help | `?` / `F1` |
| Quit / close | `q` |

Press `?` (or `F1`) in either app for the same list.

## Web app (PWA)

The `web/` folder is a self-contained static site — no build step. Serve it over
`localhost` or HTTPS, then **Install** it from Chrome to get an offline,
shelf-launchable app. Full run/deploy/update instructions, including Netlify Drop,
are in **[web/README.md](web/README.md)**.

Quick local run:

```bash
cd web
bunx serve .          # or:  npx serve .  /  python3 -m http.server
```

The PWA opens files via the picker (`o`), drag-and-drop, or the OS *Open with →
pdfreader* file handler (each file in its own window). It does not auto-resume a
previous file. State lives in IndexedDB (per-file) and `localStorage` (theme).

## Standalone desktop app

Built with Tkinter + Pillow + pypdfium2. Tkinter renders over X11/XWayland, which
keeps it stable on ChromeOS (Crostini) where the Sommelier Wayland proxy
mishandles native dialogs; file opening uses a built-in in-window browser instead
of a native dialog.

Run from source (needs [uv]):

```bash
uv sync                              # create the 3.12 venv, install deps
uv run python -m pdfreader           # restores last file, or shows Open prompt
uv run python -m pdfreader file.pdf  # open a specific file
```

Per-file state (page, scale, rotation, text size) and the global page-color theme
are stored in `state.json` in your platform config dir (`~/.config/pdfreader` on
Linux); up to 500 files are remembered. Launching with no argument reopens the
most recent file.

### Build a single executable

PyInstaller is not a cross-compiler — build on each target OS:

```bash
uv run pyinstaller build/pdfreader.spec
./dist/pdfreader            # runs with no Python/uv installed
```

A prebuilt Linux x64 binary is attached to the GitHub releases.

### Tests

```bash
uv run pytest
```

## License

[MIT](LICENSE).

The PWA bundles [PDF.js] under `web/vendor/pdfjs/`, which is distributed under the
Apache License 2.0 (see `web/vendor/pdfjs/LICENSE`). The Python build uses
[pypdfium2] (PDFium; BSD-3-Clause / Apache-2.0).

[PDF.js]: https://mozilla.github.io/pdf.js/
[pypdfium2]: https://github.com/pypdfium2-team/pypdfium2
[uv]: https://docs.astral.sh/uv/
