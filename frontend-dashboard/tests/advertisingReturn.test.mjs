import test from "node:test";
import assert from "node:assert/strict";
import { cleanAdvertisingReturnURL } from "../src/services/advertisingReturn.mjs";

const location = search => new URL("https://solveris.ia.br/mei" + search);
test("documented payment return identifiers are removed before advertising", () => {
  const result = cleanAdvertisingReturnURL(location("?mp_return=success&collection_id=123&collection_status=approved&payment_id=123&status=approved&external_reference=private-order&payment_type=credit_card&merchant_order_id=456&preference_id=private-preference&site_id=MLB&processing_mode=aggregator&merchant_account_id=null&utm_source=meta"));
  assert.equal(result, "/mei?mp_return=success&utm_source=meta");
  assert.doesNotMatch(result, /123|456|private|approved/);
});
test("failure and pending returns can be cleaned but do not establish payment", () => {
  for (const status of ["failure", "pending"]) {
    assert.equal(cleanAdvertisingReturnURL(location("?mp_return=" + status + "&payment_id=123")), "/mei?mp_return=" + status);
  }
});
test("unknown private keys and unrelated routes remain blocked", () => {
  for (const url of [
    "https://solveris.ia.br/mei?mp_return=success&cpf=123",
    "https://solveris.ia.br/mei?mp_return=success&token=private",
    "https://solveris.ia.br/mei?payment_id=123",
    "https://solveris.ia.br/mei?mp_return=success&mp_return=failure&payment_id=123",
    "https://solveris.ia.br/mei?mp_return=success&payment_id=123#private",
    "https://other.example/mei?mp_return=success&payment_id=123",
    "https://solveris.ia.br/enterprise?mp_return=success&payment_id=123",
  ]) assert.equal(cleanAdvertisingReturnURL(new URL(url)), null);
});
