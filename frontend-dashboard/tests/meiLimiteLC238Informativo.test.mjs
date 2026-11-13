import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const frontend = new URL('../src/components/MeiAssistente.jsx', import.meta.url)
const backend = new URL('../../../app/services/assistente_service.py', import.meta.url)
const engine = new URL('../../../app/services/tax_engines/mei_tax_engine.py', import.meta.url)

test('MEI: nota futura explicita teto previsto, vigência, LC238 e condição LOA', () => {
  const jsx = readFileSync(frontend, 'utf8')
  assert.match(jsx, /R\$\s*110\.?000/)
  assert.match(jsx, /2027/)
  assert.match(jsx, /R\$\s*140\.?000/)
  assert.match(jsx, /2028/)
  assert.match(jsx, /Lei Complementar (n[º°]\s*)?238\/2026/)
  assert.match(jsx, /condicionad[oa]s?.*ren[úu]ncia.*or[çc]ament/i)
  assert.match(jsx, /www2\.camara\.leg\.br\/legin\/fed\/leicom\/2026\//)
  assert.match(jsx, /n[aã]o substitui.*consulta.*limite/i)
})

test('MEI: 2027 e 2028 seguem sem autoridade para cálculo DAS ou limite', () => {
  const server = readFileSync(backend, 'utf8')
  const fiscalEngine = readFileSync(engine, 'utf8')
  assert.match(server, /carregar_binding_normativo_mei_das_2026\(/)
  assert.match(server, /MEI_LIMITE_ANUAL_FATURAMENTO/)
  assert.match(server, /AUTORIDADE_NORMATIVA_MEI_INDISPONIVEL/)
  assert.match(fiscalEngine, /data_referencia\.year\s*!=\s*2026/)
  assert.match(fiscalEngine, /BINDING_FORA_DO_ANO_2026/)
})
