"""SOLVERIS P1-02A — contrato RED para um diagnostico fiscal pago sem ST positivo.

PROPOSITO:
- Preservar F0/UX2.1: a oferta legada de credito ST e seu gate permanecem.
- Exigir uma autoridade de elegibilidade distinta para o produto de diagnostico fiscal.
- Este contrato NAO autoriza checkout, nao cria oferta, nao cobra e nao executa fiscal.
- O payload e de um RESULTADO PERSISTIDO JA VERIFICADO por provenance antes da politica.

O RED inicial deve ser APENAS P102_NEW_DIAGNOSTIC_POLICY_MISSING.
"""

import importlib

from app.services.tax_report_eligibility import (
    projetar_tax_report_eligibility,
    resultado_tem_credito_tax_report_elegivel,
)


def _documentary_result(*, empresa_id=21, creditos=None, oportunidades=None):
    return {
        "empresa_id": empresa_id,
        "dados_fiscais": {
            "chave_nfe": "1" * 44,
            "numero_nota": "312",
            "valor_total_nota": 1499.00,
            "uf_emit": "PA",
            "uf_dest": "PA",
            "icms_st": 0,
        },
        "insights": {
            "documental": [{
                "tipo": "DOCUMENTO_FISCAL_ANALISADO",
                "descricao": "Documento fiscal identificado e analisado sem credito ST positivo.",
            }],
            "empresarial": None,
        },
        "creditos_detectados": [] if creditos is None else creditos,
        "oportunidades": [] if oportunidades is None else oportunidades,
        "context_flags": {
            "documental": {"dados_incompletos": False},
            "empresarial": {"dados_incompletos": False},
        },
        "previsao_recuperacao": {
            "potencial_recuperacao_nota": None,
            "metodo": "indisponivel_sem_validacao_normativa",
        },
        "decomposicao_impacto": {
            "documental": {"valor_recuperavel_real": None, "valor_estimado": None},
            "empresarial": {"valor_recuperavel_real": None, "valor_estimado": None},
        },
    }


def test_p102_legacy_st_credit_gate_is_not_silently_relaxed():
    document = _documentary_result()
    assert resultado_tem_credito_tax_report_elegivel(document) is False
    assert projetar_tax_report_eligibility(document) == {"eligible": False}
    st = _documentary_result(creditos=[{"tipo": "CREDITO_ST_ESTIMADO", "valor_estimado": 9.99}])
    assert resultado_tem_credito_tax_report_elegivel(st) is True
    assert projetar_tax_report_eligibility(st) == {"eligible": True}


def test_p102_general_paid_diagnostic_policy_is_distinct_from_st_credit_entitlement():
    try:
        module = importlib.import_module("app.services.enterprise_paid_diagnostic_eligibility")
    except ModuleNotFoundError as exc:
        if exc.name != "app.services.enterprise_paid_diagnostic_eligibility":
            raise
        raise AssertionError("P102_NEW_DIAGNOSTIC_POLICY_MISSING") from None
    authority = getattr(module, "avaliar_elegibilidade_diagnostico_empresarial", None)
    assert callable(authority), "P102_NEW_DIAGNOSTIC_POLICY_MISSING"

    def decision(snapshot, empresa_id=21):
        result = authority(snapshot, empresa_id=empresa_id)
        assert type(result) is dict and set(result) == {"eligible"}
        assert type(result["eligible"]) is bool
        return result["eligible"]

    # Produto valido pode fornecer um resultado SEM valor recuperavel: a consulta e o bem adquirido.
    assert decision(_documentary_result()) is True, "P102_VALID_NON_ST_DIAGNOSTIC_BLOCKED"
    # Uma conclusao economica nao pode adquirir autoridade por um valor isolado.
    assert decision({"empresa_id": 21, "oportunidades": [{"valor_estimado": 99999}]}) is False
    assert decision({"empresa_id": 21, "creditos_detectados": [{"tipo": "CREDITO_ST_ESTIMADO", "valor_estimado": 100}]}) is False
    assert decision({}, 21) is False
    assert decision(_documentary_result(empresa_id=99), 21) is False
    # Resultado explicitamente incompleto nao deve ser apresentado como diagnostico completo.
    incomplete = _documentary_result()
    incomplete["context_flags"]["documental"]["dados_incompletos"] = True
    assert decision(incomplete) is False
    invalid = _documentary_result()
    invalid["dados_fiscais"]["erro"] = "XML malformado"
    assert decision(invalid) is False
