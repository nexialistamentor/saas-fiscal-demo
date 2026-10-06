import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { criarLeitorConferenciaDocumentalMei } from '../frontend-dashboard/src/services/meiConferenciaDocumental.js'

const scope = { empresaId: 77, anoCalendario: 2026, enabled: true }
const item = id => ({ documento_id: id, categoria_receita: null,
  metadados: { id, empresa_id: 77, data_emissao: '2026-01-01', tipo: 'saida', valor_total: 100,
    chave_nfe: null, conteudo_sha256: null },
  motivos: ['EMITENTE_NAO_COMPROVADO', 'NATUREZA_OPERACAO_NAO_COMPROVADA', 'ESTADO_FISCAL_NAO_COMPROVADO'],
})
const payload = observations => ({ empresa_id: 77, ano_calendario: 2026,
  documentos_para_revisao: [item(1)], documentos_sem_periodo: [],
  receitas_confirmadas: [], total_receita_confirmada: null,
  completude_anual_comprovada: false, duplicatas_ignoradas: 0,
  observacoes_operacao: observations,
})
async function carregar(body) {
  const states = []
  const reader = criarLeitorConferenciaDocumentalMei({ baseUrl: 'https://api.test',
    fetchAutenticado: async () => ({ ok: true, json: async () => body }),
    onState: state => states.push(state) })
  await reader.carregar(scope)
  return states.at(-1)
}
const observation = (overrides = {}) => ({ documento_id: 1,
  natureza_operacao_observada: 'VENDA <script>observada</script>',
  finalidade_emissao_observada: '1',
  itens: [{ item_id: 10, cfop_observado: '5102' }, { item_id: 11, cfop_observado: '5910' }],
  ...overrides,
})
test('preserva natureza, finalidade e CFOP por item sem confirmar receita', async () => {
  for (const obs of [observation(), observation({ natureza_operacao_observada: null,
    finalidade_emissao_observada: null, itens: [] }), observation({
    finalidade_emissao_observada: '4', itens: [{ item_id: 12, cfop_observado: null }] })]) {
    const body = payload([obs])
    const state = await carregar(body)
    assert.equal(state.erro, '')
    assert.deepEqual(state.resultado.observacoes_operacao, body.observacoes_operacao)
    assert.equal(state.resultado.total_receita_confirmada, null)
    assert.deepEqual(state.resultado.receitas_confirmadas, [])
  }
})
test('observações incoerentes bloqueiam todo o resultado', async () => {
  for (const observations of [null, {}, [], [observation({ documento_id: 2 })],
    [observation(), observation()], [observation({ natureza_operacao_observada: 42 })],
    [observation({ finalidade_emissao_observada: true })], [observation({ itens: null })],
    [observation({ itens: [{ item_id: 0, cfop_observado: '5102' }] })],
    [observation({ itens: [{ item_id: 10, cfop_observado: 5102 }] })],
    [observation({ itens: [{ item_id: 10, cfop_observado: null }, { item_id: 10, cfop_observado: '5102' }] })]]) {
    const state = await carregar(payload(observations))
    assert.equal(state.resultado, null, 'MEI_OPERATION_FRONTEND_CONTRACT_NOT_ENFORCED')
    assert.ok(state.erro)
  }
})
test('item repetido em documentos diferentes bloqueia resultado', async () => {
  const body = payload([observation(), observation({ documento_id: 2 })])
  body.documentos_para_revisao.push(item(2))
  const state = await carregar(body)
  assert.equal(state.resultado, null, 'MEI_OPERATION_ITEM_SCOPE_NOT_ENFORCED')
  assert.ok(state.erro)
})
test('tela apresenta observações sem declarar natureza fiscal confirmada', () => {
  const component = readFileSync(new URL('../frontend-dashboard/src/components/MeiConferenciaDocumental.jsx', import.meta.url), 'utf8')
  assert.match(component, /observacoes_operacao/, 'MEI_OPERATION_FRONTEND_NOT_WIRED')
  assert.match(component, /Natureza observada/)
  assert.match(component, /Finalidade observada/)
  assert.match(component, /CFOP observado/)
  assert.match(component, /não confirma receita/)
  assert.doesNotMatch(component, /dangerouslySetInnerHTML/)
})
