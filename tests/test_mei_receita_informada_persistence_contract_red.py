"""New informed-revenue persistence contract; existing R1-R3 stay untouched.

Disposable SQLite only. Does not prove PostgreSQL migrations or UI wiring.
Run directly with the project Python interpreter.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCENARIO = r'''
from decimal import Decimal
from datetime import date
from sqlalchemy import select
from app.database import Base, engine, SessionLocal
from app import models
from app.services.mei_receita_informada_writer import (
    MeiReceitaInformadaWriter, MeiReceitaInformadaWriterError,
)

Revenue = models.MeiReceitaInformada
Base.metadata.create_all(engine, tables=[models.Plano.__table__,
    models.User.__table__, models.Empresa.__table__, Revenue.__table__])
with SessionLocal() as db:
    db.add_all([models.User(id=1, email="owner@example.invalid", hashed_password="unused"),
                models.User(id=2, email="other@example.invalid", hashed_password="unused")])
    db.flush()
    db.add_all([
        models.Empresa(id=1, user_id=1, regime_tributario="mei", status_empresa="ativa"),
        models.Empresa(id=2, user_id=2, regime_tributario="mei", status_empresa="ativa"),
        models.Empresa(id=3, user_id=1, regime_tributario="mei", status_empresa="em_abertura"),
        models.Empresa(id=4, user_id=1, regime_tributario="real", status_empresa="ativa"),
    ])
    db.commit()

def payload(**changes):
    return dict(empresa_id=1, usuario_id=1,
        identidade_receita="11111111-1111-4111-8111-111111111111",
        data_receita="2026-01-10", valor="100.10", categoria="servicos", **changes)

def write(db, data):
    return MeiReceitaInformadaWriter(db).registrar(**data)

def reject(data):
    with SessionLocal() as db:
        before = len(db.scalars(select(Revenue)).all())
        try:
            write(db, data)
        except MeiReceitaInformadaWriterError:
            pass
        else:
            raise AssertionError("INVALID_REVENUE_ACCEPTED")
        db.rollback()
    with SessionLocal() as db:
        assert len(db.scalars(select(Revenue)).all()) == before

with SessionLocal() as db:
    first = write(db, payload())
    first_id = first.id
    assert first.valor == Decimal("100.10")
    assert first.empresa_id == 1 and first.usuario_id == 1
    assert first.data_receita == date(2026, 1, 10)
    assert first.origem == "informada_sem_nota"
    assert first.created_at is not None
    db.commit()

with SessionLocal() as db:
    repeated = write(db, payload())
    assert repeated.id == first_id
    db.commit()
    assert len(db.scalars(select(Revenue)).all()) == 1

for field, value in [
    ("valor", "100.20"), ("data_receita", "2025-12-31"),
    ("categoria", "comercio_industria"),
]:
    data = payload(); data[field] = value
    reject(data)

for changes in [
    {"empresa_id": 2}, {"usuario_id": 2}, {"empresa_id": 999},
    {"empresa_id": 3}, {"empresa_id": 4},
    {"empresa_id": True}, {"usuario_id": True},
    {"valor": 100.10}, {"valor": "100,10"}, {"valor": "0.001"},
    {"valor": "NaN"}, {"valor": "-1.00"},
    {"data_receita": "2026-02-30"}, {"categoria": "desconhecida"},
    {"identidade_receita": ""}, {"identidade_receita": "arbitrary-browser-id"},
]:
    data = payload(); data.update(changes)
    reject(data)

with SessionLocal() as db:
    data = payload()
    data.update(identidade_receita="22222222-2222-4222-8222-222222222222", valor="0.20")
    write(db, data)
    db.commit()

from app.services.mei_receita_anual_apuracao import apurar_receitas_anuais
with SessionLocal() as db:
    rows = db.scalars(select(Revenue).where(Revenue.empresa_id == 1)).all()
    records = [dict(identidade_receita=r.identidade_receita, empresa_id=r.empresa_id,
        data_receita=r.data_receita.isoformat(), valor=format(r.valor, ".2f"),
        categoria=r.categoria, origem=r.origem, estado="vigente") for r in rows]
    result = apurar_receitas_anuais(empresa_id=1, ano_calendario=2026, receitas=records)
    assert result["total_receitas_incluidas"] == "100.30"
    assert result["totais_por_origem"]["informada_sem_nota"] == "100.30"
    assert result["completude_anual_comprovada"] is False
    assert result["meses"][1]["total_receitas_incluidas"] is None
    assert apurar_receitas_anuais(empresa_id=1, ano_calendario=2025,
        receitas=records)["receitas_incluidas"] == []
    assert apurar_receitas_anuais(empresa_id=2, ano_calendario=2026,
        receitas=records)["receitas_incluidas"] == []

with SessionLocal() as db:
    data = payload(); data["identidade_receita"] = "33333333-3333-4333-8333-333333333333"
    write(db, data)
    db.rollback()
with SessionLocal() as db:
    assert len(db.scalars(select(Revenue)).all()) == 2
engine.dispose()
print("INFORMED_REVENUE_PERSISTENCE=PASS")
'''

class InformedRevenuePersistenceContract(unittest.TestCase):
    def test_real_persistence_replay_conflict_owner_and_apuration(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="mei-receita-contract-") as folder:
            allowed = ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP")
            env = {key: os.environ[key] for key in allowed if key in os.environ}
            env.update(ENVIRONMENT="test", ALEMBIC_RUNNING="1", PYTHON_DOTENV_DISABLED="1",
                DATABASE_URL="sqlite:///" + (Path(folder) / "test.db").as_posix(),
                SECRET_KEYS="test=disposable-contract-secret-not-for-production",
                MERCADO_PAGO_ENABLED="false", SERPRO_PGMEI_ENABLED="false")
            result = subprocess.run([sys.executable, "-c", SCENARIO], cwd=repo,
                env=env, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("INFORMED_REVENUE_PERSISTENCE=PASS", result.stdout)

if __name__ == "__main__":
    unittest.main()
