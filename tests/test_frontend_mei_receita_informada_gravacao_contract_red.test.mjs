import test from 'node:test'
import assert from 'node:assert/strict'
import { criarGravadorReceitaInformadaMei } from '../frontend-dashboard/src/services/meiReceitaInformadaGravacao.js'
const key = '11111111-1111-4111-8111-111111111111'
const dados = { data_receita: '2026-01-10', valor: '100.10', categoria: 'servicos' }
const scope = { empresaId: 1, enabled: true, dados }
function storage() {
  const values = new Map()
  return { getItem: k => values.get(k) ?? null, setItem: (k, v) => values.set(k, v),
    removeItem: k => values.delete(k), values }
}
function setup(fetch, store = storage(), usuarioId = 7) {
  let generated = 0
  const writer = criarGravadorReceitaInformadaMei({ baseUrl: 'https://example.invalid',
    fetchAutenticado: fetch, storage: store, usuarioId,
    randomUUID: () => { generated++; return key } })
  return { writer, store, generated: () => generated }
}
function success(payload) {
  return { ok: true, json: async () => ({ ...payload, id: 5, empresa_id: 1, origem: 'informada_sem_nota' }) }
}
test('persiste tentativa antes do POST; ator e empresa não vêm do formulário', async () => {
  const store = storage(); let payload
  const { writer, generated } = setup(async (url, options) => {
    assert.equal(store.values.size, 1)
    assert.equal(url, 'https://example.invalid/dashboard/mei/1/receitas-informadas')
    assert.equal(options.method, 'POST'); assert.equal(options.cache, 'no-store')
    assert.equal(options.headers['Content-Type'], 'application/json')
    payload = JSON.parse(options.body)
    assert.deepEqual(payload, { ...dados, identidade_receita: key })
    return success(payload)
  }, store)
  const result = await writer.registrar(scope)
  assert.equal(result.estado, 'salvo'); assert.equal(result.registro.id, 5)
  assert.equal(generated(), 1); assert.equal(store.values.size, 0)
})
test('resposta incerta e reload reutilizam identidade e dados originais', async () => {
  const store = storage(); const calls = []
  const one = setup(async (_, options) => { calls.push(JSON.parse(options.body)); throw Error('network') }, store)
  assert.equal((await one.writer.registrar(scope)).estado, 'incerto')
  const two = setup(async (_, options) => {
    calls.push(JSON.parse(options.body)); return success(calls.at(-1))
  }, store)
  assert.deepEqual(two.writer.pendente({ empresaId: 1 }).dados, dados)
  assert.equal((await two.writer.registrar(scope)).estado, 'salvo')
  assert.deepEqual(calls[0], calls[1]); assert.equal(two.generated(), 0)
})
test('dados alterados com tentativa pendente não criam novo lançamento', async () => {
  const { writer } = setup(async () => { throw Error('network') })
  assert.equal((await writer.registrar(scope)).estado, 'incerto')
  assert.equal((await writer.registrar({ ...scope, dados: { ...dados, valor: '200.00' } })).estado, 'bloqueado')
  assert.equal(writer.pendente({ empresaId: 1 }).dados.valor, '100.10')
})
for (const status of [401, 403, 409, 422, 503]) test(`HTTP ${status} preserva tentativa, sem sucesso inventado`, async () => {
  const { writer, store } = setup(async () => ({ ok: false, status }))
  const result = await writer.registrar(scope)
  assert.notEqual(result.estado, 'salvo'); assert.equal(store.values.size, 1)
})
test('resposta divergente preserva identidade para recuperação', async () => {
  const { writer, store } = setup(async (_, options) => {
    const value = JSON.parse(options.body)
    const response = success(value)
    response.json = async () => ({ ...value, id: 5, empresa_id: 2, origem: 'documento' })
    return response
  })
  assert.equal((await writer.registrar(scope)).estado, 'incerto')
  assert.equal(store.values.size, 1)
})
test('falha de storage não envia POST', async () => {
  let calls = 0
  const store = { getItem: () => null, setItem: () => { throw Error('storage') }, removeItem: () => {} }
  const { writer } = setup(async () => { calls++; }, store)
  assert.equal((await writer.registrar(scope)).estado, 'bloqueado'); assert.equal(calls, 0)
})
test('tentativa corrompida não é substituída por nova identidade', async () => {
  let calls = 0
  const store = { getItem: () => '{broken', setItem: () => { throw Error('must not overwrite') }, removeItem: () => {} }
  const { writer, generated } = setup(async () => { calls++; }, store)
  assert.equal((await writer.registrar(scope)).estado, 'bloqueado')
  assert.equal(calls, 0); assert.equal(generated(), 0)
})
test('tentativas isoladas por usuário e empresa', async () => {
  const store = storage()
  const one = setup(async () => { throw Error('network') }, store, 7)
  await one.writer.registrar(scope)
  const other = setup(async () => { throw Error('network') }, store, 8)
  assert.equal(other.writer.pendente({ empresaId: 1 }), null)
  assert.equal(one.writer.pendente({ empresaId: 2 }), null)
})
test('entrada inválida não cria tentativa nem pedido', async () => {
  let calls = 0
  const { writer, store } = setup(async () => { calls++; })
  for (const change of [{ enabled: false }, { empresaId: true }, { empresaId: 0 },
    { dados: { ...dados, valor: 100.10 } }, { dados: { ...dados, valor: '1,00' } },
    { dados: { ...dados, data_receita: '2026-02-30' } },
    { dados: { ...dados, usuario_id: 8 } }]) {
    assert.equal((await writer.registrar({ ...scope, ...change })).estado, 'bloqueado')
  }
  assert.equal(calls, 0); assert.equal(store.values.size, 0)
})
test('duplo clique em curso não envia segundo POST', async () => {
  let resolve; let calls = 0; let payload
  const { writer } = setup((_, options) => {
    calls++; payload = JSON.parse(options.body)
    return new Promise(r => { resolve = r })
  })
  const first = writer.registrar(scope)
  assert.equal((await writer.registrar(scope)).estado, 'em_curso')
  resolve(success(payload)); assert.equal((await first).estado, 'salvo')
  assert.equal(calls, 1)
})
