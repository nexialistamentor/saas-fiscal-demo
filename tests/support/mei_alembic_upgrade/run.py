"""Verify canonical Alembic bootstrap on disposable local PostgreSQL only."""
import json, os, subprocess, sys, tempfile, time, uuid
from pathlib import Path

def call(args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=120, **kwargs)

def main():
    repo = Path(sys.argv[1]).resolve()
    head = call(['git', '-C', str(repo), 'rev-parse', 'HEAD']).stdout.strip()
    assert head == '159718986ef130d1aed3e525ee7503cabc485f8a', 'HEAD_REQUIRES_REVIEW'
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
        def migrate(revision, action='upgrade'):
            with (output/'alembic.log').open('a',encoding='utf-8') as log:
                result = subprocess.run([sys.executable,'-m','alembic',action,revision],
                    cwd=repo,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=180)
            if result.returncode: raise RuntimeError('ALEMBIC_FAILED - consultar alembic.log')
        def connect():
            return psycopg2.connect(host='127.0.0.1',port=port,user='postgres',
                password=password,dbname='mei_chain')
        migrate('0056_mei_competencia_checkout_intent')
        with connect() as db:
            with db.cursor() as cursor:
                cursor.execute("INSERT INTO documentos_fiscais (id, numero_nota, tipo, valor_total, data_emissao) VALUES (91001,'LEGADO-SINTETICO','saida',123.45,'2025-12-31'),(91002,'SEM-DATA',NULL,NULL,NULL)")
                cursor.execute("INSERT INTO itens_fiscais (id,documento_id,cfop,quantidade) VALUES (92001,91001,'5102',2),(92002,91001,'5910',1)")
                cursor.execute('SELECT id,numero_nota,tipo,valor_total,data_emissao FROM documentos_fiscais ORDER BY id')
                documents=cursor.fetchall()
                cursor.execute('SELECT id,documento_id,cfop,quantidade FROM itens_fiscais ORDER BY id')
                items=cursor.fetchall()
        def verify():
            with connect() as db:
                with db.cursor() as cursor:
                    cursor.execute('SELECT version_num FROM alembic_version')
                    assert cursor.fetchall()==[('0058_documento_operacao_observada',)]
                    cursor.execute('SELECT id,numero_nota,tipo,valor_total,data_emissao FROM documentos_fiscais ORDER BY id')
                    assert cursor.fetchall()==documents, 'LEGACY_DOCUMENT_CHANGED'
                    cursor.execute('SELECT id,documento_id,cfop,quantidade FROM itens_fiscais ORDER BY id')
                    assert cursor.fetchall()==items, 'LEGACY_ITEM_CHANGED'
                    cursor.execute('SELECT cnpj_emitente,natureza_operacao_observada,finalidade_emissao_observada FROM documentos_fiscais ORDER BY id')
                    assert cursor.fetchall()==[(None,None,None),(None,None,None)], 'LEGACY_INFERENCE_DETECTED'
        migrate('head'); verify()
        migrate('0056_mei_competencia_checkout_intent','downgrade')
        migrate('head'); verify()
        (output/'resultado.json').write_text(json.dumps({'head':head,
            'upgrade0056To0058':'PASS','legacyDocumentsAndItemsPreserved':True,
            'legacyObservationsRemainNull':True,'downgradeReupgrade':'PASS',
            'syntheticData':True,'productionTested':False},indent=2),encoding='utf-8')
        print('POPULATED_UPGRADE_0056_0058=PASS; LEGACY_PRESERVED=PASS; NO_INFERENCE=PASS',flush=True)
        print('DOWNGRADE_REUPGRADE=PASS; PRODUCTION=NOT_TESTED',flush=True)
    finally:
        if started:
            removal=subprocess.run(['docker','rm','--force',container],capture_output=True,text=True,timeout=30)
            print('DISPOSABLE_CONTAINER_REMOVED=' + ('PASS' if removal.returncode==0 else 'FAIL'),flush=True)
if __name__=='__main__': main()
