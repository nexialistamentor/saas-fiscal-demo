/**
 * SOLVERIS.MEI-ANISTIA-001 smoke humano-assistido: login real no browser.
 * Exclusivamente conta MEI de teste. Não use contas reais/clientes.
 * MEI_SMOKE_URL=https://preview.vercel.app/mei?... node tests/smokeMeiAnistiaAuth.mjs
 * Não cria usuário, não envia documento, não emite DAS, não compra serviço.
 */
import { chromium } from 'playwright'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const url=process.env.MEI_SMOKE_URL
if (!url || !/^https:\/\//.test(url) || !new URL(url).pathname.endsWith('/mei')) {
  console.error('Defina MEI_SMOKE_URL com a URL HTTPS da preview integrada /mei.')
  process.exit(2)
}
const out=path.resolve('mei-anistia-smoke')
fs.mkdirSync(out,{recursive:true})
const report={mission:'SOLVERIS.MEI-ANISTIA-001',status:'BLOCKED',cases:[],writesBlocked:[]}
let browser

function intercept(context,profile) {
  context.route('**/*',route=>{
    const request=route.request(),method=request.method()
    if (['POST','PUT','PATCH','DELETE'].includes(method)) {
      const pathname=new URL(request.url()).pathname
      if (!['/auth/login','/auth/accept-terms','/auth/consent'].includes(pathname)) {
        report.writesBlocked.push({profile,method,pathname})
        return route.abort('blockedbyclient')
      }
    }
    return route.continue()
  })
}
async function check(page,profile) {
  const anistia=page.locator('section').filter({has:page.getByRole('heading',{name:/Perdão de dívidas do MEI/})}).first()
  const pix=page.locator('section').filter({has:page.getByRole('heading',{name:/Preparação PixMEI/})}).first()
  await anistia.waitFor({state:'visible',timeout:15000})
  await pix.waitFor({state:'visible',timeout:15000})
  const a=await anistia.innerText(),p=await pix.innerText()
  assert(a.includes('13/10/2026') && a.includes('01/01/2027'),'Datas normativas ausentes')
  assert(a.includes('ICMS nem ISS'),'Exclusão de ICMS/ISS ausente')
  assert(a.includes('não consulta'),'Aviso de ausência de consulta ausente')
  assert(p.includes('Inscrições ainda não abertas'),'PixMEI não bloqueia inscrição')
  assert(p.includes('não processa inscrições') && p.includes('não garante acesso'),'PixMEI não impede promessas')
  assert(!/garanta sua vaga|cadastre-se no PixMEI|inscreva-se agora/i.test(p))
  for(const href of ['https://www.regularize.pgfn.gov.br/','https://servicos.receitafederal.gov.br/']){
    assert.equal(await anistia.locator('a[href="'+href+'"]').count(),1)
  }
  assert.equal(await pix.locator('input[type="checkbox"]').count(),4)
  assert(!(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth+2)),'Overflow horizontal')
  await page.screenshot({path:path.join(out,profile+'-mei-logado.png'),fullPage:true,animations:'disabled'})
  report.cases.push({profile,state:'PASS',details:'Login real, telas B1+B3, datas, links e checklist'})
}
try{
  browser=await chromium.launch({headless:false})
  const desktop=await browser.newContext({viewport:{width:1365,height:900}})
  intercept(desktop,'desktop')
  const page=await desktop.newPage()
  await page.goto(url,{waitUntil:'domcontentloaded',timeout:45000})
  console.log('Faça login MANUAL apenas com conta MEI de teste autorizada.')
  console.log('O teste continua automaticamente quando o painel Meu MEI aparecer.')
  await page.getByRole('heading',{name:'Meu MEI',exact:true}).waitFor({state:'visible',timeout:300000})
  await check(page,'desktop')
  const mobile=await browser.newContext({storageState:await desktop.storageState(),viewport:{width:390,height:844},isMobile:true,hasTouch:true})
  intercept(mobile,'mobile')
  const phone=await mobile.newPage()
  await phone.goto(url,{waitUntil:'domcontentloaded',timeout:45000})
  await phone.getByRole('heading',{name:'Meu MEI',exact:true}).waitFor({state:'visible',timeout:30000})
  await check(phone,'mobile')
  assert.equal(report.writesBlocked.length,0,'O app tentou executar mutações fora do escopo')
  report.status='GREEN'
  console.log('GREEN: screenshots e result.json em '+out)
}catch(e){
  report.status='RED_OR_BLOCKED'
  report.error=String(e?.message||e)
  process.exitCode=1
  console.error(report.error)
}finally{
  if(browser) await browser.close()
  fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(report,null,2))
}
