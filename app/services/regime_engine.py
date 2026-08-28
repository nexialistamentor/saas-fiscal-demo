"""
Motor de regime tributário soberano V1.

Responsabilidade: dado perfil financeiro + CNAE, calcular e comparar
tributos por regime e recomendar o mais vantajoso.

Regimes suportados:
    MEI       — DAS fixo mensal (limite R$ 81.000/ano)
    Simples   — DAS por anexo (I-V) com Fator R para III vs V
    LP        — Lucro Presumido (delega lucro_presumido_engine)
    LR        — Lucro Real (delega lucro_real_engine)

Fator R (Simples):
    fator_r = folha_12_meses / faturamento_12_meses
    >= 0.28 → Anexo III (menor alíquota)
    <  0.28 → Anexo V (maior alíquota)

AVISO ARQUITECTURAL V1:
    Comparação tributos usa estimativas anualizadas.
    V2: projecção mensal com sazonalidade + benefícios fiscais regionais.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from app.services.imposto_service import calcular_imposto_simples_nacional
from app.services.tax_engines.base_tax_engine import BaseTaxEngine, TempoNormativoAusenteError
from app.services.tax_engines.mei_constants import MEI_LIMITE_ANUAL_FATURAMENTO
from app.services.tax_engines.mei_tax_engine import (
    AutoridadeFiscalIndisponivelError,
    AutoridadeNormativaMEIIndisponivelError,
    MEITaxEngine,
)

_resolver_temporal = BaseTaxEngine()

LIMITE_SIMPLES_ANUAL = Decimal("4800000.00")

# Mapeamento CNAE secção → Anexo Simples Nacional
# Fonte: Lei Complementar 123/2006 + atualizações
_SECAO_PARA_ANEXO: dict[str, str] = {
    "A": "III",   # Agricultura
    "B": "III",   # Indústria extrativa
    "C": "II",    # Indústria de transformação
    "D": "III",   # Electricidade/gás
    "E": "III",   # Saneamento
    "F": "IV",    # Construção
    "G": "I",     # Comércio
    "H": "III",   # Transporte
    "I": "I",     # Alojamento/alimentação
    "J": "III",   # TI/Comunicação (Fator R decide III vs V)
    "K": "V",     # Financeiro — verificar elegibilidade
    "L": "III",   # Imobiliário
    "M": "V",     # Profissionais/científicos (Fator R decide III vs V)
    "N": "III",   # Administrativo
    "O": "IV",    # Administração pública
    "P": "IV",    # Educação
    "Q": "IV",    # Saúde
    "R": "III",   # Arte/cultura
    "S": "III",   # Outros serviços
    "T": "III",   # Doméstico
    "U": "III",   # Organismos internacionais
}

# Secções onde Fator R decide Anexo III vs V
_SECOES_FATOR_R = {"J", "M", "S"}


@dataclass
class ResultadoRegime:
    regime: str
    carga_anual: Decimal
    carga_mensal: Decimal
    aliquota_efetiva_pct: float
    anexo_simples: Optional[str]
    fator_r: Optional[float]
    alertas: list[str]
    detalhes: dict


@dataclass
class ResultadoComparacao:
    regime_recomendado: str
    economia_anual_vs_pior: Decimal
    resultados: dict[str, ResultadoRegime]
    justificativa: list[str]
    regimes_inelegiveis: dict[str, str]  # regime → motivo
    regimes_nao_avaliados: dict[str, dict[str, str]] = field(default_factory=dict)


def _resolver_ano_referencia(ano_referencia: Optional[int]) -> int:
    """Resolve ano normativo via BaseTaxEngine — bloqueia se ausente."""
    ctx: dict = {}
    if ano_referencia is not None:
        ctx["ano_referencia"] = ano_referencia
    return _resolver_temporal.resolver_ano_referencia(ctx)


def _calcular_fator_r(folha_anual: Decimal, faturamento_anual: Decimal) -> Optional[float]:
    if not faturamento_anual or faturamento_anual <= 0:
        return None
    return round(float(folha_anual / faturamento_anual), 4)


def _anexo_por_secao_e_fator_r(secao: str, fator_r: Optional[float]) -> str:
    """Determina anexo Simples considerando Fator R para secções elegíveis."""
    anexo_base = _SECAO_PARA_ANEXO.get(secao, "III")
    if secao in _SECOES_FATOR_R and fator_r is not None:
        return "III" if fator_r >= 0.28 else "V"
    return anexo_base


def calcular_simples(
    faturamento_anual: Decimal,
    folha_anual: Decimal,
    secao_cnae: str,
    ano_referencia: int,
) -> ResultadoRegime:
    """Calcula carga Simples Nacional com Fator R."""
    fator_r = _calcular_fator_r(folha_anual, faturamento_anual)
    anexo = _anexo_por_secao_e_fator_r(secao_cnae, fator_r)

    rbt12 = float(faturamento_anual)
    resultado = calcular_imposto_simples_nacional(
        rbt12=rbt12,
        receita_mes=rbt12 / 12,
        anexo=anexo,
        ano_referencia=ano_referencia,
    )

    alertas = list(resultado.get("alertas", []))
    if fator_r is not None:
        alertas.append(
            f"Fator R: {fator_r:.2%} → Anexo {anexo} "
            f"({'≥28% folha/faturamento' if fator_r >= 0.28 else '<28% folha/faturamento'})"
        )

    return ResultadoRegime(
        regime="simples",
        carga_anual=Decimal(str(resultado["das_anual"])),
        carga_mensal=Decimal(str(resultado["das_mensal"])),
        aliquota_efetiva_pct=resultado["aliquota_efetiva_pct"],
        anexo_simples=anexo,
        fator_r=fator_r,
        alertas=alertas,
        detalhes=resultado,
    )


def calcular_lp(
    faturamento_anual: Decimal,
    atividade: str = "servicos",
    ano_referencia: Optional[int] = None,
) -> ResultadoRegime:
    """Calcula carga Lucro Presumido delegando ao engine existente."""
    from app.services.tax_engines.lucro_presumido_engine import calcular_lucro_presumido

    dados_fiscais = {
        "faturamento": float(faturamento_anual),
        "receita_bruta": float(faturamento_anual),
        "atividade": atividade,
        "ano_referencia": ano_referencia,
    }
    resultado = calcular_lucro_presumido(dados_fiscais)
    data = resultado.get("data") or {}
    tributos = data.get("tributos", {})
    total_anual = Decimal(str(sum(tributos.values())))

    return ResultadoRegime(
        regime="lp",
        carga_anual=total_anual,
        carga_mensal=total_anual / 12,
        aliquota_efetiva_pct=round(float(total_anual / faturamento_anual * 100), 2) if faturamento_anual else 0,
        anexo_simples=None,
        fator_r=None,
        alertas=list(data.get("alertas", [])),
        detalhes=resultado,
    )


def calcular_lr(
    faturamento_anual: Decimal,
    lucro_contabil: Decimal,
    atividade: str = "servicos",
    ano_referencia: Optional[int] = None,
) -> ResultadoRegime:
    """Calcula carga Lucro Real delegando ao engine existente."""
    from app.services.tax_engines.lucro_real_engine import calcular_lucro_real

    dados_fiscais = {
        "faturamento": float(faturamento_anual),
        "receita_bruta": float(faturamento_anual),
        "lucro_contabil": float(lucro_contabil),
        "atividade": atividade,
        "ano_referencia": ano_referencia,
    }
    resultado = calcular_lucro_real(dados_fiscais)
    data = resultado.get("data") or {}
    tributos = data.get("tributos", {})
    total_anual = Decimal(str(sum(tributos.values())))

    return ResultadoRegime(
        regime="lr",
        carga_anual=total_anual,
        carga_mensal=total_anual / 12,
        aliquota_efetiva_pct=round(float(total_anual / faturamento_anual * 100), 2) if faturamento_anual else 0,
        anexo_simples=None,
        fator_r=None,
        alertas=list(data.get("alertas", [])),
        detalhes=resultado,
    )


def comparar_regimes(
    faturamento_anual: Decimal,
    folha_anual: Decimal = Decimal("0"),
    lucro_contabil: Optional[Decimal] = None,
    secao_cnae: str = "J",
    atividade: Optional[str] = None,
    regimes_permitidos: Optional[list[str]] = None,
    ano_referencia: Optional[int] = None,
) -> ResultadoComparacao:
    """
    Compara regimes tributários e recomenda o mais vantajoso.

    Args:
        faturamento_anual: faturamento dos últimos 12 meses
        folha_anual: folha de pagamento anual (para Fator R)
        lucro_contabil: lucro contábil anual (necessário para LR)
        secao_cnae: secção CNAE da empresa (para Anexo Simples)
        atividade: tipo de atividade para LP/LR
        regimes_permitidos: lista de regimes a comparar (None = todos elegíveis)
        ano_referencia: ano normativo para DAS MEI e tributos LP/LR
    """
    if ano_referencia is None:
        raise TempoNormativoAusenteError(
            "comparar_regimes() requer ano_referencia explícito. "
            "Bloqueado por B13-OPS-13A."
        )

    resultados: dict[str, ResultadoRegime] = {}
    inelegiveis: dict[str, str] = {}
    nao_avaliados: dict[str, dict[str, str]] = {}
    justificativa = []

    # Determinar elegibilidade
    if regimes_permitidos is None:
        regimes_permitidos = ["simples", "lp", "lr"]

    # MEI — limite de faturamento
    if "mei" in regimes_permitidos:
        _limite_mei = Decimal(str(MEI_LIMITE_ANUAL_FATURAMENTO))
        if faturamento_anual > _limite_mei:
            inelegiveis["mei"] = (
                f"Faturamento R$ {faturamento_anual:,.2f} excede limite MEI de "
                f"R$ {_limite_mei:,.2f}"
            )
        else:
            try:
                _resultado_mei = MEITaxEngine().execute(
                    {
                        "modo": "estimativa",
                        "faturamento": faturamento_anual / Decimal("12"),
                        "faturamento_anual": faturamento_anual,
                        "atividade": atividade,
                        "ano_referencia": ano_referencia,
                    }
                )
            except (
                AutoridadeFiscalIndisponivelError,
                AutoridadeNormativaMEIIndisponivelError,
            ) as exc:
                nao_avaliados["mei"] = {
                    "estado": "autoridade_indisponivel",
                    "codigo": exc.codigo,
                    "motivo": exc.motivo,
                }
            else:
                _das_mensal = Decimal(str(_resultado_mei["tributos"]["das"]))
                _das_anual = _das_mensal * Decimal("12")
                resultados["mei"] = ResultadoRegime(
                    regime="mei",
                    carga_anual=_das_anual,
                    carga_mensal=_das_mensal,
                    aliquota_efetiva_pct=round(
                        float(_das_anual / faturamento_anual * 100), 2
                    )
                    if faturamento_anual
                    else 0,
                    anexo_simples=None,
                    fator_r=None,
                    alertas=list(_resultado_mei.get("alertas", [])),
                    detalhes=_resultado_mei,
                )

    # Simples Nacional — limite de faturamento
    if "simples" in regimes_permitidos:
        if faturamento_anual > LIMITE_SIMPLES_ANUAL:
            inelegiveis["simples"] = (
                f"Faturamento excede limite Simples de R$ {LIMITE_SIMPLES_ANUAL:,.2f}"
            )
        else:
            try:
                resultados["simples"] = calcular_simples(
                    faturamento_anual, folha_anual, secao_cnae, ano_referencia
                )
            except TempoNormativoAusenteError:
                raise
            except Exception as e:
                inelegiveis["simples"] = f"Erro no cálculo: {e}"

    # Lucro Presumido
    if "lp" in regimes_permitidos:
        try:
            resultados["lp"] = calcular_lp(faturamento_anual, atividade, ano_referencia)
        except TempoNormativoAusenteError:
            raise
        except Exception as e:
            inelegiveis["lp"] = f"Erro no cálculo: {e}"

    # Lucro Real
    if "lr" in regimes_permitidos:
        if lucro_contabil is None:
            inelegiveis["lr"] = "Lucro contábil não informado — necessário para Lucro Real"
        else:
            try:
                resultados["lr"] = calcular_lr(
                    faturamento_anual, lucro_contabil, atividade, ano_referencia
                )
            except TempoNormativoAusenteError:
                raise
            except Exception as e:
                inelegiveis["lr"] = f"Erro no cálculo: {e}"

    if not resultados:
        justificativa_sem_resultados = (
            ["Nenhum regime pôde ser avaliado com a autoridade disponível"]
            if nao_avaliados
            else ["Nenhum regime elegível para os dados fornecidos"]
        )
        return ResultadoComparacao(
            regime_recomendado="indefinido",
            economia_anual_vs_pior=Decimal("0"),
            resultados={},
            justificativa=justificativa_sem_resultados,
            regimes_inelegiveis=inelegiveis,
            regimes_nao_avaliados=nao_avaliados,
        )

    # Ordenar por carga anual
    ordenados = sorted(resultados.items(), key=lambda x: x[1].carga_anual)
    regime_melhor = ordenados[0][0]
    regime_pior = ordenados[-1][0]
    economia = resultados[regime_pior].carga_anual - resultados[regime_melhor].carga_anual

    justificativa.append(
        f"Regime recomendado: {regime_melhor.upper()} — menor carga tributária anual"
    )
    justificativa.append(f"Economia vs pior opção ({regime_pior.upper()}): R$ {economia:,.2f}/ano")

    if "simples" in resultados:
        r = resultados["simples"]
        justificativa.append(
            f"Simples Anexo {r.anexo_simples} — alíquota efectiva {r.aliquota_efetiva_pct}%"
        )
        if r.fator_r is not None:
            justificativa.append(f"Fator R: {r.fator_r:.2%}")

    return ResultadoComparacao(
        regime_recomendado=regime_melhor,
        economia_anual_vs_pior=economia,
        resultados=resultados,
        justificativa=justificativa,
        regimes_inelegiveis=inelegiveis,
        regimes_nao_avaliados=nao_avaliados,
    )
