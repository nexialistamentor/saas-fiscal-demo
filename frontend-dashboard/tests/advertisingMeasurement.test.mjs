import test from "node:test";
import assert from "node:assert/strict";
import { createMeasurement } from "../src/services/advertisingMeasurement.mjs";
function fixture(overrides = {}) {
  const map = new Map(); const events = [];
  const m = createMeasurement({
    storage: {getItem:k=>map.get(k),setItem:(k,v)=>map.set(k,v),removeItem:k=>map.delete(k)},
    digest:async k=>"hash-"+k, send:async (...args)=>{events.push(args);return true;}, now:()=>1000,
    ...overrides,
  });
  return {m, events, map};
}
const offer = {offer_code:"mei-das-one-time-company",preco:"39.90",moeda:"BRL"};
const pending = {estado:"pending",autorizado:false,checkout_url:"https://payment.example/",checkout_idempotency_key:"attempt-a"};
const paid = {...pending,estado:"paid",autorizado:true,checkout_url:null};
test("no consent sends nothing and stores no pending purchase", async()=>{
  const {m,events,map}=fixture(); await m.pending(pending,offer);await m.paid(paid);
  assert.equal(events.length,0);assert.equal(map.size,0);
});
test("historical paid recovery cannot become a new conversion",async()=>{
  const {m,events}=fixture();m.choose(true);await m.paid(paid);assert.equal(events.length,0);
});
test("only confirmed payment counts and refresh is deduplicated",async()=>{
  const {m,events}=fixture();m.choose(true);await m.pending(pending,offer);
  await m.paid(pending);await m.paid({...paid,autorizado:false});assert.equal(events.length,0);
  await Promise.all([m.paid(paid),m.paid(paid)]);await m.paid(paid);
  assert.equal(events.length,1);assert.deepEqual(events[0],["Purchase",{value:39.9,currency:"BRL"},"hash-attempt-a"]);
});
test("consent withdrawal erases pending attribution",async()=>{
  const {m,events}=fixture();m.choose(true);await m.pending(pending,offer);m.choose(false);m.choose(true);
  await m.paid(paid);assert.equal(events.length,0);
});
test("other payment identity and unavailable price never count",async()=>{
  const {m,events}=fixture();m.choose(true);await m.pending(pending,{...offer,preco:"99.00"});
  await m.paid(paid);await m.pending(pending,offer);await m.paid({...paid,checkout_idempotency_key:"other"});
  assert.equal(events.length,0);
});
test("storage, hashing and transport failure never reject business callers",async()=>{
  for (const overrides of [
    {storage:{getItem(){throw Error();},setItem(){throw Error();},removeItem(){throw Error();}}},
    {digest:async()=>{throw Error();}},
    {send:async()=>{throw Error();}},
  ]) {
    const {m}=fixture(overrides);m.choose(true);await assert.doesNotReject(m.pending(pending,offer));
    await assert.doesNotReject(m.paid(paid));
  }
});
test("expired pending checkout does not count",async()=>{
  let clock=1000; const {m,events}=fixture({now:()=>clock});m.choose(true);await m.pending(pending,offer);
  clock+=8*24*60*60*1000;await m.paid(paid);assert.equal(events.length,0);
});
