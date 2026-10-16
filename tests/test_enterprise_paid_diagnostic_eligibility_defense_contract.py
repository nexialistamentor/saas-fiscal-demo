"""P1-02A: testes negativos defensivos do novo gate separado de credito ST."""
from copy import deepcopy
import pytest

from app.services.enterprise_paid_diagnostic_eligibility import (
    avaliar_elegibilidade_diagnostico_empresarial as avaliar,
)
from app.services.tax_report_eligibility import resultado_tem_credito_tax_report_elegivel


def _base():
    return {
        "empresa_id": 21,
        "dados_fiscais": {
            "chave_nfe": "1" * 44, "valor_total_nota": 1499.0,
            "uf_emit": "PA", "uf_dest": "PA", "icms_st": 0,
        },
        "insights": {"documental": [], "empresarial": None},
        "oportunidades": [], "creditos_detectados": [],
        "previsao_recuperacao": {"potencial_recuperacao_nota": None},
        "context_flags": {
            "documental": {"dados_incompletos": False},
            "empresarial": {"dados_incompletos": False},
        },
    }


def test_documento_sem_st_nem_oportunidades_pode_ser_diagnostico_negativo():
    b = _base()
    original = deepcopy(b)
    assert avaliar(b, empresa_id=21) == {"eligible": True}
    assert resultado_tem_credito_tax_report_elegivel(b) is False
    assert b == original


def test_credito_de_st_nao_e_requisito_comercial():
    b = _base()
    b["creditos_detectados"] = [{"tipo": "CREDITO_ST_ESTIMADO", "valor_estimado": 8.0}]
    assert avaliar(b, empresa_id=21) == {"eligible": True}
    assert resultado_tem_credito_tax_report_elegivel(b) is True


@pytest.mark.parametrize("change", [
    lambda x: x.update(empresa_id=True),
    lambda x: x.update(empresa_id=99),
    lambda x: x["dados_fiscais"].update(chave_nfe="123"),
    lambda x: x["dados_fiscais"].update(valor_total_nota=True),
    lambda x: x["dados_fiscais"].update(valor_total_nota=float("nan")),
    lambda x: x["dados_fiscais"].update(valor_total_nota=float("inf")),
    lambda x: x["dados_fiscais"].update(valor_total_nota=-1),
    lambda x: x["dados_fiscais"].update(uf_emit="XX", uf_dest=None),
    lambda x: x["dados_fiscais"].update(erro="Falha XML"),
    lambda x: x.update(insights=None),
    lambda x: x["insights"].update(documental="nao-lista"),
    lambda x: x.update(oportunidades=None),
    lambda x: x.update(creditos_detectados=None),
    lambda x: x.update(previsao_recuperacao=None),
    lambda x: x["context_flags"].update(documental={}),
    lambda x: x["context_flags"].update(empresarial={"dados_incompletos": True}),
    lambda x: x["context_flags"].update(empresarial={"dados_incompletos": 0}),
])
def test_payload_nao_elegivel(change):
    b = _base()
    change(b)
    assert avaliar(b, empresa_id=21) == {"eligible": False}


@pytest.mark.parametrize("id_empresa", [None, 0, True, "21", 99])
def test_identidade_solicitante_invalida(id_empresa):
    assert avaliar(_base(), empresa_id=id_empresa) == {"eligible": False}
