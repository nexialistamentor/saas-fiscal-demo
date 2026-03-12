from __future__ import annotations

import json
import os
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from sqlalchemy import text

from app.database import SessionLocal


def analisar_xml(xml_bytes: bytes) -> dict:
    """Analisa XML de NF-e e extrai CNPJ emitente, destinatário, valor total, ICMS-ST e MVA."""
    try:
        root = ET.fromstring(xml_bytes)
        ns = {"nfe": "http://www.portalfiscal.inf.br/nfe"}

        emitente = root.find(".//nfe:emit/nfe:CNPJ", ns)
        destinatario = root.find(".//nfe:dest/nfe:CNPJ", ns)
        valor_total = root.find(".//nfe:ICMSTot/nfe:vNF", ns)

        # UF emitente e destinatário (para consulta normativa / MVA por estado)
        uf_emit = root.findtext(".//nfe:emit/nfe:enderEmit/nfe:UF", namespaces=ns)
        uf_dest = root.findtext(".//nfe:dest/nfe:enderDest/nfe:UF", namespaces=ns)
        uf_operacao = uf_dest if uf_dest else uf_emit

        # Extrair ICMS-ST: NF-e usa ICMS10, ICMS30 ou ICMS70 (não existe tag ICMSST)
        # Totais: ICMSTot/vBCST e vST
        base_st = root.find(".//nfe:ICMSTot/nfe:vBCST", ns)
        icms_st_total = root.find(".//nfe:ICMSTot/nfe:vST", ns)
        # MVA e ST por item: buscar em ICMS10, ICMS30, ICMS70
        mva = None
        for tag in ("ICMS10", "ICMS30", "ICMS70"):
            el = root.find(f".//nfe:{tag}/nfe:pMVAST", ns)
            if el is not None and el.text:
                mva = el
                break
        if mva is None:
            # Fallback: qualquer elemento pMVAST (namespace padrão)
            for el in root.iter():
                if el.tag.endswith("}pMVAST") and el.text:
                    mva = el
                    break
        icms_st_item = (
            root.find(".//nfe:ICMS10/nfe:vICMSST", ns)
            or root.find(".//nfe:ICMS30/nfe:vICMSST", ns)
            or root.find(".//nfe:ICMS70/nfe:vICMSST", ns)
        )
        icms_st = icms_st_total if icms_st_total is not None else icms_st_item

        # Chave NF-e (infProt/chNFe ou Id do infNFe)
        inf_prot = root.find(".//nfe:infProt", ns)
        inf_nfe = root.find(".//nfe:infNFe", ns)
        chave_nfe = None
        if inf_prot is not None:
            el_chave = inf_prot.find("nfe:chNFe", ns)
            chave_nfe = el_chave.text if el_chave is not None else None
        if chave_nfe is None and inf_nfe is not None:
            id_attr = inf_nfe.get("Id")
            if id_attr and id_attr.startswith("NFe"):
                chave_nfe = id_attr[3:]

        resultado = {
            "chave_nfe": chave_nfe,
            "cnpj_emitente": emitente.text if emitente is not None else None,
            "cnpj_destinatario": destinatario.text if destinatario is not None else None,
            "valor_total_nota": valor_total.text if valor_total is not None else None,
            "uf_emit": uf_emit,
            "uf_dest": uf_dest,
            "uf_operacao": uf_operacao,
            "mva_utilizada": mva.text if mva is not None else None,
            "mva_percentual": mva.text if mva is not None else None,
            "base_st": base_st.text if base_st is not None else None,
            "icms_st": icms_st.text if icms_st is not None else None,
        }

        return resultado

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
        restituicao = st_pago - st_devida
        return max(0.0, round(restituicao, 2))


def carregar_mva(ncm: str, uf: str | None = None) -> float:
    """Consulta MVA na base normativa (tabela_mva) ou fallback em mva.json.
    Quando uf é informado, usa regras estaduais do banco. Retorna 0.30 se não encontrar."""
    db = SessionLocal()

    if uf:
        query = text("""
            SELECT mva
            FROM tabela_mva
            WHERE estado = :uf
            AND ncm = :ncm
            LIMIT 1
        """)

        result = db.execute(query, {"uf": uf, "ncm": ncm}).fetchone()

        if result:
            db.close()
            return float(result[0])

    db.close()

    # fallback para JSON
    path = Path(__file__).parent / "data" / "mva.json"

    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            dados = json.load(f)
            return float(dados.get(ncm, 0.30))

    return 0.30
