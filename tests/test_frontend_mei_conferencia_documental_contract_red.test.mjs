import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { criarLeitorConferenciaDocumentalMei } from '../frontend-dashboard/src/services/meiConferenciaDocumental.js'

const scope = { empresaId: 77, anoCalendario: 2026, enabled: true }
const payload = (empresa = 77, ano = 2026) => ({
  empresa_id: empresa, ano_calendario: ano, documentos_para_revisao: [],
  documentos_sem_periodo: [], receitas_confirmadas: [], total_receita_confirmada: null,
  completude_anual_comprovada: false, duplicatas_ignoradas: 0,
})
const ok = body => ({ ok: true, json: async () => body })
function leitor(fetchAutenticado) {
  const states = []
  return { ...criarLeitorConferenciaDocumentalMei({ baseUrl: 'https://api.test',
    fetchAutenticado, onState: state => states.push(state) }), states }
}
test('GET autenticado por empresa e ano, sem cache ou efeitos comerciais', async () => {
  const calls = []
  const r = leitor(async (url, options) => { calls.push({ url, options }); return ok(payload()) })
  await r.carregar(scope)
  assert.equal(calls.length, 1)
  assert.equal(calls[0].url, 'https://api.test/dashboard/mei/77/conferencia-documental?ano_calendario=2026')
  assert.equal(calls[0].options.method, 'GET')
  assert.equal(calls[0].options.cache, 'no-store')
  assert.ok(calls[0].options.signal)
  assert.deepEqual(r.states.at(-1).resultado, payload())
  assert.equal(r.states.at(-1).erro, '')
})
test('escopo inválido ou desabilitado não faz pedidos', async () => {
  const r = leitor(() => { throw new Error('pedido proibido') })
  for (const extra of [{ empresaId: '77' }, { empresaId: 0 }, { anoCalendario: '2026' },
    { anoCalendario: 1899 }, { anoCalendario: 10000 }, { enabled: false }]) {
    await r.carregar({ ...scope, ...extra })
    assert.equal(r.states.at(-1).resultado, null)
    assert.equal(r.states.at(-1).loading, false)
    assert.equal(r.states.at(-1).erro, '')
  }
})
for (const status of [401, 403, 503]) {
  test(`erro ${status} remove resultado anterior`, async () => {
    let fail = false
    const r = leitor(async () => fail ? { ok: false, status } : ok(payload()))
    await r.carregar(scope); fail = true; await r.carregar(scope)
    assert.equal(r.states.at(-1).resultado, null)
    assert.ok(r.states.at(-1).erro)
  })
}
test('contrato divergente nunca vira receita ou inventário válido', async () => {
  for (const change of [{ empresa_id: 78 }, { ano_calendario: 2025 },
    { completude_anual_comprovada: true }, { total_receita_confirmada: '0.00' },
    { receitas_confirmadas: [{}] }, { documentos_para_revisao: [{}] },
    { documentos_sem_periodo: [{}] }, { duplicatas_ignoradas: -1 }]) {
    const r = leitor(async () => ok({ ...payload(), ...change }))
    await r.carregar(scope)
    assert.equal(r.states.at(-1).resultado, null); assert.ok(r.states.at(-1).erro)
  }
})
test('rede e JSON inválido falham sem resultado', async () => {
  for (const fetcher of [async () => { throw new Error('network') },
    async () => ({ ok: true, json: async () => { throw new Error('json') } })]) {
    const r = leitor(fetcher); await r.carregar(scope)
    assert.equal(r.states.at(-1).resultado, null); assert.ok(r.states.at(-1).erro)
  }
})
test('troca de ano descarta resposta antiga mesmo sem abort do transporte', async () => {
  const pending = []
  const r = leitor((url, options) => new Promise(resolve => pending.push({ options, resolve })))
  const old = r.carregar(scope)
  const current = r.carregar({ ...scope, anoCalendario: 2025 })
  assert.equal(pending[0].options.signal.aborted, true)
  pending[1].resolve(ok(payload(77, 2025))); await current
  pending[0].resolve(ok(payload())); await old
  assert.equal(r.states.at(-1).resultado.ano_calendario, 2025)
})
test('troca de empresa e desabilitação invalidam resposta em curso', async () => {
  const pending = []
  const r = leitor(() => new Promise(resolve => pending.push(resolve)))
  const old = r.carregar(scope)
  const next = r.carregar({ ...scope, empresaId: 78 })
  pending[1](ok(payload(78))); await next
  pending[0](ok(payload())); await old
  assert.equal(r.states.at(-1).resultado.empresa_id, 78)
  const inFlight = r.carregar(scope)
  await r.carregar({ ...scope, enabled: false })
  pending[2](ok(payload())); await inFlight
  assert.equal(r.states.at(-1).resultado, null)
})
test('tela ligada somente ao MEI existente, sem HTML injetado', () => {
  const app = readFileSync(new URL('../frontend-dashboard/src/App.jsx', import.meta.url), 'utf8')
  const component = readFileSync(new URL('../frontend-dashboard/src/components/MeiConferenciaDocumental.jsx', import.meta.url), 'utf8')
  assert.match(app, /import MeiConferenciaDocumental/)
  assert.match(app, /isExistingMei\s*&&\s*\(\s*<MeiConferenciaDocumental\s+key=\{idPerfil\}\s+empresaId=\{idPerfil\}/)
  assert.match(component, /criarLeitorConferenciaDocumentalMei/)
  assert.match(component, /Ano de referência/)
  assert.match(component, /não comprova a receita anual completa/)
  assert.doesNotMatch(component, /dangerouslySetInnerHTML/)
})
