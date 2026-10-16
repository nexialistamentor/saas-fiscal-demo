"""P1-02C — adaptador efemero de valor de NF-e para politica informativa.

Nao altera XML, resultado persistido, fingerprints, flags, gating P1-02A,
checkout, oferta ou pagamentos. Somente o futuro chamador com provenance,
status e ownership verificados podera consumir a copia normalizada.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
import math
import re

# Limite defensivo local de 13 digitos inteiros e duas casas decimais.
# Rejeita notacao cientifica, separadores locais e arredondamento implicito.
_XML_VALOR = re.compile(r"[0-9]{1,13}(?:\.[0-9]{1,2})?\Z")
_MAXIMO = Decimal("9999999999999.99")
_CENTAVO = Decimal("0.01")


def _valor_estrito(valor: object) -> float | None:
    if type(valor) is str:
        if _XML_VALOR.fullmatch(valor) is None:
            return None
        texto = valor
    elif type(valor) is int:
        if valor < 0:
            return None
        texto = str(valor)
    elif type(valor) is float:
        if not math.isfinite(valor):
            return None
        texto = str(valor)
    else:
        return None
    try:
        decimal = Decimal(texto)
    except (InvalidOperation, ValueError):
        return None
    if (not decimal.is_finite() or decimal < 0 or decimal > _MAXIMO or
            decimal != decimal.quantize(_CENTAVO)):
        return None
    resultado = float(decimal)
    return resultado if math.isfinite(resultado) else None


def normalizar_valor_nfe_para_politica(resultado: object) -> dict | None:
    """Cria copia profunda com SOMENTE valor_total_nota convertido a float.

    Falha fechada para valor ausente, ambiguo, negativo, infinito, demasiado
    grande ou com mais de dois centavos. Nao reduz escopo de nenhuma flag.
    """
    if type(resultado) is not dict:
        return None
    documento = resultado.get("dados_fiscais")
    if type(documento) is not dict:
        return None
    valor = _valor_estrito(documento.get("valor_total_nota"))
    if valor is None:
        return None
    copia = deepcopy(resultado)
    copia["dados_fiscais"]["valor_total_nota"] = valor
    return copia
