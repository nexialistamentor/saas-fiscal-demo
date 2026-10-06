"""Own disposable PostgreSQL and child processes; preserve existing local servers."""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = Path(sys.argv[1] if len(sys.argv)>1 else r'C:\dev\saas-fiscal-demo-mei').resolve()
EXPECTED = {'e8c6cf926b88a3d3acd0ec5aa5a2b5269473f03b',
            '4ab12627817fab5f3b9b8f435bbda4c27e4e130e'}
def command(args, **kwargs):
    return subprocess.run(args,check=True,text=True,capture_output=True,timeout=60,**kwargs)

def ready(url, process):
    deadline = time.monotonic()+45
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    while time.monotonic()<deadline:
        if process.poll() is not None:
            raise RuntimeError('CHILD_PROCESS_EXITED - inspect logs')
        try:
            with opener.open(url,timeout=1) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(.2)
    raise RuntimeError('LOCAL_SERVER_TIMEOUT - inspect logs')

def main():
    assert (REPO/'frontend-dashboard/package.json').is_file(), 'REPOSITORY_NOT_FOUND'
    head = command(['git','-C',str(REPO),'rev-parse','HEAD']).stdout.strip()
    baseline = '113e89e4d11bde1a24fedb2bb8d94a4b071b79d3'
    assert head == baseline, 'HEAD_REQUIRES_REVIEW'
    paths = ['app', 'frontend-dashboard']
    committed = subprocess.run(
        ['git', '-C', str(REPO), 'diff', '--quiet', baseline, 'HEAD', '--', *paths]
    )
    assert committed.returncode == 0, 'APPLICATION_DIFF_REQUIRES_REVIEW'
    working = subprocess.run(
        ['git', '-C', str(REPO), 'diff', '--quiet', 'HEAD', '--', *paths]
    )
    assert working.returncode == 0, 'LOCAL_APPLICATION_DIFF_REQUIRES_REVIEW'

    for port in (8766,5175):
        with socket.socket() as probe:
            probe.bind(('127.0.0.1',port))
    command(['docker','version','--format','{{.Server.Version}}'])
    npm = shutil.which('npm.cmd') if os.name=='nt' else shutil.which('npm')
    node = shutil.which('node')
    assert npm and node, 'NODE_OR_NPM_NOT_FOUND'
    assert (REPO/'_pw_tmp/node_modules/playwright').is_dir(), 'PLAYWRIGHT_NOT_FOUND'
    assert (REPO/'frontend-dashboard/node_modules/vite').is_dir(), 'VITE_NOT_INSTALLED'
    output = Path(tempfile.mkdtemp(prefix='solveris-mei-e2e-'))
    print('RESULTADOS:',output,flush=True)
    (output/'metadata.json').write_text(json.dumps({'head':head,'mode':'SIMULATED',
        'productionModified':False,'webhookVerified':False},indent=2))
    container = 'solveris-mei-smoke-'+uuid.uuid4().hex[:12]
    password = uuid.uuid4().hex
    children, logs = [], []
    started = False
    try:
        command(['docker','run','--detach','--rm','--name',container,
                 '-e','POSTGRES_PASSWORD='+password,'-e','POSTGRES_DB=mei_smoke',
                 '-p','127.0.0.1::5432','postgres:17.10-trixie'])
        started = True
        mapping = command(['docker','port',container,'5432/tcp']).stdout.strip()
        assert mapping.startswith('127.0.0.1:') and '\n' not in mapping
        port = int(mapping.rsplit(':',1)[1])
        import psycopg2
        deadline = time.monotonic()+45
        while True:
            try:
                connection = psycopg2.connect(host='127.0.0.1',port=port,
                    user='postgres',password=password,dbname='mei_smoke',connect_timeout=1)
                connection.close()
                break
            except psycopg2.Error:
                if time.monotonic()>deadline:
                    raise RuntimeError('POSTGRES_START_TIMEOUT') from None
                time.sleep(.25)
        preserved = {'SYSTEMROOT','WINDIR','PATH','PATHEXT','TEMP','TMP','USERPROFILE',
                     'APPDATA','LOCALAPPDATA','PROGRAMDATA','COMSPEC','PROGRAMFILES',
                     'PROGRAMFILES(X86)','SYSTEMDRIVE'}
        env = {key:value for key,value in os.environ.items() if key.upper() in preserved}
        env.update(ENVIRONMENT='test',PYTHON_DOTENV_DISABLED='1',
            DATABASE_URL=f'postgresql+psycopg2://postgres:{password}@127.0.0.1:{port}/mei_smoke?sslmode=disable',
            MERCADO_PAGO_ENABLED='false',SERPRO_PGMEI_ENABLED='false',
            SERPRO_PGMEI_ACCESS_MODE='canary',SERPRO_PGMEI_CANARY_CNPJ='12345678000195',
            REQUEST_LOG_RETENTION_DAYS='0',PYTHONUNBUFFERED='1')
        backend_log = open(output/'backend.log','w',encoding='utf-8')
        logs.append(backend_log)
        backend = subprocess.Popen([sys.executable,str(ROOT/'server.py'),str(REPO)],
            env=env,cwd=REPO,stdout=backend_log,stderr=subprocess.STDOUT)
        children.append(backend)
        ready('http://127.0.0.1:8766/health',backend)
        # Separate Vite process; current 5173/8765 remain untouched.
        front_env = env.copy()
        front_env.pop('DATABASE_URL')
        front_env['VITE_API_URL']='http://127.0.0.1:8766'
        vite = REPO/'frontend-dashboard/node_modules/vite/bin/vite.js'
        front_log = open(output/'frontend.log','w',encoding='utf-8')
        logs.append(front_log)
        front = subprocess.Popen([node,str(vite),'--host','127.0.0.1','--port','5175','--strictPort'],
            cwd=REPO/'frontend-dashboard',env=front_env,stdout=front_log,stderr=subprocess.STDOUT)
        children.append(front)
        ready('http://127.0.0.1:5175/mei/',front)
        result = subprocess.run([node,str(ROOT/'browser.cjs'),str(REPO),str(output)],
            cwd=REPO,env=front_env,timeout=180)
        if result.returncode:
            raise RuntimeError('BROWSER_SMOKE_FAILED - inspect logs and output')
        print('SMOKE_SIMULADO=PASS',flush=True)
        print('RESULTADOS:',output,flush=True)
        print('WEBHOOK_REAL/PAGAMENTO_REAL/SERPRO_REAL=NAO_TESTADOS',flush=True)
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=10)
        for log in logs:
            log.close()
        if started:
            removal = subprocess.run(['docker','rm','--force',container],
                capture_output=True,text=True,timeout=30)
            if removal.returncode:
                print('CLEANUP_FAILED_CONTAINER:',container,flush=True)

if __name__=='__main__':
    main()
