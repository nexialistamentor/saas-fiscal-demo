"""Renderizacao de PDF a partir de uma aquisicao tax.report imutavel."""

from copy import deepcopy
import hmac
from io import BytesIO
import re

from app.services.context_flags_service import default_context_flags
from app.services.pdf_report_service import gerar_pdf_relatorio
from app.services.resultado_provenance_service import (
    ResultadoProvenanceError,
    fingerprint_resultado_json,
)


class TaxReportAcquisitionPdfError(Exception):
    """Indica que uma aquisicao nao pode ser renderizada com seguranca."""


class TaxReportAcquisitionPdfRenderer:
    """Renderiza exclusivamente o snapshot validado de uma aquisicao."""

    def render(self, *, acquisition, empresa_id: int):
        if type(empresa_id) is not int or empresa_id <= 0:
            raise TaxReportAcquisitionPdfError("empresa_id invalido")

        acquisition_id = getattr(acquisition, "acquisition_id", None)
        if type(acquisition_id) is not int or acquisition_id <= 0:
            raise TaxReportAcquisitionPdfError("acquisition_id invalido")

        report_id = getattr(acquisition, "relatorio_analise_id", None)
        if type(report_id) is not int or report_id <= 0:
            raise TaxReportAcquisitionPdfError("relatorio_analise_id invalido")

        fingerprint = getattr(acquisition, "fingerprint", None)
        if not isinstance(fingerprint, str) or re.fullmatch(
            r"[0-9a-f]{64}", fingerprint
        ) is None:
            raise TaxReportAcquisitionPdfError("fingerprint invalido")

        snapshot = getattr(acquisition, "resultado_json_snapshot", None)
        if not isinstance(snapshot, dict):
            raise TaxReportAcquisitionPdfError("snapshot invalido")
        if getattr(acquisition, "created_at", None) is None:
            raise TaxReportAcquisitionPdfError("created_at invalido")

        try:
            calculated_fingerprint = fingerprint_resultado_json(snapshot)
        except ResultadoProvenanceError as exc:
            raise TaxReportAcquisitionPdfError("snapshot inconsistente") from exc
        if not hmac.compare_digest(calculated_fingerprint, fingerprint):
            raise TaxReportAcquisitionPdfError("fingerprint divergente")

        acquired_snapshot = deepcopy(snapshot)
        recovery = acquired_snapshot.get("previsao_recuperacao")
        estimated_value = (
            recovery.get("potencial_recuperacao_nota", 0)
            if isinstance(recovery, dict)
            else 0
        )

        flags = acquired_snapshot.get("context_flags")
        projected_flags = deepcopy(flags) if isinstance(flags, dict) else default_context_flags()

        impact = acquired_snapshot.get("decomposicao_impacto")
        projected_impact = deepcopy(impact) if isinstance(impact, dict) else None

        projected_insights = []
        insights = acquired_snapshot.get("insights")
        if isinstance(insights, list):
            for item in insights:
                if not isinstance(item, dict):
                    continue
                description = item.get("descricao")
                insight_type = item.get("tipo")
                if isinstance(description, str) and description:
                    projected_insights.append(description)
                elif isinstance(insight_type, str) and insight_type:
                    projected_insights.append(insight_type)

        projection = {
            "empresa_id": empresa_id,
            "potencial_recuperacao": {"valor_estimado": estimated_value},
            "context_flags": projected_flags,
            "decomposicao_impacto": projected_impact,
            "insights": projected_insights,
        }
        pdf = gerar_pdf_relatorio(projection)
        if not isinstance(pdf, BytesIO):
            raise TaxReportAcquisitionPdfError("retorno de PDF invalido")
        pdf.seek(0)
        return pdf
