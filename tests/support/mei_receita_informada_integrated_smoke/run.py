"""Local actual API/PostgreSQL/browser proof; owns all disposable resources."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error
import uuid

REPO=Path(r"C:\dev\solveris-mei-receitas-informadas")
HEAD="7ad9f7e6ca80b237261867789f9be148065aaf10"
BROWSER='import test from \'node:test\'\nimport assert from \'node:assert/strict\'\nimport { mkdtemp, writeFile, rm, readFile } from \'node:fs/promises\'\nimport { dirname, join } from \'node:path\'\nimport { fileURLToPath, pathToFileURL } from \'node:url\'\nimport { createRequire } from \'node:module\'\n\nconst repo = process.env.SOLVERIS_PROOF_REPO\nconst api = process.env.SOLVERIS_PROOF_API\nconst token = JSON.parse(await readFile(process.env.SOLVERIS_PROOF_TOKEN_FILE, \'utf8\')).token\nconst frontend = join(repo, \'frontend-dashboard\')\nconst require = createRequire(join(process.env.SOLVERIS_PLAYWRIGHT_ROOT || join(repo, \'_pw_tmp\'), \'package.json\'))\nconst { chromium } = require(\'playwright\')\nconst { createServer } = await import(pathToFileURL(join(frontend, \'node_modules/vite/dist/node/index.js\')).href)\ntest(\'tela real: gravação, totais, ano, reload incerto e isolamento em desktop e mobile\', { timeout: 120000 }, async () => {\n  let server, browser, temporary\n  try {\n    temporary = await mkdtemp(join(frontend, \'mei-receita-ui-proof-\'))\n    await writeFile(join(temporary, \'index.html\'), \'<div id="root"></div><script type="module" src="./main.jsx"></script>\')\n    await writeFile(join(temporary, \'main.jsx\'), `import React from \'react\';\nimport {createRoot} from \'react-dom/client\';\nimport MeiReceitasInformadas from \'/src/components/MeiReceitasInformadas.jsx\';\nfunction Harness(){const [empresa,setEmpresa]=React.useState(Number(new URLSearchParams(location.search).get(\'empresa\')));return <>\n<button onClick={()=>setEmpresa(empresa % 2 === 1 ? empresa + 1 : empresa - 1)}>Trocar empresa de teste</button>\n<MeiReceitasInformadas key={empresa} empresaId={empresa} usuarioId={7}/></>}\ncreateRoot(document.getElementById(\'root\')).render(<Harness/>);`)\n    server = await createServer({ root: frontend, configFile: false,\n      define: { \'import.meta.env.VITE_API_URL\': JSON.stringify(api) },\n      server: { host: \'127.0.0.1\', port: 0 }, logLevel: \'error\' })\n    await server.listen()\n    const port = server.httpServer.address().port\n    const folder = temporary.slice(frontend.length + 1).replaceAll(\'\\\\\', \'/\')\n    const url = `http://127.0.0.1:${port}/${folder}/index.html`\n    browser = await chromium.launch({ headless: true })\n    for (const width of [1280, 390]) {\n      const context = await browser.newContext({ viewport: { width, height: 900 } })\n      const page = await context.newPage()\n      const errors = [], rows = [], posts = []\n      let uncertain = false, readFailure = false\n      page.on(\'pageerror\', error => errors.push(error.message))\n      await context.addInitScript(value => localStorage.setItem(\'auth_token\', value), token)\n      await page.route(api + \'/**\', async route => {\n        const request = route.request(), parsed = new URL(request.url())\n        const match = parsed.pathname.match(/^\\/dashboard\\/mei\\/(\\d+)\\/receitas-informadas$/)\n        assert.ok(match, `UNEXPECTED_API_CALL:${parsed.pathname}`)\n        if (request.method() === \'OPTIONS\') return route.continue()\n        assert.equal(request.headers().authorization, \'Bearer \' + token)\n        const company = Number(match[1])\n        if (request.method() === \'GET\') {\n          if (readFailure) return route.fulfill({ status: 503, headers: { \'Access-Control-Allow-Origin\': \'*\' }, json: { detail: \'unavailable\' } })\n          return route.continue()\n        }\n        assert.equal(request.method(), \'POST\')\n        const payload = request.postDataJSON(); posts.push({ company, payload })\n        const actual = await route.fetch({ maxRetries: 0 })\n        assert.equal(actual.status(), 200, await actual.text())\n        const row = await actual.json()\n        if (!rows.some(x => x.id === row.id)) rows.push(row)\n        if (uncertain) { uncertain = false; return route.abort(\'failed\') }\n        return route.fulfill({ response: actual })\n      })\n      await page.goto(url + \'?empresa=\' + (width === 1280 ? 1 : 3))\n      try { await page.getByRole(\'heading\', { name: \'Receitas sem nota informadas\', exact: true }).waitFor({ timeout: 10000 }) }\n      catch { throw Error(\'RECEITA_UI_NOT_WIRED: \' + errors.join(\'; \')) }\n      const year = page.getByLabel(\'Ano das receitas\')\n      await year.fill(\'2026\')\n      await page.getByText(\'Nenhuma receita informada para este ano.\', { exact: true }).waitFor()\n      await page.getByLabel(\'Data da receita\').fill(\'2026-01-10\')\n      await page.getByLabel(\'Valor da receita (R$)\').fill(\'100.10\')\n      await page.getByLabel(\'Categoria da receita\').selectOption(\'servicos\')\n      await page.getByRole(\'button\', { name: \'Registrar receita\', exact: true }).click()\n      await page.getByText(\'Receita registrada.\', { exact: true }).waitFor()\n      await page.getByTestId(\'receitas-total-parcial\').filter({ hasText: \'100,10\' }).waitFor()\n      assert.equal(rows.length, 1)\n      await year.fill(\'2025\')\n      await page.getByText(\'Nenhuma receita informada para este ano.\', { exact: true }).waitFor()\n      assert.equal(await page.getByTestId(\'receitas-total-parcial\').count(), 0)\n      await year.fill(\'2026\')\n      await page.getByTestId(\'receitas-total-parcial\').filter({ hasText: \'100,10\' }).waitFor()\n      uncertain = true\n      await page.getByLabel(\'Data da receita\').fill(\'2026-02-10\')\n      await page.getByLabel(\'Valor da receita (R$)\').fill(\'0.20\')\n      await page.getByRole(\'button\', { name: \'Registrar receita\', exact: true }).click()\n      await page.getByRole(\'button\', { name: \'Recuperar registro pendente\', exact: true }).waitFor()\n      const previousIdentity = posts.at(-1).payload.identidade_receita\n      await page.reload()\n      await page.getByRole(\'button\', { name: \'Recuperar registro pendente\', exact: true }).waitFor()\n      assert.equal(await page.getByLabel(\'Valor da receita (R$)\').inputValue(), \'0.20\')\n      assert.equal(await page.getByLabel(\'Valor da receita (R$)\').isDisabled(), true)\n      await page.getByRole(\'button\', { name: \'Recuperar registro pendente\', exact: true }).click()\n      await page.getByText(\'Receita registrada.\', { exact: true }).waitFor()\n      assert.equal(posts.at(-1).payload.identidade_receita, previousIdentity)\n      assert.equal(rows.length, 2)\n      await year.fill(\'2026\')\n      await page.getByTestId(\'receitas-total-parcial\').filter({ hasText: \'100,30\' }).waitFor()\n      readFailure = true\n      await page.getByRole(\'button\', { name: \'Atualizar receitas\', exact: true }).click()\n      await page.getByRole(\'alert\').waitFor()\n      assert.equal(await page.getByTestId(\'receitas-total-parcial\').count(), 0)\n      readFailure = false\n      await page.getByRole(\'button\', { name: \'Trocar empresa de teste\' }).click()\n      await page.getByText(\'Nenhuma receita informada para este ano.\', { exact: true }).waitFor()\n      assert.equal(await page.getByTestId(\'receitas-total-parcial\').count(), 0)\n      assert.equal(await page.getByLabel(\'Valor da receita (R$)\').inputValue(), \'\')\n      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)\n      assert.deepEqual(errors, [])\n      await context.close()\n      console.log(`PASS: ${width}px; formulário, total, troca de ano, reload incerto, mesma identidade, erro 503 e empresa isolada`)\n    }\n  } finally {\n    await browser?.close(); await server?.close()\n    if (temporary) await rm(temporary, { recursive: true, force: true })\n  }\n})\n'
SERVER='import json\nfrom pathlib import Path\nimport socket\nimport sys\nimport uvicorn\nfrom fastapi import FastAPI\nfrom fastapi.middleware.cors import CORSMiddleware\nfrom app.database import SessionLocal\nfrom app import models\nfrom app.routers.dashboard_router import router\nfrom app.security import criar_token\n\nwith SessionLocal() as db:\n    db.add_all([models.User(id=7,email="proof-owner@example.invalid",hashed_password="unused"),\n                models.User(id=8,email="proof-other@example.invalid",hashed_password="unused")])\n    db.flush()\n    for identity in (1,2,3,4):\n        db.add(models.Empresa(id=identity,user_id=7,regime_tributario="mei",status_empresa="ativa"))\n    db.add(models.Empresa(id=5,user_id=8,regime_tributario="mei",status_empresa="ativa"))\n    db.add(models.Empresa(id=6,user_id=7,regime_tributario="mei",status_empresa="em_abertura"))\n    db.commit()\napp=FastAPI()\napp.add_middleware(CORSMiddleware,allow_origin_regex=r"http://127\\.0\\.0\\.1:[0-9]+",allow_methods=["GET","POST","OPTIONS"],allow_headers=["Authorization","Content-Type"])\napp.include_router(router)\n@app.get("/health")\ndef health(): return {"status":"ok"}\nsock=socket.socket()\nsock.bind(("127.0.0.1",0))\nsock.listen(128)\nPath(sys.argv[1]).write_text(json.dumps({"port":sock.getsockname()[1],"token":criar_token({"sub":"proof-owner@example.invalid"})}))\nuvicorn.Server(uvicorn.Config(app,log_level="warning")).run(sockets=[sock])\n'
def command(args,**kwargs):
 return subprocess.run(args,check=True,text=True,capture_output=True,timeout=120,**kwargs)
assert command(['git','-C',str(REPO),'rev-parse','HEAD']).stdout.strip()==HEAD,'HEAD_DIVERGENTE'
assert not command(['git','-C',str(REPO),'status','--porcelain','--untracked-files=all']).stdout.strip(),'WORKTREE_NAO_LIMPA'
assert command(['git','-C',str(REPO),'hash-object','tests/test_frontend_mei_receita_informada_ui_contract_red.test.mjs']).stdout.strip()=='325ecaf716715dd29dd1250846e1c62a52440df1','CONTRATO_ALTERADO'
assert (REPO/'frontend-dashboard/node_modules/vite').is_dir(),'VITE_AUSENTE'
playwright=Path(r'C:\dev\saas-fiscal-demo-mei\_pw_tmp')
assert (playwright/'node_modules/playwright').is_dir(),'PLAYWRIGHT_AUSENTE'
output=Path(tempfile.mkdtemp(prefix='solveris-receita-integrada-'))
print('RESULTADOS='+str(output),flush=True)
name='solveris-receita-integrada-'+uuid.uuid4().hex[:12]
password=uuid.uuid4().hex
started=False
backend=None
log=None
try:
 command(['docker','version','--format','{{.Server.Version}}'])
 command(['docker','run','--detach','--rm','--name',name,'-e','POSTGRES_PASSWORD='+password,'-e','POSTGRES_DB=receita_proof','-p','127.0.0.1::5432','postgres:17'])
 started=True
 mapping=command(['docker','port',name,'5432/tcp']).stdout.strip()
 assert mapping.startswith('127.0.0.1:') and '\n' not in mapping
 port=int(mapping.rsplit(':',1)[1])
 deadline=time.monotonic()+45
 while True:
  ready=subprocess.run(['docker','exec',name,'pg_isready','-U','postgres','-d','receita_proof'],capture_output=True,timeout=5)
  if ready.returncode==0: break
  if time.monotonic()>deadline: raise RuntimeError('POSTGRES_TIMEOUT')
  time.sleep(.2)
 allowed={'SYSTEMROOT','WINDIR','PATH','PATHEXT','TEMP','TMP','USERPROFILE','APPDATA','LOCALAPPDATA','COMSPEC'}
 env={k:v for k,v in os.environ.items() if k.upper() in allowed}
 env.update(ENVIRONMENT='test',ALEMBIC_RUNNING='1',PYTHON_DOTENV_DISABLED='1',
  DATABASE_URL=f'postgresql+psycopg2://postgres:{password}@127.0.0.1:{port}/receita_proof?sslmode=disable',
  SECRET_KEYS='test=local-disposable-revenue-proof',MERCADO_PAGO_ENABLED='false',SERPRO_PGMEI_ENABLED='false',PYTHONPATH=str(REPO))
 result=command([sys.executable,'-m','alembic','upgrade','0059_mei_receita_informada'],cwd=REPO,env=env)
 (output/'migration.log').write_text(result.stdout+result.stderr,encoding='utf-8')
 (output/'server.py').write_text(SERVER,encoding='utf-8')
 (output/'browser.test.mjs').write_text(BROWSER,encoding='utf-8')
 token_file=output/'local-session.json'
 log=(output/'backend.log').open('w',encoding='utf-8')
 backend=subprocess.Popen([sys.executable,str(output/'server.py'),str(token_file)],cwd=REPO,env=env,stdout=log,stderr=subprocess.STDOUT)
 opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
 deadline=time.monotonic()+45
 while True:
  if backend.poll() is not None: raise RuntimeError('BACKEND_ENCERROU; consultar backend.log')
  try:
   local=json.loads(token_file.read_text())
   base='http://127.0.0.1:'+str(local['port'])
   with opener.open(base+'/health',timeout=1) as response:
    if response.status==200: break
  except (OSError,ValueError): pass
  if time.monotonic()>deadline: raise RuntimeError('BACKEND_TIMEOUT')
  time.sleep(.2)
 for company,authorized,expected in [(1,False,401),(5,True,403),(6,True,403)]:
  headers={'Authorization':'Bearer '+local['token']} if authorized else {}
  request=urllib.request.Request(base+f'/dashboard/mei/{company}/receitas-informadas?ano_calendario=2026',headers=headers)
  try:
   with opener.open(request,timeout=5) as response: status=response.status
  except urllib.error.HTTPError as error: status=error.code
  assert status==expected,'GUARDA_HTTP_DIVERGENTE'
 print('MIGRACAO_E_GUARDAS_HTTP_POSTGRES=PASS',flush=True)
 browser_env={k:v for k,v in os.environ.items() if k.upper() in allowed}
 browser_env.update(SOLVERIS_PROOF_REPO=str(REPO),SOLVERIS_PROOF_API=base,SOLVERIS_PROOF_TOKEN_FILE=str(token_file),SOLVERIS_PLAYWRIGHT_ROOT=str(playwright))
 result=command(['node','--test',str(output/'browser.test.mjs')],cwd=REPO,env=browser_env)
 (output/'browser.log').write_text(result.stdout+result.stderr,encoding='utf-8')
 print(result.stdout,flush=True)
 result=command([sys.executable,'-c',"""
from decimal import Decimal
from sqlalchemy import select
from app.database import SessionLocal,engine
from app import models
with SessionLocal() as db:
 rows=db.scalars(select(models.MeiReceitaInformada).order_by(models.MeiReceitaInformada.id)).all()
 assert len(rows)==4
 for company in (1,3):
  owned=[row for row in rows if row.empresa_id==company]
  assert len(owned)==2 and sum((row.valor for row in owned),Decimal('0.00'))==Decimal('100.30')
  assert all(row.usuario_id==7 and row.origem=='informada_sem_nota' for row in owned)
 assert not any(row.empresa_id in (2,4,5,6) for row in rows)
 assert len({(row.empresa_id,row.identidade_receita) for row in rows})==4
engine.dispose()
print('QUATRO_REGISTROS_POSTGRES=PASS; CENTAVOS_E_EMPRESAS_PRESERVADOS')
"""],cwd=REPO,env=env)
 print(result.stdout,flush=True)
 assert not command(['git','-C',str(REPO),'status','--porcelain','--untracked-files=all']).stdout.strip(),'WORKTREE_ALTERADA'
 (output/'metadata.json').write_text(json.dumps({'head':HEAD,'mode':'LOCAL_REAL_API_POSTGRES_SYNTHETIC_DATA','browserWidths':[1280,390],'databaseRows':4,'productionAccessed':False,'providersCalled':False,'fullApplicationLoginTested':False,'uncertainCommit':'real POST committed, browser acknowledgement discarded','read503':'browser injected failure'},indent=2),encoding='utf-8')
 print('SMOKE_COMPONENTE_API_POSTGRES=PASS; PRODUCAO_NAO_ACESSADA',flush=True)
except subprocess.CalledProcessError as error:
 print(error.stdout or '',end=''); print(error.stderr or '',end='')
 print('STOP=PROVA_INTEGRADA_FALHOU; SEM_REPETICAO_AUTOMATICA',flush=True)
 sys.exit(1)
finally:
 if backend is not None and backend.poll() is None:
  backend.terminate()
  try: backend.wait(timeout=10)
  except subprocess.TimeoutExpired: backend.kill(); backend.wait(timeout=10)
 if log: log.close()
 if started:
  removed=subprocess.run(['docker','rm','--force',name],capture_output=True,text=True,timeout=30)
  print('CONTAINER_REMOVIDO='+('PASS' if removed.returncode==0 else 'VERIFICAR'),flush=True)
 token_file=output/'local-session.json'
 if token_file.exists(): token_file.unlink()
