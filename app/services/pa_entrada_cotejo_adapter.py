"""Adaptador investigativo por item PA/22021000; nunca autoriza calculo.

Sem ligacao a rotas, escritores, motores fiscais ou contratos G12-G17.
As dimensoes sao recebidas explicitamente; a origem delas nao e inferida
nem autenticada por este adaptador.
"""
from __future__ import annotations

from datetime import date

from app.services.pa_entrada_ruleversion_service import cotejar_candidato_pa_entrada


_CANDIDATO = "CANDIDATO_CONDICIONAL_COTEJADO_SEM_AUTORIDADE"


def cotejar_item_pa_entrada(*, db, indice_item: int,
        uf_operacao: str | None, ncm: str | None, cest: str | None,
        categoria_remetente: str | None, tipo_operacao: str | None,
        data_referencia: date | None,
        rule_version_record_id: str | None) -> dict:
    """Orquestra um cotejo read-only isolado, sem procurar ou deduzir fontes.

    Escopo ratificado: PA, 22021000, CEST 0301001, remetente distribuidor.
    Uma coincidencia documental nao demonstra aplicabilidade juridica.
    """
    saida = {
        "indice_item": (indice_item if type(indice_item) is int
                        and 1 <= indice_item <= 500 else None),
        "estado": "ABSTENCAO",
        "motivo": "DADOS_CONDICIONAIS_NAO_COMPROVADOS",
        "rule_version_record_id": None,
        "vinculos_declarados_cotejados": False,
        "autoridade_normativa_verificada": False,
        "calculo_autorizado": False,
        "norma_resolvida": None,
    }
    if (type(indice_item) is not int or not 1 <= indice_item <= 500
        or type(uf_operacao) is not str or uf_operacao != "PA"
        or type(ncm) is not str or ncm != "22021000"
        or type(cest) is not str or cest != "0301001"
        or type(categoria_remetente) is not str
        or categoria_remetente != "distribuidor_deposito_atacadista"
        or type(tipo_operacao) is not str
        or tipo_operacao != "antecipacao_na_entrada"
        or type(data_referencia) is not date
        or type(rule_version_record_id) is not str
        or not 1 <= len(rule_version_record_id) <= 64
        or rule_version_record_id.strip() != rule_version_record_id
        or db is None or not callable(getattr(db, "get", None))
        or getattr(db, "no_autoflush", None) is None):
        return saida

    try:
        cotejo = cotejar_candidato_pa_entrada(
            db=db, rule_version_record_id=rule_version_record_id,
            uf_operacao=uf_operacao, ncm=ncm, cest=cest,
            categoria_remetente=categoria_remetente,
            tipo_operacao=tipo_operacao, data_referencia=data_referencia,
        )
    except Exception:
        return dict(saida, motivo="COTEJO_ADR020_INDISPONIVEL")

    if (type(cotejo) is not dict
        or cotejo.get("autoridade_normativa_verificada") is not False
        or cotejo.get("calculo_autorizado") is not False
        or cotejo.get("norma_resolvida") is not None
        or any(k in cotejo for k in
               ("mva", "aliquota", "mva_percentual", "aliquota_interna_percentual"))):
        return dict(saida, motivo="CONTRATO_COTEJO_INCOMPATIVEL")

    if cotejo.get("estado") == _CANDIDATO:
        if (cotejo.get("vinculos_declarados_cotejados") is not True
            or cotejo.get("rule_version_record_id") != rule_version_record_id):
            return dict(saida, motivo="CONTRATO_COTEJO_INCOMPATIVEL")
        return dict(
            saida, estado=_CANDIDATO,
            motivo="DOCUMENTO_INTERNO_COTEJADO_SEM_AUTORIDADE",
            rule_version_record_id=rule_version_record_id,
            vinculos_declarados_cotejados=True,
        )

    if (cotejo.get("estado") != "ABSTENCAO"
        or cotejo.get("vinculos_declarados_cotejados") is not False
        or cotejo.get("rule_version_record_id") is not None):
        return dict(saida, motivo="CONTRATO_COTEJO_INCOMPATIVEL")
    return dict(saida, motivo="COTEJO_ADR020_ABSTEVE")
