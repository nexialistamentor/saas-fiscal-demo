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
  observacoes_emitente: observations,
})
async function carregar(body) {
  const states = []
  const reader = criarLeitorConferenciaDocumentalMei({ baseUrl: 'https://api.test',
    fetchAutenticado: async () => ({ ok: true, json: async () => body }),
    onState: state => states.push(state) })
  await reader.carregar(scope)
  return states.at(-1)
}
test('preserva todos os estados de observação sem confirmar receita', async () => {
  for (const [estado, cnpj] of [['coincidente', '12345678000195'], ['divergente', '11222333000181'],
    ['ausente', null], ['invalido', '123'], ['empresa_sem_cnpj_comparavel', '12345678000195']]) {
    const body = payload([{ documento_id: 1, estado, cnpj_emitente_observado: cnpj }])
    const state = await carregar(body)
    assert.equal(state.erro, '')
    assert.deepEqual(state.resultado.observacoes_emitente, body.observacoes_emitente)
    assert.equal(state.resultado.total_receita_confirmada, null)
  }
})
test('observação inválida ou vinculada a outro documento bloqueia resultado', async () => {
  for (const observations of [null, {}, [],
    [{ documento_id: 2, estado: 'coincidente', cnpj_emitente_observado: '12345678000195' }],
    [{ documento_id: 1, estado: 'confirmado', cnpj_emitente_observado: '12345678000195' }],
    [{ documento_id: 1, estado: 'coincidente', cnpj_emitente_observado: '123' }],
    [{ documento_id: 1, estado: 'ausente', cnpj_emitente_observado: '12345678000195' }],
    [{ documento_id: 1, estado: 'coincidente', cnpj_emitente_observado: '12345678000195' },
     { documento_id: 1, estado: 'coincidente', cnpj_emitente_observado: '12345678000195' }]]) {
    const state = await carregar(payload(observations))
    assert.equal(state.resultado, null, 'MEI_EMITTER_FRONTEND_CONTRACT_NOT_ENFORCED')
    assert.ok(state.erro)
  }
})
test('tela mostra observação e distingue coincidência de autenticidade', () => {
  const component = readFileSync(new URL('../frontend-dashboard/src/components/MeiConferenciaDocumental.jsx', import.meta.url), 'utf8')
  assert.match(component, /observacoes_emitente/)
  assert.match(component, /Emitente observado/)
  assert.match(component, /CNPJ coincide com o da empresa/)
  assert.match(component, /CNPJ diverge do da empresa/)
  assert.match(component, /não comprova autenticidade nem confirma receita/)
  assert.doesNotMatch(component, /dangerouslySetInnerHTML/)
})
