import test from "node:test";
import assert from "node:assert/strict";
import { webcrypto } from "node:crypto";

test("real adapter queues one confirmed purchase with sanitized URL using a simulated transport", async () => {
  const previousWindow = globalThis.window, previousDocument = globalThis.document;
  const storage = new Map(), scripts = [];
  globalThis.window = {
    location: new URL("https://solveris.ia.br/mei?utm_source=meta"),
    crypto: webcrypto,
    localStorage: {
      getItem: key => storage.get(key) ?? null,
      setItem: (key, value) => storage.set(key, value),
      removeItem: key => storage.delete(key),
    },
    history: {state:{preserved:true}, replaceState(state, title, path) {
      assert.equal(state, this.state);
      globalThis.window.location = new URL(path, "https://solveris.ia.br");
    }},
  };
  globalThis.document = {createElement: () => ({}), head:{appendChild: element => scripts.push(element)}};
  try {
    const adapter = await import("../src/services/metaAdvertising.js?adapter-contract");
    adapter.pageView();
    assert.equal(scripts.length, 0);
    assert.equal(adapter.chooseAdvertising(true), true);
    assert.equal(scripts.length, 1);
    const pending = {estado:"pending",autorizado:false,checkout_url:"https://www.mercadopago.com.br/checkout",checkout_idempotency_key:"synthetic-order"};
    await adapter.measurement.pending(pending, {offer_code:"mei-das-one-time-company",preco:"39.90",moeda:"BRL"});
    window.location = new URL("https://solveris.ia.br/mei?mp_return=success&payment_id=123&external_reference=private-order");
    const paid = {...pending,estado:"paid",autorizado:true,checkout_url:null};
    await adapter.measurement.paid(paid);
    await adapter.measurement.paid(paid);
    const purchases = window.fbq.queue.filter(args => args[0] === "trackSingle" && args[2] === "Purchase");
    assert.equal(purchases.length, 1);
    assert.equal(purchases[0][1], "1496002532350868");
    assert.deepEqual(purchases[0][3], {value:39.90,currency:"BRL"});
    assert.match(purchases[0][4].eventID, /^solveris-[a-f0-9]{64}$/);
    assert.equal(window.location.href, "https://solveris.ia.br/mei?mp_return=success");
    assert.doesNotMatch(JSON.stringify(purchases), /synthetic-order|private-order|payment_id/);
  } finally {
    globalThis.window = previousWindow;
    globalThis.document = previousDocument;
  }
});
