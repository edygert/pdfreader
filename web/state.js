// Per-file reading position (page + scale + UI text size), persisted in
// IndexedDB. Mirrors the standalone state.py: same fields, LRU-trimmed to 500
// files, plus a remembered FileSystemFileHandle so the last file can re-open.

export const FIT_WIDTH = "fit_width";
export const FIT_HEIGHT = "fit_height";
export const CUSTOM = "custom";

const DB_NAME = "pdfreader";
const DB_VERSION = 1;
const FILES = "files"; // keyPath "key"
const META = "meta"; // keyPath "k"
const MAX_FILES = 500;

let _db = null;

function openDB() {
  if (_db) return Promise.resolve(_db);
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(FILES)) {
        db.createObjectStore(FILES, { keyPath: "key" });
      }
      if (!db.objectStoreNames.contains(META)) {
        db.createObjectStore(META, { keyPath: "k" });
      }
    };
    req.onsuccess = () => {
      _db = req.result;
      resolve(_db);
    };
    req.onerror = () => reject(req.error);
  });
}

function tx(store, mode) {
  return openDB().then((db) => db.transaction(store, mode).objectStore(store));
}

function reqAsync(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export function fileKey(name, size) {
  return `${name}:${size}`;
}

export function defaultRecord(key, name, size) {
  return {
    key,
    name,
    size,
    page: 0,
    scaleMode: FIT_WIDTH,
    customFactor: 1.0,
    uiScale: 1.0,
    rotation: 0, // degrees clockwise: 0 / 90 / 180 / 270
    handle: null,
    opened: Date.now(),
  };
}

export async function getFileState(key) {
  try {
    const store = await tx(FILES, "readonly");
    return (await reqAsync(store.get(key))) || null;
  } catch (_) {
    return null;
  }
}

export async function putFileState(record) {
  try {
    record.opened = Date.now();
    const store = await tx(FILES, "readwrite");
    await reqAsync(store.put(record));
    await trim();
  } catch (_) {
    // best-effort, never throw into the UI
  }
}

export async function getLastFileKey() {
  try {
    const store = await tx(META, "readonly");
    const row = await reqAsync(store.get("lastFileKey"));
    return row ? row.v : null;
  } catch (_) {
    return null;
  }
}

export async function setLastFileKey(key) {
  try {
    const store = await tx(META, "readwrite");
    await reqAsync(store.put({ k: "lastFileKey", v: key }));
  } catch (_) {}
}

// Keep only the most-recently-opened MAX_FILES records.
async function trim() {
  const store = await tx(FILES, "readwrite");
  const all = await reqAsync(store.getAll());
  if (all.length <= MAX_FILES) return;
  all.sort((a, b) => (a.opened || 0) - (b.opened || 0));
  const drop = all.slice(0, all.length - MAX_FILES);
  for (const r of drop) store.delete(r.key);
}
