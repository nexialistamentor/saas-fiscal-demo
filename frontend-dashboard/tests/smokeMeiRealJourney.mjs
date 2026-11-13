/**
 * SOLVERIS.MEI-SMOKE-REAL-001 — smoke de jornada do cliente MEI.
 *
 * Execução:
 *   npm install --no-save --package-lock=false playwright
 *   npx playwright install chromium
 *   node tests/smokeMeiRealJourney.mjs
 *
 * Configuração:
 *   MEI_SMOKE_URL: URL de preview /mei (obrigatória).
 *   MEI_SMOKE_PROD_URL: URL da versão atual para screenshots antes/depois.
 *   MEI_SMOKE_EMAIL + MEI_SMOKE_PASSWORD: credenciais APENAS de conta de teste autorizada.
 *
 * Segurança: não faz cadastro, upload XML, registro de receitas, compra, pagamento,
 * emissão DAS ou submissão de consultas. Login com conta de teste é opcional.
 * Capturas e JSON são locais; não imprimir nem versionar credenciais/dados privados.
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { chromium } from 'playwright';

const PREVIEW = (process.env.MEI_SMOKE_URL || '').trim().replace(/\/$/, '');
const PROD = (process.env.MEI_SMOKE_PROD_URL || 'https://www.fiscosoberano.com.br/mei').trim().replace(/\/$/, '');
const EMAIL = process.env.MEI_SMOKE_EMAIL || '';
const PASSWORD = process.env.MEI_SMOKE_PASSWORD || '';
const OUT = path.resolve(process.env.MEI_SMOKE_OUT || 'mei-smoke-artifacts');
const cases = [];
const errors = [];
let browser;

if (!PREVIEW || !/^https:\/\/[^/]+\/mei$/.test(PREVIEW)) {
  console.error('MEI_SMOKE_URL deve ser uma URL HTTPS exata terminada em /mei.');
  process.exit(2);
}
if (Boolean(EMAIL) !== Boolean(PASSWORD)) {
  console.error('MEI_SMOKE_EMAIL e MEI_SMOKE_PASSWORD devem ser fornecidos juntos.');
  process.exit(2);
}
fs.mkdirSync(OUT, { recursive: true });

async function step(profile, name, fn) {
  try {
    const details = await fn();
    cases.push({ profile, name, state: 'PASS', details: details || '' });
    console.log('PASS ' + profile + ' / ' + name);
    return true;
  } catch (error) {
    cases.push({ profile, name, state: 'FAIL', details: String(error?.message || error) });
    console.error('FAIL ' + profile + ' / ' + name + ': ' + String(error?.message || error));
    return false;
  }
}
function skip(profile, name, reason) {
  cases.push({ profile, name, state: 'BLOCKED', details: reason });
  console.log('BLOCKED ' + profile + ' / ' + name + ': ' + reason);
}
async function shot(page, profile, label) {
  await page.screenshot({ path: path.join(OUT, profile + '-' + label + '.png'), fullPage: true, animations: 'disabled' });
}
async function isVisible(locator) { return (await locator.count()) > 0 && await locator.first().isVisible(); }
async function openReadOnly(page, url) {
  const response = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
  assert.equal(response?.status(), 200, 'HTTP deve ser 200');
  await page.locator('#root').waitFor({ state: 'visible', timeout: 20000 });
  await page.waitForTimeout(500);
}
async function runProfile(name, viewport) {
  const context = await browser.newContext({ viewport, serviceWorkers: 'block' });
  const page = await context.newPage();
  const posts = [];
  page.on('request', req => { if (req.method() === 'POST') posts.push(new URL(req.url()).pathname); });
  page.on('pageerror', err => errors.push({ profile: name, type: 'pageerror', message: err.message }));

  await step(name, 'Produção acessível (versão ANTES)', async () => {
    await openReadOnly(page, PROD);
    await shot(page, name, 'antes-publico');
    const img = page.locator('.solveris-logo');
    if (await img.count()) {
      const loaded = await img.evaluate(el => ({ url: el.currentSrc, naturalWidth: el.naturalWidth }));
      return 'Logo anterior: ' + JSON.stringify(loaded);
    }
  });
  const entryOk = await step(name, 'Prévia acessível e tela inicial', async () => {
    await openReadOnly(page, PREVIEW);
    assert(await isVisible(page.getByRole('heading', { name: 'SOLVERIS', exact: true })));
    assert(await isVisible(page.getByRole('button', { name: 'Já tenho MEI' })));
    assert(await isVisible(page.getByRole('button', { name: 'Entrar', exact: true })));
    await shot(page, name, 'depois-publico');
  });
  if (!entryOk) {
    skip(name, 'Cadastro e login', 'Tela inicial não carregou corretamente');
    await context.close();
    return;
  }
  await step(name, 'Logotipo renderizado e arquivo correto', async () => {
    const img = page.locator('.solveris-logo');
    assert.equal(await img.count(), 1);
    const m = await img.evaluate(el => ({
      complete: el.complete, width: el.naturalWidth,
      height: el.naturalHeight, url: el.currentSrc,
      bounds: el.getBoundingClientRect().toJSON(),
    }));
    assert(m.complete && m.width > 0, 'Logotipo ainda quebrado: ' + JSON.stringify(m));
    assert(new URL(m.url).pathname === '/solveris-logo.jpg', 'URL inesperada: ' + m.url);
    return JSON.stringify(m);
  });
  await step(name, 'Favicon sem erro 404', async () => {
    const href = await page.locator('link[rel="icon"]').getAttribute('href');
    assert(href, 'Favicon ausente');
    const url = new URL(href, PREVIEW).href;
    const response = await context.request.get(url);
    assert.equal(response.status(), 200, 'Favicon: ' + url);
    assert((response.headers()['content-type'] || '').includes('image'), 'Favicon não retornou imagem');
    return url;
  });
  await step(name, 'Rodapé jurídico único, inclusive na entrada', async () => {
    const footer = page.locator('.solveris-mei-legal-footer');
    assert.equal(await footer.count(), 1);
    assert(await footer.isVisible());
    assert((await footer.innerText()).includes('não substitui obrigações fiscais oficiais'));
  });
  await step(name, 'Sem elementos horizontais fora da tela', async () => {
    const bounds = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth, viewport: window.innerWidth,
    }));
    assert(bounds.scrollWidth <= bounds.viewport + 2, JSON.stringify(bounds));
  });
  await step(name, 'Entrada Já tenho MEI e validações locais', async () => {
    await page.getByRole('button', { name: 'Já tenho MEI' }).click();
    assert(await isVisible(page.getByRole('heading', { name: 'Criar conta para meu MEI' })));
    for (const selector of ['#solveris-register-name','#solveris-register-document','#solveris-register-email','#solveris-register-password']) {
      assert.equal(await page.locator(selector).count(), 1, 'Campo ausente: ' + selector);
      assert(await page.locator(selector).getAttribute('required') !== null, 'Campo não obrigatório: ' + selector);
    }
    await page.locator('#solveris-register-email').fill('endereco-invalido');
    await page.locator('#solveris-register-email').blur();
    assert(await isVisible(page.getByText('Informe um email válido.', { exact: true })));
    await page.locator('#solveris-register-password').fill('senhaficticia123');
    await page.getByRole('button', { name: 'Mostrar senha' }).click();
    assert.equal(await page.locator('#solveris-register-password').getAttribute('type'), 'text');
    await page.getByRole('button', { name: 'Ocultar senha' }).click();
    assert.equal(await page.locator('#solveris-register-password').getAttribute('type'), 'password');
    await shot(page, name, 'depois-cadastro-sem-envio');
    assert.equal(posts.length, 0, 'Houve requisições POST inesperadas: ' + posts.join(', '));
  });
  await step(name, 'Retorno ao login sem cadastro', async () => {
    await page.getByRole('button', { name: 'Fazer login', exact: true }).click();
    assert(await isVisible(page.locator('#solveris-login-email')));
    assert(await isVisible(page.locator('#solveris-login-password')));
    assert.equal(posts.length, 0, 'Cadastro disparado inesperadamente');
  });
  if (!EMAIL) {
    skip(name, 'Jornada autenticada: dashboard, XML, histórico, receitas, assistente e DAS',
      'É necessária conta de teste MEI autorizada (MEI_SMOKE_EMAIL/MEI_SMOKE_PASSWORD); nenhuma compra, lançamento ou XML será enviado.');
    await context.close();
    return;
  }
  const logged = await step(name, 'Login de conta MEI de teste autorizada', async () => {
    await page.locator('#solveris-login-email').fill(EMAIL);
    await page.locator('#solveris-login-password').fill(PASSWORD);
    await page.getByRole('button', { name: 'Entrar', exact: true }).click();
    await page.getByRole('heading', { name: 'Meu MEI', exact: true }).waitFor({ timeout: 25000 });
    await shot(page, name, 'depois-dashboard');
  });
  if (!logged) {
    skip(name, 'Jornada autenticada', 'Login ou perfil ativo não comprovado');
    await context.close();
    return;
  }
  await step(name, 'Benefícios MEI e navegação de seções', async () => {
    assert(await isVisible(page.getByText('Seu DAS, seus documentos e seu diagnóstico fiscal em um só lugar.')));
    for (const id of ['mei-documentos','mei-das-oficial','mei-diagnostico']) {
      assert.equal(await page.locator('#'+id).count(), 1, 'Seção ausente '+id);
    }
    await page.locator('a[href="#mei-documentos"]').click();
    assert.equal(new URL(page.url()).hash, '#mei-documentos');
    assert(await isVisible(page.getByRole('heading', { name: 'Documentos fiscais' })));
    await shot(page, name, 'depois-xml-sem-upload');
  });
  await step(name, 'Histórico, orientação e documentos anuais', async () => {
    assert(await isVisible(page.getByRole('heading', { name: 'Histórico e alertas do seu MEI' })));
    assert(await isVisible(page.getByText('Acompanhe os alertas e análises do seu MEI.')));
    assert(await isVisible(page.getByRole('heading', { name: 'Assistente de orientação MEI' })));
    assert(await isVisible(page.getByRole('heading', { name: 'Documentos para conferência anual' })));
    assert(await isVisible(page.getByText('*Documentos têm caráter informativo.')));
    await shot(page, name, 'depois-historico-conferencia');
  });
  await step(name, 'Receitas mensais sem efetuar lançamento', async () => {
    assert(await isVisible(page.getByRole('heading', { name: 'Receitas sem nota informadas' })));
    assert(await isVisible(page.getByRole('button', { name: 'Registrar receita' })));
    assert(await isVisible(page.getByText('Registre aqui o que você recebeu sem nota fiscal e acompanhe seu total do ano.')));
    await shot(page, name, 'depois-receitas-sem-envio');
  });
  await step(name, 'DAS, restrições e nenhuma cobrança', async () => {
    assert(await isVisible(page.getByRole('heading', { name: 'Emitir DAS oficial' })));
    const pay = page.getByRole('button', { name: /Pagar serviço|Retomar pagamento/ });
    if (await pay.count()) {
      assert(!(await pay.first().getAttribute('type') === 'submit'), 'Botão de pagamento inesperadamente submit');
    }
    assert(!posts.some(p => /checkout|pagamento|receitas|xml|imposto/.test(p)),
      'POST fiscal/financeiro inesperado: '+posts.join(', '));
    await shot(page, name, 'depois-das-sem-comprar');
  });
  await step(name, 'Rodapé único também no dashboard', async () => {
    assert.equal(await page.locator('.solveris-mei-legal-footer').count(), 1);
    assert(await page.locator('.solveris-mei-legal-footer').isVisible());
  });
  await context.close();
}

try {
  browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  await runProfile('desktop', { width: 1365, height: 900 });
  await runProfile('mobile', { width: 390, height: 844 });
} catch (e) {
  errors.push({ type: 'runner', message: String(e?.stack || e) });
  console.error('FATAL ' + String(e?.message || e));
} finally {
  if (browser) await browser.close();
  const counts = Object.fromEntries(['PASS','FAIL','BLOCKED'].map(s => [s, cases.filter(t => t.state === s).length]));
  const report = {
    mission: 'SOLVERIS.MEI-SMOKE-REAL-001',
    preview: PREVIEW,
    production: PROD,
    timestamp: new Date().toISOString(),
    counts, cases, errors,
    writes_allowed: false,
    verdict: counts.FAIL > 0 || errors.length ? 'RED' : counts.BLOCKED > 0 ? 'PARTIAL-BLOCKED' : 'GREEN',
  };
  fs.writeFileSync(path.join(OUT,'report.json'), JSON.stringify(report, null, 2));
  console.log('VERDICT ' + report.verdict + ' ' + JSON.stringify(counts));
  if (counts.FAIL > 0 || errors.length) process.exitCode = 1;
}
