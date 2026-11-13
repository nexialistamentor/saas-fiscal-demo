/* SOLVERIS.MEI-ANISTIA-001 — apenas ambiente local descartável.
 * Uso: API 127.0.0.1:8000, Vite 127.0.0.1:5173/mei/.
 * Identidade fiscal sintética da fixture histórica; nunca cliente real.
 * O script não modifica produção e não precisa de credenciais externas.
 */
const fs = require('fs')
const path = require('path')
const assert = require('node:assert/strict')
const { chromium, request } = require('playwright')
const API = 'http://127.0.0.1:8000'
const UI = 'http://127.0.0.1:5173/mei/'
const OUTPUT = process.env.MEI_SMOKE_OUTPUT || '/tmp/mei-anistia-001-captures'
const fixtureEmail = 'mei.smoke.' + Date.now() + '@example.com'
const fixturePass = 'SmokeLocal2026!'
const result = { mission: 'SOLVERIS.MEI-ANISTIA-001', test: 'local-isolated-real-auth', status: 'RED', scenarios: [] }
fs.mkdirSync(OUTPUT, { recursive: true })
async function main() {
  const client = await request.newContext({ baseURL: API })
  const reg = await client.post('/auth/register', { data: {
    email: fixtureEmail, password: fixturePass, nome: 'SIMULACAO LOCAL SEM VALIDADE FISCAL',
    tipo_usuario: 'mei', mei_intent: 'existing', documento: '12345678000195'
  }})
  assert(reg.ok(), 'Cadastro sintético recusado: ' + reg.status() + ' ' + (await reg.text()).slice(0, 170))
  const empresaId = (await reg.json()).empresa_id
  assert(Number.isInteger(empresaId) && empresaId > 0)
  const login = await client.post('/auth/login', { form: { username: fixtureEmail, password: fixturePass } })
  assert(login.ok(), 'Login API: ' + login.status())
  const headers = { Authorization: 'Bearer ' + (await login.json()).access_token }
  for (const route of ['/auth/accept-terms', '/auth/consent']) {
    const response = await client.post(route, { headers })
    assert(response.ok(), route + ' ' + response.status())
  }
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] })
  try {
    for (const width of [1365, 390]) {
      const kind = width === 390 ? 'mobile' : 'desktop'
      const context = await browser.newContext({
        viewport: { width, height: 900 },
        isMobile: width === 390,
        hasTouch: width === 390
      })
      const unexpectedWrites = []
      await context.route('**/*', route => {
        const req = route.request(), u = new URL(req.url())
        if (u.hostname !== '127.0.0.1') return route.abort('blockedbyclient')
        if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(req.method()) &&
            !['/auth/login', '/auth/accept-terms', '/auth/consent'].includes(u.pathname)) {
          unexpectedWrites.push(req.method() + ' ' + u.pathname)
          return route.abort('blockedbyclient')
        }
        return route.continue()
      })
      const page = await context.newPage()
      const jsErrors = []
      page.on('pageerror', error => jsErrors.push(error.message))
      await page.goto(UI, { waitUntil: 'domcontentloaded', timeout: 45000 })
      await page.locator('#solveris-login-email').fill(fixtureEmail)
      await page.locator('input[type="password"]').first().fill(fixturePass)
      const responsePromise = page.waitForResponse(r =>
        r.url().endsWith('/auth/login') && r.request().method() === 'POST')
      await page.locator('form.solveris-login-form button[type="submit"]').click()
      assert((await responsePromise).ok(), 'Login pelo navegador recusado')
      const card1 = page.locator('section[aria-labelledby="mei-remissao-titulo"]')
      const card3 = page.locator('section[aria-labelledby="pixmei-preparacao-titulo"]')
      await card1.waitFor({ state: 'visible', timeout: 35000 })
      await card3.waitFor({ state: 'visible', timeout: 35000 })
      const a = await card1.innerText(), p = await card3.innerText()
      assert(a.includes('13/10/2026') && a.includes('01/01/2027'))
      assert(a.includes('ICMS nem ISS') && !a.includes('31/10/2026'))
      assert(p.includes('Inscrições ainda não abertas'))
      assert(p.includes('não processa inscrições') && p.includes('não garante acesso'))
      assert(!/garanta sua vaga|cadastre-se no PixMEI|inscreva-se agora/i.test(p))
      const checks = card3.locator('input[type="checkbox"]')
      assert.equal(await checks.count(), 4)
      await checks.first().check()
      await page.reload({ waitUntil: 'domcontentloaded' })
      await card1.waitFor({ state: 'visible', timeout: 20000 })
      await card3.waitFor({ state: 'visible', timeout: 20000 })
      assert(await checks.first().isChecked(), 'Checklist local não persistiu')
      assert.equal(unexpectedWrites.length, 0, unexpectedWrites.join(', '))
      const widths = await page.evaluate(() => ({
        viewport: window.innerWidth, content: document.documentElement.scrollWidth
      }))
      assert(widths.content <= widths.viewport + 2, 'Overflow: ' + JSON.stringify(widths))
      const images = await page.locator('img').evaluateAll(list => list.map(img => ({
        src: img.getAttribute('src'), loaded: img.complete && img.naturalWidth > 0
      })))
      assert(images.every(img => img.loaded), 'Imagem quebrada: ' + JSON.stringify(images))
      assert.equal(jsErrors.length, 0, jsErrors.join('; '))
      await card1.screenshot({ path: path.join(OUTPUT, kind + '-anistia.png'), animations: 'disabled' })
      await card3.screenshot({ path: path.join(OUTPUT, kind + '-pixmei.png'), animations: 'disabled' })
      await page.screenshot({ path: path.join(OUTPUT, kind + '-viewport.png'), animations: 'disabled' })
      result.scenarios.push({ width, login: true, b1: true, b3: true,
        checkboxPersists: true, noUnexpectedWrites: true, noOverflow: true,
        noBrokenImages: true, noJavascriptErrors: true })
      console.log('PASS ' + kind)
      await context.close()
    }
    result.status = 'GREEN'
  } finally { await browser.close() }
}
main().catch(error => {
  result.error = String(error.message || error)
  console.error('RED ' + result.error)
  process.exitCode = 1
}).finally(() => {
  fs.writeFileSync(path.join(OUTPUT, 'result.json'), JSON.stringify(result, null, 2))
  console.log('SMOKE_STATUS=' + result.status)
})
