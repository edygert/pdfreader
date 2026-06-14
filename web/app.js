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
const tocEl = document.getElementById("toc");
const recentEl = document.getElementById("recent");
const hintEl = document.getElementById("hint");
const fileInput = document.getElementById("file-input");
const installEl = document.getElementById("install");
const toolbarEl = document.getElementById("toolbar");
const tbPageEl = document.getElementById("tb-page");
const tbMoreEl = document.getElementById("tb-more");

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
    if (tbPageEl) tbPageEl.textContent = "– / –";
    return;
  }
  if (tbPageEl) tbPageEl.textContent = `${page + 1} / ${doc.pageCount}`;
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

// ---------- table of contents (outline) popup ----------
let tocItems = [];
let tocSel = 0;

function escapeHtml(s) {
  return (s || "").replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])
  );
}

const tocVisible = () => tocEl.classList.contains("show");
const hideToc = () => tocEl.classList.remove("show");

async function showToc() {
  if (!doc) return;
  tocItems = await doc.getToc();
  if (!tocItems.length) {
    tocEl.innerHTML =
      `<div class="toc-card"><h2>Table of Contents</h2>` +
      `<p class="dim">No table of contents in this PDF.</p></div>`;
    tocEl.classList.add("show");
    return;
  }
  // Start on the entry for the current page, if any.
  tocSel = tocItems.findIndex((it) => it.page === page);
  if (tocSel < 0) tocSel = 0;
  renderToc();
  tocEl.classList.add("show");
}

function renderToc() {
  const rows = tocItems
    .map((it, i) => {
      const pad = 8 + it.level * 18;
      const pg = it.page != null ? `<span class="toc-pg">${it.page + 1}</span>` : "";
      return (
        `<div class="toc-row${i === tocSel ? " sel" : ""}" data-i="${i}" ` +
        `style="padding-left:${pad}px">${escapeHtml(it.title)}${pg}</div>`
      );
    })
    .join("");
  tocEl.innerHTML = `<div class="toc-card"><h2>Table of Contents</h2><div class="toc-list">${rows}</div></div>`;
  tocEl.querySelectorAll(".toc-row").forEach((el) =>
    el.addEventListener("click", () => tocJump(parseInt(el.dataset.i, 10)))
  );
  const sel = tocEl.querySelector(".toc-row.sel");
  if (sel) sel.scrollIntoView({ block: "nearest" });
}

function tocMove(delta) {
  if (!tocItems.length) return;
  tocSel = Math.min(Math.max(tocSel + delta, 0), tocItems.length - 1);
  renderToc();
}

function tocJump(i) {
  const it = tocItems[i];
  hideToc();
  if (it && it.page != null) goto(it.page);
}

function toggleToc() {
  if (tocVisible()) hideToc();
  else showToc();
}

// ---------- recent files popup ----------
let recentItems = [];
let recentSel = 0;

const recentVisible = () => recentEl.classList.contains("show");
const hideRecent = () => recentEl.classList.remove("show");

function fmtSize(bytes) {
  if (!bytes) return "";
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

async function showRecent() {
  const all = await state.recentFiles(11);
  const curKey = record ? record.key : null;
  recentItems = all.filter((r) => r.key !== curKey).slice(0, 10);
  if (!recentItems.length) {
    recentEl.innerHTML =
      `<div class="toc-card"><h2>Recent Files</h2>` +
      `<p class="dim">No recent files yet. Press <kbd>o</kbd> to open a PDF.</p></div>`;
    recentEl.classList.add("show");
    return;
  }
  recentSel = 0;
  renderRecent();
  recentEl.classList.add("show");
}

function renderRecent() {
  const rows = recentItems
    .map((r, i) => {
      const meta = r.handle ? fmtSize(r.size) : "re-pick";
      return (
        `<div class="recent-row${i === recentSel ? " sel" : ""}" data-i="${i}">` +
        `<span class="recent-name">${escapeHtml(r.name)}</span>` +
        `<span class="recent-meta">${meta}</span></div>`
      );
    })
    .join("");
  recentEl.innerHTML =
    `<div class="toc-card"><h2>Recent Files</h2><div class="toc-list">${rows}</div></div>`;
  recentEl.querySelectorAll(".recent-row").forEach((el) =>
    el.addEventListener("click", () =>
      openRecentItem(recentItems[parseInt(el.dataset.i, 10)])
    )
  );
  const sel = recentEl.querySelector(".recent-row.sel");
  if (sel) sel.scrollIntoView({ block: "nearest" });
}

function recentMove(delta) {
  if (!recentItems.length) return;
  recentSel = Math.min(Math.max(recentSel + delta, 0), recentItems.length - 1);
  renderRecent();
}

// Reopen a remembered file. Needs the stored FileSystemFileHandle (and read
// permission, which may prompt); without one — e.g. opened via the basic file
// input — the browser won't re-read it, so fall back to the picker.
async function openRecentItem(rec) {
  hideRecent();
  if (!rec) return;
  const h = rec.handle;
  if (h && h.getFile) {
    try {
      if (h.queryPermission) {
        let perm = await h.queryPermission({ mode: "read" });
        if (perm !== "granted" && h.requestPermission) {
          perm = await h.requestPermission({ mode: "read" });
        }
        if (perm !== "granted") throw new Error("Read permission denied.");
      }
      const file = await h.getFile();
      await openFile(file, h);
      return;
    } catch (err) {
      alert(`Cannot reopen\n\n${rec.name}\n${err}`);
      return;
    }
  }
  alert(`"${rec.name}" can't be reopened automatically — open it from the picker.`);
  openPicker();
}

function toggleRecent() {
  if (recentVisible()) hideRecent();
  else showRecent();
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

// ---------- page color theme (global) ----------
const PAGE_THEMES = ["white", "off-white", "dark"];
function applyPageTheme(theme) {
  // CSS keys "sepia" to the off-white look.
  document.body.dataset.pageTheme = theme === "off-white" ? "sepia" : theme;
}
function loadPageTheme() {
  try {
    return localStorage.getItem("pageTheme") || "white";
  } catch (_) {
    return "white";
  }
}
function cyclePageTheme() {
  const cur = loadPageTheme();
  const next = PAGE_THEMES[(PAGE_THEMES.indexOf(cur) + 1) % PAGE_THEMES.length] || "white";
  applyPageTheme(next);
  try {
    localStorage.setItem("pageTheme", next);
  } catch (_) {}
  setStatus(`Page color: ${next}`);
  clearTimeout(uiMsgJob);
  uiMsgJob = setTimeout(updateStatus, 1200);
}

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
  showToolbar(); // briefly show controls, then auto-hide while reading
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

  // While the recent-files popup is open, keys navigate it (and nothing else).
  if (recentVisible()) {
    if (k === "Escape" || k === "O") return done(e, hideRecent);
    if (k === "ArrowDown" || k === "j") return done(e, () => recentMove(1));
    if (k === "ArrowUp" || k === "k") return done(e, () => recentMove(-1));
    if (k === "Enter") return done(e, () => openRecentItem(recentItems[recentSel]));
    if (k === "Home") return done(e, () => { recentSel = 0; renderRecent(); });
    if (k === "End") return done(e, () => { recentSel = recentItems.length - 1; renderRecent(); });
    if (!ctrl) e.preventDefault(); // swallow other keys so the page doesn't react
    return;
  }

  // While the contents popup is open, keys navigate it (and nothing else).
  if (tocVisible()) {
    if (k === "Escape" || k === "c") return done(e, hideToc);
    if (k === "ArrowDown" || k === "j") return done(e, () => tocMove(1));
    if (k === "ArrowUp" || k === "k") return done(e, () => tocMove(-1));
    if (k === "Enter") return done(e, () => tocJump(tocSel));
    if (k === "Home") return done(e, () => { tocSel = 0; renderToc(); });
    if (k === "End") return done(e, () => { tocSel = tocItems.length - 1; renderToc(); });
    if (!ctrl) e.preventDefault(); // swallow other keys so the page doesn't react
    return;
  }

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
    case "O": return done(e, toggleRecent); // Shift+O: Open Recent
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
    case "t": return done(e, cyclePageTheme);
    case "c": return done(e, toggleToc);
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

// ---------- touch toolbar ----------
// On-screen controls so the app is fully usable without a keyboard (e.g. iPad).
// Each button just calls the same function as its keyboard shortcut.
let toolbarHideJob = null;

function showToolbar(autoHide = true) {
  toolbarEl.classList.add("show");
  clearTimeout(toolbarHideJob);
  // Auto-hide only while reading; keep it up when no file is open so the Open
  // button stays reachable.
  if (autoHide && doc) toolbarHideJob = setTimeout(hideToolbar, 3500);
}

function hideToolbar() {
  clearTimeout(toolbarHideJob);
  toolbarEl.classList.remove("show");
  closeMore();
}

function toggleToolbar() {
  if (toolbarEl.classList.contains("show")) hideToolbar();
  else showToolbar();
}

function closeMore() {
  tbMoreEl.classList.remove("show");
  const moreBtn = toolbarEl.querySelector('[data-act="more"]');
  if (moreBtn) moreBtn.setAttribute("aria-expanded", "false");
}

const TOOLBAR_ACTIONS = {
  open: openPicker,
  recent: toggleRecent,
  prev: prevPage,
  next: nextPage,
  goto: gotoDialog,
  zoomout: zoomOut,
  zoomin: zoomIn,
  fitwidth: fitWidth,
  fitheight: fitHeight,
  rotate: rotateCW,
  toc: toggleToc,
  theme: cyclePageTheme,
  help: toggleHelp,
};

function setupToolbar() {
  toolbarEl.addEventListener("click", (e) => {
    const btn = e.target.closest("button");
    if (!btn) return;
    const act = btn.dataset.act;
    if (act === "more") {
      const open = tbMoreEl.classList.toggle("show");
      btn.setAttribute("aria-expanded", open ? "true" : "false");
      showToolbar(); // keep the bar up while the menu is open
      return;
    }
    const fn = TOOLBAR_ACTIONS[act];
    if (fn) fn();
    closeMore();
    if (doc) showToolbar(); // refresh the auto-hide timer after acting
  });
}

// ---------- touch gestures ----------
function touchDist(a, b) {
  return Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
}

function setupTouch() {
  const TAP_MOVE = 10; // px: max movement to still count as a tap
  const TAP_TIME = 300; // ms: max duration for a tap
  const SWIPE_MIN = 60; // px: min horizontal travel for a swipe page-turn

  let startX = 0, startY = 0, startT = 0;
  let moved = false;
  let mode = null; // null | "drag" (1 finger) | "pinch" (2 fingers)
  let pinchStartDist = 0;
  let pinchStartFactor = 1;
  let pinchRatio = 1;

  // True when the page is wider than the viewport: horizontal drags must pan
  // (native scroll), so we don't steal them for page-turns.
  const hScrollable = () => viewportEl.scrollWidth > viewportEl.clientWidth + 1;

  viewportEl.addEventListener("touchstart", (e) => {
    if (e.touches.length === 2) {
      mode = "pinch";
      pinchStartDist = touchDist(e.touches[0], e.touches[1]);
      pinchRatio = 1;
      currentFactor().then((f) => (pinchStartFactor = f));
      e.preventDefault();
      return;
    }
    if (e.touches.length === 1) {
      mode = "drag";
      const t = e.touches[0];
      startX = t.clientX;
      startY = t.clientY;
      startT = e.timeStamp;
      moved = false;
    }
  }, { passive: false });

  viewportEl.addEventListener("touchmove", (e) => {
    if (mode === "pinch" && e.touches.length === 2) {
      e.preventDefault(); // own the gesture; don't let the browser zoom/scroll
      const d = touchDist(e.touches[0], e.touches[1]);
      if (pinchStartDist > 0) {
        pinchRatio = Math.max(0.2, Math.min(d / pinchStartDist, 8));
        // Cheap live preview; the real re-render commits on touchend.
        canvas.style.transformOrigin = "center center";
        canvas.style.transform = `scale(${pinchRatio})`;
      }
      return;
    }
    if (mode === "drag" && e.touches.length === 1) {
      const t = e.touches[0];
      if (Math.abs(t.clientX - startX) > TAP_MOVE ||
          Math.abs(t.clientY - startY) > TAP_MOVE) {
        moved = true; // native scroll handles the actual panning
      }
    }
  }, { passive: false });

  viewportEl.addEventListener("touchend", (e) => {
    if (mode === "pinch") {
      const ratio = pinchRatio;
      canvas.style.transform = "";
      if (doc && Math.abs(ratio - 1) > 0.02) setCustom(pinchStartFactor * ratio);
      if (e.touches.length === 0) mode = null;
      return;
    }
    if (mode !== "drag") return;
    mode = null;
    const t = e.changedTouches[0];
    const dx = t.clientX - startX;
    const dy = t.clientY - startY;
    const dt = e.timeStamp - startT;

    // Tap: little movement, quick. Edge zones turn pages (when not panning a
    // wide page); the center toggles the toolbar.
    if (!moved && dt < TAP_TIME) {
      const w = viewportEl.clientWidth;
      const x = t.clientX;
      e.preventDefault(); // suppress the synthesized click / ghost tap
      if (!hScrollable() && x < w * 0.25) prevPage();
      else if (!hScrollable() && x > w * 0.75) nextPage();
      else toggleToolbar();
      return;
    }
    // Horizontal swipe → page turn, unless the page is panning horizontally.
    if (!hScrollable() && Math.abs(dx) > SWIPE_MIN && Math.abs(dx) > Math.abs(dy)) {
      if (dx < 0) nextPage();
      else prevPage();
    }
  }, { passive: false });

  // iOS Safari pinch fallback — scoped to the viewport only, so the rest of the
  // page and non-iOS platforms are unaffected.
  viewportEl.addEventListener("gesturestart", (e) => e.preventDefault());
  viewportEl.addEventListener("gesturechange", (e) => e.preventDefault());
}

// ---------- init ----------
async function init() {
  applyUiScaleVar(1);
  applyPageTheme(loadPageTheme());
  helpEl.innerHTML = helpHTML();
  updateStatus();
  setupInstall();
  setupLaunchQueue();

  window.addEventListener("keydown", onKeyDown);
  setupDnD();
  setupToolbar();
  setupTouch();
  showToolbar(false); // visible at the empty state so Open is reachable
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
  tocEl.addEventListener("click", (e) => {
    if (e.target === tocEl) hideToc(); // click the backdrop (not a row) to close
  });
  recentEl.addEventListener("click", (e) => {
    if (e.target === recentEl) hideRecent(); // backdrop click closes
  });

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("./sw.js").catch(() => {});
  }
  // No auto-resume: the app starts at the open prompt. A file is opened only via
  // the OS file handler (setupLaunchQueue), the picker (o), or drag-drop.
}

init();
