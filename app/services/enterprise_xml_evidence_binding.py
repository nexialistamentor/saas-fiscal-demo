"""P1-03B — vínculo informativo dos bytes XML ao documento e relatório persistidos.

Não consulta base, não autentica SEFAZ, não concede elegibilidade, crédito nem pagamento.
Apenas um produtor que obteve DocumentoFiscal persistido deve criar a prova.
"""
from __future__ import annotations

import hashlib
import hmac
import re

from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

SCHEMA = "ENTERPRISE_XML_EVIDENCE_V1"
KEY = "_enterprise_xml_evidence"
_SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
_NFE_RE = re.compile(r"[0-9]{44}\Z")
_FIELDS = frozenset({
    "schema_version", "xml_sha256", "empresa_id", "usuario_id", "relatorio_id",
    "documento_id", "xml_chave",
})


def _inteiro(value: object) -> bool:
    return type(value) is int and value > 0


def _sha(value: object) -> bool:
    return type(value) is str and _SHA_RE.fullmatch(value) is not None


def _chave(value: object) -> bool:
    return type(value) is str and _NFE_RE.fullmatch(value) is not None


def _chave_observada(xml_bytes: bytes) -> str | None:
    """Lê só a identidade declarada no XML, sem considerar autenticidade fiscal."""
    if type(xml_bytes) is not bytes or not 0 < len(xml_bytes) <= 2 * 1024 * 1024:
        return None
    try:
        root = ET.fromstring(xml_bytes, forbid_dtd=True, forbid_entities=True,
                             forbid_external=True)
        inf = root.find(".//{*}infNFe")
        if inf is None:
            return None
        attr = inf.get("Id")
        if type(attr) is not str or not attr.startswith("NFe"):
            return None
        chave = attr[3:]
        if not _chave(chave):
            return None
        # Se houver protocolo, nao pode contradizer o identificador da NF-e.
        prot = root.find(".//{*}infProt/{*}chNFe")
        if prot is not None and prot.text != chave:
            return None
        return chave
    except (TypeError, ValueError, ET.ParseError, DefusedXmlException):
        return None


def construir_vinculo_documento_relatorio(
    xml_bytes: bytes, *, empresa_id: int, relatorio_id: int,
    documento: object, xml_chave: str,
) -> dict:
    """Produz evidência apenas de um objeto documental com identidade consistente.

    A função não garante que o objeto venha da BD: essa é obrigação do produtor.
    """
    digest = hashlib.sha256(xml_bytes).hexdigest() if type(xml_bytes) is bytes else None
    usuario_id = getattr(documento, "usuario_id", None)
    documento_id = getattr(documento, "id", None)
    document_sha = getattr(documento, "conteudo_sha256", None)
    if not (
        _inteiro(empresa_id) and _inteiro(relatorio_id) and _inteiro(documento_id)
        and _inteiro(usuario_id)
        and getattr(documento, "empresa_id", None) == empresa_id
        and _chave(xml_chave)
        and getattr(documento, "chave_nfe", None) == xml_chave
        and _chave_observada(xml_bytes) == xml_chave
        and _sha(document_sha) and digest is not None
        and hmac.compare_digest(digest, document_sha)
    ):
        raise ValueError("P103B_XML_EVIDENCE_UNVERIFIED")
    return {
        "schema_version": SCHEMA,
        "xml_sha256": digest,
        "empresa_id": empresa_id,
        "usuario_id": usuario_id,
        "relatorio_id": relatorio_id,
        "documento_id": documento_id,
        "xml_chave": xml_chave,
    }


def validar_vinculo_documento_relatorio(
    relatorio: object, documento: object, *, empresa_id: int,
) -> bool:
    """Valida snapshot persistido e fingerprint antes de reconciliar a evidência.

    Falha fechado para relatórios antigos sem vínculo, dados malformados,
    identidades divergentes ou alteração de conteúdo. Não verifica pagamento.
    """
    if not _inteiro(empresa_id):
        return False
    try:
        from app.services.resultado_provenance_service import (
            verificar_resultado_persistido, ResultadoProvenanceError,
        )
        business = verificar_resultado_persistido(relatorio)
    except Exception:  # Falha fechada para verificadores e envelopes inesperados.
        return False
    if type(business) is not dict:
        return False
    proof = business.get(KEY)
    if type(proof) is not dict or set(proof) != _FIELDS:
        return False
    if proof.get("schema_version") != SCHEMA:
        return False
    fields = (
        ("empresa_id", empresa_id),
        ("usuario_id", getattr(relatorio, "user_id", None)),
        ("relatorio_id", getattr(relatorio, "id", None)),
        ("documento_id", getattr(documento, "id", None)),
    )
    if any(not _inteiro(right) or type(proof.get(name)) is not int or
           proof[name] != right for name, right in fields):
        return False
    if not (
        getattr(relatorio, "analysis_type", None) == "xml_analise"
        and getattr(relatorio, "status", None) == "ok"
        and getattr(relatorio, "empresa_id", None) == empresa_id
        and getattr(documento, "empresa_id", None) == empresa_id
        and getattr(documento, "usuario_id", None) == proof["usuario_id"]
    ):
        return False
    chave = proof.get("xml_chave")
    if not (
        _chave(chave)
        and getattr(relatorio, "xml_chave", None) == chave
        and getattr(documento, "chave_nfe", None) == chave
        and type(business.get("dados_fiscais")) is dict
        and business["dados_fiscais"].get("chave_nfe") == chave
    ):
        return False
    doc_sha = getattr(documento, "conteudo_sha256", None)
    xml_sha = proof.get("xml_sha256")
    return bool(_sha(doc_sha) and _sha(xml_sha) and hmac.compare_digest(xml_sha, doc_sha))
