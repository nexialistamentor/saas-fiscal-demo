from datetime import date

from sqlalchemy import func
from app import models
from app.motor_fiscal import MotorFiscal
from app.services.fiscal_utils import uf_do_documento
from app.services.tabela_normativa_service import resolver_base_calculo_st


def _icms_st_item_saida(
    db,
    uf: str,
    ncm: str,
    valor_produto: float,
    data_referencia: date | None = None,
) -> float:
    """
    Base ST e alíquota via ``resolver_base_calculo_st`` (PMPF / IVA-ST);
    valor ST via ``MotorFiscal`` (puras).
    """
    if valor_produto <= 0:
        return 0.0
    r = resolver_base_calculo_st(
        db, uf, ncm, valor_produto, data_referencia=data_referencia
    )
    base = r.get("base_calculo")
    ali = r.get("aliquota_interna")
    if base is None or ali is None:
        return 0.0
    aliquota_pct = float(ali) * 100
    icms_proprio = MotorFiscal.calcular_icms_proprio(valor_produto, aliquota_pct)
    return MotorFiscal.calcular_icms_st(float(base), aliquota_pct, icms_proprio)


class STAnalyzer:

    def calcular_restituicao(self, db, empresa_id, periodo_inicio=None, periodo_fim=None):
        """
        MVP - Fórmula simplificada

        ST paga = soma(valor_st) das entradas
        ST devida estimada = proporção simples baseada na saída

        Esta é uma estimativa inicial. Base e alíquota vêm de
        ``resolver_base_calculo_st`` (PMPF, depois IVA-ST); o valor ST usa o motor.
        """

        # 1️⃣ ST paga nas ENTRADAS
        st_pago = (
            db.query(func.coalesce(func.sum(models.ItemFiscal.valor_st), 0))
            .join(models.DocumentoFiscal)
            .filter(
                models.DocumentoFiscal.empresa_id == empresa_id,
                models.DocumentoFiscal.tipo == "entrada"
            )
            .scalar()
        )

        # 2️⃣ ST devida estimada por item (SAÍDA): base via normativo, valor via motor
        itens_saida = (
            db.query(models.ItemFiscal)
            .join(models.DocumentoFiscal)
            .filter(
                models.DocumentoFiscal.empresa_id == empresa_id,
                models.DocumentoFiscal.tipo == "saida"
            )
            .all()
        )
        st_devida = 0.0
        for item in itens_saida:
            ncm = (item.ncm or "").strip()
            valor_produto = float(item.valor_produto or 0)
            if valor_produto <= 0:
                continue
            uf = uf_do_documento(item.documento)
            st_devida += _icms_st_item_saida(
                db,
                uf,
                ncm,
                valor_produto,
                data_referencia=item.documento.data_emissao,
            )

        restituicao = max(0, st_pago - st_devida)

        return {
            "empresa_id": empresa_id,
            "st_total_pago": round(st_pago or 0, 2),
            "st_estimado_devido": round(st_devida or 0, 2),
            "st_potencial_restituicao": round(restituicao, 2)
        }

    def analise_por_ncm(self, db, empresa_id):
        """Retorna lista por NCM: ncm, st_pago, st_devido, restituicao."""
        # ST pago por NCM (entradas)
        st_pago_por_ncm = (
            db.query(models.ItemFiscal.ncm, func.coalesce(func.sum(models.ItemFiscal.valor_st), 0).label("total"))
            .join(models.DocumentoFiscal)
            .filter(
                models.DocumentoFiscal.empresa_id == empresa_id,
                models.DocumentoFiscal.tipo == "entrada"
            )
            .group_by(models.ItemFiscal.ncm)
            .all()
        )
        mapa_st_pago = {(ncm or "").strip(): float(total) for ncm, total in st_pago_por_ncm}

        # ST devida por NCM (saídas)
        itens_saida = (
            db.query(models.ItemFiscal)
            .join(models.DocumentoFiscal)
            .filter(
                models.DocumentoFiscal.empresa_id == empresa_id,
                models.DocumentoFiscal.tipo == "saida"
            )
            .all()
        )
        mapa_st_devido = {}
        for item in itens_saida:
            ncm = (item.ncm or "").strip()
            valor_produto = float(item.valor_produto or 0)
            if valor_produto <= 0:
                continue
            uf = uf_do_documento(item.documento)
            icms_st = _icms_st_item_saida(
                db,
                uf,
                ncm,
                valor_produto,
                data_referencia=item.documento.data_emissao,
            )
            mapa_st_devido[ncm] = mapa_st_devido.get(ncm, 0.0) + icms_st

        ncms = set(mapa_st_pago) | set(mapa_st_devido)
        resultado = []
        for ncm in sorted(ncms):
            st_pago = round(mapa_st_pago.get(ncm, 0.0), 2)
            st_devido = round(mapa_st_devido.get(ncm, 0.0), 2)
            restituicao = round(max(0, st_pago - st_devido), 2)
            resultado.append({
                "ncm": ncm,
                "st_pago": st_pago,
                "st_devido": st_devido,
                "restituicao": restituicao
            })
        return resultado

    def analise_por_periodo(self, db, empresa_id, data_inicio, data_fim):
        """
        Análise ST (st_pago, st_devido, restituicao) filtrada por período de emissão.
        """
        if isinstance(data_inicio, str):
            data_inicio = date.fromisoformat(data_inicio)
        if isinstance(data_fim, str):
            data_fim = date.fromisoformat(data_fim)

        # ST pago nas entradas no período
        st_pago = (
            db.query(func.coalesce(func.sum(models.ItemFiscal.valor_st), 0))
            .join(models.DocumentoFiscal)
            .filter(
                models.DocumentoFiscal.empresa_id == empresa_id,
                models.DocumentoFiscal.tipo == "entrada",
                models.DocumentoFiscal.data_emissao >= data_inicio,
                models.DocumentoFiscal.data_emissao <= data_fim,
            )
            .scalar()
        )

        # ST devida nas saídas no período
        itens_saida = (
            db.query(models.ItemFiscal)
            .join(models.DocumentoFiscal)
            .filter(
                models.DocumentoFiscal.empresa_id == empresa_id,
                models.DocumentoFiscal.tipo == "saida",
                models.DocumentoFiscal.data_emissao >= data_inicio,
                models.DocumentoFiscal.data_emissao <= data_fim,
            )
            .all()
        )
        st_devida = 0.0
        for item in itens_saida:
            ncm = (item.ncm or "").strip()
            valor_produto = float(item.valor_produto or 0)
            if valor_produto <= 0:
                continue
            uf = uf_do_documento(item.documento)
            st_devida += _icms_st_item_saida(
                db,
                uf,
                ncm,
                valor_produto,
                data_referencia=item.documento.data_emissao,
            )

        restituicao = max(0, (st_pago or 0) - st_devida)

        return {
            "st_pago": round(st_pago or 0, 2),
            "st_devido": round(st_devida or 0, 2),
            "restituicao": round(restituicao, 2),
        }
