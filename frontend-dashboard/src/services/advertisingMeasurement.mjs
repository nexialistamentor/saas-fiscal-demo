// Advertising is optional and never participates in payment authorization.
export const CONSENT_KEY = "solveris.advertising.v1";
const PENDING_KEY = "solveris.advertising.pending.v1";
const SENT_KEY = "solveris.advertising.sent.v1";
const MAX_AGE = 7 * 24 * 60 * 60 * 1000;

export function createMeasurement({ storage, send, digest, now = Date.now }) {
  const busy = new Set();
  let choice;
  const read = key => { try { return JSON.parse(storage.getItem(key)); } catch { return null; } };
  const write = (key, value) => { try { storage.setItem(key, JSON.stringify(value)); return true; } catch { return false; } };
  const allowed = () => choice ?? (read(CONSENT_KEY)?.accepted === true);
  const clearPending = () => { try { storage.removeItem(PENDING_KEY); } catch { /* optional */ } };
  return {
    allowed,
    choose(accepted) {
      choice = accepted === true;
      const saved = write(CONSENT_KEY, { accepted: choice, at: now() });
      if (!saved) choice = false;
      if (!accepted) clearPending();
      return saved;
    },
    async pending(purchase, offer) {
      try {
        if (!allowed() || purchase?.estado !== "pending" || purchase.autorizado !== false
          || typeof purchase.checkout_url !== "string"
          || offer?.offer_code !== "mei-das-one-time-company"
          || offer.preco !== "39.90" || offer.moeda !== "BRL"
          || typeof purchase.checkout_idempotency_key !== "string") return;
        write(PENDING_KEY, { attempt: purchase.checkout_idempotency_key, at: now(), value: 39.90 });
      } catch { /* Analytics must never block checkout. */ }
    },
    async paid(purchase) {
      try {
        if (!allowed() || purchase?.estado !== "paid" || purchase.autorizado !== true
          || purchase.checkout_url !== null || typeof purchase.checkout_idempotency_key !== "string") return;
        const id = await digest(purchase.checkout_idempotency_key);
        const pending = read(PENDING_KEY);
        if (!allowed() || !pending || pending.attempt !== purchase.checkout_idempotency_key || now() - pending.at > MAX_AGE
          || now() < pending.at || read(SENT_KEY)?.includes(id) || busy.has(id)) return;
        busy.add(id);
        try {
          const accepted = await send("Purchase", { value: pending.value, currency: "BRL" }, id);
          if (accepted && allowed()) {
            const ids = read(SENT_KEY);
            write(SENT_KEY, [...(Array.isArray(ids) ? ids : []), id].slice(-100));
            clearPending();
          }
        } finally { busy.delete(id); }
      } catch { /* Analytics must never block purchase recovery. */ }
    },
  };
}

export function allowedAdvertisingLocation(location) {
  if (location.hostname !== "solveris.ia.br" || !/^\/mei\/?$/.test(location.pathname) || location.hash) return false;
  for (const [key, value] of new URLSearchParams(location.search)) {
    if (key === "fbclid" && /^[A-Za-z0-9_-]{1,512}$/.test(value)) continue;
    if (/^utm_(source|medium|campaign|content|term)$/.test(key) && /^[A-Za-z0-9 _|.-]{1,160}$/.test(value)) continue;
    if (key === "mp_return" && /^(success|failure|pending)$/.test(value)) continue;
    return false;
  }
  return true;
}
