from typing import Optional

from app.services.tax_engines.base_tax_engine import BaseTaxEngine

# Regime não-cumulativo (Lucro Real) — Lei 10.637/2002 (PIS) e Lei 10.833/2003 (COFINS)
_ALIQ_PIS_NAO_CUMUL = 0.0165
_ALIQ_COFINS_NAO_CUMUL = 0.076
_SOMA_ALIQ_CREDITO = _ALIQ_PIS_NAO_CUMUL + _ALIQ_COFINS_NAO_CUMUL  # 9,25%


def _parse_valor_nao_negativo(val, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        return max(0.0, float(val))
    except (TypeError, ValueError):
        return default


def creditos_sobre_insumos_tributados(valor_insumos: float) -> tuple[float, float]:
    """
    Créditos estimados sobre aquisições de insumos tributados pelo regime não-cumulativo,
    às alíquotas de 1,65% (PIS) e 7,6% (COFINS) — hipótese típica do art. 3º da Lei 10.637/2002.
    """
    base = max(0.0, float(valor_insumos or 0))
    return (
        round(base * _ALIQ_PIS_NAO_CUMUL, 2),
        round(base * _ALIQ_COFINS_NAO_CUMUL, 2),
    )


def _creditos_a_partir_total_informado(total_creditos: float) -> tuple[float, float]:
    """Reparte um total de créditos informado entre PIS e COFINS na proporção das alíquotas."""
    total = max(0.0, float(total_creditos or 0))
    if total <= 0:
        return 0.0, 0.0
    pis_c = round(total * (_ALIQ_PIS_NAO_CUMUL / _SOMA_ALIQ_CREDITO), 2)
    cofins_c = round(total * (_ALIQ_COFINS_NAO_CUMUL / _SOMA_ALIQ_CREDITO), 2)
    return pis_c, cofins_c


def resolver_creditos_nao_cumulativo(
    dados: dict, regime: str
) -> tuple[float, float, Optional[str]]:
    """
    Prioridade: valor total manual (`creditos_pis_cofins`) > crédito calculado sobre insumos.
    Retorna (credito_pis, credito_cofins, fonte).
    """
    if regime == "presumido":
        return 0.0, 0.0, None

    manual = dados.get("creditos_pis_cofins")
    if manual is not None:
        try:
            m = max(0.0, float(manual))
        except (TypeError, ValueError):
            m = 0.0
        if m > 0:
            cp, cc = _creditos_a_partir_total_informado(m)
            return cp, cc, "manual"

    insumos = _parse_valor_nao_negativo(dados.get("insumos_tributados"))
    if insumos > 0:
        cp, cc = creditos_sobre_insumos_tributados(insumos)
        return cp, cc, "insumos_tributados"

    return 0.0, 0.0, None


class PISCOFINSEngine(BaseTaxEngine):
    """
    Calcula PIS e COFINS conforme regime tributário.
    """

    def execute(self, context: dict):
        """
        Calcula PIS e COFINS conforme regime tributário.
        """
        faturamento = context.get("faturamento", 0)
        regime = context.get("regime", "presumido")
        # Base de cálculo: faturamento líquido do ICMS (mesma lógica de bases_calculo.base_pis_cofins)
        base = context.get("base_pis_cofins")
        if base is None:
            icms = context.get("icms", 0)
            base = faturamento - icms

        if regime == "presumido":
            pis = base * 0.0065
            cofins = base * 0.03
        else:
            pis = base * _ALIQ_PIS_NAO_CUMUL
            cofins = base * _ALIQ_COFINS_NAO_CUMUL

        return {
            "tributo": "PIS_COFINS",
            "pis": pis,
            "cofins": cofins
        }


def calcular_pis_cofins(dados_fiscais: dict, regime="presumido"):
    """
    Função de compatibilidade para chamadores legados.
    Delega para PISCOFINSEngine e adapta o retorno ao formato anterior.

    Regime não-cumulativo: créditos sobre insumos tributados (`insumos_tributados`) ou total
    manual (`creditos_pis_cofins`), conforme Lei 10.637/2002 / 10.833/2003 — estimativa.
    """
    faturamento = dados_fiscais.get("faturamento", 0)
    icms = dados_fiscais.get("icms", 0)
    base_pis_cofins = faturamento - icms
    context = {
        "faturamento": faturamento,
        "icms": icms,
        "base_pis_cofins": base_pis_cofins,
        "regime": regime,
    }
    result = PISCOFINSEngine().execute(context)

    aliquota_pis = 0.0065 if regime == "presumido" else _ALIQ_PIS_NAO_CUMUL
    aliquota_cofins = 0.03 if regime == "presumido" else _ALIQ_COFINS_NAO_CUMUL

    base_com_icms = faturamento
    pis_com_icms = base_com_icms * aliquota_pis
    cofins_com_icms = base_com_icms * aliquota_cofins

    pis_sem_icms = result["pis"]
    cofins_sem_icms = result["cofins"]

    credito_pis_estimado = pis_com_icms - pis_sem_icms
    credito_cofins_estimado = cofins_com_icms - cofins_sem_icms
    credito_total_estimado = credito_pis_estimado + credito_cofins_estimado

    comparativo_icms_base = {
        "base_com_icms": base_com_icms,
        "base_sem_icms": base_pis_cofins,
        "pis_com_icms": pis_com_icms,
        "pis_sem_icms": pis_sem_icms,
        "cofins_com_icms": cofins_com_icms,
        "cofins_sem_icms": cofins_sem_icms,
        "credito_pis_estimado": credito_pis_estimado,
        "credito_cofins_estimado": credito_cofins_estimado,
        "credito_total_estimado": credito_total_estimado,
    }

    cred_pis, cred_cofins, fonte_cred = resolver_creditos_nao_cumulativo(
        dados_fiscais, regime
    )
    cred_total = round(cred_pis + cred_cofins, 2)
    pis_liq = max(0.0, round(pis_sem_icms - cred_pis, 2))
    cofins_liq = max(0.0, round(cofins_sem_icms - cred_cofins, 2))

    alertas = [
        "Apuração oficial depende da escrituração contábil.",
    ]
    if regime == "presumido":
        alertas.insert(
            0,
            "Valores estimados sem considerar créditos não-cumulativos (regime cumulativo).",
        )
    elif fonte_cred == "insumos_tributados":
        alertas.insert(
            0,
            "Créditos PIS/COFINS estimados sobre insumos tributados (hipótese típica art. 3º "
            "Lei 10.637/2002). Exclui bloqueios e ajustes da escrituração.",
        )
    elif fonte_cred == "manual":
        alertas.insert(
            0,
            "Créditos PIS/COFINS conforme total manual informado.",
        )
    else:
        alertas.insert(
            0,
            "Débitos PIS/COFINS na alíquota não-cumulativa; sem créditos calculados — "
            "informe insumos_tributados ou creditos_pis_cofins para estimar compensação.",
        )

    return {
        "tributos": {
            "pis": pis_sem_icms,
            "cofins": cofins_sem_icms,
        },
        "tributos_liquidos": {
            "pis": pis_liq,
            "cofins": cofins_liq,
        },
        "creditos": {
            "pis": cred_pis,
            "cofins": cred_cofins,
            "total": cred_total,
            "fonte": fonte_cred,
        },
        "bases_calculo": {
            "faturamento": faturamento,
            "icms_excluido": icms,
            "base_pis_cofins": base_pis_cofins,
            **(
                {"insumos_tributados": _parse_valor_nao_negativo(
                    dados_fiscais.get("insumos_tributados")
                )}
                if regime != "presumido"
                else {}
            ),
        },
        "comparativo_icms_base": comparativo_icms_base,
        "regime": regime,
        "alertas": alertas,
    }
