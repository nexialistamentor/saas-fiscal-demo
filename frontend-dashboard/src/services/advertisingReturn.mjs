import { allowedAdvertisingLocation } from "./advertisingMeasurement.mjs";

// These provider return fields are discarded, never trusted as payment proof.
// Purchase authority continues to come exclusively from authenticated recovery.
const PAYMENT_FIELDS = new Set([
  "collection_id", "collection_status", "payment_id", "status",
  "external_reference", "payment_type", "merchant_order_id", "preference_id",
  "site_id", "processing_mode", "merchant_account_id",
]);

export function cleanAdvertisingReturnURL(location) {
  try {
    if (location.hostname !== "solveris.ia.br" || !/^\/mei\/?$/.test(location.pathname) || location.hash) return null;
    const params = new URLSearchParams(location.search);
    const returns = params.getAll("mp_return");
    if (returns.length !== 1 || !/^(success|failure|pending)$/.test(returns[0])) return null;
    let removed = false;
    for (const key of PAYMENT_FIELDS) {
      if (params.has(key)) { params.delete(key); removed = true; }
    }
    if (!removed) return null;
    const search = params.toString();
    if (!allowedAdvertisingLocation({hostname:location.hostname, pathname:location.pathname, hash:"", search})) return null;
    return location.pathname + (search ? "?" + search : "");
  } catch { return null; }
}
