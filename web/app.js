// Main app: rendering, navigation, scaling, vim keymap, status line, per-file
// memory, drag-drop + picker, OS file handler. Mirrors the standalone viewer.py.

import { PdfDoc } from "./pdf.js";
import * as state from "./state.js";
import { FIT_WIDTH, FIT_HEIGHT, CUSTOM } from "./state.js";
import { CHEATS, helpHTML } from "./shortcuts.js";

const MARGIN = 4; // px shaved off the viewport in fit modes
const PAN_STEP = 60; // px per arrow/hjkl pan

// ---- DOM ----
const viewportEl = document.getElementById("viewport");
const canvas = document.getElementById("page");
const statusEl = document.getElementById("status");
const helpEl = document.getElementById("help");
const hintEl = document.getElementById("hint");
const fileInput = document.getElementById("file-input");
const installEl = document.getElementById("install");

// ---- session state ----
let doc = null;
let page = 0;
let record = null; // per-file IndexedDB record (page/scaleMode/customFactor/uiScale)
let uiScale = 1.0;
let lastScale = 1.0; // last effective page scale (for the status %)
let gPending = false;
let renderSeq = 0;
let resizeJob = null;
let uiMsgJob = null;

// ---------- rendering & scaling ----------
async function effectiveScale() {
  const [wpt, hpt] = await doc.pageSize(page, record.rotation || 0);
  const vw = viewportEl.clientWidth;
  const vh = viewportEl.clientHeight;
  if (record.scaleMode === FIT_WIDTH) return Math.max(0.05, (vw - MARGIN) / wpt);
  if (record.scaleMode === FIT_HEIGHT) return Math.max(0.05, (vh - MARGIN) / hpt);
  return record.customFactor;
}

async function currentFactor() {
  if (record.scaleMode === CUSTOM) return record.customFactor;
  return effectiveScale();
}

async function renderCurrent() {
  if (!doc) return;
  const seq = ++renderSeq;
  doc.cancel();
  const scale = await effectiveScale();
  lastScale = scale;
  const dpr = window.devicePixelRatio || 1;
  try {
    await doc.render(page, scale, dpr, canvas, record.rotation || 0);
  } catch (err) {
    if (err && err.name === "RenderingCancelledException") return;
    console.error(err);
    return;
  }
  if (seq !== renderSeq) return; // a newer render superseded this one
  updateStatus();
}

async function setCustom(factor) {
  record.scaleMode = CUSTOM;
  record.customFactor = Math.max(0.05, Math.min(factor, 12.0));
  await renderCurrent();
  save();
}

async function zoomIn() {
  if (doc) setCustom((await currentFactor()) * 1.25);
}
async function zoomOut() {
  if (doc) setCustom((await currentFactor()) * 0.8);
}
async function fitWidth() {
  if (!doc) return;
  record.scaleMode = FIT_WIDTH;
  await renderCurrent();
  save();
}
async function fitHeight() {
  if (!doc) return;
  record.scaleMode = FIT_HEIGHT;
  await renderCurrent();
  save();
}
async function customScaleDialog() {
  if (!doc) return;
  const cur = Math.round((await currentFactor()) * 1000) / 10;
  const ans = window.prompt("Scale (%):", cur);
  if (ans == null) return;
  const pct = parseFloat(ans);
  if (!isNaN(pct)) setCustom(Math.max(5, Math.min(pct, 1200)) / 100);
}

// ---------- rotation ----------
async function setRotation(deg) {
  record.rotation = ((deg % 360) + 360) % 360;
  await renderCurrent(); // fit modes recompute against the rotated dimensions
  save();
}
const rotateCW = () => doc && setRotation((record.rotation || 0) + 90);
const rotateCCW = () => doc && setRotation((record.rotation || 0) - 90);

// ---------- navigation ----------
async function goto(index) {
  if (!doc) return;
  index = Math.min(Math.max(index, 0), doc.pageCount - 1);
  if (index !== page) {
    page = index;
    await renderCurrent();
    save();
  }
  viewportEl.scrollTo(0, 0);
}
const nextPage = () => goto(page + 1);
const prevPage = () => goto(page - 1);
const firstPage = () => goto(0);
const lastPage = () => doc && goto(doc.pageCount - 1);

function onGKey() {
  if (gPending) {
    gPending = false;
    firstPage();
  } else {
    gPending = true;
    setTimeout(() => (gPending = false), 600);
  }
}

function gotoDialog() {
  if (!doc) return;
  const ans = window.prompt(`Page (1–${doc.pageCount}):`, page + 1);
  if (ans == null) return;
  const n = parseInt(ans, 10);
  if (!isNaN(n)) goto(n - 1);
}

// ---------- panning ----------
const panX = (dir) => viewportEl.scrollBy({ left: dir * PAN_STEP });
const panY = (dir) => viewportEl.scrollBy({ top: dir * PAN_STEP });

// ---------- status & help ----------
function setStatus(text) {
  statusEl.textContent = text;
}

function updateStatus() {
  if (!doc) {
    setStatus(`No document open        ${CHEATS}`);
    return;
  }
  const pct = Math.round(lastScale * 100);
  let scaleText;
  if (record.scaleMode === FIT_WIDTH) scaleText = `Fit width (${pct}%)`;
  else if (record.scaleMode === FIT_HEIGHT) scaleText = `Fit height (${pct}%)`;
  else scaleText = `${pct}%`;
  const rot = record.rotation ? `    ·    ↻${record.rotation}°` : "";
  setStatus(
    `${record.name}    ·    Page ${page + 1} / ${doc.pageCount}` +
      `    ·    ${scaleText}${rot}        ${CHEATS}`
  );
}

function toggleHelp() {
  helpEl.classList.toggle("show");
}
function hideHelp() {
  helpEl.classList.remove("show");
}

// ---------- UI text scaling (chrome only) ----------
function applyUiScaleVar(s) {
  document.documentElement.style.setProperty("--ui-scale", s);
}
function applyUiScale(s) {
  uiScale = Math.max(0.6, Math.min(s, 3.0));
  applyUiScaleVar(uiScale);
  if (doc) {
    record.uiScale = uiScale;
    save();
  }
  setStatus(`UI text ${Math.round(uiScale * 100)}%`);
  clearTimeout(uiMsgJob);
  uiMsgJob = setTimeout(updateStatus, 1200);
}
const uiScaleUp = () => applyUiScale(uiScale * 1.1);
const uiScaleDown = () => applyUiScale(uiScale * 0.9);
const uiScaleReset = () => applyUiScale(1.0);

// ---------- opening files ----------
async function openFile(file, handle) {
  let buf;
  try {
    buf = await file.arrayBuffer();
    const newDoc = await PdfDoc.open(buf);
    if (doc) doc.destroy();
    doc = newDoc;
  } catch (err) {
    alert(`Cannot open PDF\n\n${file.name}\n${err}`);
    return;
  }
  const key = state.fileKey(file.name, file.size);
  record =
    (await state.getFileState(key)) ||
    state.defaultRecord(key, file.name, file.size);
  record.name = file.name;
  record.size = file.size;
  if (handle) record.handle = handle;

  record.rotation = record.rotation || 0; // default for records saved pre-rotation
  uiScale = record.uiScale || 1.0;
  applyUiScaleVar(uiScale);
  page = Math.min(Math.max(record.page || 0, 0), doc.pageCount - 1);

  hintEl.classList.add("hidden");
  document.title = `${file.name} — pdfreader`;
  await renderCurrent();
  save();
}

async function openFromHandle(handle) {
  const file = await handle.getFile();
  await openFile(file, handle);
}

async function openPicker() {
  if (window.showOpenFilePicker) {
    try {
      const [handle] = await window.showOpenFilePicker({
        types: [{ description: "PDF", accept: { "application/pdf": [".pdf"] } }],
      });
      await openFromHandle(handle);
    } catch (_) {
      /* user cancelled */
    }
  } else {
    fileInput.click();
  }
}

function isPdf(file) {
  return (
    file &&
    (file.type === "application/pdf" ||
      file.name.toLowerCase().endsWith(".pdf"))
  );
}

function save() {
  if (!doc || !record) return;
  record.page = page;
  state.putFileState(record);
}

// ---------- OS file handler ("Open with pdfreader") ----------
function setupLaunchQueue() {
  if (!("launchQueue" in window)) return;
  // When the OS opens a PDF with this app, the file arrives here as a
  // FileSystemFileHandle.
  window.launchQueue.setConsumer(async (params) => {
    if (!params || !params.files || !params.files.length) return;
    try {
      const handle = params.files[0];
      const file = await handle.getFile();
      await openFile(file, handle);
    } catch (err) {
      console.error(err);
    }
  });
}

// ---------- keyboard ----------
function onKeyDown(e) {
  const k = e.key;
  const ctrl = e.ctrlKey || e.metaKey;

  if (ctrl) {
    if (k === "+" || k === "=") return done(e, uiScaleUp);
    if (k === "-") return done(e, uiScaleDown);
    if (k === "0") return done(e, uiScaleReset);
    if (k === "f" || k === "F") return done(e, nextPage); // override Find
    if (k === "b" || k === "B") return done(e, prevPage);
    if (k === "ArrowRight") return done(e, nextPage);
    if (k === "ArrowLeft") return done(e, prevPage);
    return; // leave other Ctrl combos to the browser
  }

  switch (k) {
    case "o": return done(e, openPicker);
    case ":": return done(e, gotoDialog);
    case "g": return done(e, onGKey);
    case "G": return done(e, lastPage);
    case " ":
    case "PageDown": return done(e, nextPage);
    case "PageUp": return done(e, prevPage);
    case "Home": return done(e, firstPage);
    case "End": return done(e, lastPage);
    case "+":
    case "=": return done(e, zoomIn);
    case "-": return done(e, zoomOut);
    case "W": return done(e, fitWidth);
    case "H": return done(e, fitHeight);
    case "f": return done(e, customScaleDialog);
    case "r": return done(e, rotateCW);
    case "R": return done(e, rotateCCW);
    case "h": return done(e, () => panX(-1));
    case "l": return done(e, () => panX(1));
    case "j": return done(e, () => panY(1));
    case "k": return done(e, () => panY(-1));
    case "ArrowLeft": return done(e, () => panX(-1));
    case "ArrowRight": return done(e, () => panX(1));
    case "ArrowUp": return done(e, () => panY(-1));
    case "ArrowDown": return done(e, () => panY(1));
    case "?": return done(e, toggleHelp);
    case "F1": return done(e, toggleHelp);
    case "q": return done(e, () => window.close());
    case "Escape": return done(e, hideHelp);
  }
}

function done(e, fn) {
  e.preventDefault();
  fn();
}

// ---------- drag & drop ----------
function setupDnD() {
  window.addEventListener("dragover", (e) => {
    e.preventDefault();
    document.body.classList.add("dragging");
  });
  window.addEventListener("dragleave", (e) => {
    if (e.relatedTarget === null) document.body.classList.remove("dragging");
  });
  window.addEventListener("drop", async (e) => {
    e.preventDefault(); // stop Chrome from opening the PDF itself
    document.body.classList.remove("dragging");
    let handle = null;
    let file = null;
    const items = e.dataTransfer.items;
    if (items && items[0]) {
      if (items[0].getAsFileSystemHandle) {
        const h = await items[0].getAsFileSystemHandle();
        if (h && h.kind === "file") {
          handle = h;
          file = await h.getFile();
        }
      }
      if (!file) file = items[0].getAsFile();
    } else if (e.dataTransfer.files[0]) {
      file = e.dataTransfer.files[0];
    }
    if (isPdf(file)) openFile(file, handle);
  });
}

// ---------- install prompt ----------
let deferredPrompt = null;
function setupInstall() {
  // Fires only when the browser deems the app installable (https/localhost, not
  // incognito, manifest + SW valid). Gives an in-app button so the user need not
  // hunt through Chrome's menus.
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferredPrompt = e;
    installEl.classList.add("show");
  });
  installEl.addEventListener("click", async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    await deferredPrompt.userChoice;
    deferredPrompt = null;
    installEl.classList.remove("show");
  });
  window.addEventListener("appinstalled", () =>
    installEl.classList.remove("show")
  );
}

// ---------- init ----------
async function init() {
  applyUiScaleVar(1);
  helpEl.innerHTML = helpHTML();
  updateStatus();
  setupInstall();
  setupLaunchQueue();

  window.addEventListener("keydown", onKeyDown);
  setupDnD();
  fileInput.addEventListener("change", () => {
    const f = fileInput.files[0];
    if (f) openFile(f, null);
    fileInput.value = "";
  });
  window.addEventListener("resize", () => {
    if (!doc) return;
    if (record.scaleMode !== FIT_WIDTH && record.scaleMode !== FIT_HEIGHT) return;
    clearTimeout(resizeJob);
    resizeJob = setTimeout(renderCurrent, 80);
  });
  helpEl.addEventListener("click", hideHelp);

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("./sw.js").catch(() => {});
  }
  // No auto-resume: the app starts at the open prompt. A file is opened only via
  // the OS file handler (setupLaunchQueue), the picker (o), or drag-drop.
}

init();
