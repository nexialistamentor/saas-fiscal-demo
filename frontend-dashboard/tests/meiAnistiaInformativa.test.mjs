import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const component = new URL('../src/components/MeiAnistiaInformativa.jsx', import.meta.url)
const app = new URL('../src/App.jsx', import.meta.url)

test('anistia MEI: conteúdo informativo é acessível no dashboard, sem consulta simulada', () => {
  const jsx = readFileSync(component, 'utf8')
  const appJsx = readFileSync(app, 'utf8')
  assert.match(appJsx, /<MeiAnistiaInformativa\s*\/>/)
  assert.match(jsx, /13\/10\/2026/)
  assert.match(jsx, /01\/01\/2027/)
  assert.match(jsx, /ICMS/)
  assert.match(jsx, /ISS/)
  assert.match(jsx, /contribui[çc][ãa]o previdenci[áa]ria/)
  assert.match(jsx, /www\.regularize\.pgfn\.gov\.br/)
  assert.match(jsx, /servicos\.receitafederal\.gov\.br/)
  assert.match(jsx, /car[aá]ter informativo|informativa|apenas orienta/)
  assert.match(jsx, /n[aã]o consult|n[aã]o verifica/)
  assert.doesNotMatch(jsx, /gerardaspdf|consulta_paga|valor_perdoado|valor_estimado|fetch\s*\(|axios\s*\(/i)
})

test('anistia MEI: sem anistia fictícia ou promessa de liberação instantânea', () => {
  const jsx = readFileSync(component, 'utf8')
  assert.doesNotMatch(jsx, /seu d[eé]bito foi perdoado|garantimos a anistia|devolu[çc][aã]o de valores|inscreva-se agora/i)
})
