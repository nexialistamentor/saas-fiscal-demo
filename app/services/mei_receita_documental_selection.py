"""Select persisted fiscal metadata for review, never as confirmed revenue.

No database or authentication here. The reader must resolve ownership first.
DocumentoFiscal does not establish issuer, operation nature or fiscal status;
this service deliberately preserves those missing facts as review reasons.
"""
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
import math
import re


_CAMPOS = frozenset({"id", "empresa_id", "data_emissao", "tipo", "valor_total",
                     "chave_nfe", "conteudo_sha256"})
_MOTIVOS = ("EMITENTE_NAO_COMPROVADO", "NATUREZA_OPERACAO_NAO_COMPROVADA",
            "ESTADO_FISCAL_NAO_COMPROVADO")
_DATA = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", re.ASCII)
_CHAVE = re.compile(r"[0-9]{44}", re.ASCII)
_HASH = re.compile(r"[0-9a-f]{64}", re.ASCII)


def _validar(item):
    if not isinstance(item, Mapping) or set(item) != _CAMPOS:
        raise ValueError("DOCUMENTO_CAMPOS_INVALIDOS")
    for campo in ("id", "empresa_id"):
        if type(item[campo]) is not int or item[campo] <= 0:
            raise ValueError("DOCUMENTO_IDENTIFICADOR_INVALIDO")
    data = item["data_emissao"]
    if data is not None:
        if type(data) is not str or not _DATA.fullmatch(data):
            raise ValueError("DOCUMENTO_DATA_INVALIDA")
        try:
            data = date.fromisoformat(data)
        except ValueError:
            raise ValueError("DOCUMENTO_DATA_INVALIDA") from None
    tipo = item["tipo"]
    if tipo is not None and (type(tipo) is not str or tipo not in ("entrada", "saida")):
        raise ValueError("DOCUMENTO_TIPO_INVALIDO")
    valor = item["valor_total"]
    if valor is not None:
        if (type(valor) not in (int, float) or
                (type(valor) is float and not math.isfinite(valor)) or
                valor < 0 or valor > 9999999999999.99):
            raise ValueError("DOCUMENTO_VALOR_INVALIDO")
        # Float metadata is retained as an observation, never converted into a
        # rounded authoritative revenue amount. Precision needs source review.
        if Decimal(str(valor)).as_tuple().exponent < -2:
            raise ValueError("DOCUMENTO_PRECISAO_INVALIDA")
    for campo, padrao in (("chave_nfe", _CHAVE), ("conteudo_sha256", _HASH)):
        valor_campo = item[campo]
        if valor_campo is not None and (type(valor_campo) is not str
                                       or not padrao.fullmatch(valor_campo)):
            raise ValueError("DOCUMENTO_REFERENCIA_INVALIDA")
    return dict(item), data


def selecionar_documentos_para_conferencia(*, empresa_id, ano_calendario, documentos):
    """Inventory within the requested scope; missing dates remain unresolved.

    Validation errors block the inventory instead of producing a success with
    silently dropped malformed records. Filtering is defense in depth, not
    a substitute for tenant authorization in the database reader/HTTP route.
    """
    if type(empresa_id) is not int or empresa_id <= 0:
        raise ValueError("EMPRESA_INVALIDA")
    if type(ano_calendario) is not int or not 1900 <= ano_calendario <= 9999:
        raise ValueError("ANO_CALENDARIO_INVALIDO")
    if type(documentos) not in (list, tuple) or len(documentos) > 100000:
        raise ValueError("DOCUMENTOS_INVALIDOS")
    revisao, sem_periodo, vistos = [], [], {}
    duplicatas = 0
    for entrada in documentos:
        item, data = _validar(entrada)
        if item["empresa_id"] != empresa_id:
            continue
        identidade = item["id"]
        if identidade in vistos:
            if vistos[identidade] != item:
                raise ValueError("DOCUMENTO_IDENTIDADE_CONFLITANTE")
            if data is None or data.year == ano_calendario:
                duplicatas += 1
            continue
        vistos[identidade] = item
        if data is not None and data.year != ano_calendario:
            continue
        motivos = list(_MOTIVOS)
        for campo, motivo in (("data_emissao", "PERIODO_NAO_COMPROVADO"),
                              ("tipo", "TIPO_DOCUMENTAL_AUSENTE"),
                              ("valor_total", "VALOR_DOCUMENTAL_AUSENTE")):
            if item[campo] is None:
                motivos.append(motivo)
        if item["chave_nfe"] is None and item["conteudo_sha256"] is None:
            motivos.append("REFERENCIA_DOCUMENTAL_AUSENTE")
        registro = {"documento_id": identidade, "metadados": item,
                    "categoria_receita": None, "motivos": motivos}
        (sem_periodo if data is None else revisao).append(registro)
    return {"empresa_id": empresa_id, "ano_calendario": ano_calendario,
            "documentos_para_revisao": revisao, "documentos_sem_periodo": sem_periodo,
            "receitas_confirmadas": [], "total_receita_confirmada": None,
            "completude_anual_comprovada": False, "duplicatas_ignoradas": duplicatas}
