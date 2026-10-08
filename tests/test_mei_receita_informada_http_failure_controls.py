"""HTTP informed-revenue contract with real authentication and disposable SQLite.

Run directly with Python. Does not import the production application lifecycle
or prove PostgreSQL migrations, providers or deployment.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCENARIO = r'''

from datetime import date
from decimal import Decimal
from uuid import uuid4
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.database import Base, engine, SessionLocal
from app import models
from app.routers.dashboard_router import router
from app.security import criar_token
from app.services.mei_receita_anual_apuracao import apurar_receitas_anuais

Base.metadata.create_all(engine, tables=[models.Plano.__table__,models.User.__table__,
 models.Empresa.__table__,models.DocumentoFiscal.__table__,models.MeiReceitaInformada.__table__])
with SessionLocal() as db:
 db.add_all([models.User(id=1,email='owner@example.invalid',hashed_password='unused'),
             models.User(id=2,email='other@example.invalid',hashed_password='unused')])
 db.flush()
 db.add_all([models.Empresa(id=1,user_id=1,regime_tributario='mei',status_empresa='ativa'),
  models.Empresa(id=2,user_id=2,regime_tributario='mei',status_empresa='ativa'),
  models.Empresa(id=3,user_id=1,regime_tributario='mei',status_empresa='em_abertura'),
  models.Empresa(id=4,user_id=1,regime_tributario='real',status_empresa='ativa'),
  models.Empresa(id=5,user_id=1,regime_tributario='mei',status_empresa='suspensa')])
 db.flush()
 db.add(models.DocumentoFiscal(id=1,empresa_id=1,usuario_id=1,
  data_emissao=date(2026,1,10),tipo='saida',valor_total=999.0))
 db.commit()
app=FastAPI()
app.include_router(router)
headers={'Authorization':'Bearer '+criar_token({'sub':'owner@example.invalid'})}
other={'Authorization':'Bearer '+criar_token({'sub':'other@example.invalid'})}
path='/dashboard/mei/1/receitas-informadas'
def payload(**changes):
 return dict(identidade_receita=str(uuid4()),data_receita='2026-01-10',
             valor='100.10',categoria='servicos',**changes)
def count():
 with SessionLocal() as db:
  return db.query(models.MeiReceitaInformada).count()
with TestClient(app) as client:
 first=payload()
 assert client.get(path,params={'ano_calendario':2026}).status_code==401, 'RECEITA_HTTP_ROUTE_NOT_WIRED'
 assert client.post(path,json=first).status_code==401
 assert client.get(path,params={'ano_calendario':2026},headers=other).status_code==403
 assert client.post(path,json=first,headers=other).status_code==403
 for company in (2,3,4,5,999):
  target=f'/dashboard/mei/{company}/receitas-informadas'
  assert client.get(target,params={'ano_calendario':2026},headers=headers).status_code==403
  assert client.post(target,json=first,headers=headers).status_code==403
 assert count()==0
 for year in ('abc',1899,10000):
  assert client.get(path,params={'ano_calendario':year},headers=headers).status_code==422
 assert client.get(path,headers=headers).status_code==422
 empty=client.get(path,params={'ano_calendario':2026},headers=headers)
 assert empty.status_code==200, empty.text
 assert 'no-store' in empty.headers.get('cache-control','')
 assert empty.json()==apurar_receitas_anuais(empresa_id=1,ano_calendario=2026,receitas=[])
 invalid=[{'valor':100.10},{'valor':'NaN'},{'valor':'-1.00'},{'valor':'100,10'},
 {'valor':'1.001'},{'data_receita':'2026-02-30'},{'data_receita':'1899-01-01'},
 {'categoria':'desconhecida'},{'identidade_receita':'arbitraria'},
 {'identidade_receita':str(uuid4()).upper()},{'empresa_id':2},{'usuario_id':2},
 {'origem':'documento'},{'estado':'vigente'},{'observacao':'texto livre'}]
 for changes in invalid:
  response=client.post(path,json={**first,**changes},headers=headers)
  assert response.status_code==422, (changes,response.status_code,response.text)
 assert client.post(path,json={},headers=headers).status_code==422
 assert count()==0
 response=client.post(path,json=first,headers=headers)
 assert response.status_code==200, response.text
 assert 'no-store' in response.headers.get('cache-control','')
 body=response.json()
 expected={**first,'empresa_id':1,'origem':'informada_sem_nota'}
 assert set(body)==set(expected)|{'id'} and type(body['id']) is int
 assert {k:v for k,v in body.items() if k!='id'}==expected
 with SessionLocal() as db:
  row=db.get(models.MeiReceitaInformada,body['id'])
  assert row.usuario_id==1 and row.valor==Decimal('100.10')
 replay=client.post(path,json=first,headers=headers)
 assert replay.status_code==200 and replay.json()==body and count()==1
 for changes in ({'valor':'100.20'},{'data_receita':'2025-01-10'}, {'categoria':'comercio_industria'}):
  response=client.post(path,json={**first,**changes},headers=headers)
  assert response.status_code==409, response.text
  assert count()==1
 second={**payload(),'valor':'0.20','categoria':'comercio_industria'}
 previous={**payload(),'data_receita':'2025-12-31','valor':'50.00'}
 following={**payload(),'data_receita':'2027-01-01','valor':'60.00'}
 for item in (second,previous,following):
  assert client.post(path,json=item,headers=headers).status_code==200
 target='/dashboard/mei/2/receitas-informadas'
 assert client.post(target,json={**payload(),'valor':'900.00'},headers=other).status_code==200
 for year,items in ((2026,[first,second]),(2025,[previous]),(2027,[following]),(2024,[])):
  response=client.get(path,params={'ano_calendario':year},headers=headers)
  assert response.status_code==200 and 'no-store' in response.headers.get('cache-control','')
  actual=response.json()
  evidence=[{**item,'empresa_id':1,'origem':'informada_sem_nota','estado':'vigente'} for item in items]
  expected=apurar_receitas_anuais(empresa_id=1,ano_calendario=year,receitas=evidence)
  actual['receitas_incluidas']=sorted(actual['receitas_incluidas'],key=lambda x:x['identidade_receita'])
  expected['receitas_incluidas']=sorted(expected['receitas_incluidas'],key=lambda x:x['identidade_receita'])
  assert actual==expected, (year,actual,expected)
 assert count()==5
 with SessionLocal() as db:
  document=db.get(models.DocumentoFiscal,1)
  assert document.valor_total==999.0 and document.tipo=='saida'

from unittest.mock import patch
from sqlalchemy.orm import Session, Query
from sqlalchemy.exc import OperationalError
from app.services.mei_receita_informada_writer import MeiReceitaInformadaWriter, MeiReceitaInformadaWriterError
import app.routers.dashboard_router as routes
sensitive='DO_NOT_EXPOSE_DATABASE_OR_PROVIDER_SECRET'
def failure():
 return OperationalError('hidden statement',{},Exception(sensitive))
def unavailable(response):
 assert response.status_code==503, response.text
 assert response.json()=={'detail':'RECEITAS_INFORMADAS_INDISPONIVEIS'}
 assert sensitive not in response.text
with TestClient(app) as client:
 before=count()
 fresh=payload()
 with patch.object(Session,'commit',side_effect=failure()):
  unavailable(client.post(path,json=fresh,headers=headers))
 assert count()==before, 'FAILED_COMMIT_LEFT_REVENUE'
 for error in (failure(),MeiReceitaInformadaWriterError('RECEITA_INFORMADA_RECUSADA')):
  with patch.object(MeiReceitaInformadaWriter,'registrar',side_effect=error):
   unavailable(client.post(path,json=payload(),headers=headers))
   unavailable(client.post(path,json=first,headers=headers))
 assert count()==before
 with patch.object(Query,'all',side_effect=failure()):
  unavailable(client.get(path,params={'ano_calendario':2026},headers=headers))
 with patch.object(routes,'apurar_receitas_anuais',side_effect=ValueError(sensitive)):
  unavailable(client.get(path,params={'ano_calendario':2026},headers=headers))
 assert count()==before
 # The database may commit before the caller loses its acknowledgement.
 uncertain=payload()
 original_commit=Session.commit
 def committed_then_lost(db):
  original_commit(db)
  raise failure()
 with patch.object(Session,'commit',new=committed_then_lost):
  unavailable(client.post(path,json=uncertain,headers=headers))
 assert count()==before+1
 retry=client.post(path,json=uncertain,headers=headers)
 assert retry.status_code==200, retry.text
 saved_id=retry.json()['id']
 assert count()==before+1
 again=client.post(path,json=uncertain,headers=headers)
 assert again.status_code==200 and again.json()['id']==saved_id
 assert count()==before+1
 response=client.get(path,params={'ano_calendario':2026},headers=headers)
 assert response.status_code==200
 assert response.json()['total_receitas_incluidas']=='200.40'
print('HTTP_FAILURES_ROLLBACK_AND_UNCERTAIN_COMMIT=PASS')

engine.dispose()
print('MEI_RECEITA_INFORMADA_HTTP_CONTRACT=PASS')
'''


class InformedRevenueHttpFailureControls(unittest.TestCase):
    def test_failure_rollback_and_uncertain_commit_recovery(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="mei-informed-http-") as temporary:
            allowed = ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PYTHONPATH")
            env = {key: os.environ[key] for key in allowed if key in os.environ}
            env.update(ENVIRONMENT="test", ALEMBIC_RUNNING="1", PYTHON_DOTENV_DISABLED="1",
                DATABASE_URL="sqlite:///" + (Path(temporary) / "test.db").as_posix(),
                SECRET_KEYS="test=disposable-contract-secret-not-for-production",
                MERCADO_PAGO_ENABLED="false", SERPRO_PGMEI_ENABLED="false")
            result = subprocess.run([sys.executable, "-c", SCENARIO], cwd=repo,
                env=env, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("MEI_RECEITA_INFORMADA_HTTP_CONTRACT=PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
