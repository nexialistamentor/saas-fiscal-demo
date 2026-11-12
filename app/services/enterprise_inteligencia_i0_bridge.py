"""Ligacao interna, sem novos calculos, de capturas de inteligencia ao I0.

Consome apenas resultados JA persistidos/selados pelo escritor. O chamador
deve verificar o fingerprint do RelatorioAnalise antes de passar o payload.
Nao altera _CAPACIDADES, G12-G17, nem concede autoridade ou checkout.
"""
from __future__ import annotations

from copy import deepcopy
from math import isfinite

_IDS = (
    "score_tributario", "maturidade", "ranking_restituicao",
    "ranking_estrategico", "impacto_financeiro",
)
_CHAVES_LISTA = {
    "ranking_restituicao": ("restituicao_estimada",),
    "ranking_estrategico": ("score", "potencial", "creditos", "distorcao"),
    "impacto_financeiro": ("impacto_anual_estimado", "prioridade_fiscal"),
}


def _numero(v):
    return type(v) in (int, float) and isfinite(v)


def _valido(nome, valor):
    if nome == "score_tributario":
        return (type(valor) is dict
                and _numero(valor.get("score_global_tributario"))
                and type(valor.get("nivel_empresa")) is str
                and bool(valor["nivel_empresa"]))
    if nome == "maturidade":
        return (type(valor) is dict
                and _numero(valor.get("score_maturidade_tributaria"))
                and type(valor.get("nivel_maturidade")) is str
                and bool(valor["nivel_maturidade"]))
    if type(valor) is not list:
        return False
    campos = _CHAVES_LISTA[nome]
    return all(
        type(row) is dict
        and type(row.get("ncm")) is str and bool(row["ncm"])
        and all(_numero(row.get(k)) for k in campos)
        for row in valor
    )


def fundir_inteligencia_i0(*, i0: dict, resultado: dict, empresa_id: int,
                          relatorio_id: int, xml_sha256: str) -> dict:
    """Funde somente cinco produtores capturados; ausentes seguem pendentes.

    Identidade ancorada no vínculo documental do snapshot persistido,
    não em dict solto de origem HTTP. Quarentena integral dos números.
    """
    if (type(empresa_id) is not int or empresa_id <= 0
            or type(relatorio_id) is not int or relatorio_id <= 0
            or type(xml_sha256) is not str or len(xml_sha256) != 64):
        raise ValueError("INTELIGENCIA_ARGUMENTOS_INVALIDOS")
    if (type(i0) is not dict or i0.get("empresa_id") != empresa_id
            or i0.get("uso") != "INTERNO_NAO_PUBLICAVEL"
            or i0.get("checkout_autorizado") is not False
            or i0.get("diagnostico_empresarial_completo") is not False
            or i0.get("comprovacao_normativa") is not False
            or type(i0.get("cobertura")) is not list
            or len(i0["cobertura"]) != 52):
        raise ValueError("INTELIGENCIA_I0_INVALIDO")
    if type(resultado) is not dict or resultado.get("empresa_id") != empresa_id:
        raise ValueError("INTELIGENCIA_RESULTADO_OUTRA_EMPRESA")
    prova = resultado.get("_enterprise_xml_evidence")
    if (type(prova) is not dict
            or prova.get("schema_version") != "ENTERPRISE_XML_EVIDENCE_V1"
            or prova.get("empresa_id") != empresa_id
            or prova.get("relatorio_id") != relatorio_id
            or prova.get("xml_sha256") != xml_sha256):
        raise ValueError("INTELIGENCIA_XML_RELATORIO_NAO_VINCULADOS")

    saida = deepcopy(i0)
    capturas = resultado.get("inteligencia_capturas")
    if capturas is None:
        return saida  # snapshots antigos, sem fabricar cobertura
    if (type(capturas) is not dict
            or capturas.get("empresa_id") != empresa_id
            or capturas.get("relatorio_id") != relatorio_id
            or type(capturas.get("dados")) is not dict):
        raise ValueError("INTELIGENCIA_CAPTURAS_IDENTIDADE_OU_TIPO_INVALIDOS")
    itens = {entry.get("id"): entry for entry in saida["cobertura"]}
    if len(itens) != 52:
        raise ValueError("INTELIGENCIA_CATALOGO_DUPLICADO")
    for nome in _IDS:
        if nome not in capturas["dados"]:
            continue
        item = itens.get(nome)
        if (type(item) is not dict or item.get("grupo") != "inteligencia"
                or item.get("estado") != "nao_integrado_ao_snapshot"):
            raise ValueError("INTELIGENCIA_ALVO_NAO_PENDENTE")
        bruto = capturas["dados"][nome]
        item["autoridade_fiscal"] = False
        if not _valido(nome, bruto):
            item.update(estado="falha_motor", causa="CAPTURA_PRODUTOR_INVALIDA",
                        resultado_bruto_nao_validado=None)
        elif type(bruto) is list and not bruto:
            item.update(estado="nao_apurado", causa="PRODUTOR_EXECUTADO_SEM_RESULTADOS",
                        resultado_bruto_nao_validado=None)
        else:
            item.update(estado="informativo_sem_prova",
                        causa="INTELIGENCIA_INTERNA_SEM_PROVA_FISCAL",
                        resultado_bruto_nao_validado=deepcopy(bruto))
    return saida
