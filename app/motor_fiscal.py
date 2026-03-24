from __future__ import annotations

import json
import os
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from app.database import SessionLocal


def analisar_xml(xml_bytes: bytes) -> dict:
    """Analisa XML de NF-e reaproveitando o parser central de xml_service."""
    try:
        from app.xml_service import ler_xml_unico

        with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp:
            tmp.write(xml_bytes)
            caminho_tmp = tmp.name

        try:
            dados = ler_xml_unico(caminho_tmp)

            itens = dados.get("itens", []) or []
            primeiro_item_com_st = next(
                (
                    item for item in itens
                    if item.get("base_st") is not None or item.get("valor_st") is not None
                ),
                {}
            )

            return {
                "chave_nfe": dados.get("chave_nfe"),
                "cnpj_emitente": dados.get("cnpj"),
                "cnpj_destinatario": (
                    next(
                        (
                            item for item in [
                                dados.get("cnpj_destinatario"),
                                dados.get("cpf_destinatario"),
                                dados.get("documento_destinatario")
                            ]
                            if item
                        ),
                        None
                    )
                ),
                "valor_total_nota": dados.get("valor_total"),
                "uf_emit": dados.get("uf_emit"),
                "uf_dest": dados.get("uf_dest"),
                "uf_operacao": dados.get("uf_dest") or dados.get("uf_emit"),
                "mva_utilizada": dados.get("mva_utilizada"),
                "mva_percentual": dados.get("mva_utilizada"),
                "base_st": primeiro_item_com_st.get("base_st"),
                "icms_st": primeiro_item_com_st.get("valor_st"),
            }
        finally:
            if os.path.exists(caminho_tmp):
                os.remove(caminho_tmp)

    except Exception as e:
        return {"erro": str(e)}


class MotorFiscal:
    """Motor de cálculos fiscais com funções puras e determinísticas."""

    @staticmethod
    def calcular_base_st(valor_produto: float, mva: float) -> float:
        """Calcula a base de cálculo do ICMS ST. MVA em percentual (ex: 40 para 40%)."""
        if valor_produto < 0 or mva < 0:
            return 0.0
        base = valor_produto * (1 + mva / 100)
        return max(0.0, round(base, 2))

    @staticmethod
    def calcular_icms_proprio(valor_produto: float, aliquota_icms: float) -> float:
        """Calcula o ICMS próprio. Alíquota em percentual (ex: 18 para 18%)."""
        if valor_produto < 0 or aliquota_icms < 0:
            return 0.0
        icms = valor_produto * (aliquota_icms / 100)
        return max(0.0, round(icms, 2))

    @staticmethod
    def calcular_icms_st(
        base_st: float, aliquota_icms: float, icms_proprio: float
    ) -> float:
        """Calcula o ICMS ST: (base_st * aliquota) - icms_proprio."""
        if base_st < 0 or aliquota_icms < 0 or icms_proprio < 0:
            return 0.0
        icms_st = (base_st * (aliquota_icms / 100)) - icms_proprio
        return max(0.0, round(icms_st, 2))

    @staticmethod
    def estimar_restituicao(st_pago: float, st_devida: float) -> float:
        """Estima a restituição quando st_pago > st_devida."""
        if st_pago < 0 or st_devida < 0:
            return 0.0
        restituicao = max(st_pago - st_devida, 0)
        return max(0.0, round(restituicao, 2))


def carregar_mva(ncm: str, uf: str | None = None) -> float | None:
    """
    Adaptador de compatibilidade para consulta de MVA.
    Fonte prioritária: tabela_mva via buscar_mva.
    Fallback JSON deve existir apenas como compatibilidade temporária.
    """
    db = SessionLocal()
    try:
        if uf:
            from app.services.tabela_normativa_service import buscar_mva

            regra = buscar_mva(db, uf, ncm)
            if regra and regra.get("mva") is not None:
                return float(regra["mva"])
    finally:
        db.close()

    path = Path(__file__).parent / "data" / "mva.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            dados = json.load(f)
            valor = dados.get(ncm)
            return float(valor) if valor is not None else None

    return None
