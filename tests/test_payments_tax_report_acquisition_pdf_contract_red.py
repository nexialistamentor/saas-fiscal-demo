"""RED: PDF de uma aquisicao tax.report previamente autorizada."""

from copy import deepcopy
from dataclasses import replace
from datetime import datetime
from inspect import getsource, signature
from io import BytesIO

import pytest

from app.services.context_flags_service import default_context_flags
from app.services.resultado_provenance_service import fingerprint_resultado_json
from app.services.tax_report_acquisition_reader import TaxReportAcquisitionReadResult


EMPRESA_ID = 21


def _future_contract():
    from app.services.tax_report_acquisition_pdf import (  # noqa: PLC0415
        TaxReportAcquisitionPdfError,
        TaxReportAcquisitionPdfRenderer,
    )

    return TaxReportAcquisitionPdfRenderer, TaxReportAcquisitionPdfError


def _snapshot(tag="adquirido"):
    return {
        "previsao_recuperacao": {
            "potencial_recuperacao_nota": 321.45,
            "tag": tag,
        },
        "context_flags": {
            "dados_incompletos": True,
            "valores_normalizados": False,
            "usa_estimativa": True,
            "base_presumida": False,
        },
        "decomposicao_impacto": {
            "valor_recuperavel_real": 300.0,
            "valor_estimado": 21.45,
            "normalizacoes_aplicadas": 1,
        },
        "insights": [
            {"descricao": f"Descricao {tag}", "tipo": "TIPO_IGNORADO"},
            {"tipo": f"Tipo {tag}"},
            {"descricao": "", "tipo": ""},
            {"descricao": None},
            "entrada-nao-dict",
        ],
        "_resultado_provenance": {
            "source": f"origem-{tag}",
            "commercial_secret": f"segredo-{tag}",
        },
        "campo_fora_da_projecao": f"nao-exibir-{tag}",
    }


def _acquisition(snapshot=None):
    snapshot = deepcopy(snapshot if snapshot is not None else _snapshot())
    return TaxReportAcquisitionReadResult(
        acquisition_id=601,
        relatorio_analise_id=501,
        fingerprint=fingerprint_resultado_json(snapshot),
        resultado_json_snapshot=snapshot,
        created_at=datetime(2026, 1, 2, 3, 4, 5),
    )


def _render(renderer_type, acquisition, empresa_id=EMPRESA_ID):
    return renderer_type().render(acquisition=acquisition, empresa_id=empresa_id)


def test_tax_report_acquisition_pdf_contract_red(monkeypatch):
    renderer_type, error_type = _future_contract()

    method = signature(renderer_type.render)
    assert tuple(method.parameters) == ("self", "acquisition", "empresa_id")
    assert all(
        method.parameters[name].kind.name == "KEYWORD_ONLY"
        for name in ("acquisition", "empresa_id")
    )

    source = getsource(renderer_type)
    for forbidden in (
        "Session",
        "RelatorioAnalise",
        "Insight",
        "gerar_mapa_oportunidades",
        "calcular_score_global_tributario",
        "consulta_paga",
        ".pago",
        "Entitlement",
        "executar_analise",
        "InsightEngine",
    ):
        assert forbidden not in source

    # O gerador real deve produzir um PDF valido, posicionado no inicio, sem mutacao.
    acquisition = _acquisition()
    acquisition_before = deepcopy(acquisition)
    snapshot_before = deepcopy(acquisition.resultado_json_snapshot)
    pdf = _render(renderer_type, acquisition)
    assert isinstance(pdf, BytesIO)
    assert pdf.tell() == 0
    assert pdf.read(4) == b"%PDF"
    assert acquisition == acquisition_before
    assert acquisition.resultado_json_snapshot == snapshot_before

    # A projecao comercial e formada exclusivamente a partir do snapshot adquirido.
    import app.services.tax_report_acquisition_pdf as pdf_module  # noqa: PLC0415

    received = []

    def spy_gerar_pdf_relatorio(projection):
        received.append(deepcopy(projection))
        return BytesIO(b"%PDF-spy")

    monkeypatch.setattr(pdf_module, "gerar_pdf_relatorio", spy_gerar_pdf_relatorio)
    acquired_snapshot = _snapshot("historico-A")
    current_result_b = _snapshot("resultado-atual-B")
    acquired = _acquisition(acquired_snapshot)
    acquired_before = deepcopy(acquired)
    expected_projection = {
        "empresa_id": EMPRESA_ID,
        "potencial_recuperacao": {"valor_estimado": 321.45},
        "context_flags": deepcopy(acquired_snapshot["context_flags"]),
        "decomposicao_impacto": deepcopy(
            acquired_snapshot["decomposicao_impacto"]
        ),
        "insights": ["Descricao historico-A", "Tipo historico-A"],
    }

    spied_pdf = _render(renderer_type, acquired)
    assert spied_pdf.tell() == 0
    assert received == [expected_projection]
    assert acquired == acquired_before
    assert current_result_b["previsao_recuperacao"]["tag"] == "resultado-atual-B"
    assert "resultado-atual-B" not in repr(received)
    assert "_resultado_provenance" not in repr(received)
    assert "segredo-historico-A" not in repr(received)

    # Defaults canonicos para campos opcionais ausentes ou invalidos.
    minimal_snapshot = {
        "context_flags": ["nao-e-dict"],
        "decomposicao_impacto": "nao-e-dict-nem-none",
        "insights": None,
    }
    _render(renderer_type, _acquisition(minimal_snapshot))
    assert received[-1] == {
        "empresa_id": EMPRESA_ID,
        "potencial_recuperacao": {"valor_estimado": 0},
        "context_flags": default_context_flags(),
        "decomposicao_impacto": None,
        "insights": [],
    }

    # Cada inconsistencia defensiva e rejeitada isoladamente.
    valid = _acquisition()
    divergent_snapshot = deepcopy(valid.resultado_json_snapshot)
    divergent_snapshot["campo_fora_da_projecao"] = "adulterado"
    negative_cases = (
        (0, valid),
        (-1, valid),
        (True, valid),
        (EMPRESA_ID, replace(valid, acquisition_id=0)),
        (EMPRESA_ID, replace(valid, relatorio_analise_id=0)),
        (EMPRESA_ID, replace(valid, fingerprint="A" * 64)),
        (EMPRESA_ID, replace(valid, resultado_json_snapshot=["nao-e-dict"])),
        (EMPRESA_ID, replace(valid, resultado_json_snapshot=divergent_snapshot)),
        (EMPRESA_ID, replace(valid, created_at=None)),
    )
    for empresa_id, invalid_acquisition in negative_cases:
        before = deepcopy(invalid_acquisition)
        with pytest.raises(error_type):
            _render(renderer_type, invalid_acquisition, empresa_id)
        assert invalid_acquisition == before
