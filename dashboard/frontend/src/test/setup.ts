import "@testing-library/jest-dom";

// Node 20+'s built-in (experimental) `localStorage` global gets installed before jsdom's
// and is a broken stub in this environment (`--localstorage-file` has no valid path here),
// which shadows jsdom's real implementation for every test. Replace it with a real in-memory
// Storage so `localStorage.getItem/setItem` work as they do in an actual browser — this is a
// test-environment shim only, app code is untouched.
class MemoryStorage implements Storage {
  private store = new Map<string, string>();
  get length() {
    return this.store.size;
  }
  clear() {
    this.store.clear();
  }
  getItem(key: string) {
    return this.store.has(key) ? this.store.get(key)! : null;
  }
  key(index: number) {
    return Array.from(this.store.keys())[index] ?? null;
  }
  removeItem(key: string) {
    this.store.delete(key);
  }
  setItem(key: string, value: string) {
    this.store.set(key, String(value));
  }
}

if (typeof globalThis.localStorage?.setItem !== "function") {
  Object.defineProperty(globalThis, "localStorage", {
    value: new MemoryStorage(),
    configurable: true,
    writable: true,
  });
}

// jsdom has no ResizeObserver implementation, but cmdk (the ⌘K command palette) uses one
// internally to measure its list for virtualization/sizing. Without this stub, mounting
// CommandPalette in tests throws "ResizeObserver is not defined" — a jsdom environment gap,
// not an app bug (the browser has ResizeObserver natively).
if (typeof globalThis.ResizeObserver === "undefined") {
  class StubResizeObserver implements ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  globalThis.ResizeObserver = StubResizeObserver;
}

// jsdom also doesn't implement Element.scrollIntoView, which cmdk calls when the
// keyboard-selected item changes. No-op stub, same rationale as ResizeObserver above.
if (typeof Element.prototype.scrollIntoView !== "function") {
  Element.prototype.scrollIntoView = () => {};
}

// AppShell auto-opens HelpGuide the first time `atlas-guide-seen` is unset in localStorage
// (a one-time hint for real first-time users). A fresh in-memory localStorage per test file
// means every test would otherwise see that "first visit" state, and Radix's Dialog marks
// the rest of the page aria-hidden while HelpGuide is open — hiding the sidebar nav from
// role-based queries. Tests want the steady-state app (guide already dismissed), so seed the
// flag once here, matching a returning user.
localStorage.setItem("atlas-guide-seen", "1");

// jsdom ships its own AbortController/AbortSignal polyfill, but the global `Request` here is
// Node's own (undici-backed) — jsdom doesn't implement fetch's Request at all, so it leaks
// through unpatched. Node's Request does a strict internal-slot brand check on `init.signal`
// that only accepts signals from ITS OWN AbortController, so a signal built from jsdom's
// AbortController (what react-router's data router uses internally to build request objects
// for navigation) is rejected with "Expected signal to be an instance of AbortSignal" even
// though `instanceof AbortSignal` is true. This is a realm mismatch between two different
// polyfills sharing one globalThis, not an app bug. Work around it by constructing requests
// without a foreign signal when the native check rejects it — navigation abort-on-interrupt
// is a perf optimization the data router doesn't require to function correctly in tests.
const NativeRequest = globalThis.Request;
if (NativeRequest) {
  class PatchedRequest extends NativeRequest {
    constructor(input: RequestInfo | URL, init?: RequestInit) {
      try {
        super(input, init);
      } catch (e) {
        if (init?.signal && e instanceof TypeError && /signal/i.test(e.message)) {
          const rest = { ...init };
          delete rest.signal;
          super(input, rest);
        } else {
          throw e;
        }
      }
    }
  }
  globalThis.Request = PatchedRequest as unknown as typeof Request;
}
