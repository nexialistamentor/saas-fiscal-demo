import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { criarLeitorDashboardMei } from '../frontend-dashboard/src/services/meiDashboard.js'

const ok = data => ({ ok: true, json: async () => data })
const scope = { empresaId: 77, enabled: true }
const analise = { id: 1, status: 'ok', data: '2026-09-01' }
const alerta = { id: 2, descricao: 'Revisar documentos', nivel: 'medio' }
function leitor(fetchAutenticado) {
  const states = []
  const reader = criarLeitorDashboardMei({ baseUrl: 'https://api.test', fetchAutenticado, onState: s => states.push(s) })
  return { ...reader, states }
}
test('carrega somente metadados e alertas com GET autenticado e sem cache', async () => {
  const calls = []
  const r = leitor(async (url, opts) => { calls.push({url, opts}); return ok(url.includes('/analises/') ? [analise] : [alerta]) })
  await r.carregar(scope)
  assert.deepEqual(calls.map(c => c.url), ['https://api.test/dashboard/analises/77','https://api.test/dashboard/alertas/77'])
  for (const c of calls) { assert.equal(c.opts.method, 'GET'); assert.equal(c.opts.cache, 'no-store'); assert.ok(c.opts.signal) }
  assert.equal(r.states[0].loading, true)
  assert.deepEqual(r.states.at(-1).analises, [analise])
  assert.deepEqual(r.states.at(-1).alertas, [alerta])
  assert.equal(r.states.at(-1).loading, false)
})
test('empresa inválida ou perfil desabilitado não faz pedidos', async () => {
  const r = leitor(() => { throw new Error('pedido proibido') })
  for (const s of [{empresaId:77,enabled:false},{empresaId:'77',enabled:true},{empresaId:0,enabled:true}]) {
    await r.carregar(s); assert.equal(r.states.at(-1).erro, ''); assert.equal(r.states.at(-1).loading, false)
  }
})
test('ausência de registros permanece vazia, sem score ou quitação inventados', async () => {
  const r = leitor(async () => ok([])); await r.carregar(scope)
  const s = r.states.at(-1)
  assert.deepEqual(s.analises, []); assert.deepEqual(s.alertas, []); assert.equal(s.erro, '')
  for (const key of ['score','risco','pago','autorizado','consulta_paga']) assert.equal(key in s, false)
})
for (const failure of ['401','403','503','rede','payload','item']) {
  test(`falha ${failure} não se torna estado vazio bem-sucedido`, async () => {
    const r = leitor(async () => {
      if (failure === 'rede') throw new Error('network')
      if (failure === 'payload') return ok({})
      if (failure === 'item') return ok([{id:1,status:{}}])
      return {ok:false,status:Number(failure)}
    })
    await r.carregar(scope); assert.ok(r.states.at(-1).erro); assert.equal(r.states.at(-1).loading,false)
  })
}
test('troca de empresa cancela e descarta resposta antiga mesmo se transporte ignora abort', async () => {
  const pending=[]
  const r=leitor((url,opts)=>new Promise(resolve=>pending.push({url,opts,resolve})))
  const old=r.carregar(scope)
  const newer=r.carregar({empresaId:78,enabled:true})
  assert.equal(pending[0].opts.signal.aborted,true)
  pending[2].resolve(ok([{...analise,id:78}]))
  pending[3].resolve(ok([])); await newer
  pending[0].resolve(ok([analise])); pending[1].resolve(ok([alerta])); await old
  assert.equal(r.states.at(-1).empresaId,78)
  assert.equal(r.states.at(-1).analises[0].id,78)
})
test('desabilitar limpa dados e invalida pedido em curso', async () => {
  const pending=[];const r=leitor(()=>new Promise(resolve=>pending.push(resolve)))
  const old=r.carregar(scope)
  await r.carregar({...scope,enabled:false})
  pending.forEach(resolve=>resolve(ok([])));await old
  assert.equal(r.states.at(-1).loading,false);assert.deepEqual(r.states.at(-1).analises,[])
})
test('refetch substitui dados anteriores por erro, sem reapresentar resultado obsoleto', async () => {
  let fail=false
  const r=leitor(async url=>fail?{ok:false}:ok(url.includes('/analises/')?[analise]:[alerta]))
  await r.carregar(scope);fail=true;await r.carregar(scope)
  assert.ok(r.states.at(-1).erro);assert.deepEqual(r.states.at(-1).analises,[])
})
test('UI não promete regularidade e mantém leitura isolada do MEI ativo', () => {
  const app=readFileSync(new URL('../frontend-dashboard/src/App.jsx',import.meta.url),'utf8')
  const component=readFileSync(new URL('../frontend-dashboard/src/components/MeiHistoricoAlertas.jsx',import.meta.url),'utf8')
  const hook=readFileSync(new URL('../frontend-dashboard/src/hooks/useMeiDashboard.js',import.meta.url),'utf8')
  assert.match(app,/useMeiDashboard\(\{[\s\S]*?empresaId: idPerfil,[\s\S]*?tipoPerfil === "mei" && perfilAtual.status_empresa === "ativa"/)
  assert.match(component,/não comprovam quitação/);assert.match(component,/não confirma ausência de pendências/)
  assert.match(component,/role="alert"/);assert.match(component,/aria-live="polite"/)
  assert.match(hook,/return leitor.invalidar/);assert.match(hook,/snapshot\?\.empresaId === empresaId/)
  assert.match(hook,/historico: \[\]/);assert.match(hook,/loading: false/)
})
