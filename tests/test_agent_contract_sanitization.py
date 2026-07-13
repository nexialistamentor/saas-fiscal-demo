"""
tests/test_agent_contract_sanitization.py — ADR-008 B14.0 Commit 2
"""
from __future__ import annotations

import uuid as _uuid_mod
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import BaseModel

from app.agents.contracts.sanitization import (
    assert_context_sanitized,
    assert_result_sanitized,
    verificar_contexto,
)


# ---------------------------------------------------------------------------
# Contextos limpos
# ---------------------------------------------------------------------------

class TestContextoLimpo:
    def test_vazio(self):
        assert verificar_contexto({}).ok is True

    def test_campos_operacionais(self):
        r = verificar_contexto({"ano_referencia": 2026, "tenant_id": 42, "mission_type": "M"})
        assert r.ok is True

    def test_texto_neutro(self):
        assert verificar_contexto({"msg": "Erro ao processar documento fiscal"}).ok is True

    def test_datetime_com_tz(self):
        assert verificar_contexto({"ts": datetime(2026, 7, 13, tzinfo=timezone.utc)}).ok is True

    def test_uuid_v4(self):
        assert verificar_contexto({"id": uuid4()}).ok is True

    def test_decimal_finito(self):
        assert verificar_contexto({"v": Decimal("123.45")}).ok is True

    def test_pydantic_limpo(self):
        class Mini(BaseModel):
            x: int
        assert verificar_contexto({"m": Mini(x=1)}).ok is True


# ---------------------------------------------------------------------------
# Tipos canónicos inválidos — fail-closed via canonical_json()
# ---------------------------------------------------------------------------

class TestTiposCanonicosinvalidos:
    def test_datetime_sem_tz_bloqueado(self):
        r = verificar_contexto({"ts": datetime(2026, 7, 13)})
        assert r.ok is False
        assert any("serializacao_canonica_invalida" in v for v in r.violations)

    def test_decimal_nan_bloqueado(self):
        r = verificar_contexto({"v": Decimal("NaN")})
        assert r.ok is False
        assert any("serializacao_canonica_invalida" in v for v in r.violations)

    def test_decimal_infinity_bloqueado(self):
        r = verificar_contexto({"v": Decimal("Infinity")})
        assert r.ok is False
        assert any("serializacao_canonica_invalida" in v for v in r.violations)

    def test_uuid_v1_bloqueado(self):
        r = verificar_contexto({"id": _uuid_mod.uuid1()})
        assert r.ok is False
        assert any("serializacao_canonica_invalida" in v for v in r.violations)

    def test_chave_nao_string_bloqueada(self):
        r = verificar_contexto({1: "valor"})
        assert r.ok is False
        assert any("serializacao_canonica_invalida" in v for v in r.violations)

    def test_tipo_desconhecido_fail_closed(self):
        r = verificar_contexto({"obj": object()})
        assert r.ok is False
        assert any("tipo_desconhecido" in v or "serializacao_canonica_invalida" in v
                   for v in r.violations)

    def test_tipo_desconhecido_em_resultado_fail_closed(self):
        with pytest.raises(ValueError, match="ResultSanitizationGuard"):
            assert_result_sanitized({"payload": {"obj": object()}})


# ---------------------------------------------------------------------------
# Falsos positivos — campos seguros
# ---------------------------------------------------------------------------

class TestFalsoPositivo:
    def test_source_request_id(self):
        assert verificar_contexto({"source_request_id": "req-abc-123"}).ok is True

    def test_status_http(self):
        assert verificar_contexto({"status_http": 200}).ok is True

    def test_token_count(self):
        assert verificar_contexto({"token_count": 1500}).ok is True

    def test_xml_hash(self):
        assert verificar_contexto({"xml_hash": "abc123def456"}).ok is True

    def test_ipv4_invalido_nao_bloqueado(self):
        assert verificar_contexto({"ref": "999.999.999.999"}).ok is True

    def test_cpf_invalido_11_digitos_nao_bloqueado(self):
        assert verificar_contexto({"doc": "12345678900"}).ok is True

    def test_cnpj_invalido_todos_zeros_nao_bloqueado(self):
        assert verificar_contexto({"doc": "00000000000000"}).ok is True


# ---------------------------------------------------------------------------
# Chaves proibidas exactas
# ---------------------------------------------------------------------------

class TestChavesProibidas:
    def test_password_none(self):
        r = verificar_contexto({"password": None})
        assert r.ok is False and any("password" in v for v in r.violations)

    def test_token_vazio(self):
        r = verificar_contexto({"token": ""})
        assert r.ok is False and any("token" in v for v in r.violations)

    def test_authorization_redacted(self):
        assert verificar_contexto({"authorization": "redacted"}).ok is False

    def test_api_key_none(self):
        assert verificar_contexto({"api_key": None}).ok is False

    def test_senha(self):
        assert verificar_contexto({"senha": "x"}).ok is False

    def test_secret(self):
        assert verificar_contexto({"secret": "x"}).ok is False

    def test_cpf_chave(self):
        assert verificar_contexto({"cpf": "qualquer"}).ok is False

    def test_cnpj_chave(self):
        assert verificar_contexto({"cnpj": "qualquer"}).ok is False

    def test_email_chave(self):
        assert verificar_contexto({"email": "qualquer"}).ok is False

    def test_xml_chave(self):
        assert verificar_contexto({"xml": "<NFe/>"}).ok is False

    def test_headers_chave(self):
        assert verificar_contexto({"headers": {"Authorization": "Bearer x"}}).ok is False

    def test_body_chave(self):
        assert verificar_contexto({"body": {"campo": "valor"}}).ok is False


# ---------------------------------------------------------------------------
# Padrões de conteúdo
# ---------------------------------------------------------------------------

class TestPadroesConteudo:
    def test_bearer_token(self):
        r = verificar_contexto({"auth": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"})
        assert r.ok is False and any("token_bearer" in v for v in r.violations)

    def test_jwt_sem_bearer(self):
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        r = verificar_contexto({"tok": jwt})
        assert r.ok is False and any("jwt_sem_bearer" in v for v in r.violations)

    def test_api_key_sk(self):
        assert verificar_contexto({"k": "sk-abcdefghijklmnopqrst"}).ok is False

    def test_api_key_sk_proj(self):
        assert verificar_contexto({"k": "sk-proj-abcdefghijklmnopqrst"}).ok is False

    def test_api_key_ghp(self):
        assert verificar_contexto({"k": "ghp_" + "a" * 36}).ok is False

    def test_github_pat(self):
        assert verificar_contexto({"k": "github_pat_abcdefghijklmnopqrst"}).ok is False

    def test_gho(self):
        assert verificar_contexto({"k": "gho_" + "a" * 36}).ok is False

    def test_ghu(self):
        assert verificar_contexto({"k": "ghu_" + "a" * 36}).ok is False

    def test_ghs(self):
        assert verificar_contexto({"k": "ghs_" + "a" * 36}).ok is False

    def test_ghr(self):
        assert verificar_contexto({"k": "ghr_" + "a" * 36}).ok is False

    def test_email_em_valor(self):
        r = verificar_contexto({"c": "usuario@empresa.com.br"})
        assert r.ok is False and any("email" in v for v in r.violations)

    def test_xml_fiscal(self):
        assert verificar_contexto({"d": "<?xml version='1.0'?><nfeProc>"}).ok is False

    def test_nfe_tag(self):
        assert verificar_contexto({"d": "<NFe xmlns='...'>"}).ok is False

    def test_traceback(self):
        assert verificar_contexto({"e": "Traceback (most recent call last):\n  ..."}).ok is False

    def test_ipv4_valido(self):
        r = verificar_contexto({"o": "192.168.1.100"})
        assert r.ok is False and any("ipv4" in v for v in r.violations)

    def test_ipv6_full(self):
        r = verificar_contexto({"o": "2001:0db8:85a3:0000:0000:8a2e:0370:7334"})
        assert r.ok is False and any("ipv6" in v for v in r.violations)

    def test_ipv6_comprimido_loopback(self):
        r = verificar_contexto({"o": "::1"})
        assert r.ok is False and any("ipv6" in v for v in r.violations)

    def test_ipv6_comprimido_db8(self):
        r = verificar_contexto({"o": "2001:db8::1"})
        assert r.ok is False and any("ipv6" in v for v in r.violations)

    def test_ipv6_mapeado_ipv4(self):
        # ::ffff:192.168.1.1 e IPv4-mapped IPv6. O sanitizer detecta ipv4
        # (regex IPv4 apanha 192.168.1.1 dentro) ou ipv6 - ambos correcto.
        r = verificar_contexto({"origem": "::ffff:192.168.1.1"})
        assert r.ok is False and any("ipv4" in v or "ipv6" in v for v in r.violations)

    def test_cpf_valido_em_chave_neutra(self):
        r = verificar_contexto({"documento": "529.982.247-25"})
        assert r.ok is False and any("cpf" in v for v in r.violations)

    def test_cnpj_valido_em_chave_neutra(self):
        r = verificar_contexto({"documento": "11.222.333/0001-81"})
        assert r.ok is False and any("cnpj" in v for v in r.violations)


# ---------------------------------------------------------------------------
# Varredura recursiva
# ---------------------------------------------------------------------------

class TestVarreduraRecursiva:
    def test_email_aninhado(self):
        assert verificar_contexto({"a": {"b": {"c": "x@y.com"}}}).ok is False

    def test_email_em_lista(self):
        assert verificar_contexto({"lista": ["normal", "user@test.com"]}).ok is False

    def test_email_em_dict_dentro_de_lista(self):
        assert verificar_contexto({"items": [{"c": "a@b.com"}]}).ok is False

    def test_chave_proibida_aninhada(self):
        assert verificar_contexto({"dados": {"password": "x"}}).ok is False

    def test_headers_estrutura_real(self):
        assert verificar_contexto({"headers": {"Authorization": "Bearer tok"}}).ok is False

    def test_body_estrutura_real(self):
        assert verificar_contexto({"body": {"campo": "valor"}}).ok is False

    def test_caminho_registado(self):
        r = verificar_contexto({"a": {"b": {"c": "x@y.com"}}})
        assert any("a.b.c" in v or "c" in v for v in r.violations)

    def test_pydantic_com_email(self):
        class Sensiveis(BaseModel):
            email: str
        assert verificar_contexto({"m": Sensiveis(email="user@test.com")}).ok is False

    def test_pydantic_sensivel_em_lista(self):
        class S(BaseModel):
            email: str
        assert verificar_contexto({"lista": [S(email="a@b.com")]}).ok is False

    def test_pydantic_sensivel_em_dict_aninhado(self):
        class S(BaseModel):
            email: str
        assert verificar_contexto({"dados": {"modelo": S(email="a@b.com")}}).ok is False

    def test_json_string_com_password(self):
        assert verificar_contexto({"payload": '{"password":"segredo"}'}).ok is False

    def test_json_string_com_body(self):
        assert verificar_contexto({"payload": '{"body":{"campo":"valor"}}'}).ok is False

    def test_json_string_escalada_com_email(self):
        # JSON scalar string com email Unicode-escaped
        r = verificar_contexto({"payload": '"user\\u0040example.com"'})
        assert r.ok is False

    def test_pydantic_limpo_em_lista_nao_bloqueado(self):
        class S(BaseModel):
            x: int
        # Pydantic limpo em lista não deve bloquear
        assert verificar_contexto({"lista": [S(x=1)]}).ok is True


    def test_email_em_chave_bloqueado(self):
        assert verificar_contexto({"user@example.com": "valor"}).ok is False

    def test_token_em_chave_bloqueado(self):
        assert verificar_contexto({"sk-proj-abcdefghijklmnopqrst": "valor"}).ok is False

    def test_chave_proibida_com_espacos_bloqueada(self):
        assert verificar_contexto({" Authorization ": "redacted"}).ok is False

    def test_estrutura_ciclica_falha_fechada(self):
        contexto: dict = {}
        contexto["self"] = contexto
        resultado = verificar_contexto(contexto)
        assert resultado.ok is False
        assert any("estrutura_ciclica" in v or "serializacao_canonica_invalida" in v
                   for v in resultado.violations)

    def test_contexto_raiz_nao_dict_verificar(self):
        r = verificar_contexto(["invalido"])  # type: ignore[arg-type]
        assert r.ok is False


# ---------------------------------------------------------------------------
# assert_context_sanitized
# ---------------------------------------------------------------------------

class TestAssertContextSanitized:
    def test_limpo_nao_levanta(self):
        assert_context_sanitized({"ano": 2026})

    def test_email_levanta(self):
        with pytest.raises(ValueError, match="ContextSanitizationGuard"):
            assert_context_sanitized({"c": "x@y.com"})

    def test_mensagem_inclui_violacoes(self):
        with pytest.raises(ValueError, match="email"):
            assert_context_sanitized({"c": "x@y.com"})

    def test_contexto_raiz_nao_dict_bloqueado(self):
        with pytest.raises(ValueError, match="dict"):
            assert_context_sanitized(["invalido"])  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# assert_result_sanitized
# ---------------------------------------------------------------------------

class TestAssertResultSanitized:
    def test_limpo_nao_levanta(self):
        assert_result_sanitized({
            "alerts": [], "evidence": [], "payload": {"status": "ok"},
            "error_message": None, "actions_proposed": [], "actions_executed": [],
        })

    def test_email_em_alert_message(self):
        with pytest.raises(ValueError, match="ResultSanitizationGuard"):
            assert_result_sanitized({"alerts": [{"message": "Erro para user@test.com"}]})

    def test_ip_em_evidence_reference(self):
        with pytest.raises(ValueError, match="ResultSanitizationGuard"):
            assert_result_sanitized({"evidence": [{"reference": "192.168.1.1"}]})

    def test_token_em_payload(self):
        with pytest.raises(ValueError, match="ResultSanitizationGuard"):
            assert_result_sanitized({"payload": {"token": "secret_value"}})

    def test_traceback_em_error_message(self):
        with pytest.raises(ValueError, match="ResultSanitizationGuard"):
            assert_result_sanitized({"error_message": "Traceback (most recent call last):\n..."})

    def test_xml_em_action_proposed(self):
        with pytest.raises(ValueError, match="ResultSanitizationGuard"):
            assert_result_sanitized({"actions_proposed": [{"xml": "<NFe/>"}]})

    def test_dado_sensivel_em_action_executed(self):
        with pytest.raises(ValueError, match="ResultSanitizationGuard"):
            assert_result_sanitized({"actions_executed": [{"message": "Enviado para user@test.com"}]})

    def test_campos_ausentes_ignorados(self):
        assert_result_sanitized({"payload": {"status": "ok"}})

    def test_multiplas_violacoes(self):
        with pytest.raises(ValueError):
            assert_result_sanitized({
                "alerts": [{"message": "user@test.com"}],
                "payload": {"token": "x"},
            })

    def test_resultado_raiz_nao_dict_bloqueado(self):
        with pytest.raises(ValueError, match="dict"):
            assert_result_sanitized(["invalido"])  # type: ignore[arg-type]
