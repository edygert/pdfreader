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

## Deploy it (recommended — most reliable)

Hosting the app at a stable **HTTPS** URL is the robust way to run it: the installed
PWA launches from the shelf online or offline, with no local server ever, and none
of the fragility of a `localhost`-origin install. Because there's no build step,
deploying is just copying these static files to any static host.

### Netlify Drop (fastest, no account needed to try)

1. Go to **<https://app.netlify.com/drop>** in Chrome.
2. Drag the **`web/`** folder onto the page. Drag the folder *itself* so its contents
   land at the site root — `index.html`, `manifest.webmanifest`, and `sw.js` must be
   at `/`, not under `/web/…`, or the manifest/service worker paths 404 and the app
   won't be installable.
3. Netlify gives you an `https://<name>.netlify.app` URL. Open it in a **normal**
   (non-Incognito) Chrome window.
4. If the **⬇ Install app** button doesn't appear immediately, **reload once**
   (Ctrl-R) — the service worker has to take control before Chrome offers install.
5. Click **⬇ Install app** (or Chrome's install icon in the address bar). It opens in
   its own standalone window and is added to the shelf; thereafter it runs offline.

**Updating after code changes:** re-drag the `web/` folder onto Netlify Drop (or
connect the repo for auto-deploy), then open the app and reload once so the new
service worker (`pdfreader-vN`) installs and replaces the old one.

### Other hosts

**GitHub Pages** or **Cloudflare Pages** work the same way — point them at the
contents of `web/` so the files are served from the site root over HTTPS.

## Open a file

- **Right-click a PDF in the Files app → Open with → pdfreader** (the installed app
  registers as a `.pdf` handler). Each file opens in its own window
  (`launch_handler: navigate-new`), so you can have several PDFs open side by side.
- Or, inside the app, press <kbd>o</kbd> to pick a PDF, or **drag a PDF onto the
  window**.
- The app does **not** auto-resume a previous file — it starts at the open prompt.
- Page, scale, and UI text size are still remembered **per file** (IndexedDB), so
  reopening a given PDF restores where you were in it.

After deploying an update, the file-association may need a nudge: in the ChromeOS
Files app, right-click a PDF → *Open with…* → set **pdfreader** (optionally as
default). File handling only works once the PWA is installed.

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
