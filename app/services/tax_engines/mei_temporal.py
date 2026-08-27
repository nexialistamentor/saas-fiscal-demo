"""Resolucao temporal estrita para fatos normativos MEI."""

from __future__ import annotations

from datetime import date, datetime
from typing import Mapping

from app.services.tax_engines.base_tax_engine import (
    TempoNormativoAusenteError,
)


class TempoNormativoMEIAmbiguoError(TempoNormativoAusenteError):
    """O ano nao identifica uma unica vigencia normativa MEI."""


class TempoNormativoMEIInvalidoError(ValueError):
    """O contexto temporal MEI e contraditorio ou malformado."""


def _data_iso_exata(value: object, *, campo: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise TempoNormativoMEIInvalidoError(
            f"{campo} deve ser data ISO YYYY-MM-DD"
        )
    if len(value) != 10 or value[4] != "-" or value[7] != "-":
        raise TempoNormativoMEIInvalidoError(
            f"{campo} deve ser data ISO YYYY-MM-DD"
        )
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise TempoNormativoMEIInvalidoError(
            f"{campo} deve ser data ISO valida"
        ) from exc
    if parsed.isoformat() != value:
        raise TempoNormativoMEIInvalidoError(
            f"{campo} deve usar representacao ISO canonica"
        )
    return parsed


def _ano_exato(value: object, *, campo: str) -> int:
    if isinstance(value, bool):
        raise TempoNormativoMEIInvalidoError(f"{campo} invalido")
    if isinstance(value, int):
        ano = value
    elif isinstance(value, str) and len(value) == 4 and value.isascii() and value.isdigit():
        ano = int(value)
    else:
        raise TempoNormativoMEIInvalidoError(f"{campo} deve ser ano YYYY")
    if ano < 1900 or ano > 9999:
        raise TempoNormativoMEIInvalidoError(f"{campo} fora do dominio")
    return ano


def resolver_data_referencia_mei(context: Mapping[str, object]) -> date:
    """Preserva data exata e bloqueia anos com mais de uma vigencia conhecida."""
    if not isinstance(context, Mapping) or not context:
        raise TempoNormativoAusenteError(
            "Calculo MEI bloqueado: data ou ano normativo ausente."
        )

    datas = [
        _data_iso_exata(context[campo], campo=campo)
        for campo in ("data_referencia", "data_emissao")
        if context.get(campo) is not None
    ]
    anos = [
        _ano_exato(context[campo], campo=campo)
        for campo in ("ano_referencia", "ano_calendario")
        if context.get(campo) is not None
    ]

    if len(set(datas)) > 1 or len(set(anos)) > 1:
        raise TempoNormativoMEIInvalidoError(
            "contexto temporal MEI contraditorio"
        )

    if datas:
        data_referencia = datas[0]
        if anos and anos[0] != data_referencia.year:
            raise TempoNormativoMEIInvalidoError(
                "ano e data de referencia MEI divergem"
            )
        return data_referencia

    if not anos:
        raise TempoNormativoAusenteError(
            "Calculo MEI bloqueado: data ou ano normativo ausente."
        )

    ano = anos[0]
    if ano == 2023:
        raise TempoNormativoMEIAmbiguoError(
            "MEI 2023 exige data_referencia exata: houve mais de uma vigencia de salario minimo no ano."
        )

    return date(ano, 1, 1)
