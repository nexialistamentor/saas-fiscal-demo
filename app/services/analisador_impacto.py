from app.services.simulador_st import simular_st


def calcular_impacto_st(valor_produto, st_pago, mva, aliquota):
    simulacao = simular_st(valor_produto, mva, aliquota)
    st_correta = simulacao["st_calculada"]
    impacto = st_pago - st_correta
    return {
        "st_pago": st_pago,
        "st_correta": st_correta,
        "impacto": impacto
    }
