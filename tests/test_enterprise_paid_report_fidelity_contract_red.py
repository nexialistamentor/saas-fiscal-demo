"""P1-01 RED (Enterprise): relatório adquirido deve entregar conteúdo do snapshot.

Não altera MEI, pagamento, dados nem produção. Contratos com dados sintéticos;
NÃO representam direito fiscal ou validação SEFAZ. Só PDF adquirido.
"""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from io import BytesIO

import pdfplumber
import pytest

from app.services.resultado_empresarial_service import compor_resultado_empresarial
from app.services.resultado_provenance_service import (
    fingerprint_resultado_json, selar_resultado_nao_mei,
)
from app.services.tax_report_acquisition_pdf import (
    TaxReportAcquisitionPdfError, TaxReportAcquisitionPdfRenderer,
)
from app.services.tax_report_acquisition_reader import TaxReportAcquisitionReadResult

EMPRESA_ID = 21


def _enterprise_payload(*, opportunities=None):
    xml = {
        "dados_fiscais": {"chave_nfe": "1" * 44, "icms_st": 120.00},
        "insights": [{
            "tipo": "ICMS_ST_IDENTIFICADO",
            "descricao": "ICMS-ST observado no XML; credito nao comprovado",
        }],
        "previsao_recuperacao": {
            "potencial_recuperacao_nota": None,
            "metodo": "indisponivel_sem_validacao_normativa",
        },
        "context_flags": {
            "dados_incompletos": True, "usa_estimativa": False,
            "base_presumida": False, "valores_normalizados": False,
        },
        "decomposicao_impacto": {
            "valor_recuperavel_real": None, "valor_estimado": None,
            "normalizacoes_aplicadas": 0,
        },
    }
    rico = {
        "empresa_id": EMPRESA_ID,
        "oportunidades": opportunities if opportunities is not None else [{
            "tipo": "DISTORCAO_MVA", "ncm": "22030000",
            "descricao": "NCM 22030000 anomalia fiscal a verificar",
            "valor_estimado": None,
            "recomendacao": "Conferir regra por UF e data",
        }],
        "creditos_detectados": [{
            "tipo": "CREDITO_ST_ESTIMADO", "ncm": "10019010",
            "descricao": "NCM 10019010 credito ST estimado, nao confirmado",
            "valor_estimado": 5.80,
            "recomendacao": "Validar prova fiscal e regra vigente",
        }],
        "risco_tributario": {"nivel_risco": "medio", "score_risco_tributario": 1.0},
        "resultados_engines": {}, "comparativo_regime": {},
        "context_flags": {"dados_incompletos": True, "usa_estimativa": True},
        "decomposicao_impacto": {
            "valor_recuperavel_real": None,
            "valor_estimado": 5.80,
            "normalizacoes_aplicadas": 0,
        },
    }
    return compor_resultado_empresarial(EMPRESA_ID, xml, rico)


def _acquisition(payload=None):
    snapshot = selar_resultado_nao_mei(
        _enterprise_payload() if payload is None else deepcopy(payload),
        producer_id="app.services.resultado_empresarial_service.compor_resultado_empresarial",
    )
    return TaxReportAcquisitionReadResult(
        acquisition_id=601, relatorio_analise_id=501,
        fingerprint=fingerprint_resultado_json(snapshot),
        resultado_json_snapshot=snapshot,
        created_at=datetime(2026, 10, 15, tzinfo=timezone.utc),
    )


def _pdf_text(acquisition, empresa_id=EMPRESA_ID):
    output = TaxReportAcquisitionPdfRenderer().render(
        acquisition=acquisition, empresa_id=empresa_id,
    )
    assert isinstance(output, BytesIO)
    assert output.tell() == 0
    with pdfplumber.open(output) as report:
        assert len(report.pages) >= 1
        text = " ".join((page.extract_text() or "") for page in report.pages)
    return text


def test_p101_paid_pdf_contains_documentary_and_enterprise_diagnostics():
    acquisition = _acquisition()
    before = deepcopy(acquisition)
    content = _pdf_text(acquisition)
    required = (
        "ICMS-ST observado no XML",
        "NCM 22030000",
        "NCM 10019010",
        "Conferir regra por UF e data",
        "Validar prova fiscal e regra vigente",
    )
    missing = [fragment for fragment in required if fragment not in content]
    assert not missing, f"P101_ENTERPRISE_DIAG_LOST: {missing!r}"
    assert acquisition == before, "P101_ACQUIRED_SNAPSHOT_MUTATED"
    assert "_resultado_provenance" not in content
    assert "producer_id" not in content


def test_p101_enterprise_unknown_value_not_rendered_as_cash_or_confirmed_credit():
    content = _pdf_text(_acquisition())
    assert "R$ None" not in content, "P101_UNAVAILABLE_VALUE_PRINTED_AS_CASH"
    assert "dados incompletos" in content.lower(), "P101_INCOMPLETE_DATA_WARNING_LOST"
    assert "estimad" in content.lower(), "P101_ESTIMATE_STATUS_LOST"


def test_p101_enterprise_payload_cannot_be_displayed_under_another_empresa():
    payload = _enterprise_payload()
    acquisition = _acquisition(payload)
    with pytest.raises(TaxReportAcquisitionPdfError, match=".+"):
        TaxReportAcquisitionPdfRenderer().render(acquisition=acquisition, empresa_id=22)


def test_p101_long_acquired_enterprise_report_preserves_last_opportunity():
    opportunities = [
        {"tipo": "ANOMALIA_FISCAL", "ncm": f"{n:08d}",
         "descricao": f"OPORTUNIDADE_SINTETICA_{n:03d}", "valor_estimado": None}
        for n in range(1, 71)
    ]
    content = _pdf_text(_acquisition(_enterprise_payload(opportunities=opportunities)))
    assert "OPORTUNIDADE_SINTETICA_001" in content, "P101_FIRST_DIAG_LOST"
    assert "OPORTUNIDADE_SINTETICA_070" in content, "P101_LAST_DIAG_LOST_OR_NOT_PAGINATED"
