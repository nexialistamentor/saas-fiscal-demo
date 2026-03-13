from sqlalchemy import func
from datetime import datetime
from app.models import NotaFiscalItem, DocumentoFiscal, Empresa, EngineResultado, RelatorioAnalise, Insight
from app.services.motor_predicao_tributaria import prever_impacto_st
from app.motor_fiscal import carregar_mva
from app.services.tabela_normativa_service import buscar_mva
from app.services.motor_decisao_tributaria import decidir_acao_st
from app.services.ranking_restituicao_service import gerar_ranking_restituicao
from app.services.mapa_oportunidades_service import gerar_mapa_oportunidades
from app.services.detector_creditos_service import detectar_creditos
from app.services.analisador_distorcao_service import detectar_distorcoes
from app.services.motor_preditivo_service import calcular_potencial_recuperacao
from app.services.ranking_estrategico_service import gerar_ranking_estrategico
from app.services.impacto_financeiro_service import calcular_impacto_financeiro
from app.services.memoria_estrategica_service import registrar_snapshot_inteligencia
from app.services.score_global_tributario_service import calcular_score_global_tributario
from app.services.risco_tributario_service import calcular_risco_tributario
from app.services.maturidade_tributaria_service import calcular_maturidade_tributaria
from app.services.engine_registry import ENGINES


def executar_engines(context: dict) -> dict:
    """Executa todas as engines fiscais registradas e retorna os resultados."""
    resultados = {}
    for nome, engine in ENGINES.items():
        try:
            resultados[nome] = engine.execute(context)
        except Exception as e:
            resultados[nome] = {"erro": str(e)}
    return resultados


class InsightEngine:

    def __init__(self, db):
        self.db = db

    def _montar_contexto_engines(self, empresa_id: int) -> dict:
        """Monta o contexto fiscal para execução das engines."""
        faturamento = (
            self.db.query(func.coalesce(func.sum(NotaFiscalItem.valor_produto), 0))
            .join(NotaFiscalItem.documento)
            .filter(DocumentoFiscal.empresa_id == empresa_id)
            .filter(DocumentoFiscal.tipo == "saida")
            .scalar()
        ) or 0
        custos = (
            self.db.query(func.coalesce(func.sum(NotaFiscalItem.valor_produto), 0))
            .join(NotaFiscalItem.documento)
            .filter(DocumentoFiscal.empresa_id == empresa_id)
            .filter(DocumentoFiscal.tipo == "entrada")
            .scalar()
        ) or 0
        st_entradas = (
            self.db.query(func.coalesce(func.sum(NotaFiscalItem.valor_st), 0))
            .join(NotaFiscalItem.documento)
            .filter(DocumentoFiscal.empresa_id == empresa_id)
            .filter(DocumentoFiscal.tipo == "entrada")
            .scalar()
        ) or 0
        st_saidas = (
            self.db.query(func.coalesce(func.sum(NotaFiscalItem.valor_st), 0))
            .join(NotaFiscalItem.documento)
            .filter(DocumentoFiscal.empresa_id == empresa_id)
            .filter(DocumentoFiscal.tipo == "saida")
            .scalar()
        ) or 0
        empresa = self.db.query(Empresa).filter(Empresa.id == empresa_id).first()
        regime = (empresa.regime_tributario or "presumido").lower() if empresa else "presumido"
        lucro = faturamento - custos
        base_calculo = lucro if regime == "real" else faturamento * 0.08
        return {
            "empresa_id": empresa_id,
            "db": self.db,
            "faturamento": float(faturamento),
            "custos": float(custos),
            "lucro_contabil": float(max(0, lucro)),
            "lucro": float(max(0, lucro)),
            "base_calculo": float(base_calculo),
            "regime": regime,
            "atividade": "comercio",
            "icms_pago": float(st_entradas),
            "icms_devido": float(st_saidas),
        }

    def gerar_insights_empresa(self, empresa_id: int, relatorio_analise_id: int | None = None):

        inicio = datetime.utcnow()
        relatorio = None
        if relatorio_analise_id is None:
            empresa = self.db.query(Empresa).filter(Empresa.id == empresa_id).first()
            user_id = empresa.user_id if empresa and empresa.user_id else None
            if user_id:
                relatorio = RelatorioAnalise(
                    user_id=user_id,
                    empresa_id=empresa_id,
                    analysis_type="empresa_tax",
                    status="processando",
                )
                self.db.add(relatorio)
                self.db.flush()
                relatorio_analise_id = relatorio.id

        insights = []

        insights.extend(
            self._analisar_restituicao_st(empresa_id)
        )

        insights.extend(
            self._analisar_anomalia_mva(empresa_id)
        )

        insights.extend(
            self._analisar_concentracao_ncm(empresa_id)
        )

        insights.extend(
            self._analisar_margem_real(empresa_id)
        )

        insights.extend(
            self._analisar_st_sem_saida(empresa_id)
        )

        insights.extend(
            self._analisar_mva_oficial_divergente(empresa_id)
        )

        insights.extend(
            self._analisar_decisao_st(empresa_id)
        )

        insights.extend(
            self._analisar_ranking_restituicao(empresa_id)
        )

        insights.extend(prever_impacto_st(self.db, empresa_id))

        insights.extend(self._analisar_creditos(empresa_id))

        insights.extend(self._analisar_distorcoes(empresa_id))

        insights.extend(self._obter_radar_tributario(empresa_id))

        insights.extend(self._analisar_oportunidades_preditivas(empresa_id))

        insights.extend(self._analisar_ranking_estrategico(empresa_id))

        insights.extend(self._analisar_impacto_financeiro(empresa_id))

        for item in insights:
            registro_insight = Insight(
                empresa_id=empresa_id,
                relatorio_analise_id=None,
                tipo=item.get("tipo", "INSIGHT_GENERICO"),
                valor_estimado=float(item.get("valor_estimado", 0) or 0),
                impacto=item.get("impacto"),
                descricao=item.get("descricao"),
                recomendacao=item.get("recomendacao"),
                ncm=item.get("ncm"),
                payload_json=item
            )
            self.db.add(registro_insight)

        score = calcular_score_global_tributario(self.db, empresa_id)
        risco = calcular_risco_tributario(self.db, empresa_id)
        maturidade = calcular_maturidade_tributaria(self.db, empresa_id)
        registrar_snapshot_inteligencia(
            self.db,
            empresa_id,
            score["score_global_tributario"],
            risco["nivel_risco"],
            maturidade["nivel_maturidade"]
        )

        creditos_detectados = [i for i in insights if i.get("tipo") == "CREDITO_ST_ESTIMADO"]
        oportunidades = [i for i in insights if i.get("tipo") != "CREDITO_ST_ESTIMADO"]

        context = self._montar_contexto_engines(empresa_id)
        resultados_engines = executar_engines(context)

        for nome, resultado in resultados_engines.items():
            registro = EngineResultado(
                empresa_id=empresa_id,
                relatorio_analise_id=None,
                engine_nome=nome,
                resultado=resultado,
                criado_em=datetime.utcnow()
            )
            self.db.add(registro)

        if relatorio:
            from app.services.registro_analise_service import contar_alertas_empresa
            relatorio.status = "ok"
            relatorio.tempo_execucao = (datetime.utcnow() - inicio).total_seconds()
            relatorio.total_alertas = contar_alertas_empresa(self.db, empresa_id)
            relatorio.score_resultante = round(score["score_global_tributario"], 2)
            relatorio.resultado_json = {
                "empresa_id": empresa_id,
                "oportunidades": oportunidades,
                "creditos_detectados": creditos_detectados,
                "risco_tributario": risco,
                "resultados_engines": resultados_engines,
            }

        self.db.commit()

        return {
            "empresa_id": empresa_id,
            "oportunidades": oportunidades,
            "creditos_detectados": creditos_detectados,
            "risco_tributario": risco,
            "resultados_engines": resultados_engines
        }

    def _analisar_impacto_financeiro(self, empresa_id: int):
        """Seleciona top 5 impactos financeiros e transforma em insights estruturados."""
        impactos = calcular_impacto_financeiro(self.db, empresa_id)
        insights = []
        for item in impactos[:5]:
            insights.append({
                "tipo": "IMPACTO_FINANCEIRO_TRIBUTARIO",
                "ncm": item["ncm"],
                "impacto_anual_estimado": item["impacto_anual_estimado"],
                "prioridade_fiscal": item["prioridade_fiscal"]
            })
        return insights

    def _analisar_ranking_estrategico(self, empresa_id: int):
        """Transforma o ranking estratégico em insights consumíveis pela plataforma."""
        ranking = gerar_ranking_estrategico(self.db, empresa_id)
        insights = []
        for item in ranking[:5]:
            insights.append({
                "tipo": "RANKING_ESTRATEGICO_TRIBUTARIO",
                "ncm": item["ncm"],
                "score": item["score"],
                "potencial": item["potencial"],
                "creditos": item["creditos"],
                "distorcao": item["distorcao"]
            })
        return insights

    def _analisar_oportunidades_preditivas(self, empresa_id: int):
        """Utiliza o motor preditivo para identificar top 5 oportunidades tributárias."""
        oportunidades = calcular_potencial_recuperacao(self.db, empresa_id)
        insights = []
        for item in oportunidades[:5]:
            insights.append({
                "tipo": "OPORTUNIDADE_TRIBUTARIA_PREDITIVA",
                "ncm": item["ncm"],
                "potencial_recuperacao": item["potencial_recuperacao"],
                "score": item["score_oportunidade"],
                "volume_operacoes": item["volume_operacoes"]
            })
        return insights

    def _analisar_creditos(self, empresa_id: int):
        """Orquestra detectar_creditos e converte resultados em insights."""
        creditos = detectar_creditos(self.db, empresa_id)
        insights = []
        for item in creditos:
            credito = item.get("credito_estimado", 0)
            if credito <= 0:
                continue
            insights.append({
                "tipo": "CREDITO_ST_ESTIMADO",
                "impacto": "alto",
                "ncm": item.get("ncm"),
                "valor_estimado": round(credito, 2),
                "descricao": f"NCM {item.get('ncm')}: crédito de ST estimado em R$ {round(credito, 2)}.",
                "recomendacao": "Verificar elegibilidade para restituição de crédito de ST."
            })
        return insights

    def _analisar_distorcoes(self, empresa_id: int):
        """Orquestra detectar_distorcoes e converte resultados em insights."""
        distorcoes = detectar_distorcoes(self.db, empresa_id)
        insights = []
        for item in distorcoes:
            distorcao = item.get("distorcao", 0)
            if distorcao <= 0:
                continue
            insights.append({
                "tipo": "DISTORCAO_MVA_REAL",
                "impacto": "medio",
                "ncm": item.get("ncm"),
                "valor_estimado": round(distorcao * 100, 1),
                "descricao": f"NCM {item.get('ncm')}: distorção de {round(distorcao * 100, 1)}% entre MVA oficial e margem real.",
                "recomendacao": "Analisar preços e base de cálculo para identificar possível distorção tributária."
            })
        return insights

    def _obter_radar_tributario(self, empresa_id: int):
        """Utiliza o mapa de oportunidades como radar tributário."""
        mapa = gerar_mapa_oportunidades(self.db, empresa_id)
        if not any(mapa.values()):
            return []
        return [{
            "tipo": "RADAR_TRIBUTARIO",
            "impacto": "medio",
            "mapa_oportunidades": mapa,
            "descricao": "Resumo de oportunidades fiscais por categoria.",
            "recomendacao": "Analisar o mapa para priorizar ações de otimização tributária."
        }]

    def _analisar_restituicao_st(self, empresa_id: int):
        insights = []

        st_total = (
            self.db.query(func.sum(NotaFiscalItem.valor_st))
            .join(NotaFiscalItem.documento)
            .filter(DocumentoFiscal.empresa_id == empresa_id)
            .scalar()
        )

        base_st_total = (
            self.db.query(func.sum(NotaFiscalItem.base_st))
            .join(NotaFiscalItem.documento)
            .filter(DocumentoFiscal.empresa_id == empresa_id)
            .scalar()
        )

        if not st_total or not base_st_total:
            return insights

        st_devida = base_st_total * 0.18
        restituicao_estimada = st_total - st_devida

        if restituicao_estimada <= 0:
            return insights

        if restituicao_estimada < 100:
            return insights

        insight = {
            "tipo": "ST_RESTITUICAO",
            "impacto": "alto",
            "valor_estimado": round(restituicao_estimada, 2),
            "descricao": f"Possível restituição de ST estimada em R$ {round(restituicao_estimada,2)} com base nas operações analisadas.",
            "recomendacao": "Verificar diferença entre ST paga e ST devida."
        }

        insights.append(insight)

        return insights

    def _analisar_anomalia_mva(self, empresa_id: int):
        insights = []

        preco_medio_venda = (
            self.db.query(
                NotaFiscalItem.ncm,
                func.avg(NotaFiscalItem.valor_produto).label("preco_medio")
            )
            .join(NotaFiscalItem.documento)
            .filter(DocumentoFiscal.empresa_id == empresa_id)
            .filter(DocumentoFiscal.tipo == "saida")
            .group_by(NotaFiscalItem.ncm)
            .all()
        )

        base_presumida_st = (
            self.db.query(
                NotaFiscalItem.ncm,
                func.avg(NotaFiscalItem.base_st).label("base_media")
            )
            .join(NotaFiscalItem.documento)
            .filter(DocumentoFiscal.empresa_id == empresa_id)
            .filter(DocumentoFiscal.tipo == "entrada")
            .group_by(NotaFiscalItem.ncm)
            .all()
        )

        base_por_ncm = {item.ncm: item.base_media for item in base_presumida_st}

        for venda in preco_medio_venda:
            preco_real = venda.preco_medio or 0
            base_presumida = base_por_ncm.get(venda.ncm, 0)

            if base_presumida == 0:
                continue

            if preco_real < (base_presumida * 0.7):
                insight = {
                    "tipo": "ANOMALIA_MVA",
                    "impacto": "medio",
                    "valor_estimado": round(base_presumida - preco_real, 2),
                    "descricao": f"NCM {venda.ncm} apresenta preço médio de venda significativamente abaixo da base presumida de ST.",
                    "recomendacao": "Avaliar se a MVA aplicada reflete a realidade das operações."
                }
                insights.append(insight)

        return insights

    def _analisar_concentracao_ncm(self, empresa_id: int):
        insights = []
        st_por_ncm = (
            self.db.query(
                NotaFiscalItem.ncm,
                func.sum(NotaFiscalItem.valor_st).label("st_total")
            )
            .join(NotaFiscalItem.documento)
            .filter(DocumentoFiscal.empresa_id == empresa_id)
            .group_by(NotaFiscalItem.ncm)
            .all()
        )

        if not st_por_ncm:
            return insights

        st_total_empresa = sum([item.st_total or 0 for item in st_por_ncm])
        if st_total_empresa <= 0:
            return insights

        for item in st_por_ncm:
            st_item = item.st_total or 0
            if st_item <= 0:
                continue
            percentual = st_item / st_total_empresa
            if percentual > 0.4:
                insight = {
                    "tipo": "CONCENTRACAO_ST_NCM",
                    "impacto": "medio",
                    "valor_estimado": round(st_item, 2),
                    "descricao": f"NCM {item.ncm} representa {round(percentual*100,2)}% da ST total.",
                    "recomendacao": "Avaliar dependência tributária deste NCM e possíveis estratégias fiscais."
                }
                insights.append(insight)

        return insights

    def _analisar_margem_real(self, empresa_id: int):
        insights = []

        custo_por_ncm = (
            self.db.query(
                NotaFiscalItem.ncm,
                func.avg(NotaFiscalItem.valor_produto).label("custo_medio")
            )
            .join(NotaFiscalItem.documento)
            .filter(DocumentoFiscal.empresa_id == empresa_id)
            .filter(DocumentoFiscal.tipo == "entrada")
            .group_by(NotaFiscalItem.ncm)
            .all()
        )

        venda_por_ncm = (
            self.db.query(
                NotaFiscalItem.ncm,
                func.avg(NotaFiscalItem.valor_produto).label("preco_medio"),
                func.sum(NotaFiscalItem.valor_st).label("st_total")
            )
            .join(NotaFiscalItem.documento)
            .filter(DocumentoFiscal.empresa_id == empresa_id)
            .filter(DocumentoFiscal.tipo == "saida")
            .group_by(NotaFiscalItem.ncm)
            .all()
        )

        custo_medio = {item.ncm: (item.custo_medio or 0) for item in custo_por_ncm}

        for venda in venda_por_ncm:
            custo = custo_medio.get(venda.ncm)
            if not custo or custo <= 0:
                continue

            preco_venda = venda.preco_medio or 0
            if preco_venda <= 0:
                continue

            mva_presumida = carregar_mva(venda.ncm)
            if mva_presumida is None:
                continue
            if mva_presumida <= 0:
                continue

            margem_real = (preco_venda - custo) / custo

            mva_decimal = mva_presumida if mva_presumida <= 1 else mva_presumida / 100
            diff = mva_decimal - margem_real
            if diff > 0.15 and margem_real < mva_decimal * 0.6:
                valor_st = venda.st_total or 0
                insight = {
                    "tipo": "DISTORCAO_MARGEM_MVA",
                    "impacto": "medio",
                    "valor_estimado": round(valor_st, 2),
                    "descricao": f"NCM {venda.ncm}: margem real {round(margem_real*100,1)}% vs MVA presumida {round(mva_decimal*100,1)}%.",
                    "recomendacao": "Analisar estrutura de preços e avaliar possíveis distorções tributárias."
                }
                insights.append(insight)

        return insights

    def _analisar_st_sem_saida(self, empresa_id: int):
        insights = []

        st_entradas = (
            self.db.query(func.sum(NotaFiscalItem.valor_st))
            .join(NotaFiscalItem.documento)
            .filter(DocumentoFiscal.empresa_id == empresa_id)
            .filter(DocumentoFiscal.tipo == "entrada")
            .scalar()
        )

        st_saidas = (
            self.db.query(func.sum(NotaFiscalItem.valor_st))
            .join(NotaFiscalItem.documento)
            .filter(DocumentoFiscal.empresa_id == empresa_id)
            .filter(DocumentoFiscal.tipo == "saida")
            .scalar()
        )

        if not st_entradas:
            return insights

        st_saidas = st_saidas or 0

        st_em_estoque = st_entradas - st_saidas

        if st_em_estoque <= 100:
            return insights

        insight = {
            "tipo": "ST_SEM_SAIDA",
            "impacto": "medio",
            "valor_estimado": round(st_em_estoque, 2),
            "descricao": f"ST estimada de R$ {round(st_em_estoque,2)} ainda não realizada em vendas.",
            "recomendacao": "Verificar itens em estoque ou divergências entre entradas e saídas."
        }

        insights.append(insight)

        return insights

    def _analisar_mva_oficial_divergente(self, empresa_id):
        insights = []

        itens = (
            self.db.query(NotaFiscalItem)
            .join(NotaFiscalItem.documento)
            .filter(DocumentoFiscal.empresa_id == empresa_id)
            .all()
        )

        for item in itens:
            if not item.ncm:
                continue

            regra = buscar_mva(self.db, "PA", item.ncm)

            if not regra:
                continue

            base = item.base_st or 0
            valor = item.valor_produto or 0

            if valor <= 0:
                continue

            mva_aplicada = (base - valor) / valor

            mva_oficial = regra["mva"] / 100

            diferenca = abs(mva_aplicada - mva_oficial)

            if diferenca > 0.1:
                insights.append({
                    "tipo": "MVA_OFICIAL_DIVERGENTE",
                    "impacto": "medio",
                    "valor_estimado": 0,
                    "descricao": f"NCM {item.ncm} apresenta divergência entre MVA aplicada e MVA oficial.",
                    "recomendacao": "Verificar parametrização fiscal e possível restituição de ST."
                })

        return insights

    def _analisar_ranking_restituicao(self, empresa_id: int):
        ranking = gerar_ranking_restituicao(self.db, empresa_id)
        insights = []
        for item in ranking[:5]:
            if item["restituicao_estimada"] > 0:
                insights.append({
                    "tipo": "PRODUTO_COM_RESTITUICAO_RELEVANTE",
                    "ncm": item["ncm"],
                    "valor_estimado": item["restituicao_estimada"]
                })
        return insights

    def _analisar_decisao_st(self, empresa_id):
        insights = []

        itens = (
            self.db.query(NotaFiscalItem)
            .join(NotaFiscalItem.documento)
            .filter(DocumentoFiscal.empresa_id == empresa_id)
            .all()
        )

        for item in itens:
            valor = item.valor_produto or 0
            st_pago = item.valor_st or 0

            if valor <= 0:
                continue

            regra = buscar_mva(self.db, "PA", item.ncm)

            if not regra:
                continue

            decisao = decidir_acao_st(
                valor_produto=valor,
                st_pago=st_pago,
                mva=regra["mva"] / 100,
                aliquota=regra["aliquota_interna"]
            )

            if decisao["decisao"] != "OPERACAO_CORRETA":
                insights.append({
                    "tipo": decisao["decisao"],
                    "impacto": "alto",
                    "valor_estimado": decisao["valor_estimado"],
                    "descricao": decisao["descricao"],
                    "recomendacao": decisao["recomendacao"]
                })

        return insights
