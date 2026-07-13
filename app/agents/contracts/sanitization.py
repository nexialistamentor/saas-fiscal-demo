"""
app/agents/contracts/sanitization.py

ContextSanitizationGuard e ResultSanitizationGuard — ADR-008 B14.0.

Fail-closed: qualquer tipo não reconhecido ou objecto não serializável
canonicamente retorna violação, em vez de passar silenciosamente.

Não importa agentes, serviços, ORM, BD, HTTP ou providers.
"""
from __future__ import annotations

import ipaddress
import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.agents.contracts.canonical import canonical_json


# ---------------------------------------------------------------------------
# Chaves proibidas exactas
#
# A comparação é feita depois de:
# - normalização Unicode NFC;
# - remoção de espaços externos;
# - casefold.
#
# A comparação exacta evita bloquear campos seguros como:
# source_request_id, token_count e xml_hash.
# ---------------------------------------------------------------------------

_FORBIDDEN_KEYS: frozenset[str] = frozenset({
    "password",
    "senha",
    "secret",
    "token",
    "authorization",
    "api_key",
    "cpf",
    "cnpj",
    "email",
    "xml",
    "headers",
    "body",
})


# ---------------------------------------------------------------------------
# Padrões de conteúdo
# ---------------------------------------------------------------------------

_BEARER_RE = re.compile(
    r"\bBearer\s+[A-Za-z0-9\-._~+/]+=*",
    re.IGNORECASE,
)
_JWT_RE = re.compile(
    r"\bey[A-Za-z0-9_\-]{10,}"
    r"\.[A-Za-z0-9_\-]{10,}"
    r"\.[A-Za-z0-9_\-]+"
)
_SK_RE = re.compile(
    r"\bsk-[A-Za-z0-9_\-]{20,}"
)
_GHP_RE = re.compile(
    r"\bghp_[A-Za-z0-9]{36}"
)
_GH_PAT_RE = re.compile(
    r"\bgithub_pat_[A-Za-z0-9_]{20,}"
)
_GHO_RE = re.compile(
    r"\bgho_[A-Za-z0-9]{36}"
)
_GHU_RE = re.compile(
    r"\bghu_[A-Za-z0-9]{36}"
)
_GHS_RE = re.compile(
    r"\bghs_[A-Za-z0-9]{36}"
)
_GHR_RE = re.compile(
    r"\bghr_[A-Za-z0-9]{36}"
)
_EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+\-]+"
    r"@[A-Za-z0-9.\-]+"
    r"\.[A-Za-z]{2,}\b"
)
_XML_RE = re.compile(
    r"<\?xml|<nfeProc|<NFe\b",
    re.IGNORECASE,
)
_TB_RE = re.compile(
    r"Traceback \(most recent call last\)",
    re.IGNORECASE,
)
_IPV4_RE = re.compile(
    r"\b(\d{1,3}(?:\.\d{1,3}){3})\b"
)
_IPV6_RE = re.compile(
    r"(?:"
    r"(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}"
    r"|(?:[0-9a-fA-F]{1,4}:){1,7}:"
    r"|:(?::[0-9a-fA-F]{1,4}){1,7}"
    r"|(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}"
    r"|(?:[0-9a-fA-F]{1,4}:){1,5}"
    r"(?::[0-9a-fA-F]{1,4}){1,2}"
    r"|(?:[0-9a-fA-F]{1,4}:){1,4}"
    r"(?::[0-9a-fA-F]{1,4}){1,3}"
    r"|(?:[0-9a-fA-F]{1,4}:){1,3}"
    r"(?::[0-9a-fA-F]{1,4}){1,4}"
    r"|(?:[0-9a-fA-F]{1,4}:){1,2}"
    r"(?::[0-9a-fA-F]{1,4}){1,5}"
    r"|[0-9a-fA-F]{1,4}:"
    r"(?::[0-9a-fA-F]{1,4}){1,6}"
    r"|::(?:ffff(?::0{1,4})?:)?"
    r"(?:\d{1,3}\.){3}\d{1,3}"
    r"|::1"
    r"|::"
    r")",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# IP
# ---------------------------------------------------------------------------

def _is_valid_ipv4(text: str) -> bool:
    try:
        ipaddress.IPv4Address(text)
        return True
    except ipaddress.AddressValueError:
        return False


def _is_valid_ipv6(text: str) -> bool:
    try:
        ipaddress.IPv6Address(text)
        return True
    except ipaddress.AddressValueError:
        return False


def _contains_ip(text: str) -> str | None:
    for match in _IPV4_RE.finditer(text):
        if _is_valid_ipv4(match.group(1)):
            return "ipv4"

    for match in _IPV6_RE.finditer(text):
        if _is_valid_ipv6(match.group(0)):
            return "ipv6"

    return None


# ---------------------------------------------------------------------------
# CPF/CNPJ com validação dos dígitos verificadores
# ---------------------------------------------------------------------------

def _luhn_cpf(digits: str) -> bool:
    if len(digits) != 11 or len(set(digits)) == 1:
        return False

    def calcular(dados: str, tamanho: int) -> int:
        soma = sum(
            int(dados[indice]) * (tamanho - indice)
            for indice in range(tamanho - 1)
        )
        resto = (soma * 10) % 11
        return 0 if resto >= 10 else resto

    return (
        calcular(digits, 10) == int(digits[9])
        and calcular(digits, 11) == int(digits[10])
    )


def _luhn_cnpj(digits: str) -> bool:
    if len(digits) != 14 or len(set(digits)) == 1:
        return False

    def calcular(dados: str, pesos: list[int]) -> int:
        soma = sum(
            int(dados[indice]) * pesos[indice]
            for indice in range(len(pesos))
        )
        resto = soma % 11
        return 0 if resto < 2 else 11 - resto

    pesos_primeiro = [
        5, 4, 3, 2,
        9, 8, 7, 6,
        5, 4, 3, 2,
    ]
    pesos_segundo = [
        6, 5, 4, 3, 2,
        9, 8, 7, 6,
        5, 4, 3, 2,
    ]

    return (
        calcular(digits, pesos_primeiro) == int(digits[12])
        and calcular(digits, pesos_segundo) == int(digits[13])
    )


def _contains_cpf_cnpj(text: str) -> str | None:
    raw = re.sub(r"[.\-/]", "", text)

    for indice in range(len(raw) - 10):
        segmento = raw[indice:indice + 11]

        if segmento.isdigit() and _luhn_cpf(segmento):
            return "cpf"

    for indice in range(len(raw) - 13):
        segmento = raw[indice:indice + 14]

        if segmento.isdigit() and _luhn_cnpj(segmento):
            return "cnpj"

    return None


# ---------------------------------------------------------------------------
# Resultado e violação
# ---------------------------------------------------------------------------

@dataclass
class SanitizationResult:
    ok: bool
    violations: list[str] = field(default_factory=list)


@dataclass
class Violation:
    path: str
    reason: str


# ---------------------------------------------------------------------------
# Varredura de strings
# ---------------------------------------------------------------------------

def _scan_string(
    text: str,
    path: str,
    violations: list[Violation],
) -> None:
    checks = [
        (_BEARER_RE, "token_bearer"),
        (_JWT_RE, "jwt_sem_bearer"),
        (_SK_RE, "api_key_sk"),
        (_GHP_RE, "api_key_ghp"),
        (_GH_PAT_RE, "api_key_github_pat"),
        (_GHO_RE, "api_key_gho"),
        (_GHU_RE, "api_key_ghu"),
        (_GHS_RE, "api_key_ghs"),
        (_GHR_RE, "api_key_ghr"),
        (_EMAIL_RE, "email"),
        (_XML_RE, "xml_fiscal"),
        (_TB_RE, "traceback"),
    ]

    for pattern, reason in checks:
        if pattern.search(text):
            violations.append(
                Violation(
                    path=path,
                    reason=reason,
                )
            )

    ip_type = _contains_ip(text)

    if ip_type:
        violations.append(
            Violation(
                path=path,
                reason=ip_type,
            )
        )

    cpf_cnpj_type = _contains_cpf_cnpj(text)

    if cpf_cnpj_type:
        violations.append(
            Violation(
                path=path,
                reason=cpf_cnpj_type,
            )
        )

    # Também varre JSON codificado dentro de strings.
    # Inclui objectos, listas e strings escalares JSON.
    stripped = text.strip()

    if stripped.startswith(("{", "[", '"')):
        try:
            parsed = json.loads(text)

            # Evita reprocessamento quando a desserialização devolve
            # exactamente a string original.
            if parsed != text:
                _scan(
                    parsed,
                    f"{path}[json]",
                    violations,
                )

        except (json.JSONDecodeError, ValueError):
            pass


# ---------------------------------------------------------------------------
# Varredura recursiva
# ---------------------------------------------------------------------------

def _scan(
    obj: Any,
    path: str,
    violations: list[Violation],
    ativos: set[int] | None = None,
) -> None:
    """
    Varre recursivamente chaves e valores.

    `ativos` contém somente os objectos presentes na pilha de recursão.
    Referências partilhadas são permitidas; ciclos activos são bloqueados.
    """
    if ativos is None:
        ativos = set()

    if isinstance(obj, dict):
        object_id = id(obj)

        if object_id in ativos:
            violations.append(
                Violation(
                    path=path or "$",
                    reason="estrutura_ciclica",
                )
            )
            return

        ativos.add(object_id)

        try:
            for key, value in obj.items():
                key_is_sensitive = False

                if isinstance(key, str):
                    key_path = (
                        f"{path}.<key>"
                        if path
                        else "<key>"
                    )

                    key_violations: list[Violation] = []
                    _scan_string(
                        key,
                        key_path,
                        key_violations,
                    )

                    if key_violations:
                        key_is_sensitive = True
                        violations.extend(key_violations)

                    normalized_key = (
                        unicodedata
                        .normalize("NFC", key)
                        .strip()
                        .casefold()
                    )

                    if normalized_key in _FORBIDDEN_KEYS:
                        key_is_sensitive = True
                        violations.append(
                            Violation(
                                path=key_path,
                                reason=(
                                    "chave_proibida:"
                                    f"{normalized_key}"
                                ),
                            )
                        )

                    path_key = (
                        "<sensitive_key>"
                        if key_is_sensitive
                        else key
                    )

                else:
                    # canonical_json() já regista a chave não textual.
                    # Não reproduzimos o valor da chave no caminho.
                    path_key = "<non_string_key>"

                child_path = (
                    f"{path}.{path_key}"
                    if path
                    else path_key
                )

                _scan(
                    value,
                    child_path,
                    violations,
                    ativos,
                )

        finally:
            ativos.remove(object_id)

        return

    if isinstance(obj, (list, tuple)):
        object_id = id(obj)

        if object_id in ativos:
            violations.append(
                Violation(
                    path=path or "$",
                    reason="estrutura_ciclica",
                )
            )
            return

        ativos.add(object_id)

        try:
            for index, item in enumerate(obj):
                _scan(
                    item,
                    f"{path}[{index}]",
                    violations,
                    ativos,
                )

        finally:
            ativos.remove(object_id)

        return

    if isinstance(obj, str):
        _scan_string(
            obj,
            path,
            violations,
        )
        return

    if isinstance(obj, (int, float, bool, type(None))):
        return

    if isinstance(obj, (datetime, date, UUID, Decimal)):
        # canonical_json() em _verificar() já bloqueia:
        # - datetime sem timezone;
        # - UUID não-v4;
        # - Decimal não-finito.
        return

    if hasattr(obj, "model_dump"):
        object_id = id(obj)

        if object_id in ativos:
            violations.append(
                Violation(
                    path=path or "$",
                    reason="estrutura_ciclica",
                )
            )
            return

        ativos.add(object_id)

        try:
            try:
                dumped = obj.model_dump(mode="python")
            except Exception as exc:
                violations.append(
                    Violation(
                        path=path or "$",
                        reason=(
                            "model_dump_invalido:"
                            f"{type(exc).__name__}"
                        ),
                    )
                )
                return

            _scan(
                dumped,
                path,
                violations,
                ativos,
            )

        finally:
            ativos.remove(object_id)

        return

    violations.append(
        Violation(
            path=path or "$",
            reason=(
                "tipo_desconhecido:"
                f"{type(obj).__name__}"
            ),
        )
    )


# ---------------------------------------------------------------------------
# Verificação interna
# ---------------------------------------------------------------------------

def _verificar(obj: Any) -> SanitizationResult:
    violations: list[Violation] = []

    try:
        canonical_json(obj)
    except Exception as exc:
        # Não inclui a mensagem da excepção, pois ela pode conter
        # conteúdo que não deve ser persistido.
        violations.append(
            Violation(
                path="$",
                reason=(
                    "serializacao_canonica_invalida:"
                    f"{type(exc).__name__}"
                ),
            )
        )

    _scan(
        obj,
        "",
        violations,
    )

    formatted_violations = [
        f"{violation.path}:{violation.reason}"
        for violation in violations
    ]

    return SanitizationResult(
        ok=not violations,
        violations=formatted_violations,
    )


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def assert_context_sanitized(context: dict) -> None:
    """Bloqueia contextos inválidos ou com dados sensíveis."""
    if not isinstance(context, dict):
        raise ValueError(
            "ContextSanitizationGuard exige context do tipo dict"
        )

    result = _verificar(context)

    if not result.ok:
        raise ValueError(
            "ContextSanitizationGuard bloqueou criação da missão. "
            f"Violações: {result.violations}"
        )


def assert_result_sanitized(result: dict) -> None:
    """Bloqueia resultados inválidos ou com dados sensíveis."""
    if not isinstance(result, dict):
        raise ValueError(
            "ResultSanitizationGuard exige result do tipo dict"
        )

    fields_to_check = {
        key: result[key]
        for key in (
            "alerts",
            "evidence",
            "payload",
            "error_message",
            "actions_proposed",
            "actions_executed",
        )
        if key in result
    }

    verification = _verificar(fields_to_check)

    if not verification.ok:
        raise ValueError(
            "ResultSanitizationGuard bloqueou persistência do resultado. "
            f"Violações: {verification.violations}"
        )


def verificar_contexto(context: dict) -> SanitizationResult:
    """Retorna o resultado da sanitização sem levantar excepção."""
    if not isinstance(context, dict):
        return SanitizationResult(
            ok=False,
            violations=[
                "$:contexto_raiz_invalida"
            ],
        )

    return _verificar(context)


def sanitizar_ou_levantar(context: dict) -> None:
    """Alias compatível para assert_context_sanitized()."""
    assert_context_sanitized(context)
