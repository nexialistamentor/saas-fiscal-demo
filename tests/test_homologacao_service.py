"""
Testes do HomologacaoService — domínio regulatório soberano.
"""

import hashlib
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.services.homologacao_service import (
    HomologacaoError,
    HomologacaoJaExisteError,
    HomologacaoNaoPendenteError,
    ContadorNaoAprovadoError,
    _gerar_assinatura_logica,
    criar_fila_homologacao,
    registar_decisao,
)
from app.models import HomologacaoDocumental, PerfilContador


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def db():
    return MagicMock()


@pytest.fixture
def contador_aprovado():
    c = MagicMock(spec=PerfilContador)
    c.id = 1
    c.status = "aprovado"
    return c


@pytest.fixture
def contador_pendente():
    c = MagicMock(spec=PerfilContador)
    c.id = 2
    c.status = "pendente"
    return c


@pytest.fixture
def homologacao_pendente():
    h = MagicMock(spec=HomologacaoDocumental)
    h.id = 1
    h.status = "pendente"
    h.contador_id = 1
    h.documento_ingerido_id = 10
    return h


@pytest.fixture
def homologacao_aprovada():
    h = MagicMock(spec=HomologacaoDocumental)
    h.id = 2
    h.status = "aprovado"
    h.contador_id = 1
    h.documento_ingerido_id = 10
    return h


# ---------------------------------------------------------------------------
# Assinatura lógica
# ---------------------------------------------------------------------------
def test_assinatura_logica_deterministica():
    dt = datetime(2026, 5, 11, 12, 0, 0)
    a1 = _gerar_assinatura_logica("parecer", 1, 10, dt)
    a2 = _gerar_assinatura_logica("parecer", 1, 10, dt)
    assert a1 == a2


def test_assinatura_logica_sha256():
    dt = datetime(2026, 5, 11, 12, 0, 0)
    payload = f"parecer{1}{10}{dt.isoformat()}"
    esperado = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    assert _gerar_assinatura_logica("parecer", 1, 10, dt) == esperado


def test_assinatura_muda_com_parecer():
    dt = datetime(2026, 5, 11, 12, 0, 0)
    a1 = _gerar_assinatura_logica("parecer A", 1, 10, dt)
    a2 = _gerar_assinatura_logica("parecer B", 1, 10, dt)
    assert a1 != a2


def test_assinatura_muda_com_contador():
    dt = datetime(2026, 5, 11, 12, 0, 0)
    a1 = _gerar_assinatura_logica("parecer", 1, 10, dt)
    a2 = _gerar_assinatura_logica("parecer", 2, 10, dt)
    assert a1 != a2


def test_assinatura_muda_com_documento():
    dt = datetime(2026, 5, 11, 12, 0, 0)
    a1 = _gerar_assinatura_logica("parecer", 1, 10, dt)
    a2 = _gerar_assinatura_logica("parecer", 1, 99, dt)
    assert a1 != a2


# ---------------------------------------------------------------------------
# criar_fila_homologacao
# ---------------------------------------------------------------------------
def test_contador_nao_aprovado_levanta_erro(db, contador_pendente):
    db.query.return_value.filter.return_value.first.return_value = contador_pendente
    with pytest.raises(ContadorNaoAprovadoError):
        criar_fila_homologacao(db, documento_ingerido_id=1, contador_id=2)


def test_contador_inexistente_levanta_erro(db):
    db.query.return_value.filter.return_value.first.return_value = None
    with pytest.raises(ContadorNaoAprovadoError):
        criar_fila_homologacao(db, documento_ingerido_id=1, contador_id=99)


def test_homologacao_ja_existe_levanta_erro(db, contador_aprovado, homologacao_pendente):
    db.query.return_value.filter.return_value.first.side_effect = [
        contador_aprovado,
        homologacao_pendente,
    ]
    with pytest.raises(HomologacaoJaExisteError):
        criar_fila_homologacao(db, documento_ingerido_id=10, contador_id=1)


def test_criar_fila_sucesso(db, contador_aprovado):
    db.query.return_value.filter.return_value.first.side_effect = [
        contador_aprovado,
        None,
    ]
    resultado = criar_fila_homologacao(db, documento_ingerido_id=5, contador_id=1)
    db.add.assert_called_once()
    db.flush.assert_called_once()
    assert resultado is not None


# ---------------------------------------------------------------------------
# registar_decisao
# ---------------------------------------------------------------------------
def test_status_invalido_levanta_erro(db, homologacao_pendente):
    db.query.return_value.filter.return_value.first.return_value = homologacao_pendente
    with pytest.raises(HomologacaoError):
        registar_decisao(db, 1, "invalido", "parecer", 1)


def test_homologacao_nao_pendente_levanta_erro(db, homologacao_aprovada):
    db.query.return_value.filter.return_value.first.return_value = homologacao_aprovada
    with pytest.raises(HomologacaoNaoPendenteError):
        registar_decisao(db, 2, "aprovado", "parecer", 1)


def test_homologacao_nao_encontrada_levanta_erro(db):
    db.query.return_value.filter.return_value.first.return_value = None
    with pytest.raises(HomologacaoError):
        registar_decisao(db, 99, "aprovado", "parecer", 1)


def test_registar_decisao_aprovado(db, homologacao_pendente):
    fixed_now = datetime(2026, 5, 11, 15, 30, 0)
    db.query.return_value.filter.return_value.first.return_value = homologacao_pendente

    with patch(
        "app.services.homologacao_service.datetime"
    ) as mock_dt:
        mock_dt.utcnow.return_value = fixed_now

        resultado = registar_decisao(
            db, 1, "aprovado", "Documento válido.", 1
        )

    assert resultado is homologacao_pendente
    assert homologacao_pendente.status == "aprovado"
    assert homologacao_pendente.parecer_texto == "Documento válido."
    esperado = _gerar_assinatura_logica(
        "Documento válido.", 1, homologacao_pendente.documento_ingerido_id, fixed_now
    )
    assert homologacao_pendente.assinatura_logica == esperado
    assert homologacao_pendente.decidido_em == fixed_now


def test_registar_decisao_rejeitado(db, homologacao_pendente):
    db.query.return_value.filter.return_value.first.return_value = homologacao_pendente
    registar_decisao(db, 1, "rejeitado", "Documento ilegível.", 1)
    assert homologacao_pendente.status == "rejeitado"
