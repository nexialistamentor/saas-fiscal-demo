"""MEI-R005: uma falha do motor não pode ser publicada como DAS zero."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import User
from app.security import get_usuario_atual
from app.services.engine_registry import ENGINES


@pytest.fixture
def client_auth():
    mock_user = MagicMock(spec=User)
    mock_user.id = 1
    mock_user.email = "mei-r005@test.local"
    app.dependency_overrides[get_usuario_atual] = lambda: mock_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_falha_do_mei_tax_engine_nao_pode_ser_publicada_como_imposto_zero(
    client_auth, monkeypatch
):
    def mei_tax_engine_com_falha(_self, _dados):
        raise RuntimeError("falha realista no cálculo do MEITaxEngine")

    monkeypatch.setattr(ENGINES["mei_tax"], "execute", mei_tax_engine_com_falha)

    response = client_auth.post(
        "/imposto/calcular",
        json={
            "tipo_usuario": "MEI",
            "faturamento_mensal": 5432.10,
            "ano_referencia": 2026,
        },
    )

    assert response.status_code >= 400, (
        "MEI-R005: a falha do motor deve ser explícita/fail-closed, mas a rota "
        f"respondeu {response.status_code} com {response.json()}"
    )
