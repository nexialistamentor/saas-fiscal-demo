import { createMeasurement, CONSENT_KEY, allowedAdvertisingLocation } from "./advertisingMeasurement.mjs";
import { cleanAdvertisingReturnURL } from "./advertisingReturn.mjs";

export const PIXEL_ID = "1496002532350868";
let initialized = false;
let pageSent = false;
let owned = false;

function cleanPage() {
  if (allowedAdvertisingLocation(window.location)) return true;
  const clean = cleanAdvertisingReturnURL(window.location);
  if (!clean) return false;
  try {
    // Remove provider identifiers before the Meta runtime reads the page URL.
    // Keep mp_return and history state so application recovery is unchanged.
    window.history.replaceState(window.history.state, "", clean);
    return allowedAdvertisingLocation(window.location);
  } catch { return false; }
}
function dispatch(event, data = {}, eventID) {
  try {
    if (!measurement.allowed() || !cleanPage()) return false;
    // Do not adopt another integration or enable automatic matching.
    if (!initialized) {
      if (window.fbq) return false;
      const queue = function (...args) {
        if (queue.callMethod) queue.callMethod(...args);
        else queue.queue.push(args);
      };
      queue.queue = [];
      queue.loaded = true;
      queue.version = "2.0";
      queue.push = queue;
      window.fbq = queue;
      window._fbq = queue;
      owned = true;
      queue("consent", "grant");
      queue("set", "autoConfig", false, PIXEL_ID);
      queue("init", PIXEL_ID);
      const script = document.createElement("script");
      script.async = true;
      script.src = "https://connect.facebook.net/en_US/fbevents.js";
      script.referrerPolicy = "no-referrer";
      document.head.appendChild(script);
      initialized = true;
    }
    if (!owned) return false;
    window.fbq("trackSingle", PIXEL_ID, event, data, ...(eventID ? [{ eventID }] : []));
    return true; // Queued, not proof of receipt. Validate in Meta Test Events.
  } catch { return false; }
}
export const measurement = createMeasurement({
  storage: {
    getItem: key => window.localStorage.getItem(key),
    setItem: (key, value) => window.localStorage.setItem(key, value),
    removeItem: key => window.localStorage.removeItem(key),
  },
  send: dispatch,
  digest: async key => {
    const hash = await window.crypto.subtle.digest("SHA-256", new TextEncoder().encode(key));
    return "solveris-" + Array.from(new Uint8Array(hash), b => b.toString(16).padStart(2, "0")).join("");
  },
});
export function pageView() {
  if (!pageSent && dispatch("PageView")) pageSent = true;
}
export function chooseAdvertising(accepted) {
  const saved = measurement.choose(accepted);
  try {
    if (!accepted && owned) {
      window.fbq("consent", "revoke");
      // Reload removes the third-party runtime; keep app state/server data untouched.
      if (saved) window.location.reload();
    } else if (accepted) {
      if (owned) window.fbq("consent", "grant");
      pageView();
    }
  } catch { /* optional */ }
  return saved;
}
export function hasAdvertisingChoice() {
  try { return typeof JSON.parse(window.localStorage.getItem(CONSENT_KEY))?.accepted === "boolean"; }
  catch { return false; }
}

