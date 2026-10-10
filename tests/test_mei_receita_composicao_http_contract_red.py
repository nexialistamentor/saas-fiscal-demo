"""Contrato RED da consulta HTTP MEI, com SQLite descartavel."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCENARIO = r"""
from datetime import date
from decimal import Decimal
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import Base, engine, SessionLocal
from app import models
from app.routers.dashboard_router import router
from app.security import criar_token

Base.metadata.create_all(engine, tables=[
    models.Plano.__table__,
    models.User.__table__,
    models.Empresa.__table__,
    models.DocumentoFiscal.__table__,
    models.ItemFiscal.__table__,
    models.MeiReceitaInformada.__table__,
])

with SessionLocal() as db:
    db.add_all([
        models.User(id=1, email="owner@example.invalid",
                    hashed_password="unused"),
        models.User(id=2, email="other@example.invalid",
                    hashed_password="unused"),
    ])
    db.flush()

    db.add_all([
        models.Empresa(id=1, user_id=1,
            regime_tributario="mei", status_empresa="ativa"),
        models.Empresa(id=2, user_id=2,
            regime_tributario="mei", status_empresa="ativa"),
        models.Empresa(id=3, user_id=1,
            regime_tributario="real", status_empresa="ativa"),
        models.Empresa(id=4, user_id=1,
            regime_tributario="mei", status_empresa="suspensa"),
    ])
    db.flush()

    db.add(models.MeiReceitaInformada(
        empresa_id=1,
        usuario_id=1,
        identidade_receita=str(uuid4()),
        data_receita=date(2026, 10, 8),
        valor=Decimal("100.30"),
        categoria="servicos",
        origem="informada_sem_nota",
    ))

    db.add(models.DocumentoFiscal(
        id=42,
        empresa_id=1,
        usuario_id=1,
        data_emissao=date(2026, 10, 8),
        tipo="saida",
        valor_total=100.30,
        conteudo_sha256="a" * 64,
    ))
    db.commit()

app = FastAPI()
app.include_router(router)

owner = {
    "Authorization": "Bearer " +
    criar_token({"sub": "owner@example.invalid"})
}
other = {
    "Authorization": "Bearer " +
    criar_token({"sub": "other@example.invalid"})
}

path = "/dashboard/mei/1/composicao-consultiva"
params = {"ano_calendario": 2026}

with TestClient(app) as client:
    response = client.get(path, params=params, headers=owner)

    assert response.status_code == 200, (
        "ROTA_COMPOSICAO_AINDA_NAO_LIGADA",
        response.status_code,
        response.text,
    )

    body = response.json()

    assert body["empresa_id"] == 1
    assert body["ano_calendario"] == 2026
    assert body["total_receitas_informadas"] == "100.30"
    assert body["total_consolidado_comprovado"] is None
    assert body["completude_anual_comprovada"] is False

    documentos = body["documentos_para_conferencia"]
    assert len(documentos) == 1
    assert documentos[0]["documento_id"] == 42
    assert "ESTADO_FISCAL_NAO_COMPROVADO" in documentos[0]["motivos"]

    cache = response.headers.get("cache-control", "")
    assert "private" in cache and "no-store" in cache

    assert client.get(path, params=params).status_code == 401

    assert client.get(
        path, params=params, headers=other
    ).status_code == 403

    for empresa_id in (2, 3, 4, 999):
        resposta = client.get(
            f"/dashboard/mei/{empresa_id}/composicao-consultiva",
            params=params,
            headers=owner,
        )
        assert resposta.status_code == 403, (
            empresa_id, resposta.status_code
        )

    for ano in ("abc", "1899", "10000"):
        assert client.get(
            path,
            params={"ano_calendario": ano},
            headers=owner,
        ).status_code == 422

    assert client.get(path, headers=owner).status_code == 422

    with SessionLocal() as db:
        assert db.query(models.MeiReceitaInformada).count() == 1
        assert db.query(models.DocumentoFiscal).count() == 1

        documento = db.get(models.DocumentoFiscal, 42)
        assert documento.valor_total == 100.30
        assert documento.tipo == "saida"

        documento.tipo = "desconhecido"
        db.commit()

    resposta = client.get(path, params=params, headers=owner)
    assert resposta.status_code == 503, (
        "DOCUMENTO_INVALIDO_DEVE_BLOQUEAR",
        resposta.status_code,
    )

engine.dispose()

print("MEI_COMPOSICAO_HTTP_CONTRACT=PASS")
"""


class MeiComposicaoHttpContract(unittest.TestCase):
    def test_autorizacao_isolamento_e_integridade(self):
        repo = Path(__file__).resolve().parents[1]

        with tempfile.TemporaryDirectory(
            prefix="mei-composicao-http-"
        ) as temporario:
            permitidas = (
                "PATH", "SYSTEMROOT", "WINDIR",
                "TEMP", "TMP", "PYTHONPATH",
            )
            env = {
                chave: os.environ[chave]
                for chave in permitidas
                if chave in os.environ
            }
            env.update(
                ENVIRONMENT="test",
                ALEMBIC_RUNNING="1",
                PYTHON_DOTENV_DISABLED="1",
                DATABASE_URL="sqlite:///" + (
                    Path(temporario) / "test.db"
                ).as_posix(),
                SECRET_KEYS="test=disposable-contract-secret",
                MERCADO_PAGO_ENABLED="false",
                SERPRO_PGMEI_ENABLED="false",
            )

            resultado = subprocess.run(
                [sys.executable, "-c", SCENARIO],
                cwd=repo,
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
            )

            self.assertEqual(
                resultado.returncode,
                0,
                resultado.stdout + resultado.stderr,
            )
            self.assertIn(
                "MEI_COMPOSICAO_HTTP_CONTRACT=PASS",
                resultado.stdout,
            )


if __name__ == "__main__":
    unittest.main()