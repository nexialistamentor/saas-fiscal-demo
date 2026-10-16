"""P1-04A — leitura interna, restrita e exclusivamente informativa do diagnostico.

Nao executa fiscal, nao cria estado, nao consulta pagamentos nem autoriza checkout.
A evidencia documental e diferente de completude empresarial e de permissao de venda.
Quem chamar e responsavel por autenticar o utilizador antes desta fronteira.
"""
from __future__ import annotations

import hashlib
import hmac

from app.models import DocumentoFiscal, RelatorioAnalise
from app.services.enterprise_diagnostic_amount_binding import (
    normalizar_valor_nfe_para_politica,
)
from app.services.enterprise_diagnostic_coverage import avaliar_cobertura_nfe_documental
from app.services.enterprise_paid_diagnostic_eligibility import (
    avaliar_elegibilidade_diagnostico_empresarial,
)
from app.services.enterprise_xml_evidence_binding import (
    KEY as EVIDENCE_KEY,
    validar_vinculo_documento_relatorio,
)
from app.services.resultado_provenance_service import verificar_resultado_persistido

_NEGADO = {
    "documental_suficiente": False,
    "empresarial_completo": False,
    "st_nao_destacado_observado": False,
    "politica_diagnostico_elegivel": False,
    "diagnostico_documental_apresentavel": False,
    "checkout_autorizado": False,
}


def _id_positivo(value: object) -> bool:
    return type(value) is int and value > 0


def avaliar_prontidao_diagnostico_enterprise(
    db: object,
    *,
    authenticated_user_id: int,
    empresa_id: int,
    relatorio_id: int,
    xml_bytes: bytes,
) -> dict[str, bool]:
    """Consulta report e documento da sessao fornecida, sempre em modo read-only.

    Ausencia, divergencia ou excecao implica indisponibilidade TOTAL. Esta
    funcao nao verifica sessao HTTP e nao devolve direito a compra, mesmo que
    a politica pura indique elegibilidade informativa.
    """
    if (
        not all(_id_positivo(v) for v in (authenticated_user_id, empresa_id, relatorio_id))
        or type(xml_bytes) is not bytes
        or not 0 < len(xml_bytes) <= 2 * 1024 * 1024
        or db is None
    ):
        return dict(_NEGADO)
    try:
        rel = db.get(RelatorioAnalise, relatorio_id)
        if (
            rel is None
            or getattr(rel, "id", None) != relatorio_id
            or getattr(rel, "user_id", None) != authenticated_user_id
            or getattr(rel, "empresa_id", None) != empresa_id
            or getattr(rel, "analysis_type", None) != "xml_analise"
            or getattr(rel, "status", None) != "ok"
        ):
            return dict(_NEGADO)

        # Fingerprint e provenance ANTES de confiar no identificador do documento.
        resultado = verificar_resultado_persistido(rel)
        if type(resultado) is not dict or resultado.get("empresa_id") != empresa_id:
            return dict(_NEGADO)
        prova = resultado.get(EVIDENCE_KEY)
        if type(prova) is not dict:
            return dict(_NEGADO)
        documento_id = prova.get("documento_id")
        if not _id_positivo(documento_id):
            return dict(_NEGADO)

        documento = db.get(DocumentoFiscal, documento_id)
        if documento is None or not validar_vinculo_documento_relatorio(
            rel, documento, empresa_id=empresa_id,
        ):
            return dict(_NEGADO)

        # O verificador P1-03 liga relatorio a SHA armazenado, nao aos bytes
        # submetidos nesta consulta. Essa correspondencia adicional e obrigatoria.
        observado = hashlib.sha256(xml_bytes).hexdigest()
        gravado = getattr(documento, "conteudo_sha256", None)
        if type(gravado) is not str or not hmac.compare_digest(observado, gravado):
            return dict(_NEGADO)

        cobertura = avaliar_cobertura_nfe_documental(
            xml_bytes, resultado, empresa_id=empresa_id,
        )
        chaves = {
            "documental_suficiente", "empresarial_completo", "st_nao_destacado_observado",
        }
        if (
            type(cobertura) is not dict or set(cobertura) != chaves
            or any(type(v) is not bool for v in cobertura.values())
            or cobertura["documental_suficiente"] is not True
            or cobertura["empresarial_completo"] is not False
        ):
            return dict(_NEGADO)

        # A politica P1-02A nao e alterada ou alargada: e informativa e
        # tipicamente negada quando as flags empresariais ainda estao incompletas.
        normalizado = normalizar_valor_nfe_para_politica(resultado)
        politica = (
            avaliar_elegibilidade_diagnostico_empresarial(
                normalizado, empresa_id=empresa_id,
            ) if normalizado is not None else {"eligible": False}
        )
        if (type(politica) is not dict or set(politica) != {"eligible"}
                or type(politica["eligible"]) is not bool):
            return dict(_NEGADO)

        return {
            "documental_suficiente": True,
            "empresarial_completo": False,
            "st_nao_destacado_observado": cobertura["st_nao_destacado_observado"],
            "politica_diagnostico_elegivel": politica["eligible"],
            "diagnostico_documental_apresentavel": True,
            "checkout_autorizado": False,
        }
    except Exception:
        # Falhar fechado sem propagar mensagens internas de BD ou fiscal.
        return dict(_NEGADO)


__all__ = ["avaliar_prontidao_diagnostico_enterprise"]
