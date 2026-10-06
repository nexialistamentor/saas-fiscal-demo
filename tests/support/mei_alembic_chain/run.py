"""Verify canonical Alembic bootstrap on disposable local PostgreSQL only."""
import json, os, subprocess, sys, tempfile, time, uuid
from pathlib import Path

def call(args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=120, **kwargs)

def main():
    repo = Path(sys.argv[1]).resolve()
    head = call(['git', '-C', str(repo), 'rev-parse', 'HEAD']).stdout.strip()
    assert head == 'e759b9038a0d6c45bd9e38554650d184d71bbe66', 'HEAD_REQUIRES_REVIEW'
    call(['git', '-C', str(repo), 'diff', '--quiet', 'HEAD', '--', 'app', 'migrations', 'alembic.ini'])
    call(['docker', 'version', '--format', '{{.Server.Version}}'])
    output = Path(tempfile.mkdtemp(prefix='solveris-mei-alembic-'))
    print('RESULTADOS:', output, flush=True)
    container = 'solveris-mei-alembic-' + uuid.uuid4().hex[:12]
    password = uuid.uuid4().hex
    started = False
    try:
        call(['docker', 'run', '--detach', '--rm', '--name', container,
              '-e', 'POSTGRES_PASSWORD='+password, '-e', 'POSTGRES_DB=mei_chain',
              '-p', '127.0.0.1::5432', 'postgres:17.10-trixie'])
        started = True
        mapping = call(['docker', 'port', container, '5432/tcp']).stdout.strip()
        assert mapping.startswith('127.0.0.1:') and '\n' not in mapping
        port = int(mapping.rsplit(':', 1)[1])
        import psycopg2
        deadline = time.monotonic()+45
        while True:
            try:
                connection = psycopg2.connect(host='127.0.0.1', port=port, user='postgres',
                    password=password, dbname='mei_chain', connect_timeout=1)
                connection.close(); break
            except psycopg2.Error:
                if time.monotonic() > deadline: raise RuntimeError('POSTGRES_START_TIMEOUT') from None
                time.sleep(.25)
        allowed = {'PATH','SYSTEMROOT','WINDIR','PATHEXT','TEMP','TMP','USERPROFILE',
                   'APPDATA','LOCALAPPDATA','COMSPEC','SYSTEMDRIVE','PROGRAMFILES','PROGRAMFILES(X86)'}
        env = {k:v for k,v in os.environ.items() if k.upper() in allowed}
        env.update(ENVIRONMENT='test', PYTHON_DOTENV_DISABLED='1', ALEMBIC_RUNNING='1',
            DATABASE_URL=f'postgresql+psycopg2://postgres:{password}@127.0.0.1:{port}/mei_chain?sslmode=disable',
            MERCADO_PAGO_ENABLED='false', SERPRO_PGMEI_ENABLED='false')
        with (output/'alembic.log').open('w',encoding='utf-8') as log:
            result = subprocess.run([sys.executable,'-m','alembic','upgrade','head'],
                cwd=repo,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=180)
        if result.returncode:
            print('FULL_ALEMBIC_CHAIN=FAIL; consultar alembic.log',flush=True)
            raise RuntimeError('ALEMBIC_CHAIN_FAILED')
        with psycopg2.connect(host='127.0.0.1',port=port,user='postgres',password=password,dbname='mei_chain') as db:
            with db.cursor() as cursor:
                cursor.execute('SELECT version_num FROM alembic_version'); revisions=cursor.fetchall()
                assert revisions == [('0058_documento_operacao_observada',)], revisions
                cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='documentos_fiscais'")
                columns={r[0] for r in cursor.fetchall()}
                assert {'cnpj_emitente','natureza_operacao_observada','finalidade_emissao_observada'} <= columns
        (output/'resultado.json').write_text(json.dumps({'head':head,'fullAlembicBootstrap':'PASS',
            'productionTested':False,'revision':revisions[0][0]},indent=2),encoding='utf-8')
        print('FULL_ALEMBIC_CHAIN=PASS; OBSERVED_COLUMNS=PASS; PRODUCTION=NOT_TESTED',flush=True)
    finally:
        if started:
            removal=subprocess.run(['docker','rm','--force',container],capture_output=True,text=True,timeout=30)
            print('DISPOSABLE_CONTAINER_REMOVED=' + ('PASS' if removal.returncode==0 else 'FAIL'),flush=True)
if __name__=='__main__': main()
