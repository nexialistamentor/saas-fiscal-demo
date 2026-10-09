"""Composicao consultiva MEI: apresenta evidencias sem certificar receita fiscal.

Sem acesso ao banco, provedores, motor DAS ou motores de outros regimes.
"""
from collections.abc import Mapping
from copy import deepcopy
import re


class MeiComposicaoConsultivaError(ValueError):
    """Entrada consultiva inconsistente ou sem autoridade suficiente."""


def _validar_fonte(fonte, *, empresa_id, ano_calendario):
    if not isinstance(fonte, Mapping):
        raise MeiComposicaoConsultivaError("FONTE_INVALIDA")
    if (
        type(fonte.get("empresa_id")) is not int
        or fonte["empresa_id"] != empresa_id
        or type(fonte.get("ano_calendario")) is not int
        or fonte["ano_calendario"] != ano_calendario
        or fonte.get("completude_anual_comprovada") is not False
    ):
        raise MeiComposicaoConsultivaError("ESCOPO_OU_AUTORIDADE_INVALIDA")


def compor_receitas_mei(*, empresa_id, ano_calendario, apuracao, selecao_documental):
    """Compoe duas observacoes ja autorizadas, sem produzir total fiscal novo."""
    if type(empresa_id) is not int or empresa_id <= 0:
        raise MeiComposicaoConsultivaError("EMPRESA_INVALIDA")
    if type(ano_calendario) is not int or not 1900 <= ano_calendario <= 9999:
        raise MeiComposicaoConsultivaError("ANO_INVALIDO")

    _validar_fonte(apuracao, empresa_id=empresa_id, ano_calendario=ano_calendario)
    _validar_fonte(
        selecao_documental, empresa_id=empresa_id, ano_calendario=ano_calendario
    )

    total = apuracao.get("total_receitas_incluidas")
    if (
        type(total) is not str
        or re.fullmatch(r"(?:0|[1-9][0-9]{0,12})\.[0-9]{2}", total, re.ASCII) is None
    ):
        raise MeiComposicaoConsultivaError("TOTAL_INFORMADO_INVALIDO")

    if selecao_documental.get("receitas_confirmadas") != []:
        raise MeiComposicaoConsultivaError("CONFIRMACAO_DOCUMENTAL_NAO_AUTORIZADA")
    if selecao_documental.get("total_receita_confirmada") is not None:
        raise MeiComposicaoConsultivaError("TOTAL_DOCUMENTAL_NAO_AUTORIZADO")

    campos_listas = (
        (apuracao, "pendencias"),
        (selecao_documental, "documentos_para_revisao"),
        (selecao_documental, "documentos_sem_periodo"),
    )
    for fonte, campo in campos_listas:
        if type(fonte.get(campo)) is not list or len(fonte[campo]) > 100000:
            raise MeiComposicaoConsultivaError("LISTA_INVALIDA")

    # Observacoes documentais nunca sao aceites sem estrutura minima.
    for campo in ("documentos_para_revisao", "documentos_sem_periodo"):
        for documento in selecao_documental[campo]:
            if not isinstance(documento, Mapping):
                raise MeiComposicaoConsultivaError("DOCUMENTO_INVALIDO")
            if (
                type(documento.get("documento_id")) is not int
                or documento["documento_id"] <= 0
            ):
                raise MeiComposicaoConsultivaError("DOCUMENTO_IDENTIDADE_INVALIDA")
            motivos = documento.get("motivos")
            if (
                type(motivos) is not list
                or any(type(motivo) is not str or not motivo for motivo in motivos)
            ):
                raise MeiComposicaoConsultivaError("DOCUMENTO_MOTIVOS_INVALIDOS")
    return {
        "empresa_id": empresa_id,
        "ano_calendario": ano_calendario,
        "total_receitas_informadas": total,
        "documentos_para_conferencia": deepcopy(
            selecao_documental["documentos_para_revisao"]
        ),
        "documentos_sem_periodo": deepcopy(
            selecao_documental["documentos_sem_periodo"]
        ),
        "pendencias_receitas": deepcopy(apuracao["pendencias"]),
        "total_consolidado_comprovado": None,
        "completude_anual_comprovada": False,
    }