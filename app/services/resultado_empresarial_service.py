"""Composição pura: preserva origem e indisponibilidade, sem persistência."""
from copy import deepcopy


def compor_resultado_empresarial(empresa_id: int, resultado_xml: dict, resultado_insights: dict | None) -> dict:
    rico = resultado_insights if resultado_insights is not None else {}
    if rico.get("empresa_id") not in (None, empresa_id):
        raise ValueError("Resultado empresarial pertence a outra empresa.")
    return {
        "empresa_id": empresa_id,
        "dados_fiscais": deepcopy(resultado_xml.get("dados_fiscais")),
        "insights": {
            "documental": deepcopy(resultado_xml.get("insights")),
            # Lista bruta não auditada para o produto pago.
            "empresarial": None,
        },
        "previsao_recuperacao": deepcopy(resultado_xml.get("previsao_recuperacao")),
        "oportunidades": deepcopy(rico.get("oportunidades")),
        "creditos_detectados": deepcopy(rico.get("creditos_detectados")),
        "risco_tributario": deepcopy(rico.get("risco_tributario")),
        "resultados_engines": deepcopy(rico.get("resultados_engines")),
        "comparativo_regime": deepcopy(rico.get("comparativo_regime")),
        "context_flags": {
            "documental": deepcopy(resultado_xml.get("context_flags")),
            "empresarial": deepcopy(rico.get("context_flags")),
        },
        "decomposicao_impacto": {
            "documental": deepcopy(resultado_xml.get("decomposicao_impacto")),
            "empresarial": deepcopy(rico.get("decomposicao_impacto")),
        },
    }
