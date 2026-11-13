import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const file = new URL('../src/components/MeiPixMeiPreparacao.jsx', import.meta.url)
const app = new URL('../src/App.jsx', import.meta.url)

test('PixMEI: somente PREPARAÇÃO no painel, sem inscrição nem promessa', () => {
  const jsx = readFileSync(file, 'utf8')
  const appJsx = readFileSync(app, 'utf8')
  assert.match(appJsx, /<MeiPixMeiPreparacao\s+key=\{idPerfil\}/)
  for (const expression of [
    /Prepara[çc][ãa]o PixMEI/,
    /Inscri[çc][õo]es ainda n[aã]o abertas/,
    /crit[eé]rios finais ainda n[aã]o publicados/,
    /n[aã]o processa inscri[çc][õo]es/,
    /n[aã]o garante/,
    /R\$ 40\.500/,
    /at[eé] R\$ 5 mil/,
    /gov\.br\/memp\/pt-br\/prospera-mei\/pixmei/,
    /13\/11\/2026/,
  ]) assert.match(jsx, expression)
  assert.doesNotMatch(jsx, /garanta sua vaga|cadastre-se para receber|garantimos seu benefício|taxa de ades[aã]o/i)
})

test('PixMEI: checklist local de preparação não consulta API nem grava banco/CPF/CNPJ', () => {
  const jsx = readFileSync(file, 'utf8')
  assert.match(jsx, /type="checkbox"/)
  assert.match(jsx, /localStorage/)
  assert.match(jsx, /apenas neste navegador/)
  assert.doesNotMatch(jsx, /<input[^>]+type=["'](?:text|email|number|file|tel|password)["']/i)
  assert.doesNotMatch(jsx, /fetch\s*\(|axios|XMLHttpRequest|name=["'](?:pix|banco|agencia|conta|cpf|cnpj)["']/i)
  assert.match(jsx, /Desconfie de cobranças/)
  assert.doesNotMatch(jsx, /onSubmit|<form|type="submit"/i)
})

test('PixMEI: aviso automático permanece indisponível sem implementação real', () => {
  const jsx = readFileSync(file, 'utf8')
  assert.match(jsx, /Avisos autom[aá]ticos ainda indispon[ií]veis/)
  assert.doesNotMatch(jsx, /<button[^>]*>[^<]*avisar|<input[^>]*type="email"|subscribe|inscrever\(/i)
})
