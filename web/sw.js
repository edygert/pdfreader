// Offline service worker. Navigations are network-first (fresh when online,
// cached app shell when offline); other same-origin GETs are cache-first with a
// network fallback. Every branch is guarded so the handler can never reject and
// strand a navigation with ERR_FAILED.

const CACHE = "pdfreader-v2";

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

self.addEventListener("install", (e) => {
  e.waitUntil(
    (async () => {
      const c = await caches.open(CACHE);
      // Individual adds so one failure can't abort the whole precache.
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

  // Navigations: try the network first; fall back to the cached app shell.
  if (req.mode === "navigate") {
    e.respondWith(
      (async () => {
        try {
          return await fetch(req);
        } catch (_) {
          return (
            (await caches.match("./index.html")) ||
            (await caches.match("./")) ||
            Response.error()
          );
        }
      })()
    );
    return;
  }

  // Assets: cache-first, then network (and cache the result).
  e.respondWith(
    (async () => {
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
    })()
  );
});
