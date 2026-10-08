import test from 'node:test'
import assert from 'node:assert/strict'
import { criarLeitorReceitasInformadasMei } from '../frontend-dashboard/src/services/meiReceitasInformadas.js'

const scope = { empresaId: 1, anoCalendario: 2026, enabled: true }
const identity = '11111111-1111-4111-8111-111111111111'
function body() {
  return {
    empresa_id: 1, ano_calendario: 2026, completude_anual_comprovada: false,
    total_receitas_incluidas: '100.10',
    totais_por_categoria: { comercio_industria: '0.00', servicos: '100.10' },
    totais_por_origem: { documento: '0.00', informada_sem_nota: '100.10' },
    meses: Array.from({ length: 12 }, (_, i) => ({ mes: i + 1,
      estado: i === 0 ? 'parcial' : 'nao_informado',
      total_receitas_incluidas: i === 0 ? '100.10' : null })),
    receitas_incluidas: [{ identidade_receita: identity, empresa_id: 1,
      data_receita: '2026-01-10', valor: '100.10', categoria: 'servicos',
      origem: 'informada_sem_nota', estado: 'vigente' }],
    pendencias: [], duplicatas_ignoradas: 0,
  }
}
const response = value => ({ ok: true, json: async () => value })
function client(fetchAutenticado) {
  const states = []
  const reader = criarLeitorReceitasInformadasMei({ baseUrl: 'https://example.invalid',
    fetchAutenticado, onState: state => states.push(state) })
  return { reader, states }
}
test('GET autenticado, sem cache; preserva centavos e meses desconhecidos', async () => {
  const calls = []
  const { reader, states } = client(async (...args) => { calls.push(args); return response(body()) })
  await reader.carregar(scope)
  assert.equal(calls.length, 1)
  assert.equal(calls[0][0], 'https://example.invalid/dashboard/mei/1/receitas-informadas?ano_calendario=2026')
  assert.equal(calls[0][1].method, 'GET')
  assert.equal(calls[0][1].cache, 'no-store')
  assert.ok(calls[0][1].signal instanceof AbortSignal)
  assert.deepEqual(states.at(-1).resultado, body())
  assert.equal(states.at(-1).erro, '')
})
test('escopo inválido ou desabilitado não faz pedido', async () => {
  let calls = 0
  const { reader, states } = client(async () => { calls++; return response(body()) })
  for (const changes of [{ enabled: false }, { empresaId: 0 }, { empresaId: true },
    { anoCalendario: 1899 }, { anoCalendario: '2026' }]) {
    await reader.carregar({ ...scope, ...changes })
    assert.equal(states.at(-1).resultado, null)
  }
  assert.equal(calls, 0)
})
for (const status of [401, 403, 503]) test(`erro ${status} remove resultado anterior`, async () => {
  let fail = false
  const { reader, states } = client(async () => fail ? { ok: false, status } : response(body()))
  await reader.carregar(scope)
  fail = true
  await reader.carregar(scope)
  assert.equal(states.at(-1).resultado, null)
  assert.ok(states.at(-1).erro)
})
const invalid = [
  x => { x.empresa_id = 2 }, x => { x.ano_calendario = 2025 },
  x => { x.completude_anual_comprovada = true }, x => { x.total_receitas_incluidas = '100.20' },
  x => { x.total_receitas_incluidas = 100.10 }, x => { x.totais_por_categoria.servicos = '99.10' },
  x => { x.totais_por_origem.documento = '100.10' }, x => { x.meses[1].total_receitas_incluidas = '0.00' },
  x => { x.meses[1].mes = 1 }, x => { x.receitas_incluidas[0].empresa_id = 2 },
  x => { x.receitas_incluidas[0].data_receita = '2025-01-10' },
  x => { x.receitas_incluidas[0].origem = 'documento' },
  x => { x.receitas_incluidas[0].estado = 'pendente_revisao' },
  x => { x.receitas_incluidas.push({ ...x.receitas_incluidas[0] }) },
  x => { x.pendencias = [x.receitas_incluidas[0]] }, x => { x.duplicatas_ignoradas = -1 },
]
for (const [i, mutate] of invalid.entries()) test(`contrato divergente ${i + 1} falha sem total`, async () => {
  const value = body(); mutate(value)
  const { reader, states } = client(async () => response(value))
  await reader.carregar(scope)
  assert.equal(states.at(-1).resultado, null)
  assert.ok(states.at(-1).erro)
})
test('ano sem registros preserva meses desconhecidos; não certifica receita zero', async () => {
  const value = body()
  value.receitas_incluidas = []; value.total_receitas_incluidas = '0.00'
  value.totais_por_categoria.servicos = '0.00'; value.totais_por_origem.informada_sem_nota = '0.00'
  value.meses[0] = { mes: 1, estado: 'nao_informado', total_receitas_incluidas: null }
  const { reader, states } = client(async () => response(value))
  await reader.carregar(scope)
  assert.deepEqual(states.at(-1).resultado, value)
})
test('troca de empresa descarta transporte antigo que ignora abort', async () => {
  let resolveOld
  const calls = []
  const { reader, states } = client((url, options) => {
    calls.push(options)
    if (calls.length === 1) return new Promise(resolve => { resolveOld = resolve })
    const value = body(); value.empresa_id = 2; value.receitas_incluidas[0].empresa_id = 2
    return Promise.resolve(response(value))
  })
  const old = reader.carregar(scope)
  await reader.carregar({ ...scope, empresaId: 2 })
  resolveOld(response(body())); await old
  assert.equal(calls[0].signal.aborted, true)
  assert.equal(states.at(-1).empresaId, 2)
  assert.equal(states.at(-1).resultado.empresa_id, 2)
})
test('invalidar impede resposta atrasada de restaurar dados', async () => {
  let resolveOld
  const { reader, states } = client(() => new Promise(resolve => { resolveOld = resolve }))
  const pending = reader.carregar(scope)
  reader.invalidar()
  const length = states.length
  resolveOld(response(body())); await pending
  assert.equal(states.length, length)
})
