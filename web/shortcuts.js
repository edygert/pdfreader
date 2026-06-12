// Canonical shortcut list + one-line cheat sheet. Single source of truth, used
// to render the help overlay and the status-line cheats. Mirrors help.py.

export const SHORTCUTS = [
  ["Open file", ["o", "drag-drop"]],
  ["Go to page", [":"]],
  ["Table of contents", ["c"]],
  ["Next page", ["Ctrl f", "Ctrl →", "Space", "PageDown"]],
  ["Previous page", ["Ctrl b", "Ctrl ←", "PageUp"]],
  ["First page", ["gg", "Home"]],
  ["Last page", ["G", "End"]],
  ["Zoom in", ["+", "="]],
  ["Zoom out", ["-"]],
  ["Fit to width", ["Shift W"]],
  ["Fit to height", ["Shift H"]],
  ["Custom scale (enter %)", ["f"]],
  ["Rotate clockwise / counter", ["r", "Shift r"]],
  ["Page color: white / off-white / dark", ["t"]],
  ["UI text bigger / smaller / reset", ["Ctrl +", "Ctrl -", "Ctrl 0"]],
  ["Pan (when zoomed)", ["h j k l", "← → ↑ ↓"]],
  ["Show this help", ["?", "F1"]],
  ["Close", ["q"]],
];

export const CHEATS =
  "o open · : goto · Ctrl-f/b page · hjkl pan · " +
  "W/H fit · f scale · +/- zoom · r/R rotate · ? help · q quit";

export function helpHTML() {
  const rows = SHORTCUTS.map(
    ([label, keys]) =>
      `<tr><td class="keys">${keys
        .map((k) => `<kbd>${k}</kbd>`)
        .join(" ")}</td><td>${label}</td></tr>`
  ).join("");
  return `<div class="help-card">
    <h2>Keyboard Shortcuts</h2>
    <table>${rows}</table>
    <p class="dim">Arrow keys / hjkl pan when the page is zoomed past the window.
    Press <kbd>?</kbd> or <kbd>Esc</kbd> to close.</p>
  </div>`;
}
