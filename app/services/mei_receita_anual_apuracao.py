"""Apurate supplied revenue evidence without certifying annual completeness.

Pure arithmetic boundary. Callers must authenticate, resolve the tenant, and
establish revenue identity/category/status before invoking this function.
No fiscal event resolution, normative conclusion or declaration submission.
"""
from collections.abc import Mapping
from datetime import date
from decimal import Decimal, localcontext
import re


_CATEGORIAS = ("comercio_industria", "servicos")
_ORIGENS = ("documento", "informada_sem_nota")
_CAMPOS = frozenset({"identidade_receita", "empresa_id", "data_receita",
                     "valor", "categoria", "origem", "estado"})
_VALOR = re.compile(r"(?:0|[1-9][0-9]{0,12})\.[0-9]{2}", re.ASCII)
_DATA = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", re.ASCII)


def _validar_receita(item):
    if not isinstance(item, Mapping) or set(item) != _CAMPOS:
        raise ValueError("RECEITA_CAMPOS_INVALIDOS")
    if type(item["empresa_id"]) is not int or item["empresa_id"] <= 0:
        raise ValueError("RECEITA_EMPRESA_INVALIDA")
    identidade = item["identidade_receita"]
    if (type(identidade) is not str or not identidade.strip()
            or identidade != identidade.strip() or len(identidade) > 255):
        raise ValueError("RECEITA_IDENTIDADE_INVALIDA")
    data = item["data_receita"]
    if type(data) is not str or not _DATA.fullmatch(data):
        raise ValueError("RECEITA_DATA_INVALIDA")
    try:
        parsed = date.fromisoformat(data)
    except ValueError:
        raise ValueError("RECEITA_DATA_INVALIDA") from None
    valor = item["valor"]
    if type(valor) is not str or not _VALOR.fullmatch(valor):
        raise ValueError("RECEITA_VALOR_INVALIDO")
    for campo, permitidos in (("categoria", _CATEGORIAS), ("origem", _ORIGENS),
                              ("estado", ("vigente", "pendente_revisao"))):
        if type(item[campo]) is not str or item[campo] not in permitidos:
            raise ValueError(f"RECEITA_{campo.upper()}_INVALIDO")
    return dict(item), parsed, Decimal(valor)


def apurar_receitas_anuais(*, empresa_id, ano_calendario, receitas):
    """Return partial totals in BRL over validated, explicitly supplied records.

    Empty months stay unknown. A zero aggregate means no included revenue,
    never a declaration of zero turnover. Repeated identity with different
    evidence blocks the result, including different dates/years. Unknown fiscal
    events must be submitted as pending review, not automatically deducted.
    """
    if type(empresa_id) is not int or empresa_id <= 0:
        raise ValueError("EMPRESA_INVALIDA")
    if type(ano_calendario) is not int or not 1900 <= ano_calendario <= 9999:
        raise ValueError("ANO_CALENDARIO_INVALIDO")
    if type(receitas) not in (list, tuple) or len(receitas) > 100000:
        raise ValueError("RECEITAS_INVALIDAS")

    incluidos, pendencias = [], []
    categorias = dict.fromkeys(_CATEGORIAS, Decimal("0.00"))
    origens = dict.fromkeys(_ORIGENS, Decimal("0.00"))
    mensais = [None] * 12
    vistos, duplicatas = {}, 0
    # Bound count/amount and use sufficient precision regardless of ambient
    # Decimal settings. Do not mutate the caller's context or input records.
    with localcontext() as contexto:
        contexto.prec = 32
        for entrada in receitas:
            item, data, valor = _validar_receita(entrada)
            if item["empresa_id"] != empresa_id:
                continue
            identidade = item["identidade_receita"]
            if identidade in vistos:
                if vistos[identidade] != item:
                    raise ValueError("RECEITA_IDENTIDADE_CONFLITANTE")
                if data.year == ano_calendario:
                    duplicatas += 1
                continue
            vistos[identidade] = item
            if data.year != ano_calendario:
                continue
            if item["estado"] == "pendente_revisao":
                pendencias.append(item)
                continue
            incluidos.append(item)
            categorias[item["categoria"]] += valor
            origens[item["origem"]] += valor
            indice = data.month - 1
            mensais[indice] = (mensais[indice] or Decimal("0.00")) + valor

        meses = [{"mes": indice + 1,
                  "estado": "nao_informado" if total is None else "parcial",
                  "total_receitas_incluidas": None if total is None else format(total, ".2f")}
                 for indice, total in enumerate(mensais)]
        return {
            "empresa_id": empresa_id,
            "ano_calendario": ano_calendario,
            "completude_anual_comprovada": False,
            "total_receitas_incluidas": format(sum(categorias.values(), Decimal("0.00")), ".2f"),
            "totais_por_categoria": {k: format(v, ".2f") for k, v in categorias.items()},
            "totais_por_origem": {k: format(v, ".2f") for k, v in origens.items()},
            "meses": meses,
            "receitas_incluidas": incluidos,
            "pendencias": pendencias,
            "duplicatas_ignoradas": duplicatas,
        }
