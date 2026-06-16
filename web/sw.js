// Offline service worker.
//
// Strategy chosen so redeploys actually propagate without manual cache-busting:
//   - App shell/code (HTML, JS, CSS, manifest): NETWORK-FIRST. Always fresh when
//     online (so a new deploy takes effect on the next launch and index.html +
//     app.js never end up on mismatched versions), cached copy used offline.
//   - Big immutable assets (vendored PDF.js, icons): CACHE-FIRST, so the ~2.8 MB
//     engine isn't refetched every launch.
// Every branch is guarded so the handler can't reject and strand a navigation
// with ERR_FAILED.

const CACHE = "pdfreader-v4";

// Seed the cache so the very first offline launch has everything.
const CORE = [
  "./",
  "./index.html",
  "./styles.css",
  "./app.js",
  "./pdf.js",
  "./state.js",
  "./shortcuts.js",
  "./manifest.webmanifest",
  "./icons/icon.svg",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./vendor/pdfjs/pdf.js",
  "./vendor/pdfjs/pdf.worker.js",
];

// Paths served cache-first (large + rarely changing).
function isImmutable(pathname) {
  return pathname.includes("/vendor/") || pathname.includes("/icons/");
}

self.addEventListener("install", (e) => {
  e.waitUntil(
    (async () => {
      const c = await caches.open(CACHE);
      await Promise.allSettled(CORE.map((u) => c.add(u)));
      await self.skipWaiting();
    })()
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(
        keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))
      );
      await self.clients.claim();
    })()
  );
});

async function networkFirst(req, fallbackKey) {
  try {
    const res = await fetch(req);
    if (res && res.ok) {
      const copy = res.clone();
      caches.open(CACHE).then((c) => c.put(fallbackKey || req, copy)).catch(() => {});
    }
    return res;
  } catch (_) {
    return (
      (await caches.match(req)) ||
      (fallbackKey ? await caches.match(fallbackKey) : null) ||
      Response.error()
    );
  }
}

async function cacheFirst(req) {
  const hit = await caches.match(req).catch(() => null);
  if (hit) return hit;
  try {
    const res = await fetch(req);
    if (res && res.ok) {
      const copy = res.clone();
      caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
    }
    return res;
  } catch (_) {
    return Response.error();
  }
}

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  let url;
  try {
    url = new URL(req.url);
  } catch (_) {
    return;
  }
  if (url.origin !== self.location.origin) return;

  if (req.mode === "navigate") {
    // Network-first, fall back to the cached shell offline.
    e.respondWith(networkFirst(req, "./index.html"));
    return;
  }
  if (isImmutable(url.pathname)) {
    e.respondWith(cacheFirst(req));
    return;
  }
  // App code (js/css/manifest): network-first so deploys propagate immediately.
  e.respondWith(networkFirst(req));
});
