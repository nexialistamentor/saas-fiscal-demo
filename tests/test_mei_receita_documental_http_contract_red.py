"""HTTP reader contract with real tenant dependencies and disposable SQLite.

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
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.database import Base, engine, SessionLocal
from app import models
from app.routers.dashboard_router import router
from app.security import criar_token

Base.metadata.create_all(engine, tables=[models.Plano.__table__,
    models.User.__table__, models.Empresa.__table__, models.DocumentoFiscal.__table__])
with SessionLocal() as db:
    db.add_all([models.User(id=1, email="owner@example.invalid", hashed_password="unused"),
                models.User(id=2, email="other@example.invalid", hashed_password="unused")])
    db.flush()
    db.add_all([models.Empresa(id=1, user_id=1, regime_tributario="mei", status_empresa="ativa"),
                models.Empresa(id=2, user_id=2, regime_tributario="mei", status_empresa="ativa")])
    db.flush()
    for ident, company, emitted, kind in [
        (1, 1, date(2026, 1, 1), "saida"),
        (2, 1, date(2026, 12, 31), "entrada"),
        (3, 1, date(2025, 12, 31), "saida"),
        (4, 1, date(2027, 1, 1), "saida"),
        (5, 1, None, "saida"),
        (6, 2, date(2026, 6, 1), "saida")]:
        db.add(models.DocumentoFiscal(id=ident, empresa_id=company,
            usuario_id=company, data_emissao=emitted, tipo=kind, valor_total=100.0))
    db.commit()

app = FastAPI()
app.include_router(router)
headers = {"Authorization": "Bearer " + criar_token({"sub": "owner@example.invalid"})}
path = "/dashboard/mei/1/conferencia-documental"
with TestClient(app) as client:
    response = client.get(path, params={"ano_calendario": 2026})
    assert response.status_code == 401, (
        "MEI_DOCUMENTAL_ROUTE_NOT_WIRED", response.status_code, response.text)
    assert client.get("/dashboard/mei/2/conferencia-documental",
        params={"ano_calendario": 2026}, headers=headers).status_code == 403
    for year in ("abc", "1899", "10000"):
        assert client.get(path, params={"ano_calendario": year}, headers=headers).status_code == 422
    assert client.get(path, headers=headers).status_code == 422
    response = client.get(path, params={"ano_calendario": 2026}, headers=headers)
    assert response.status_code == 200, response.text
    assert "no-store" in response.headers.get("cache-control", "")
    body = response.json()
    assert body["empresa_id"] == 1 and body["ano_calendario"] == 2026
    assert [x["documento_id"] for x in body["documentos_para_revisao"]] == [1, 2]
    assert [x["documento_id"] for x in body["documentos_sem_periodo"]] == [5]
    assert body["receitas_confirmadas"] == []
    assert body["total_receita_confirmada"] is None
    assert body["completude_anual_comprovada"] is False
    assert body["documentos_para_revisao"][0]["metadados"]["data_emissao"] == "2026-01-01"
    for item in body["documentos_para_revisao"] + body["documentos_sem_periodo"]:
        assert item["categoria_receita"] is None
        assert "EMITENTE_NAO_COMPROVADO" in item["motivos"]
    with SessionLocal() as db:
        assert db.query(models.DocumentoFiscal).count() == 6
        db.query(models.DocumentoFiscal).filter_by(id=1).one().tipo = "desconhecido"
        db.commit()
    assert client.get(path, params={"ano_calendario": 2026}, headers=headers).status_code == 503
engine.dispose()
print("MEI_DOCUMENTAL_HTTP_CONTRACT=PASS")
'''


class DocumentaryHttpContract(unittest.TestCase):
    def test_authenticated_reader_preserves_tenant_year_and_uncertainty(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="mei-documental-contract-") as temporary:
            allowed = ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PYTHONPATH")
            env = {key: os.environ[key] for key in allowed if key in os.environ}
            env.update(ENVIRONMENT="test", ALEMBIC_RUNNING="1", PYTHON_DOTENV_DISABLED="1",
                DATABASE_URL="sqlite:///" + (Path(temporary) / "test.db").as_posix(),
                SECRET_KEYS="test=disposable-contract-secret-not-for-production",
                MERCADO_PAGO_ENABLED="false", SERPRO_PGMEI_ENABLED="false")
            result = subprocess.run([sys.executable, "-c", SCENARIO], cwd=repo,
                env=env, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("MEI_DOCUMENTAL_HTTP_CONTRACT=PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
