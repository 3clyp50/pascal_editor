import { callJsonApi } from "/js/api.js";
import { createStore } from "/js/AlpineStore.js";
import { setupFloatingSurfaceModalChrome } from "/js/surfaces.js";
import { toastFrontendError } from "/components/notifications/notification-store.js";

const API = "plugins/pascal_editor/pascal";
const EDITOR_URL = "/pascal"; // canonical index (Next.js has no trailing slash)
const MIN_SIZE = 80;
const SOURCE_TITLE = "Pascal Editor";

const sleep = (ms) => new Promise((resolve) => globalThis.setTimeout(resolve, ms));

function nextFrame() {
  const schedule = globalThis.requestAnimationFrame || ((callback) => globalThis.setTimeout(callback, 16));
  return new Promise((resolve) => schedule(() => resolve()));
}

function elementVisible(root) {
  if (!root?.isConnected) return false;
  const surface = root.closest?.(".pascal-canvas-surface");
  for (const element of [surface, root].filter(Boolean)) {
    const style = globalThis.getComputedStyle?.(element);
    if (!style) continue;
    if (style.display === "none" || style.visibility === "hidden" || Number(style.opacity) === 0) {
      return false;
    }
  }
  const rect = root.getBoundingClientRect?.();
  return Boolean(rect && Math.round(rect.width || 0) >= MIN_SIZE && Math.round(rect.height || 0) >= MIN_SIZE);
}

const model = {
  loading: false,
  error: "",
  status: "idle",
  handoff: false,
  _iframe: null,
  _host: null,
  _pending: null,
  _watching: false,
  _openPromise: null,
  _openKey: "",
  _restoreUrl: "",
  _handoffTimer: null,

  activeIframe() {
    return this._iframe;
  },

  tokenFor(element) {
    if (!element.__pascalToken) {
      element.__pascalToken = Math.random().toString(36).slice(2);
    }
    return element.__pascalToken;
  },

  canvasSelector() {
    return '.pascal-canvas-surface .pascal-panel';
  },

  findCanvasHost() {
    return globalThis.document?.querySelector?.(this.canvasSelector());
  },

  beginSurfaceHandoff() {
    this.clearHandoffTimer();
    this.handoff = true;
    this._handoffTimer = globalThis.setTimeout(() => {
      this.handoff = false;
      this._handoffTimer = null;
    }, 5000);
    // When the canvas host already exists, move the live iframe there before the
    // modal host is unmounted so the 3D scene survives the dock transition.
    if (this._iframe && this._host && this._iframe.parentElement === this._host) {
      const canvasHost = this.findCanvasHost();
      if (canvasHost && canvasHost !== this._host) {
        this.attachTo(canvasHost);
        this.finishSurfaceHandoff();
      }
    }
  },

  finishSurfaceHandoff() {
    this.clearHandoffTimer();
    this.handoff = false;
  },

  cancelSurfaceHandoff() {
    this.clearHandoffTimer();
    this.handoff = false;
  },

  clearHandoffTimer() {
    if (this._handoffTimer) {
      globalThis.clearTimeout(this._handoffTimer);
      this._handoffTimer = null;
    }
  },

  async onOpen(element = null, options = {}) {
    if (!element) return;
    if (element.closest(".modal-inner") && !element.__pascalModalCleanup) {
      element.__pascalModalCleanup = setupFloatingSurfaceModalChrome({
        root: element,
        minWidth: 640,
        minHeight: 480,
      });
    }
    const mode = options?.mode === "modal" ? "modal" : "canvas";
    if (mode === "canvas" && !elementVisible(element)) {
      this._pending = { element, options: { ...options, mode } };
      this.startVisibilityWatch();
      return;
    }
    const key = `${mode}:${this.tokenFor(element)}`;
    if (this._openPromise && this._openKey === key) {
      return await this._openPromise;
    }
    const promise = this.openSurface(element, { ...options, mode });
    this._openPromise = promise;
    this._openKey = key;
    try {
      await promise;
    } finally {
      if (this._openPromise === promise) {
        this._openPromise = null;
        this._openKey = "";
      }
    }
  },

  startVisibilityWatch() {
    if (this._watching) return;
    this._watching = true;
    let stable = 0;
    const step = async () => {
      if (!this._watching) return;
      const pending = this._pending;
      if (!pending) {
        this._watching = false;
        return;
      }
      if (!pending.element.isConnected) {
        this._pending = null;
        this._watching = false;
        return;
      }
      const visible = elementVisible(pending.element);
      if (visible) stable += 1;
      else stable = 0;
      if (visible && stable >= 2) {
        this._pending = null;
        this._watching = false;
        void this.onOpen(pending.element, pending.options);
        return;
      }
      await nextFrame();
      if (this._watching) void step();
    };
    void step();
  },

  async openSurface(element = null, options = {}) {
    if (this._iframe && this._host === element && this._iframe.isConnected) {
      return;
    }
    this.loading = true;
    try {
      if (!this._iframe) {
        await this.ensureRuntime();
        await this.waitForEditorRoot();
        this.createIframeElement();
      }
      this.attachTo(element);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      this.error = message;
      this.loading = false;
      toastFrontendError(message, SOURCE_TITLE);
    }
  },

  async ensureRuntime() {
    try {
      await callJsonApi(API, { action: "ensure" });
    } catch (error) {
      // The proxy auto-starts the runtime on first /pascal hit; the polling
      // loop below is the real readiness signal.
      console.warn("Pascal Editor ensure action failed", error);
    }
  },

  async waitForEditorRoot(timeoutMs = 120000) {
    const started = globalThis.Date.now();
    let detail = "";
    while (globalThis.Date.now() - started < timeoutMs) {
      try {
        const response = await fetch(EDITOR_URL, {
          method: "GET",
          credentials: "same-origin",
          headers: { "x-pascal-wait": "1" },
        });
        if (response.ok) {
          const type = response.headers.get("content-type") || "";
          if (type.includes("text/html")) return true;
          detail = `unexpected content-type: ${type || "none"}`;
        } else {
          detail = String(response.status);
        }
      } catch (error) {
        detail = error instanceof Error ? error.message : String(error);
      }
      await sleep(1000);
    }
    throw new Error(`Pascal Editor runtime did not become ready${detail ? ` (${detail})` : ""}.`);
  },

  createIframeElement() {
    const iframe = globalThis.document.createElement("iframe");
    iframe.className = "pascal-editor-frame";
    iframe.title = SOURCE_TITLE;
    iframe.setAttribute("allow", "fullscreen");
    iframe.addEventListener("load", () => this.onFrameLoad(iframe));
    iframe.src = this._restoreUrl || EDITOR_URL;
    this._iframe = iframe;
    this.status = "loading";
  },

  onFrameLoad(iframe) {
    if (iframe && iframe !== this._iframe) return;
    try {
      const href = iframe?.contentWindow?.location?.href;
      if (href && href.includes("/pascal")) this._restoreUrl = href;
    } catch {
      // contentWindow not available yet; keep previous restore url
    }
    this.loading = false;
    this.error = "";
    this.status = "ready";
  },

  attachTo(element) {
    const iframe = this._iframe;
    if (!iframe || !element) return;
    if (iframe.parentElement === element) {
      this._host = element;
      return;
    }
    // appendChild reloads even a connected iframe: it tears down the document
    // and GPU context. An atomic move preserves both during dock/undock.
    // Older browsers retain the reload fallback; first mount also uses append.
    const preserveDocument = iframe.isConnected && element.isConnected
      && typeof element.moveBefore === "function";
    if (preserveDocument) {
      element.moveBefore(iframe, null);
      // An atomic move does not fire load again; retain the readiness state.
      this.loading = this.status !== "ready";
    } else {
      // Capture client-side scene navigation as well as the initial load URL.
      if (iframe.isConnected) {
        try {
          this._restoreUrl = iframe.contentWindow.location.href;
          iframe.src = this._restoreUrl;
        } catch {
          // Keep the existing src when same-origin access is unavailable.
        }
      }
      element.appendChild(iframe);
      this.loading = true;
      this.status = "loading";
    }
    this._host = element;
    if (this.handoff) this.finishSurfaceHandoff();
  },

  async retry() {
    this.error = "";
    this.loading = true;
    try {
      const current = this._host && this._host.isConnected ? this._host : this.findCanvasHost();
      this.destroyIframe();
      await this.ensureRuntime();
      await this.waitForEditorRoot();
      this.createIframeElement();
      if (current && elementVisible(current)) {
        this.attachTo(current);
      } else {
        this.loading = false;
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      this.error = message;
      this.loading = false;
      toastFrontendError(message, SOURCE_TITLE);
    }
  },

  close() {
    this.destroyIframe();
  },

  cleanup(element = null) {
    element?.__pascalModalCleanup?.();
    if (element) delete element.__pascalModalCleanup;
    if (this._pending && this._pending.element === element) {
      this._pending = null;
    }
    if (!this._iframe) return;
    if (element && this._iframe.parentElement === element) {
      if (this.handoff) {
        // Dock handoff in progress: keep the iframe alive on the canvas host
        // when one exists; otherwise it will reload from _restoreUrl.
        const canvasHost = this.findCanvasHost();
        if (canvasHost && canvasHost !== element) {
          this.attachTo(canvasHost);
        }
      } else {
        this.destroyIframe();
      }
    }
  },

  destroyIframe() {
    if (!this._iframe) return;
    const frame = this._iframe;
    try {
      frame.src = "about:blank";
    } catch {
      // ignore unload errors
    }
    if (frame.parentElement) frame.parentElement.removeChild(frame);
    this._iframe = null;
    this._host = null;
    this.loading = false;
    this.status = "idle";
  },
};

export const store = createStore("pascalEditor", model);
