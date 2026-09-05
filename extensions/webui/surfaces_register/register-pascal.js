import { store as pascalStore } from "/plugins/pascal_editor/webui/pascal-store.js";

function nextAnimationFrame() {
  return new Promise((resolve) => {
    const schedule = globalThis.requestAnimationFrame || ((callback) => globalThis.setTimeout(callback, 16));
    schedule(() => resolve());
  });
}

function isVisiblePanel(panel) {
  if (!panel?.isConnected) return false;
  const surface = panel.closest(".pascal-canvas-surface");
  const surfaceStyle = surface ? globalThis.getComputedStyle?.(surface) : null;
  const panelStyle = globalThis.getComputedStyle?.(panel);
  if (surfaceStyle?.display === "none" || surfaceStyle?.visibility === "hidden") return false;
  if (panelStyle?.display === "none" || panelStyle?.visibility === "hidden") return false;
  const rect = panel.getBoundingClientRect?.();
  return Boolean(rect && Math.round(rect.width || 0) >= 80 && Math.round(rect.height || 0) >= 80);
}

async function waitForVisiblePanel(selector, timeoutMs = 4000) {
  const deadline = globalThis.Date.now() + timeoutMs;
  let stableKey = "";
  let stableCount = 0;

  while (globalThis.Date.now() <= deadline) {
    const panel = document.querySelector(selector);
    const visible = isVisiblePanel(panel);
    if (visible) {
      const rect = panel.getBoundingClientRect();
      const key = `${Math.round(rect.width || 0)}x${Math.round(rect.height || 0)}`;
      if (key === stableKey) {
        stableCount += 1;
        if (stableCount >= 2) return panel;
      } else {
        stableKey = key;
        stableCount = 0;
      }
    } else {
      stableKey = "";
      stableCount = 0;
    }
    await nextAnimationFrame();
  }

  return document.querySelector(selector);
}

export default async function registerPascalSurface(canvas) {
  canvas.registerSurface({
    id: "pascal",
    title: "Pascal Editor",
    icon: "home",
    order: 15,
    modalPath: "/plugins/pascal_editor/webui/main.html",
    beginDockHandoff() {
      pascalStore.beginSurfaceHandoff?.();
    },
    finishDockHandoff() {
      pascalStore.finishSurfaceHandoff?.();
    },
    cancelDockHandoff() {
      pascalStore.cancelSurfaceHandoff?.();
    },
    async open(payload = {}) {
      await pascalStore.ensureRuntime?.();
      const panel =
        document.querySelector('.pascal-canvas-surface .pascal-panel')
        || await waitForVisiblePanel('.pascal-canvas-surface .pascal-panel');
      if (panel && pascalStore?.onOpen) {
        await pascalStore.onOpen(panel, { mode: "canvas", ...payload });
      }
    },
    async close() {
      await pascalStore.close?.();
    },
  });
}
