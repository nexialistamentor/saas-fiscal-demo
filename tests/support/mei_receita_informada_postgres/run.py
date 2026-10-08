"""Disposable local PostgreSQL migration proof. Never reads production credentials."""
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

repo = Path(r'C:\dev\solveris-mei-receitas-informadas')
def command(args, **kwargs):
    return subprocess.run(args, check=True, text=True, capture_output=True, timeout=120, **kwargs)
assert command(['git','-C',str(repo),'rev-parse','HEAD']).stdout.strip() == '47115a5e7a1e7932da075d1a4a4c35e99889a2c3', 'HEAD_DIVERGENTE'
assert command(['git','-C',str(repo),'hash-object','tests/test_mei_receita_informada_persistence_contract_red.py']).stdout.strip() == '4e8153768ea3dbf8924d621a420ad4da1d4328de', 'CONTRATO_ALTERADO'
name = 'solveris-receita-proof-' + uuid.uuid4().hex[:12]
password = uuid.uuid4().hex
started = False
try:
    command(['docker','version','--format','{{.Server.Version}}'])
    command(['docker','run','--detach','--rm','--name',name,
             '-e','POSTGRES_PASSWORD='+password,'-e','POSTGRES_DB=receita_test',
             '-p','127.0.0.1::5432','postgres:17'])
    started = True
    mapping = command(['docker','port',name,'5432/tcp']).stdout.strip()
    assert mapping.startswith('127.0.0.1:') and '\n' not in mapping
    port = int(mapping.rsplit(':',1)[1])
    deadline = time.monotonic()+45
    while True:
        ready = subprocess.run(['docker','exec',name,'pg_isready','-U','postgres','-d','receita_test'], capture_output=True, timeout=5)
        if ready.returncode == 0:
            break
        if time.monotonic() > deadline:
            raise RuntimeError('POSTGRES_TIMEOUT')
        time.sleep(.3)
    allowed = {'SYSTEMROOT','WINDIR','PATH','PATHEXT','TEMP','TMP','USERPROFILE','APPDATA','LOCALAPPDATA','COMSPEC'}
    env = {k:v for k,v in os.environ.items() if k.upper() in allowed}
    env.update(ENVIRONMENT='test',ALEMBIC_RUNNING='1',PYTHON_DOTENV_DISABLED='1',
               DATABASE_URL=f'postgresql+psycopg2://postgres:{password}@127.0.0.1:{port}/receita_test?sslmode=disable',
               SECRET_KEYS='test=disposable-revenue-test-secret',MERCADO_PAGO_ENABLED='false',SERPRO_PGMEI_ENABLED='false')
    def alembic(*args):
        result = command([sys.executable,'-m','alembic',*args],cwd=repo,env=env)
        print(result.stderr, end='', flush=True)
    def python(code):
        result = command([sys.executable,'-c',code],cwd=repo,env=env)
        print(result.stdout, end='', flush=True)
    alembic('upgrade','0058_documento_operacao_observada')
    python('''
from sqlalchemy import text
from app.database import engine
with engine.begin() as c:
 c.execute(text("INSERT INTO usuarios (id,email,hashed_password) VALUES (91001,'receita-test@example.invalid','unused')"))
 c.execute(text("INSERT INTO empresas (id,user_id,regime_tributario,status_empresa) VALUES (91001,91001,'mei','ativa')"))
engine.dispose()
print('BASELINE_0058_COM_DADOS=PASS')
''')
    alembic('upgrade','0059_mei_receita_informada')
    python('''
from decimal import Decimal
from sqlalchemy import inspect, select, text
from app.database import engine, SessionLocal
from app import models
from app.services.mei_receita_informada_writer import MeiReceitaInformadaWriter
columns={c['name']:c for c in inspect(engine).get_columns('mei_receitas_informadas')}
assert columns['valor']['type'].precision == 15 and columns['valor']['type'].scale == 2
with SessionLocal() as db:
 args=dict(empresa_id=91001,usuario_id=91001,identidade_receita='11111111-1111-4111-8111-111111111111',data_receita='2026-01-10',valor='100.10',categoria='servicos')
 row=MeiReceitaInformadaWriter(db).registrar(**args)
 identity=row.id
 db.commit()
with SessionLocal() as db:
 row=MeiReceitaInformadaWriter(db).registrar(**args)
 assert row.id == identity and row.valor == Decimal('100.10')
 db.commit()
 assert len(db.scalars(select(models.MeiReceitaInformada)).all()) == 1
with engine.connect() as c:
 assert c.execute(text('SELECT count(*) FROM usuarios WHERE id=91001')).scalar_one()==1
 assert c.execute(text('SELECT count(*) FROM empresas WHERE id=91001 AND user_id=91001')).scalar_one()==1
 assert c.execute(text('SELECT version_num FROM alembic_version')).scalar_one()=='0059_mei_receita_informada'
engine.dispose()
print('ALEMBIC_ONLINE_0059=PASS')
print('NUMERIC_E_WRITER_POSTGRES=PASS')
print('REENVIO_POSTGRES=PASS')
print('DADOS_ANTERIORES_PRESERVADOS=PASS')
''')
    python('\nfrom concurrent.futures import ThreadPoolExecutor\nfrom threading import Barrier\nfrom uuid import uuid4\nfrom decimal import Decimal\nfrom sqlalchemy import select, text\nfrom app.database import engine, SessionLocal\nfrom app import models\nfrom app.services.mei_receita_informada_writer import MeiReceitaInformadaWriter, MeiReceitaInformadaWriterError\n\ndef race(values):\n identity=str(uuid4())\n barrier=Barrier(2, timeout=15)\n class RacingWriter(MeiReceitaInformadaWriter):\n  first=True\n  def _find(self, company, key):\n   found=super()._find(company,key)\n   if self.first:\n    self.first=False\n    assert found is None, \'RACE_REQUIRES_ABSENT_ROW\'\n    barrier.wait()\n   return found\n def worker(value):\n  with SessionLocal() as db:\n   db.execute(text("SET LOCAL statement_timeout = \'20000\'"))\n   try:\n    row=RacingWriter(db).registrar(empresa_id=91001,usuario_id=91001,\n      identidade_receita=identity,data_receita=\'2026-01-10\',valor=value,categoria=\'servicos\')\n    row_id=row.id\n    db.commit()\n    return (\'ok\',row_id,value)\n   except MeiReceitaInformadaWriterError as error:\n    db.rollback()\n    assert str(error)==\'RECEITA_INFORMADA_RECUSADA\'\n    return (\'rejected\',None,value)\n with ThreadPoolExecutor(max_workers=2) as pool:\n  jobs=[pool.submit(worker,value) for value in values]\n  results=[job.result(timeout=30) for job in jobs]\n with SessionLocal() as db:\n  rows=db.scalars(select(models.MeiReceitaInformada).where(models.MeiReceitaInformada.identidade_receita==identity)).all()\n  assert len(rows)==1, \'RACE_DUPLICATED_REVENUE\'\n  winner=rows[0]\n  success=[r for r in results if r[0]==\'ok\']\n  assert all(r[1]==winner.id and Decimal(r[2])==winner.valor for r in success)\n return results\nfor attempt in range(5):\n results=race([\'100.10\',\'100.10\'])\n assert [r[0] for r in results]==[\'ok\',\'ok\'] and results[0][1]==results[1][1]\n results=race([\'100.10\',\'100.20\'])\n assert sorted(r[0] for r in results)==[\'ok\',\'rejected\']\nprint(\'CORRIDA_FORCADA_IDENTICA_5X=PASS; UMA_LINHA_MESMO_ID\')\nprint(\'CORRIDA_FORCADA_DIVERGENTE_5X=PASS; UM_SUCESSO_UMA_RECUSA\')\nidentity=str(uuid4())\nwith SessionLocal() as db:\n MeiReceitaInformadaWriter(db).registrar(empresa_id=91001,usuario_id=91001,\n  identidade_receita=identity,data_receita=\'2026-01-10\',valor=\'0.20\',categoria=\'servicos\')\n db.rollback()\nwith SessionLocal() as db:\n assert db.scalar(select(models.MeiReceitaInformada).where(models.MeiReceitaInformada.identidade_receita==identity)) is None\nprint(\'ROLLBACK_POSTGRES=PASS\')\nengine.dispose()\n')
    alembic('downgrade','0058_documento_operacao_observada')
    python('''
from sqlalchemy import inspect,text
from app.database import engine
assert not inspect(engine).has_table('mei_receitas_informadas')
with engine.connect() as c:
 assert c.execute(text('SELECT count(*) FROM empresas WHERE id=91001')).scalar_one()==1
 assert c.execute(text('SELECT count(*) FROM usuarios WHERE id=91001')).scalar_one()==1
engine.dispose()
print('DOWNGRADE_0058=PASS; DADOS_ANTERIORES=PRESERVADOS')
''')
    alembic('upgrade','0059_mei_receita_informada')
    python('''
from sqlalchemy import text
from app.database import engine
with engine.connect() as c:
 assert c.execute(text('SELECT count(*) FROM mei_receitas_informadas')).scalar_one()==0
 assert c.execute(text('SELECT version_num FROM alembic_version')).scalar_one()=='0059_mei_receita_informada'
engine.dispose()
print('REAPLICACAO_0059=PASS')
''')
    print('PRODUCAO=NAO_ACESSADA; CONCORRENCIA_FORCADA=PASS',flush=True)
except subprocess.CalledProcessError as error:
    # Do not print command arguments/environment: they include disposable credentials.
    print(error.stdout or '',end='')
    print(error.stderr or '',end='')
    print('STOP=PROVA_POSTGRES_FALHOU',flush=True)
    sys.exit(1)
finally:
    if started:
        removed=subprocess.run(['docker','rm','--force',name],capture_output=True,text=True,timeout=30)
        print('CONTAINER_REMOVIDO='+('PASS' if removed.returncode==0 else 'VERIFICAR'),flush=True)
