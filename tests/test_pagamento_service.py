"""
Testes do domínio financeiro soberano — PagamentoService.

Confrontação de bugs, transições inválidas e edge cases FinTech.
"""

from decimal import Decimal

from unittest.mock import MagicMock

import pytest

from app.services.pagamento_service import (
    TRANSICOES_VALIDAS,
    ESTADOS_VALIDOS,
    PagamentoDuplicadoError,
    TransicaoEstadoInvalidaError,
    _gerar_idempotency_key,
    _sanitizar_external_reference,
    _mapear_status_gateway,
    criar_intencao_pagamento,
    transitar_estado,
    rejeitar_pagamento,
)

from app.models import Pagamento, PagamentoTentativa


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def db():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    return db


@pytest.fixture
def pagamento_pending():
    p = MagicMock(spec=Pagamento)
    p.id = 1
    p.user_id = 42
    p.status = "gateway_requested"
    p.gateway_provider = "mercadopago"
    p.gateway_payment_type = "pix"
    return p


@pytest.fixture
def pagamento_approved():
    p = MagicMock(spec=Pagamento)
    p.id = 2
    p.user_id = 42
    p.status = "approved"
    p.gateway_provider = "mercadopago"
    p.gateway_payment_type = "pix"
    return p


# ---------------------------------------------------------------------------
# Máquina de estados — estrutura
# ---------------------------------------------------------------------------
def test_estados_terminais_nao_tem_transicoes():
    """Estados terminais não podem transitar para nada."""
    terminais = {"expired", "cancelled", "rejected", "refunded", "chargeback"}
    for estado in terminais:
        assert TRANSICOES_VALIDAS[estado] == set(), f"{estado} deveria ser terminal"


def test_todos_estados_tem_entrada_em_transicoes():
    """Todos os estados válidos têm entrada no mapa de transições."""
    for estado in ESTADOS_VALIDOS:
        assert estado in TRANSICOES_VALIDAS, f"{estado} não tem entrada em TRANSICOES_VALIDAS"


def test_destinos_de_transicao_sao_estados_validos():
    """Todos os destinos de transição são estados válidos."""
    for origem, destinos in TRANSICOES_VALIDAS.items():
        for destino in destinos:
            assert destino in ESTADOS_VALIDOS, f"Destino inválido: {origem} → {destino}"


# ---------------------------------------------------------------------------
# Transições — aprovadas e proibidas
# ---------------------------------------------------------------------------
def test_transicao_valida(db, pagamento_pending):
    pagamento_pending.status = "gateway_requested"
    resultado = transitar_estado(db, pagamento_pending, "pending")
    assert pagamento_pending.status == "pending"


def test_transicao_invalida_approved_para_created(db, pagamento_approved):
    """approved → created deve ser impossível."""
    with pytest.raises(TransicaoEstadoInvalidaError):
        transitar_estado(db, pagamento_approved, "created")


def test_transicao_invalida_rejected_para_approved(db):
    p = MagicMock(spec=Pagamento)
    p.status = "rejected"
    with pytest.raises(TransicaoEstadoInvalidaError):
        transitar_estado(db, p, "approved")


def test_transicao_estado_inexistente(db, pagamento_pending):
    with pytest.raises(TransicaoEstadoInvalidaError):
        transitar_estado(db, pagamento_pending, "estado_fantasma")


# ---------------------------------------------------------------------------
# Idempotência
# ---------------------------------------------------------------------------
def test_idempotency_key_deterministica():
    """Mesmos inputs → mesma chave."""
    k1 = _gerar_idempotency_key(1, "perfil-abc", "cpf", "ctx-123")
    k2 = _gerar_idempotency_key(1, "perfil-abc", "cpf", "ctx-123")
    assert k1 == k2


def test_idempotency_key_diferente_por_contexto():
    """Contextos diferentes → chaves diferentes."""
    k1 = _gerar_idempotency_key(1, "perfil-abc", "cpf", "ctx-123")
    k2 = _gerar_idempotency_key(1, "perfil-abc", "cpf", "ctx-456")
    assert k1 != k2


def test_criar_intencao_idempotente_nao_duplica(db):
    """Se pagamento pending já existe, devolve o existente sem criar novo."""
    existente = MagicMock(spec=Pagamento)
    existente.status = "pending"
    db.query.return_value.filter.return_value.first.return_value = existente

    resultado = criar_intencao_pagamento(
        db=db, user_id=1, perfil_id="abc", tipo_perfil="cpf",
        valor=Decimal("99.90"), contexto_idempotencia="ctx-001"
    )
    assert resultado is existente
    db.add.assert_not_called()


def test_criar_intencao_aprovada_levanta_erro(db):
    """Se pagamento já aprovado, deve levantar PagamentoDuplicadoError."""
    existente = MagicMock(spec=Pagamento)
    existente.status = "approved"
    db.query.return_value.filter.return_value.first.return_value = existente

    with pytest.raises(PagamentoDuplicadoError):
        criar_intencao_pagamento(
            db=db, user_id=1, perfil_id="abc", tipo_perfil="cpf",
            valor=Decimal("99.90"), contexto_idempotencia="ctx-001"
        )


# ---------------------------------------------------------------------------
# Mapeamento de status gateway
# ---------------------------------------------------------------------------
def test_status_gateway_conhecido():
    assert _mapear_status_gateway("approved") == "approved"
    assert _mapear_status_gateway("in_process") == "pending"
    assert _mapear_status_gateway("charged_back") == "chargeback"


def test_status_gateway_desconhecido():
    """Status desconhecido do gateway → reconciliation_failed."""
    assert _mapear_status_gateway("status_novo_do_mp") == "reconciliation_failed"


# ---------------------------------------------------------------------------
# Sanitização external reference
# ---------------------------------------------------------------------------
def test_sanitizar_remove_caracteres_invalidos():
    ref = _sanitizar_external_reference("cpf", "123.456.789-00", "ctx uuid")
    assert "." not in ref
    assert " " not in ref


def test_sanitizar_trunca_256_chars():
    longo = "x" * 300
    ref = _sanitizar_external_reference("cpf", longo, "ctx")
    assert len(ref) <= 256


# ---------------------------------------------------------------------------
# Valor financeiro — Decimal obrigatório
# ---------------------------------------------------------------------------
def test_valor_decimal_nao_float(db):
    """Garantir que o serviço aceita Decimal e não float."""
    resultado = criar_intencao_pagamento(
        db=db, user_id=1, perfil_id="abc", tipo_perfil="mei",
        valor=Decimal("149.90"), contexto_idempotencia="ctx-002"
    )
    db.add.assert_called_once()
    pagamento_criado = db.add.call_args[0][0]
    assert isinstance(pagamento_criado.valor, Decimal)


# ---------------------------------------------------------------------------
# Rejeição com ledger
# ---------------------------------------------------------------------------
def test_rejeitar_pagamento_regista_tentativa(db, pagamento_pending):
    pagamento_pending.status = "gateway_requested"
    rejeitar_pagamento(
        db=db,
        pagamento=pagamento_pending,
        error_code="cc_rejected_insufficient_amount",
        error_message="Saldo insuficiente",
        error_origin="issuer",
        http_status=422,
    )
    db.add.assert_called()
    tentativa = db.add.call_args_list[0][0][0]
    assert isinstance(tentativa, PagamentoTentativa)
    assert tentativa.error_code == "cc_rejected_insufficient_amount"
    assert tentativa.error_origin == "issuer"
