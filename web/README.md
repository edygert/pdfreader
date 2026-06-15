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

### Other hosts

**GitHub Pages** or **Cloudflare Pages** work the same way — point them at the
contents of `web/` so the files are served from the site root over HTTPS.

### AWS S3 + CloudFront

Two scripts here automate an S3 deploy fronted by CloudFront for HTTPS (plain S3
website hosting is HTTP-only, which disables the service worker, install, and the
File System Access picker). Set your bucket via `PDFREADER_BUCKET` (or the first
argument); region defaults to `us-east-1` and the AWS CLI profile is taken from
`AWS_PROFILE` (default credentials if unset).

1. **One-time infra** — `bootstrap-aws.sh` (idempotent): creates the private
   bucket, an Origin Access Control, a CloudFront distribution
   (`redirect-to-https`, root object `index.html`, managed *CachingOptimized*
   policy), and a bucket policy that lets only that distribution read the bucket.
   It prints the distribution ID and the `https://<id>.cloudfront.net` URL.

   ```bash
   web/bootstrap-aws.sh <bucket>
   ```

   A custom domain is optional — without one the `*.cloudfront.net` URL is a
   fully working PWA origin. For a custom domain, create and validate an ACM
   cert **in us-east-1** first, then:

   ```bash
   DOMAIN=pdf.example.com ACM_CERT_ARN=arn:aws:acm:us-east-1:…:certificate/… \
     web/bootstrap-aws.sh <bucket>
   ```

2. **Deploy the files** — `deploy.sh`: syncs `vendor/` and `icons/` cache-first
   (1-year immutable) and the app shell network-first (`no-cache`), fixes the
   `manifest.webmanifest` content type, and invalidates the app-shell paths at
   CloudFront.

   ```bash
   web/deploy.sh <bucket> <distribution-id>
   PDFREADER_CF_DIST=<id> web/deploy.sh <bucket>   # same, via env
   DRY_RUN=1 web/deploy.sh <bucket> <id>           # preview the sync, upload nothing
   ```

   Re-run `deploy.sh` for every release. When you change vendored PDF.js or
   icons, also bump the `CACHE` constant in `sw.js` (see below).

#### Path-based hosting (multiple apps on one domain)

One bucket + one distribution can host many apps, each under its own path
prefix, e.g. `https://apps.example.com/pdfreader/`. Deploy with
`PDFREADER_PREFIX` (the app uses relative paths, so it runs fine under a subpath,
and each app gets its own service-worker scope):

```bash
PDFREADER_PREFIX=pdfreader web/deploy.sh <bucket> <distribution-id>
```

This requires one piece of CloudFront config, because an OAC (S3 REST) origin
has no "index document" behavior: a **CloudFront Function** on *viewer-request*
that rewrites `…/` → `…/index.html` and 301-redirects extensionless paths to add
a trailing slash (so relative URLs resolve under the app's directory). The
bucket root can hold a small landing page listing the apps — see
[`apps-root/index.html`](../apps-root/index.html):

```bash
aws s3 cp apps-root/index.html s3://<bucket>/index.html \
  --content-type text/html --cache-control no-cache
```

## Updating a deployed install

The app is served by a **service worker**, so a redeploy doesn't reach the installed
app until that worker updates. The strategy in `sw.js` is set up to make this almost
automatic:

- **App code** — `index.html`, `*.js`, `styles.css`, `manifest.webmanifest` — is
  **network-first**. A new deploy is picked up on the next online launch; no version
  bump needed.
- **Vendored PDF.js + icons** (`vendor/`, `icons/`) are **cache-first** (so the
  ~2.8 MB engine isn't refetched every launch).

### Normal update (you changed app code)

1. Re-deploy: drag the `web/` folder onto <https://app.netlify.com/drop> (same site),
   or `git push` if you've connected the repo for auto-deploy.
2. Open the app (shelf icon) and **reload once or twice** (Ctrl-R). The browser
   re-checks `sw.js`, the new app code loads, done.

That's it — because app code is network-first, you do **not** need to touch `sw.js`.

### When you change vendored PDF.js or icons

Those are cache-first, so bump the cache name so the new worker re-caches them:

- Edit `sw.js` → change `const CACHE = "pdfreader-vN"` to the next number
  (`v3` → `v4`).
- Re-deploy. On the next launch the new worker installs, deletes the old cache, and
  re-fetches the vendored files.

### If an update seems stuck

The service worker only swaps in on a fresh launch, and Chrome re-checks `sw.js` at
most once a day unless you reload. To force it:

- Reload the app a couple of times, **or**
- DevTools (F12) → **Application → Service Workers → Update** (or **Storage → Clear
  site data**), then reload, **or**
- Uninstall and reinstall the PWA from the URL.

> Tip: bump the `CACHE` constant in `sw.js` on any release where you want to be 100%
> certain every client drops its old cache — it forces a clean re-cache even for the
> cache-first assets.

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
| Recent files (last 10) | `Shift+O` |
| Go to page | `:` |
| Table of contents | `c` |
| Next / previous page | `Ctrl-f` / `Ctrl-b` (also Space/PageDown, PageUp, Ctrl-→/←) |
| First / last page | `gg` / `G` (also Home / End) |
| Pan | `h` `j` `k` `l`, arrows, touchpad |
| Zoom page | `+` / `=` , `-` |
| Fit width / height | `Shift+W` / `Shift+H` |
| Custom scale | `f` |
| Rotate clockwise / counter | `r` / `Shift+R` |
| Page color (white / off-white / dark) | `t` |
| UI text size | `Ctrl +` / `Ctrl -` / `Ctrl 0` |
| Help | `?` / `F1` |
| Close | `q` |

## Touch controls

No keyboard required (e.g. on iPad). All gestures act on the page area:

| Gesture | Action |
| --- | --- |
| Tap the center | Show / hide the toolbar |
| Tap the left / right edge | Previous / next page |
| Swipe ◀ / ▶ | Previous / next page |
| Pinch in / out | Zoom |
| Drag (one finger) | Pan, when the page is zoomed past the window |

The toolbar holds every other action (open, recent, go-to-page, zoom, fit,
rotate, contents, page color, help); less-used items live under the **⋯** menu.
It's shown at startup so **Open** is reachable, then auto-hides while reading —
tap the center to bring it back. When the page is zoomed wider than the window,
horizontal drags pan instead of turning pages, so swipe/edge-tap page-turns
pause until you fit the page again.

[PDF.js]: https://mozilla.github.io/pdf.js/
