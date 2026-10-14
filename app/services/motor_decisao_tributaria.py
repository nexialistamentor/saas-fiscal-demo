from app.services.analisador_impacto import calcular_impacto_st


def decidir_acao_st(valor_produto, st_pago, mva, aliquota):
    analise = calcular_impacto_st(valor_produto, st_pago, mva, aliquota)
    impacto = analise["impacto"]

    if impacto > 0:
        return {
            "decisao": "RESTITUICAO_POSSIVEL",
            "valor_estimado": impacto,
            "descricao": "O valor de ST documentado no XML está acima do cenário normativo estimado.",
            "recomendacao": "avaliar pedido de restituição de ST."
        }

    if impacto < 0:
        return {
            "decisao": "RISCO_FISCAL",
            "valor_estimado": impacto,
            "descricao": "O valor de ST documentado no XML está abaixo do cenário normativo estimado.",
            "recomendacao": "verificar parametrização fiscal para evitar autuação."
        }

    return {
        "decisao": "OPERACAO_CORRETA",
        "valor_estimado": 0,
        "descricao": "O valor de ST documentado no XML é compatível com o cenário normativo estimado.",
        "recomendacao": "nenhuma ação necessária."
    }
