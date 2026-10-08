import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, writeFile, rm } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { createRequire } from 'node:module'

const repo = dirname(dirname(fileURLToPath(import.meta.url)))
const frontend = join(repo, 'frontend-dashboard')
const require = createRequire(join(process.env.SOLVERIS_PLAYWRIGHT_ROOT || join(repo, '_pw_tmp'), 'package.json'))
const { chromium } = require('playwright')
const { createServer } = await import(pathToFileURL(join(frontend, 'node_modules/vite/dist/node/index.js')).href)
function apurar(rows, company, year) {
  const included = rows.filter(x => x.empresa_id === company && Number(x.data_receita.slice(0, 4)) === year)
  const cents = value => BigInt(value.replace('.', ''))
  const money = value => `${value / 100n}.${String(value % 100n).padStart(2, '0')}`
  const categories = { comercio_industria: 0n, servicos: 0n }, months = Array(12).fill(null)
  let total = 0n
  for (const row of included) {
    const amount = cents(row.valor), index = Number(row.data_receita.slice(5, 7)) - 1
    total += amount; categories[row.categoria] += amount; months[index] = (months[index] ?? 0n) + amount
  }
  return { empresa_id: company, ano_calendario: year, completude_anual_comprovada: false,
    total_receitas_incluidas: money(total), totais_por_categoria: Object.fromEntries(Object.entries(categories).map(([k,v]) => [k,money(v)])),
    totais_por_origem: { documento: '0.00', informada_sem_nota: money(total) },
    meses: months.map((value, i) => ({ mes: i+1, estado: value === null ? 'nao_informado' : 'parcial', total_receitas_incluidas: value === null ? null : money(value) })),
    receitas_incluidas: included.map(({ id, ...row }) => ({ ...row, estado: 'vigente' })),
    pendencias: [], duplicatas_ignoradas: 0 }
}
test('tela real: gravação, totais, ano, reload incerto e isolamento em desktop e mobile', { timeout: 120000 }, async () => {
  let server, browser, temporary
  try {
    temporary = await mkdtemp(join(frontend, 'mei-receita-ui-proof-'))
    await writeFile(join(temporary, 'index.html'), '<div id="root"></div><script type="module" src="./main.jsx"></script>')
    await writeFile(join(temporary, 'main.jsx'), `import React from 'react';
import {createRoot} from 'react-dom/client';
import MeiReceitasInformadas from '/src/components/MeiReceitasInformadas.jsx';
function Harness(){const [empresa,setEmpresa]=React.useState(1);return <>
<button onClick={()=>setEmpresa(empresa===1?2:1)}>Trocar empresa de teste</button>
<MeiReceitasInformadas key={empresa} empresaId={empresa} usuarioId={7}/></>}
createRoot(document.getElementById('root')).render(<Harness/>);`)
    server = await createServer({ root: frontend, configFile: false,
      define: { 'import.meta.env.VITE_API_URL': JSON.stringify('https://example.invalid') },
      server: { host: '127.0.0.1', port: 0 }, logLevel: 'error' })
    await server.listen()
    const port = server.httpServer.address().port
    const folder = temporary.slice(frontend.length + 1).replaceAll('\\', '/')
    const url = `http://127.0.0.1:${port}/${folder}/index.html`
    browser = await chromium.launch({ headless: true })
    for (const width of [1280, 390]) {
      const context = await browser.newContext({ viewport: { width, height: 900 } })
      const page = await context.newPage()
      const errors = [], rows = [], posts = []
      let uncertain = false, readFailure = false
      page.on('pageerror', error => errors.push(error.message))
      await context.addInitScript(() => localStorage.setItem('auth_token', 'synthetic-ui-token'))
      await page.route('https://example.invalid/**', async route => {
        const request = route.request(), parsed = new URL(request.url())
        const match = parsed.pathname.match(/^\/dashboard\/mei\/(\d+)\/receitas-informadas$/)
        assert.ok(match, `UNEXPECTED_API_CALL:${parsed.pathname}`)
        if (request.method() === 'OPTIONS') return route.fulfill({ headers: { 'Access-Control-Allow-Origin': '*' }, status: 204, headers: { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET, POST, OPTIONS', 'Access-Control-Allow-Headers': 'authorization, content-type' } })
        assert.equal(request.headers().authorization, 'Bearer synthetic-ui-token')
        const company = Number(match[1])
        if (request.method() === 'GET') {
          if (readFailure) return route.fulfill({ headers: { 'Access-Control-Allow-Origin': '*' }, status: 503, json: { detail: 'unavailable' } })
          return route.fulfill({ headers: { 'Access-Control-Allow-Origin': '*' }, status: 200, json: apurar(rows, company, Number(parsed.searchParams.get('ano_calendario'))) })
        }
        assert.equal(request.method(), 'POST')
        const payload = request.postDataJSON(); posts.push({ company, payload })
        let row = rows.find(x => x.empresa_id === company && x.identidade_receita === payload.identidade_receita)
        if (!row) { row = { ...payload, id: rows.length + 1, empresa_id: company, origem: 'informada_sem_nota' }; rows.push(row) }
        if (uncertain) { uncertain = false; return route.abort('failed') }
        return route.fulfill({ headers: { 'Access-Control-Allow-Origin': '*' }, status: 200, json: row })
      })
      await page.goto(url)
      try { await page.getByRole('heading', { name: 'Receitas sem nota informadas', exact: true }).waitFor({ timeout: 10000 }) }
      catch { throw Error('RECEITA_UI_NOT_WIRED: ' + errors.join('; ')) }
      const year = page.getByLabel('Ano das receitas')
      await year.fill('2026')
      await page.getByText('Nenhuma receita informada para este ano.', { exact: true }).waitFor()
      await page.getByLabel('Data da receita').fill('2026-01-10')
      await page.getByLabel('Valor da receita (R$)').fill('100.10')
      await page.getByLabel('Categoria da receita').selectOption('servicos')
      await page.getByRole('button', { name: 'Registrar receita', exact: true }).click()
      await page.getByText('Receita registrada.', { exact: true }).waitFor()
      await page.getByTestId('receitas-total-parcial').filter({ hasText: '100,10' }).waitFor()
      assert.equal(rows.length, 1)
      await year.fill('2025')
      await page.getByText('Nenhuma receita informada para este ano.', { exact: true }).waitFor()
      assert.equal(await page.getByTestId('receitas-total-parcial').count(), 0)
      await year.fill('2026')
      await page.getByTestId('receitas-total-parcial').filter({ hasText: '100,10' }).waitFor()
      uncertain = true
      await page.getByLabel('Data da receita').fill('2026-02-10')
      await page.getByLabel('Valor da receita (R$)').fill('0.20')
      await page.getByRole('button', { name: 'Registrar receita', exact: true }).click()
      await page.getByRole('button', { name: 'Recuperar registro pendente', exact: true }).waitFor()
      const previousIdentity = posts.at(-1).payload.identidade_receita
      await page.reload()
      await page.getByRole('button', { name: 'Recuperar registro pendente', exact: true }).waitFor()
      assert.equal(await page.getByLabel('Valor da receita (R$)').inputValue(), '0.20')
      assert.equal(await page.getByLabel('Valor da receita (R$)').isDisabled(), true)
      await page.getByRole('button', { name: 'Recuperar registro pendente', exact: true }).click()
      await page.getByText('Receita registrada.', { exact: true }).waitFor()
      assert.equal(posts.at(-1).payload.identidade_receita, previousIdentity)
      assert.equal(rows.length, 2)
      await year.fill('2026')
      await page.getByTestId('receitas-total-parcial').filter({ hasText: '100,30' }).waitFor()
      readFailure = true
      await page.getByRole('button', { name: 'Atualizar receitas', exact: true }).click()
      await page.getByRole('alert').waitFor()
      assert.equal(await page.getByTestId('receitas-total-parcial').count(), 0)
      readFailure = false
      await page.getByRole('button', { name: 'Trocar empresa de teste' }).click()
      await page.getByText('Nenhuma receita informada para este ano.', { exact: true }).waitFor()
      assert.equal(await page.getByTestId('receitas-total-parcial').count(), 0)
      assert.equal(await page.getByLabel('Valor da receita (R$)').inputValue(), '')
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
      assert.deepEqual(errors, [])
      await context.close()
      console.log(`PASS: ${width}px; formulário, total, troca de ano, reload incerto, mesma identidade, erro 503 e empresa isolada`)
    }
  } finally {
    await browser?.close(); await server?.close()
    if (temporary) await rm(temporary, { recursive: true, force: true })
  }
})
