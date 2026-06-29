"""
Testes B13-OPS-06 — SourceAuthorityGuard.
12 invariantes L3.
"""
import pytest
from app.schemas.source_authority_schema import SourceAuthorityRequest
from app.services.source_authority_guard import verificar


def _req(fonte_id: str, uso: str) -> SourceAuthorityRequest:
    return SourceAuthorityRequest(fonte_id=fonte_id, uso_pretendido=uso)


def test_fonte_inexistente_bloqueia():
    r = verificar(_req("FONTE-INEXISTENTE-999", "fundamentar_decisao"))
    assert not r.permitido
    assert "não existe" in r.motivo


def test_proibida_para_decisao_bloqueia_sempre():
    for uso in ["fundamentar_decisao", "validar_fato_operacional", "apoiar_explicacao_ux", "contexto_llm"]:
        r = verificar(_req("VEDACAO-LLM-001", uso))
        assert not r.permitido, f"VEDACAO-LLM-001 devia bloquear uso={uso}"
        assert "vedação institucional" in r.motivo


def test_vedacao_llm_bloqueia_como_fonte_fiscal():
    r = verificar(_req("VEDACAO-LLM-001", "fundamentar_decisao"))
    assert not r.permitido
    assert r.tipo == "proibida_para_decisao"


def test_operacional_nao_fundamenta_decisao():
    r = verificar(_req("RFB-001", "fundamentar_decisao"))
    assert not r.permitido
    assert "normativa_oficial" in r.motivo


def test_operacional_pode_validar_fato():
    r = verificar(_req("RFB-001", "validar_fato_operacional"))
    assert r.permitido
    assert r.pode_validar_fato_operacional is True


def test_informativa_nao_fundamenta_decisao():
    r = verificar(_req("GOVBR-MEI-001", "fundamentar_decisao"))
    assert not r.permitido


def test_informativa_nao_valida_fato():
    r = verificar(_req("GOVBR-MEI-001", "validar_fato_operacional"))
    assert not r.permitido


def test_informativa_pode_apoiar_explicacao_ux():
    r = verificar(_req("GOVBR-MEI-001", "apoiar_explicacao_ux"))
    assert r.permitido


def test_normativa_sem_hash_nao_fundamenta_decisao():
    """Hoje todas as normativas têm pode_fundamentar_decisao=false — nenhuma tem hash."""
    r = verificar(_req("LC123-001", "fundamentar_decisao"))
    assert not r.permitido
    assert "hash_referencia" in r.motivo or "internalização" in r.motivo


def test_normativa_pode_ser_contexto_llm():
    """LC123-001 tem pode_ser_usada_por_llm=true."""
    r = verificar(_req("LC123-001", "contexto_llm"))
    assert r.permitido
    assert "supervisionado" in r.acao.lower()


def test_fonte_sem_llm_bloqueia_contexto_llm():
    """RFB-001 tem pode_ser_usada_por_llm=false."""
    r = verificar(_req("RFB-001", "contexto_llm"))
    assert not r.permitido
    assert r.pode_ser_usada_por_llm is False


def test_auxiliar_nao_normativa_nunca_fundamenta_decisao():
    r = verificar(_req("IBPT-001", "fundamentar_decisao"))
    assert not r.permitido
    assert r.tipo == "auxiliar_nao_normativa"
    assert "normativa_oficial" in r.motivo
