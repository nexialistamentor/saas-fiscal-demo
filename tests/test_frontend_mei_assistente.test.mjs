import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { criarAssistenteMei, prepararPerguntaMei } from '../frontend-dashboard/src/services/meiAssistente.js'
const scope = { empresaId: 77, enabled: true, tema: 'limite', ano: '2026' }
const limite = { resposta: 'Limite normativo.', analysis_type: 'mei_limit', requires_payment: false }
function harness(fetcher) { const states = []; const client = criarAssistenteMei({ baseUrl: 'https://api.example', fetchAutenticado: fetcher, onState: s => states.push(s) }); return { states, client } }
const ok = data => ({ ok: true, json: async () => data })
test('gera somente perguntas guiadas sem identidade fiscal ou texto livre', () => {
  assert.equal(prepararPerguntaMei(scope).pergunta, 'Qual o limite do MEI em 2026?')
  assert.equal(prepararPerguntaMei({ tema: 'das', ano: '2026', atividade: 'servicos', faturamento: '6000,25', texto: 'encerrar empresa' }).pergunta,
    'Como MEI de serviços em 2026, faturando R$ 6000.25 por mês, quanto pago de DAS?')
})
for (const fields of [{ ano: '' }, { ano: '2026 abrir' }, { tema: 'abertura' }, { tema: 'das', atividade: 'encerrar', faturamento: '6000' }, { tema: 'das', atividade: 'servicos', faturamento: '0' }, { tema: 'das', atividade: 'servicos', faturamento: '6000 abrir' }]) {
  test(`entrada inválida não faz pedido: ${JSON.stringify(fields)}`, async () => {
    let calls = 0; const h = harness(async () => { calls++; return ok(limite) })
    await h.client.consultar({ ...scope, ...fields }); assert.equal(calls, 0); assert.ok(h.states.at(-1).erro)
  })
}
test('escopo inválido/desabilitado não faz pedido', async () => {
  const h = harness(() => { throw Error('não chamar') })
  for (const patch of [{ empresaId: 0 }, { empresaId: '77' }, { enabled: false }]) await h.client.consultar({ ...scope, ...patch })
  assert.equal(h.states.at(-1).resultado, null)
})
test('POST autenticado no contrato existente, sem preço, compra ou empresa enviada', async () => {
  let pedido; const h = harness(async (...args) => { pedido = args; return ok(limite) })
  await h.client.consultar(scope)
  assert.equal(pedido[0], 'https://api.example/perguntar'); assert.equal(pedido[1].method, 'POST')
  assert.equal(pedido[1].cache, 'no-store'); assert.deepEqual(JSON.parse(pedido[1].body), { pergunta: 'Qual o limite do MEI em 2026?' })
  assert.equal(h.states.at(-1).resultado.resposta, limite.resposta)
})
for (const payload of [{ ...limite, requires_payment: true }, { ...limite, analysis_type: 'tax_recovery' }, { ...limite, resposta: '' }, { ...limite, bloqueado: 'true' }, { ...limite, bloqueado: true }]) {
  test(`contrato divergente falha fechado: ${JSON.stringify(payload)}`, async () => {
    const h = harness(async () => ok(payload)); await h.client.consultar(scope)
    assert.ok(h.states.at(-1).erro); assert.equal(h.states.at(-1).resultado, null)
  })
}
test('DAS exige modo estimativa, preserva bloqueio normativo', async () => {
  const fields = { ...scope, tema: 'das', atividade: 'servicos', faturamento: '6000' }
  for (const modo of [null, 'decisao_definitiva', 'estimativa']) {
    const h = harness(async () => ok({ ...limite, analysis_type: 'mei_tax', modo }))
    await h.client.consultar(fields); assert.equal(Boolean(h.states.at(-1).erro), modo !== 'estimativa')
  }
  const h = harness(async () => ok({ ...limite, analysis_type: 'mei_tax', bloqueado: true, estado_l3: 'bloqueado', tipo_bloqueio: 'AUTORIDADE_NORMATIVA_MEI_INDISPONIVEL' }))
  await h.client.consultar(fields); assert.equal(h.states.at(-1).resultado.bloqueado, true)
})
for (const mode of ['401', '403', '503', 'network', 'payload', 'session']) {
  test(`erro ${mode} não mostra resposta anterior`, async () => {
    let failed = false
    const h = harness(async () => { if (!failed) return ok(limite); if (mode === 'session') return null; if (mode === 'network') throw Error('network'); if (mode === 'payload') return { ok: true, json: async () => { throw Error('json') } }; return { ok: false, status: Number(mode) } })
    await h.client.consultar(scope); failed = true; await h.client.consultar(scope)
    assert.ok(h.states.at(-1).erro); assert.equal(h.states.at(-1).resultado, null)
  })
}
test('troca de empresa cancela e ignora transporte antigo que não respeita abort', async () => {
  let finish; let signal; let n = 0
  const h = harness(async (_, options) => { if (++n === 1) { signal = options.signal; return new Promise(resolve => { finish = resolve }) }; return ok({ ...limite, resposta: 'nova' }) })
  const old = h.client.consultar(scope)
  await h.client.consultar({ ...scope, empresaId: 78 }); finish(ok({ ...limite, resposta: 'antiga' })); await old
  assert.equal(signal.aborted, true); assert.equal(h.states.at(-1).resultado.resposta, 'nova')
})
test('limpar invalida resposta em curso', async () => {
  let finish; const h = harness(() => new Promise(resolve => { finish = resolve }))
  const old = h.client.consultar(scope); h.client.limpar(); finish(ok(limite)); await old
  assert.equal(h.states.at(-1).resultado, null); assert.equal(h.states.at(-1).loading, false)
})
test('UI é isolada no MEI ativo, escapa texto e distingue estimativa', () => {
  const app = readFileSync(new URL('../frontend-dashboard/src/App.jsx', import.meta.url), 'utf8')
  assert.match(app, /usuario && tipoPerfil === "mei" && perfilAtual.status_empresa === "ativa"\s*&& Number.isInteger\(idPerfil\) && idPerfil > 0 && \(\s*<MeiAssistente key=\{idPerfil\}/)
  const ui = readFileSync(new URL('../frontend-dashboard/src/components/MeiAssistente.jsx', import.meta.url), 'utf8')
  assert.match(ui, /não comprova regularidade fiscal/); assert.match(ui, /não é DAS oficial/)
  assert.doesNotMatch(ui, /dangerouslySetInnerHTML|checkout|emitirDas|textarea/)
})
