import assert from "node:assert/strict"
import { test } from "node:test"
import { existsSync, readFileSync } from "node:fs"

const clientPath = new URL("../frontend-dashboard/src/services/meiCompetenciaCheckout.js", import.meta.url)
const oferta = {
  offer_code: "mei-das-one-time-company", nome_publico: "MEI por competência",
  vertical: "tax", commercial_model: "one_time", subject_type: "company",
  moeda: "BRL", preco: "39.90", billing_period: null,
  usage_unit: "competence", usage_limit: 1, checkout_mode: "automatic",
}
const scope = { empresaId: 77, competencia: "202609" }
const pending = {
  estado: "pending", competencia: "202609", autorizado: false,
  checkout_idempotency_key: "existing-key", checkout_url: "https://checkout.example.invalid/pending",
}
const paid = { ...pending, estado: "paid", autorizado: true, checkout_url: null }
const response = (status, payload) => ({ status, ok: status >= 200 && status < 300, json: async () => payload })

async function setup(replies) {
  assert.ok(existsSync(clientPath), "Ausente cliente MEI por competência")
  const { criarMeiCompetenciaCheckout } = await import(clientPath)
  const requests = []
  const values = new Map()
  let uuidCalls = 0
  const client = criarMeiCompetenciaCheckout({
    baseUrl: "https://api.example.invalid",
    fetchAutenticado: async (url, options = {}) => {
      requests.push({ url, ...options })
      const reply = replies.shift()
      assert.ok(reply, `Pedido inesperado: ${url}`)
      if (reply instanceof Error) throw reply
      return reply
    },
    storage: {
      getItem: key => values.get(key) ?? null,
      setItem: (key, value) => values.set(key, value),
    },
    randomUUID: () => { uuidCalls++; return "synthetic-new-key" },
  })
  return { client, requests, values, uuidCalls: () => uuidCalls }
}

test("catalogo usa somente oferta avulsa publicada a R$39,90", async () => {
  const { client } = await setup([response(200, [oferta])])
  assert.deepEqual(await client.obterOferta(), oferta)
})

test("oferta ausente nao fabrica produto nem preco", async () => {
  const { client } = await setup([response(200, [])])
  assert.equal(await client.obterOferta(), null)
})

for (const changes of [
  { commercial_model: "monthly" }, { preco: "99.99" },
  { usage_limit: 3 }, { subject_type: "person" }, { moeda: "USD" },
]) {
  test(`catalogo bloqueia termos divergentes: ${JSON.stringify(changes)}`, async () => {
    const { client } = await setup([response(200, [{ ...oferta, ...changes }])])
    await assert.rejects(client.obterOferta())
  })
}

test("recuperacao confirma somente competencia solicitada", async () => {
  const { client, requests } = await setup([response(200, paid)])
  assert.deepEqual(await client.recuperar(scope), paid)
  assert.match(requests[0].url, /\/imposto\/mei\/77\/checkout-recovery\?competencia=202609$/)
  assert.equal(requests[0].method, "GET")
})

for (const changes of [
  { competencia: "202610" }, { autorizado: "true" },
  { estado: "pending", autorizado: true }, { estado: "paid", autorizado: false },
  { estado: "unknown" }, { checkout_url: "javascript:alert(1)" },
]) {
  test(`recuperacao recusa resposta divergente: ${JSON.stringify(changes)}`, async () => {
    const { client } = await setup([response(200, { ...paid, ...changes })])
    await assert.rejects(client.recuperar(scope))
  })
}

test("identidade e competencia invalidas nao fazem pedidos", async () => {
  const { client, requests } = await setup([])
  for (const changes of [{ empresaId: 0 }, { empresaId: "77" }, { competencia: "202613" }]) {
    await assert.rejects(client.recuperar({ ...scope, ...changes }))
  }
  assert.equal(requests.length, 0)
})

test("compra paga nao cria intencao, checkout nem nova chave", async () => {
  const { client, requests, uuidCalls } = await setup([response(200, paid)])
  assert.deepEqual(await client.iniciar({ ...scope, oferta: null }), paid)
  assert.equal(requests.length, 1)
  assert.equal(uuidCalls(), 0)
})

test("compra pendente retoma URL original sem nova cobranca", async () => {
  const { client, requests, uuidCalls } = await setup([response(200, pending)])
  assert.deepEqual(await client.iniciar({ ...scope, oferta }), pending)
  assert.equal(requests.length, 1)
  assert.equal(uuidCalls(), 0)
})

test("409, 503 e perda de sessao nunca se tornam compra nova", async () => {
  for (const reply of [response(409, {}), response(503, {}), null]) {
    const { client, requests, uuidCalls } = await setup([reply])
    await assert.rejects(client.iniciar({ ...scope, oferta }))
    assert.equal(requests.length, 1)
    assert.equal(uuidCalls(), 0)
  }
})

test("nova compra persiste intencao antes do checkout com a mesma chave", async () => {
  const { client, requests, values } = await setup([
    response(404, {}), response(204, null),
    response(200, { checkout_url: "https://checkout.example.invalid/new" }),
  ])
  const result = await client.iniciar({ ...scope, oferta })
  assert.equal(result.autorizado, false)
  assert.match(requests[1].url, /\/mei\/77\/checkout-intents$/)
  assert.match(requests[2].url, /\/checkout\/one-time$/)
  assert.equal(requests[1].headers["Idempotency-Key"], requests[2].headers["Idempotency-Key"])
  assert.deepEqual(JSON.parse(requests[1].body), { competencia: "202609", offer_code: oferta.offer_code })
  assert.deepEqual(JSON.parse(requests[2].body), { empresa_id: 77, offer_code: oferta.offer_code })
  assert.ok([...values.values()].includes("synthetic-new-key"))
})

test("falha de intencao nunca chama gateway", async () => {
  const { client, requests } = await setup([response(404, {}), response(409, {})])
  await assert.rejects(client.iniciar({ ...scope, oferta }))
  assert.equal(requests.length, 2)
})

test("nova tentativa reutiliza chave apos resposta incerta do checkout", async () => {
  const { client, requests, uuidCalls } = await setup([
    response(404, {}), response(204, null), new Error("network"),
    response(404, {}), response(204, null), response(200, { checkout_url: pending.checkout_url }),
  ])
  await assert.rejects(client.iniciar({ ...scope, oferta }))
  await client.iniciar({ ...scope, oferta })
  assert.equal(requests[2].headers["Idempotency-Key"], requests[5].headers["Idempotency-Key"])
  assert.equal(uuidCalls(), 1)
})

test("sem oferta nao existe checkout novo", async () => {
  const { client, requests, uuidCalls } = await setup([response(404, {})])
  await assert.rejects(client.iniciar({ ...scope, oferta: null }))
  assert.equal(requests.length, 1)
  assert.equal(uuidCalls(), 0)
})

test("checkout recusa URL sem HTTPS", async () => {
  const { client } = await setup([
    response(404, {}), response(204, null), response(200, { checkout_url: "http://checkout.example.invalid" }),
  ])
  await assert.rejects(client.iniciar({ ...scope, oferta }))
})

test("tela preserva checkout do relatorio e explica preco separado do tributo", () => {
  const source = readFileSync(new URL("../frontend-dashboard/src/App.jsx", import.meta.url), "utf8")
  assert.match(source, /tax-report-one-time-company/)
  assert.match(source, /useMeiCompetenciaCheckout/)
  assert.match(source, /O tributo do DAS é pago separadamente/)
  assert.match(source, /!compraDasAutorizada/)
})
