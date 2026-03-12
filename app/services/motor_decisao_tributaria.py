from app.services.analisador_impacto import calcular_impacto_st


def decidir_acao_st(valor_produto, st_pago, mva, aliquota):
    analise = calcular_impacto_st(valor_produto, st_pago, mva, aliquota)
    impacto = analise["impacto"]

    if impacto > 0:
        return {
            "decisao": "RESTITUICAO_POSSIVEL",
            "valor_estimado": impacto,
            "descricao": "ST recolhida acima do valor correto.",
            "recomendacao": "avaliar pedido de restituição de ST."
        }

    if impacto < 0:
        return {
            "decisao": "RISCO_FISCAL",
            "valor_estimado": impacto,
            "descricao": "ST recolhida abaixo do valor correto.",
            "recomendacao": "verificar parametrização fiscal para evitar autuação."
        }

    return {
        "decisao": "OPERACAO_CORRETA",
        "valor_estimado": 0,
        "descricao": "ST recolhida corretamente.",
        "recomendacao": "nenhuma ação necessária."
    }
