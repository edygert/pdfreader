# pdfreader — web / PWA

A browser version of the standalone PDF reader: same keyboard-driven workflow,
single-page rendering, per-file memory, and scaling — built as an installable,
offline-capable **Progressive Web App**. Plain JavaScript + [PDF.js], **no build
step** — the files here *are* the app.

This is completely separate from the Python standalone app; no standalone code is
shared or changed.

## Run it locally

A PWA needs a `localhost` (or `https`) origin — a `file://` page can't use service
workers or the File System Access API. Serve this folder with any static server:

```bash
cd web
python3 -m http.server 8000      # or:  npx serve .   /   bunx serve .
```

Open **`http://localhost:8000`** in Chrome — it must be the `localhost` address, not
a `192.168.x.x` network address (only `localhost`/HTTPS count as a secure context),
and **not an Incognito window** (PWAs can't be installed there).

When the app is installable, an **"⬇ Install app" button** appears in the top-right
of the app itself — click it. (Chrome's own affordance is the install icon in the
address bar, or ⋮ → *Cast, save, and share* → *Install pdfreader…*.) After the first
load the service worker caches everything, so the installed app **launches from the
shelf and works offline**.

## Deploy it (minimum effort)

Because there's no build, deploying = copying these static files to any host that
serves HTTPS:

- **GitHub Pages / Netlify / Cloudflare Pages** — drop the `web/` folder; you get an
  HTTPS URL that's installable as a PWA on any device.

## Open a file

- Press <kbd>o</kbd> to pick a PDF, or **drag a PDF onto the window**.
- The last file, page, scale, and text size are remembered per file (IndexedDB).
- On a fresh launch the app offers a **Resume** button to reopen your last PDF — one
  click re-grants read access (the browser requires a gesture). Installed PWAs can
  retain permission and resume silently.

## Shortcuts

| Action | Keys |
| --- | --- |
| Open file | `o`, drag-drop |
| Go to page | `:` |
| Next / previous page | `Ctrl-f` / `Ctrl-b` (also Space/PageDown, PageUp, Ctrl-→/←) |
| First / last page | `gg` / `G` (also Home / End) |
| Pan | `h` `j` `k` `l`, arrows, touchpad |
| Zoom page | `+` / `=` , `-` |
| Fit width / height | `Shift+W` / `Shift+H` |
| Custom scale | `f` |
| UI text size | `Ctrl +` / `Ctrl -` / `Ctrl 0` |
| Help | `?` / `F1` |
| Close | `q` |

[PDF.js]: https://mozilla.github.io/pdf.js/
