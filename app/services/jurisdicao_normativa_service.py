"""Selecao jurisdicional de regra ST/MVA, sem promover cadastro a autoridade.

Reutiliza TabelaMVA/buscar_mva e resolver_aliquota_e_mva. Nao altera o
resolvedor fiscal, nem cria tabela ou politica de governanca.
"""
from __future__ import annotations

from datetime import date

from app.services.fiscal_utils import resolver_aliquota_e_mva
from app.services.tabela_normativa_service import buscar_mva


_DOMINIO = "ICMS_ST_MVA"
_USO = "icms_st_mva"
_AVISO_SEM_PROVA = "cobertura normativa não comprovada"


def selecionar_norma_por_jurisdicao(*, db, empresa, ncm: str, data_referencia: date) -> dict:
    """Lê a UF da empresa e seleciona uma norma por UF/NCM/data.

    O objecto retornado reaproveita as chaves de metadados ``scope``,
    ``domain``, ``policy_version``, ``policy_hash`` e
    ``declared_material_applicability``. Os dois campos de policy ficam
    nulos: cadastro MVA não equivale a política assinada.

    Norma só é liberada quando o resolvedor fiscal existente autoriza
    integralmente e a fonte legal está explicitamente identificada.
    """
    uf_bruta = getattr(empresa, "uf", None)
    uf = uf_bruta.strip().upper() if isinstance(uf_bruta, str) else ""
    ncm_norm = ncm.strip() if isinstance(ncm, str) else ""

    resultado = {
        "scope": {
            "jurisdiction": f"BR-{uf}" if len(uf) == 2 and uf.isalpha() and uf.isascii() else None,
            "sphere": "estadual",
            "territory": {"uf": uf or None, "municipio": None},
            "source_id": None,
            "use": _USO,
        },
        "domain": _DOMINIO,
        "policy_version": None,
        "policy_hash": None,
        "declared_material_applicability": None,
        "estado": "COBERTURA_NORMATIVA_NAO_COMPROVADA",
        "regra_cadastrada": False,
        "autoridade_normativa_verificada": False,
        "calculo_autorizado": False,
        "aviso": _AVISO_SEM_PROVA,
        "motivo": "chave_normativa_invalida",
        "registro_mva_id": None,
        "norma_resolvida": None,
    }
    if (
        len(uf) != 2 or not uf.isascii() or not uf.isalpha()
        or len(ncm_norm) != 8 or not ncm_norm.isascii() or not ncm_norm.isdigit()
        or type(data_referencia) is not date
    ):
        return resultado

    # A consulta existente usa igualdade de UF + NCM e vigencia na data.
    # Nao pesquisa uma UF substituta nem promove dados de outra empresa.
    regra = buscar_mva(db, uf, ncm_norm, data_referencia=data_referencia)
    if regra is None:
        resultado["motivo"] = "regra_vigente_nao_encontrada"
        return resultado

    resultado["regra_cadastrada"] = True
    resultado["estado"] = "REGRA_CADASTRADA_AUTORIDADE_NAO_COMPROVADA"
    resultado["registro_mva_id"] = regra.get("registro_mva_id")
    fonte = regra.get("fonte_legal")
    resultado["scope"]["source_id"] = fonte.strip() if isinstance(fonte, str) and fonte.strip() else None
    inicio, fim = regra.get("vigencia_inicio"), regra.get("vigencia_fim")
    if type(inicio) is date and (fim is None or type(fim) is date):
        resultado["declared_material_applicability"] = {
            "kind": "vigencia_regra_cadastrada",
            "from": inicio.isoformat(),
            "until": fim.isoformat() if fim is not None else None,
        }

    # O indicador 'oficial' sozinho NAO e prova de fonte identificada.
    if resultado["scope"]["source_id"] is None:
        resultado["motivo"] = "fonte_legal_ausente"
        return resultado

    # Mantem intacto o contrato vigente de validacao de fonte, confianca,
    # tempo, MVA e aliquota. Nunca interpreta fallback como calculo valido.
    resolvida = resolver_aliquota_e_mva(db, uf, ncm_norm, data_referencia=data_referencia)
    if not (
        resolvida.get("calculo_autorizado") is True
        and resolvida.get("calculo_parcial") is False
        and resolvida.get("mva_autorizada") is True
        and resolvida.get("aliquota_autorizada") is True
        and resolvida.get("uf") == uf
        and resolvida.get("ncm") == ncm_norm
        and regra.get("nivel_confianca_fonte") == "oficial"
    ):
        resultado["motivo"] = resolvida.get("motivo_bloqueio") or "autoridade_normativa_insuficiente"
        return resultado

    resultado.update(
        estado="NORMA_VERIFICADA",
        autoridade_normativa_verificada=True,
        calculo_autorizado=True,
        aviso=None,
        motivo=None,
        norma_resolvida=resolvida,
    )
    return resultado
