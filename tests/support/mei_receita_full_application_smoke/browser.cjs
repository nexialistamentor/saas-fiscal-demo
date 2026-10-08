// TEST ONLY: real local HTTP routes; simulated payment and fiscal provider.
const { createRequire } = require('node:module');
const path = require('node:path');
const fs = require('node:fs/promises');
const assert = require('node:assert/strict');
const repo = path.resolve(process.argv[2]);
const output = path.resolve(process.argv[3]);
const localRequire = createRequire(path.join(process.env.SOLVERIS_PLAYWRIGHT_ROOT, 'package.json'));
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
    const pendingEmail = `mei.pending.${Date.now()}@example.com`;
    const blockedOpening = await client.post('/auth/register', {data:{
      email:`blocked.${Date.now()}@example.com`, password:PASSWORD,
      nome:'SIMULACAO BLOQUEADA', tipo_usuario:'mei', mei_intent:'opening'
    }});
    assert.equal(blockedOpening.status(),409);
    console.log('PASS: backend bloqueia novo cadastro em abertura com HTTP 409');
    const pendingRegistered = await checked(await client.post('/auth/register', {data:{
      email:pendingEmail, password:PASSWORD, nome:'SIMULACAO LOCAL PENDENTE',
      tipo_usuario:'mei', mei_intent:'existing', documento:'11222333000181'
    }}), [200,201]);
    const pendingId = (await pendingRegistered.json()).empresa_id;
    assert(Number.isInteger(pendingId) && pendingId > 0);
    const pendingLogin = await checked(await client.post('/auth/login', {
      form:{username:pendingEmail,password:PASSWORD}
    }));
    const pendingHeaders = {
      Authorization:`Bearer ${(await pendingLogin.json()).access_token}`
    };
    const seededPending = await checked(await client.post(
      '/__smoke__/legacy-opening-seed',{headers:pendingHeaders}
    ));
    assert.equal((await seededPending.json()).empresa_id,pendingId);
    await checked(await client.post('/auth/accept-terms',{headers:pendingHeaders}));
    await checked(await client.post('/auth/consent',{headers:pendingHeaders}));
    const pendingCompanies = async () =>
      (await checked(await client.get('/empresas/',{headers:pendingHeaders}))).json();
    const beforePending = await pendingCompanies();
    assert.equal(beforePending.length,1);
    assert.equal(beforePending[0].id,pendingId);
    assert.equal(beforePending[0].status_empresa,'em_abertura');
    assert.equal(beforePending[0].cnpj,null);

    for (const width of [1280,390]) {
      await checked(await client.post('/__smoke__/reset-rate-limit',{headers}));
      const context = await browser.newContext({viewport:{width,height:900}});
      try {
        const page = await context.newPage();
        const errors = [], external = [], fiscal = [];
        page.on('pageerror',e=>errors.push(e.message));
        page.on('request',r=>{
          const u = new URL(r.url());
          if (u.port==='8766' &&
              /\/(?:imposto|dashboard|checkout)(?:\/|$)/.test(u.pathname)) {
            fiscal.push(u.pathname);
          }
        });
        await context.route('**/*',route=>{
          const u = new URL(route.request().url());
          if (u.hostname==='127.0.0.1' && ['5175','8766'].includes(u.port))
            return route.continue();
          external.push(u.origin);
          return route.abort();
        });
        await page.goto(UI,{waitUntil:'domcontentloaded'});
        await page.locator('#solveris-login-email').fill(pendingEmail);
        await page.locator('input[type="password"]').fill(PASSWORD);
        const response = page.waitForResponse(r=>
          r.url().endsWith('/auth/login') && r.request().method()==='POST');
        await page.getByRole('button',{name:'Entrar',exact:true}).click();
        await checked(await response);
        const heading = page.getByRole('heading',{
          name:'Seu acesso MEI precisa de confirma\u00e7\u00e3o',exact:true
        });
        await heading.waitFor();
        assert.equal(await page.getByRole('button',{
          name:'Come\u00e7ar minha abertura',exact:true
        }).count(),0);
        assert.equal(await page.locator('.solveris-opening-steps').count(),0);
        assert.equal(await page.locator('#mei-das-oficial').count(),0);
        assert.equal(await page.locator('#mei-assistente-titulo').count(),0);
        assert.equal(await page.getByRole('region',{name:'Receitas sem nota informadas',exact:true}).count(),0);
        assert.equal(await page.evaluate(()=>
          document.documentElement.scrollWidth > window.innerWidth),false);
        await page.screenshot({
          path:path.join(output,`acesso-pendente-${width}.png`),fullPage:true
        });
        await page.reload({waitUntil:'domcontentloaded'});
        await heading.waitFor();
        assert.deepEqual(await pendingCompanies(),beforePending);
        assert.deepEqual(fiscal,[]);
        assert.deepEqual(external,[]);
        assert.deepEqual(errors,[]);
        await page.getByRole('button',{name:'Sair',exact:true}).click();
        await page.locator('#solveris-login-email').waitFor();
        console.log(`PASS: ${width}px; acesso pendente, sem abertura ou pedidos fiscais, dados preservados, reload e logout`);
      } finally {
        await context.close();
      }
    }
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

      const revenue = page.getByRole('region',{name:'Receitas sem nota informadas',exact:true});
      await revenue.waitFor();
      const revenueYear = revenue.getByLabel('Ano das receitas');
      await revenueYear.fill('2026');
      const firstTotal = width===1280 ? '100,10' : '200,40';
      const finalTotal = width===1280 ? '100,30' : '200,60';
      const revenueCallsBefore = await getStats();
      const fillRevenue = async (date,value) => {
        await revenue.getByLabel('Data da receita').fill(date);
        await revenue.getByLabel('Valor da receita (R$)').fill(value);
        await revenue.getByLabel('Categoria da receita').selectOption('servicos');
      };
      await fillRevenue(width===1280?'2026-01-10':'2026-03-10','100.10');
      await revenue.getByRole('button',{name:'Registrar receita',exact:true}).click();
      await revenue.getByText('Receita registrada.',{exact:true}).waitFor();
      await revenue.getByTestId('receitas-total-parcial').filter({hasText:firstTotal}).waitFor();
      await revenueYear.fill('2025');
      await revenue.getByText('Nenhuma receita informada para este ano.',{exact:true}).waitFor();
      assert.equal(await revenue.getByTestId('receitas-total-parcial').count(),0);
      await revenueYear.fill('2026');
      await revenue.getByTestId('receitas-total-parcial').filter({hasText:firstTotal}).waitFor();
      const postPattern=`**/dashboard/mei/${empresaId}/receitas-informadas`;
      let discardConfirmation=true, uncertainIdentity=null;
      await context.route(postPattern, async route => {
        if(route.request().method()!=='POST' || !discardConfirmation) return route.continue();
        discardConfirmation=false;
        uncertainIdentity=route.request().postDataJSON().identidade_receita;
        const actual=await route.fetch({maxRetries:0});
        await checked(actual);
        return route.abort('failed');
      });
      await fillRevenue(width===1280?'2026-02-10':'2026-04-10','0.20');
      await revenue.getByRole('button',{name:'Registrar receita',exact:true}).click();
      await revenue.getByRole('alert').waitFor();
      await revenue.getByRole('button',{name:'Recuperar registro pendente',exact:true}).waitFor();
      await page.reload({waitUntil:'domcontentloaded'});
      await revenue.waitFor();
      await revenue.getByRole('button',{name:'Recuperar registro pendente',exact:true}).waitFor();
      assert.equal(await revenue.getByLabel('Valor da receita (R$)').inputValue(),'0.20');
      assert.equal(await revenue.getByLabel('Valor da receita (R$)').isDisabled(),true);
      const recoveryResponse=page.waitForResponse(r=>r.url().endsWith(`/dashboard/mei/${empresaId}/receitas-informadas`) && r.request().method()==='POST');
      await revenue.getByRole('button',{name:'Recuperar registro pendente',exact:true}).click();
      const recovered=await (await checked(await recoveryResponse)).json();
      assert.equal(recovered.identidade_receita,uncertainIdentity);
      await revenue.getByText('Receita registrada.',{exact:true}).waitFor();
      await revenue.getByTestId('receitas-total-parcial').filter({hasText:finalTotal}).waitFor();
      await context.unroute(postPattern);
      const annual=await (await checked(await client.get(`/dashboard/mei/${empresaId}/receitas-informadas?ano_calendario=2026`,{headers}))).json();
      assert.equal(annual.total_receitas_incluidas,width===1280?'100.30':'200.60');
      assert.equal(annual.receitas_incluidas.length,width===1280?2:4);
      assert.equal(annual.completude_anual_comprovada,false);
      assert.equal(annual.totais_por_origem.documento,'0.00');
      assert(annual.receitas_incluidas.every(row=>row.origem==='informada_sem_nota'));
      const pendingDenied=await checked(await client.get(`/dashboard/mei/${pendingId}/receitas-informadas?ano_calendario=2026`,{headers}),[403]);
      assert.equal(pendingDenied.status(),403);
      assert.deepEqual(await getStats(),revenueCallsBefore,'Revenue flow must not call checkout or fiscal provider');
      await page.screenshot({path:path.join(output,`receitas-aplicacao-${width}.png`),fullPage:true});
      console.log(`PASS: ${width}px; login real, painel ativo, receitas reais PostgreSQL, reload e recuperação sem duplicação, sem checkout ou SERPRO`);

      const inventory = page.getByRole('region', {name: 'Documentos para conferência anual', exact: true});
      await inventory.waitFor();
      const year = inventory.getByRole('spinbutton', {name: 'Ano de referência'});
      await year.fill('2026');
      await inventory.getByText(`Documento #${documents.year2026}`, {exact:true}).waitFor();
      await inventory.getByText('Natureza observada: OPERACAO <script>observada</script>.', {exact:true}).waitFor();
      await inventory.getByText('Finalidade observada: 1.', {exact:true}).waitFor();
      await inventory.getByText(/CFOP observado: 5102/).waitFor();
      await inventory.getByText(/CFOP observado: 5910/).waitFor();
      assert.equal(await inventory.locator('script').count(), 0);
      await inventory.getByText('Natureza observada: não informada.', {exact:true}).waitFor();
      await inventory.getByText('Finalidade observada: não informada.', {exact:true}).waitFor();

      await inventory.getByText(/CNPJ coincide com o da empresa/).waitFor();
      await inventory.getByText('A comparação de CNPJ não comprova autenticidade nem confirma receita.', {exact:true}).waitFor();
      await inventory.getByText(`Documento #${documents.undated}`, {exact:true}).waitFor();
      await inventory.getByText(/CNPJ do emitente não informado/).waitFor();
      assert.equal(await inventory.getByText(`Documento #${documents.year2025}`, {exact:true}).count(), 0);
      await year.fill('2025');
      await inventory.getByText(`Documento #${documents.year2025}`, {exact:true}).waitFor();
      await inventory.getByText('Finalidade observada: 4.', {exact:true}).waitFor();
      await inventory.getByText(/CFOP observado: não informado/).waitFor();
      assert.equal(await inventory.getByText(/CFOP observado: 5102/).count(), 0);
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
      await inventory.getByText('Natureza observada: OPERACAO <script>observada</script>.', {exact:true}).waitFor();
      await inventory.getByText('Finalidade observada: 1.', {exact:true}).waitFor();
      await inventory.getByText(/CFOP observado: 5102/).waitFor();
      await inventory.getByText(/CFOP observado: 5910/).waitFor();
      assert.equal(await inventory.locator('script').count(), 0);
      await inventory.getByText('Natureza observada: não informada.', {exact:true}).waitFor();
      await inventory.getByText('Finalidade observada: não informada.', {exact:true}).waitFor();

      await inventory.getByText(/CNPJ coincide com o da empresa/).waitFor();
      await inventory.getByText('A comparação de CNPJ não comprova autenticidade nem confirma receita.', {exact:true}).waitFor();
      console.log(`PASS: ${width}px; natureza, finalidade, CFOPs por item, ausencias, texto escapado, troca de ano e erro 503`);
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
        noDuplicateCharge:true,noOverflow:true,noJavaScriptErrors:true,
        revenuePersistence:true,revenueUncertainRecovery:true,revenuePartialTotals:true});
      console.log(`PASS: ${width}px; checkout, retomada, confirmacao simulada, PDF, codigo de barras, competencia isolada`);
      await page.getByRole('button',{name:'Sair',exact:true}).click();
      await page.locator('#solveris-login-email').waitFor();
      await context.close();
    }
    await fs.writeFile(path.join(output,'resultado.json'),JSON.stringify({
      fullApplicationStartupVerified:true,realLoginVerified:true,revenueUiApiPostgresVerified:true,operationObservationVerified:true,emitterObservationVerified:true,documentaryInventoryVerified:true,status:'PASS',providerMode:'SIMULATED',webhookVerified:false,
      realPaymentVerified:false,realSerproVerified:false,scenarios:results
    },null,2));
  } finally {
    await browser.close();
    await client.dispose();
  }
}
main().catch(error => { console.error(error); process.exitCode=1; });
