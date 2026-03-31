"""
Rastreabilidade: flags e decomposição de valores sem alterar regras de negócio.
"""


def default_context_flags() -> dict:
    return {
        "dados_incompletos": False,
        "valores_normalizados": False,
        "usa_estimativa": False,
        "base_presumida": False,
    }


def inferir_flags_contexto_empresa(
    *,
    regime: str | None,
    faturamento: float,
    custos: float,
) -> dict:
    """Heurísticas sobre o contexto montado para engines (empresa)."""
    flags = default_context_flags()
    r = (regime or "presumido").lower()
    flags["base_presumida"] = r in ("presumido", "simples", "mei")
    flags["dados_incompletos"] = faturamento <= 0 and custos <= 0
    return flags


def merge_context_flags(*flag_dicts: dict) -> dict:
    """União por OU lógico (qualquer origem sinaliza)."""
    out = default_context_flags()
    for fd in flag_dicts:
        if not fd:
            continue
        for k in out:
            out[k] = bool(out[k] or fd.get(k))
    return out


def inferir_flags_xml(
    dados_fiscais: dict,
    previsao: dict | None,
) -> dict:
    """Flags para análise pontual de XML (motor_fiscal + previsão)."""
    flags = default_context_flags()
    if dados_fiscais.get("erro"):
        flags["dados_incompletos"] = True
        return flags

    chave = dados_fiscais.get("chave_nfe")
    v_total = dados_fiscais.get("valor_total_nota")
    icms_st = dados_fiscais.get("icms_st")
    if not chave or v_total is None:
        flags["dados_incompletos"] = True
    if icms_st is None:
        flags["dados_incompletos"] = True

    pv = previsao or {}
    metodo = (pv.get("metodo") or "").lower()
    if "estimativa" in metodo:
        flags["usa_estimativa"] = True

    return flags


def anexar_flags_nos_resultados_engines(
    resultados: dict,
    context_flags: dict | None,
) -> dict:
    """Propaga uma cópia das flags para cada engine (rastreabilidade na resposta)."""
    base = dict(context_flags) if context_flags else default_context_flags()
    out = {}
    for nome, res in resultados.items():
        if isinstance(res, dict):
            merged = dict(res)
            merged["context_flags"] = dict(base)
            out[nome] = merged
        else:
            out[nome] = res
    return out


def contagem_normalizacoes_exibicao(
    *,
    mapa_risco_pontuacao: int,
    motor_irpj_csll: int,
) -> int:
    """Total exibido ao usuário (escalas + ajustes de motor)."""
    return int(mapa_risco_pontuacao) + int(motor_irpj_csll)
