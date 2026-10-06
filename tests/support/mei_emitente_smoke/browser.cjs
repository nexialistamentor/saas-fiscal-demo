// TEST ONLY: real local HTTP routes; simulated payment and fiscal provider.
const { createRequire } = require('node:module');
const path = require('node:path');
const fs = require('node:fs/promises');
const assert = require('node:assert/strict');
const repo = path.resolve(process.argv[2]);
const output = path.resolve(process.argv[3]);
const localRequire = createRequire(path.join(repo, '_pw_tmp', 'package.json'));
const { chromium, request } = localRequire('playwright');
const API = 'http://127.0.0.1:8766';
const UI = 'http://127.0.0.1:5175/mei/';
const PASSWORD = 'SmokeLocal2026!';
const BARCODE = ['858900000008','860503282026','608201234567','890123456789'];

async function checked(response, statuses=[200]) {
  if (!statuses.includes(response.status())) {
    let body = '[response body unavailable]';
    try { body = await response.text(); } catch {}
    throw new Error(`${response.url()}: HTTP ${response.status()} ${body}`);
  }
  return response;
}
async function main() {
  await fs.mkdir(output, { recursive: true });
  const client = await request.newContext({baseURL: API, timeout: 15000});
  const email = `mei.smoke.${Date.now()}@example.com`;
  const registered = await checked(await client.post('/auth/register', {data: {
    email, password: PASSWORD, nome: 'SIMULACAO LOCAL SEM VALIDADE FISCAL',
    tipo_usuario: 'mei', mei_intent: 'existing', documento: '12345678000195'
  }}), [200,201]);
  const empresaId = (await registered.json()).empresa_id;
  assert(Number.isInteger(empresaId) && empresaId > 0);
  const logged = await checked(await client.post('/auth/login', {form:{username:email,password:PASSWORD}}));
  const headers = {Authorization: `Bearer ${(await logged.json()).access_token}`};
  await checked(await client.post('/auth/accept-terms', {headers}));
  await checked(await client.post('/auth/consent', {headers}));
  const documents = await (await checked(await client.post('/__smoke__/documental-seed', {headers}))).json();
  const getStats = async () => (await checked(await client.get('/__smoke__/stats',{headers}))).json();
  const recover = async competence => {
    const response = await checked(await client.get(`/imposto/mei/${empresaId}/checkout-recovery?competencia=${competence}`,{headers}));
    return response.json();
  };
  const browser = await chromium.launch();
  const results = [];
  try {
    for (const [width, month] of [[1280,'2026-07'],[390,'2026-08']]) {
      await checked(await client.post('/__smoke__/reset-rate-limit',{headers}));
      const context = await browser.newContext({viewport:{width,height:900},acceptDownloads:true});
      const page = await context.newPage();
      const errors = [], external = [];
      let virtualCheckouts = 0;
      page.on('pageerror', error => errors.push(error.message));
      await context.route('**/*', async route => {
        const url = new URL(route.request().url());
        if (url.hostname === 'checkout.example.invalid' && /^\/local\/\d+$/.test(url.pathname)) {
          virtualCheckouts++;
          return route.fulfill({status:200,contentType:'text/html',body:
            '<!doctype html><meta charset="utf-8"><h1>Pagamento simulado local</h1><p>Nenhuma cobranca real.</p>'});
        }
        if (url.hostname === '127.0.0.1' && ['5175','8766'].includes(url.port)) return route.continue();
        external.push(url.origin);
        return route.abort();
      });
      const login = async () => {
        await page.goto(UI,{waitUntil:'domcontentloaded'});
        await page.locator('#solveris-login-email').fill(email);
        await page.locator('input[type="password"]').fill(PASSWORD);
        const response = page.waitForResponse(r => r.url().endsWith('/auth/login') && r.request().method()==='POST');
        await page.getByRole('button',{name:'Entrar',exact:true}).click();
        await checked(await response);
        await page.locator('#mei-das-oficial').waitFor();
        await page.locator('#mei-assistente-titulo').waitFor();
      };
      const scope = page.locator('#mei-das-oficial');
      const emit = scope.getByRole('button',{name:'Emitir DAS oficial',exact:true});
      const competence = month.replace('-','');
      const begin = await getStats();
      await login();
      const inventory = page.getByRole('region', {name: 'Documentos para conferência anual', exact: true});
      await inventory.waitFor();
      const year = inventory.getByRole('spinbutton', {name: 'Ano de referência'});
      await year.fill('2026');
      await inventory.getByText(`Documento #${documents.year2026}`, {exact:true}).waitFor();
      await inventory.getByText(/CNPJ coincide com o da empresa/).waitFor();
      await inventory.getByText('A comparação de CNPJ não comprova autenticidade nem confirma receita.', {exact:true}).waitFor();
      await inventory.getByText(`Documento #${documents.undated}`, {exact:true}).waitFor();
      await inventory.getByText(/CNPJ do emitente não informado/).waitFor();
      assert.equal(await inventory.getByText(`Documento #${documents.year2025}`, {exact:true}).count(), 0);
      await year.fill('2025');
      await inventory.getByText(`Documento #${documents.year2025}`, {exact:true}).waitFor();
      await inventory.getByText(/CNPJ diverge do da empresa/).waitFor();
      assert.equal(await inventory.getByText(`Documento #${documents.year2026}`, {exact:true}).count(), 0);
      await year.fill('2024');
      await inventory.getByText('Nenhum documento encontrado para este ano. Isso não significa receita anual zero.', {exact:true}).waitFor();
      await inventory.getByText(`Documento #${documents.undated}`, {exact:true}).waitFor();
      await inventory.getByText(/CNPJ do emitente não informado/).waitFor();
      await context.route('**/dashboard/mei/*/conferencia-documental?*', route => route.fulfill({status:503,contentType:'application/json',body:'{}'}));
      await inventory.getByRole('button', {name:'Atualizar documentos',exact:true}).click();
      await inventory.getByRole('alert').waitFor();
      assert.equal(await inventory.getByText(`Documento #${documents.undated}`, {exact:true}).count(), 0);
      await context.unroute('**/dashboard/mei/*/conferencia-documental?*');
      await year.fill('2026');
      await inventory.getByText(`Documento #${documents.year2026}`, {exact:true}).waitFor();
      await inventory.getByText(/CNPJ coincide com o da empresa/).waitFor();
      await inventory.getByText('A comparação de CNPJ não comprova autenticidade nem confirma receita.', {exact:true}).waitFor();
      console.log(`PASS: ${width}px; emitente coincidente/divergente/ausente, inventario, troca de ano e erro 503`);
      await scope.locator('input[type="month"]').fill(month);
      const buy = scope.getByRole('button',{name:/^Pagar servi/});
      await buy.waitFor();
      await page.waitForFunction(() => {
        const buttons = [...document.querySelectorAll('#mei-das-oficial button')];
        return buttons.some(b => b.textContent.startsWith('Pagar servi') && !b.disabled);
      });
      assert(await emit.isDisabled(), 'DAS enabled before purchase');
      const before = await checked(await client.post(`/imposto/mei/${empresaId}/das`,{
        headers,data:{periodo_apuracao:competence,formato:'pdf'}
      }),[403]);
      assert.equal((await before.json()).detail.tipo_bloqueio,'AUTORIDADE_ECONOMICA_MEI_COMPETENCIA_AUSENTE');
      assert.equal((await getStats()).serpro_calls,begin.serpro_calls);
      await buy.click();
      await page.waitForURL(/checkout\.example\.invalid\/local\/\d+$/);
      const orderId = Number(new URL(page.url()).pathname.split('/').pop());
      assert.equal(virtualCheckouts,1);
      const pending = await recover(competence);
      assert.equal(pending.estado,'pending');
      assert.equal(pending.autorizado,false);
      const key = pending.checkout_idempotency_key;
      const afterCheckout = await getStats();
      assert.equal(afterCheckout.orders,begin.orders+1);
      assert.equal(afterCheckout.gateway_calls,begin.gateway_calls+1);
      // Reload and resume must reuse the exact checkout and retry key.
      await page.goto(UI,{waitUntil:'domcontentloaded'});
      await scope.waitFor();
      await scope.getByRole('button',{name:'Retomar pagamento',exact:true}).click();
      await page.waitForURL(pending.checkout_url);
      assert.equal(virtualCheckouts,2);
      assert.equal((await recover(competence)).checkout_idempotency_key,key);
      assert.deepEqual(await getStats(),afterCheckout);
      await checked(await client.post('/__smoke__/confirm',{headers,data:{ordem_id:orderId}}));
      const paid = await recover(competence);
      assert.equal(paid.estado,'paid');
      assert.equal(paid.autorizado,true);
      assert.equal(paid.checkout_url,null);
      const confirmed = await getStats();
      assert.equal(confirmed.bindings,begin.bindings+1);
      assert.equal(confirmed.gateway_calls,afterCheckout.gateway_calls);
      await page.goto(UI,{waitUntil:'domcontentloaded'});
      await scope.waitFor();
      await scope.getByRole('button',{name:'Atualizar confirma\u00e7\u00e3o da compra',exact:true}).click();
      await page.waitForFunction(() => [...document.querySelectorAll('#mei-das-oficial button')]
        .some(b => b.textContent==='Emitir DAS oficial' && !b.disabled));
      await scope.locator('select').selectOption('pdf');
      const downloadPromise = page.waitForEvent('download');
      const pdfResponse = page.waitForResponse(r => r.url().endsWith(`/imposto/mei/${empresaId}/das`) && r.request().method()==='POST');
      await emit.click();
      const pdf = await (await checked(await pdfResponse)).json();
      assert.equal(pdf.estado_oficial,'emitido');
      assert.equal(pdf.periodo_apuracao,competence);
      const download = await downloadPromise;
      assert.equal(download.suggestedFilename(),`das-mei-${competence}.pdf`);
      const pdfPath = path.join(output,`SIMULADO-${width}-${download.suggestedFilename()}`);
      await download.saveAs(pdfPath);
      const bytes = await fs.readFile(pdfPath);
      assert(bytes.equals(Buffer.from(pdf.documento.pdf_base64,'base64')));
      assert(bytes.includes(Buffer.from('SEM VALIDADE FISCAL')));
      await scope.locator('select').selectOption('codigo_barras');
      const barcodeResponse = page.waitForResponse(r => r.url().endsWith(`/imposto/mei/${empresaId}/das`) && r.request().method()==='POST');
      await emit.click();
      const barcode = await (await checked(await barcodeResponse)).json();
      assert.equal(barcode.estado_oficial,'emitido');
      assert.deepEqual(barcode.documento.codigo_barras,BARCODE);
      for (const block of BARCODE) await scope.getByText(block,{exact:true}).waitFor();
      // Authority for the paid month must never enable a different month.
      const untouched = '2026-10';
      const blocked = await checked(await client.post(`/imposto/mei/${empresaId}/das`,{
        headers,data:{periodo_apuracao:untouched.replace('-',''),formato:'pdf'}
      }),[403]);
      assert.equal((await blocked.json()).detail.tipo_bloqueio,'AUTORIDADE_ECONOMICA_MEI_COMPETENCIA_AUSENTE');
      await scope.locator('input[type="month"]').fill(untouched);
      await buy.waitFor();
      assert(await emit.isDisabled());
      const end = await getStats();
      assert.equal(end.serpro_calls,begin.serpro_calls+2);
      assert.equal(end.orders,begin.orders+1);
      assert.equal(end.gateway_calls,begin.gateway_calls+1);
      assert.equal(end.bindings,begin.bindings+1);
      const dimensions = await page.evaluate(() => ({width:innerWidth,content:document.documentElement.scrollWidth}));
      assert(dimensions.content<=dimensions.width,JSON.stringify(dimensions));
      assert.deepEqual(errors,[],'JavaScript errors');
      assert.deepEqual(external,[],'Unexpected external requests');
      await page.screenshot({path:path.join(output,`smoke-${width}.png`),fullPage:true});
      results.push({width,competence,registered:true,login:true,pendingResume:true,
        simulatedConfirmation:true,pdfDownload:true,barcode:true,otherCompetenceBlocked:true,
        noDuplicateCharge:true,noOverflow:true,noJavaScriptErrors:true});
      console.log(`PASS: ${width}px; checkout, retomada, confirmacao simulada, PDF, codigo de barras, competencia isolada`);
      await context.close();
    }
    await fs.writeFile(path.join(output,'resultado.json'),JSON.stringify({
      emitterObservationVerified:true,documentaryInventoryVerified:true,status:'PASS',providerMode:'SIMULATED',webhookVerified:false,
      realPaymentVerified:false,realSerproVerified:false,scenarios:results
    },null,2));
  } finally {
    await browser.close();
    await client.dispose();
  }
}
main().catch(error => { console.error(error); process.exitCode=1; });
