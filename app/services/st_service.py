from sqlalchemy import func
from app import models
from app.motor_fiscal import MotorFiscal, carregar_mva

# Alíquota ICMS padrão (%). ItemFiscal não possui campo aliquota_icms no banco.
ALIQUOTA_ICMS_PADRAO = 18.0


class STAnalyzer:

    def calcular_restituicao(self, db, empresa_id, periodo_inicio=None, periodo_fim=None):
        """
        MVP - Fórmula simplificada

        ST paga = soma(valor_st) das entradas
        ST devida estimada = proporção simples baseada na saída

        Esta é uma estimativa inicial.
        Não considera MVA dinâmica nem ICMS por estado.
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

        # 2️⃣ ST devida estimada por item (SAÍDA) via MotorFiscal
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
            mva = carregar_mva(ncm)
            base_st = MotorFiscal.calcular_base_st(valor_produto, mva)
            icms_proprio = MotorFiscal.calcular_icms_proprio(valor_produto, ALIQUOTA_ICMS_PADRAO)
            icms_st = MotorFiscal.calcular_icms_st(base_st, ALIQUOTA_ICMS_PADRAO, icms_proprio)
            st_devida += icms_st

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
            mva = carregar_mva(ncm)
            base_st = MotorFiscal.calcular_base_st(valor_produto, mva)
            icms_proprio = MotorFiscal.calcular_icms_proprio(valor_produto, ALIQUOTA_ICMS_PADRAO)
            icms_st = MotorFiscal.calcular_icms_st(base_st, ALIQUOTA_ICMS_PADRAO, icms_proprio)
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
        from datetime import date
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
            mva = carregar_mva(ncm)
            base_st = MotorFiscal.calcular_base_st(valor_produto, mva)
            icms_proprio = MotorFiscal.calcular_icms_proprio(valor_produto, ALIQUOTA_ICMS_PADRAO)
            icms_st = MotorFiscal.calcular_icms_st(base_st, ALIQUOTA_ICMS_PADRAO, icms_proprio)
            st_devida += icms_st

        restituicao = max(0, (st_pago or 0) - st_devida)

        return {
            "st_pago": round(st_pago or 0, 2),
            "st_devido": round(st_devida or 0, 2),
            "restituicao": round(restituicao, 2),
        }
