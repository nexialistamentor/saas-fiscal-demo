from sqlalchemy import func
from datetime import datetime
from app.models import (
    NotaFiscalItem,
    DocumentoFiscal,
    Empresa,
    EngineResultado,
    RelatorioAnalise,
    Insight,
    InteligenciaSnapshot,
)
from app.services.motor_predicao_tributaria import prever_impacto_st
from app.motor_fiscal import carregar_mva
from app.services.fiscal_utils import resolver_aliquota_e_mva, uf_do_documento
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
from app.services.analysis_types import ANALYSIS_TYPE_MEI_TAX
from app.services.tax_engines.base_tax_engine import TempoNormativoAusenteError
from app.services.tax_engines.pis_cofins_engine import calcular_pis_cofins
from app.services.context_flags_service import (
    anexar_flags_nos_resultados_engines,
    inferir_flags_contexto_empresa,
    merge_context_flags,
)


def executar_engines(context: dict) -> dict:
    """Executa todas as engines fiscais registradas e retorna os resultados."""
    resultados = {}
    faturamento_mei = context.pop("_faturamento_material_mei", context.get("faturamento"))
    for nome, engine in ENGINES.items():
        if nome == ANALYSIS_TYPE_MEI_TAX and context.get("regime") != "mei":
            continue
        try:
            if nome == "pis_cofins":
                dados = dict(context)
                if dados.get("icms") is None:
                    dados["icms"] = float(
                        dados.get("icms_devido") or dados.get("icms_pago") or 0
                    )
                regime = context.get("regime") or "presumido"
                resultados[nome] = calcular_pis_cofins(dados, regime=regime)
            elif nome == ANALYSIS_TYPE_MEI_TAX:
                contexto_mei = dict(context)
                contexto_mei["faturamento"] = faturamento_mei
                resultados[nome] = engine.execute(contexto_mei)
            else:
                resultados[nome] = engine.execute(context)
        except TempoNormativoAusenteError as e:
            resultados[nome] = {
                "erro": str(e),
                "codigo": "TEMPO_NORMATIVO_AUSENTE",
                "estado_l3": "bloqueado",
            }
        except Exception as e:
            resultados[nome] = {"erro": str(e)}
    return resultados


class InsightEngine:

    def __init__(self, db):
        self.db = db

    def _montar_contexto_engines(self, empresa_id: int) -> dict:
        """Monta o contexto fiscal para execução das engines."""
        faturamento_material_mei = (
            self.db.query(func.sum(NotaFiscalItem.valor_produto))
            .join(NotaFiscalItem.documento)
            .filter(DocumentoFiscal.empresa_id == empresa_id)
            .filter(DocumentoFiscal.tipo == "saida")
            .scalar()
        )
        faturamento = faturamento_material_mei or 0
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
        data_referencia = (
            self.db.query(func.max(DocumentoFiscal.data_emissao))
            .filter(DocumentoFiscal.empresa_id == empresa_id)
            .scalar()
        )

        return {
            "empresa_id": empresa_id,
            "db": self.db,
            "data_referencia": data_referencia,
            "faturamento": float(faturamento),
            "_faturamento_material_mei": (
                float(faturamento_material_mei)
                if faturamento_material_mei is not None
                else None
            ),
            "custos": float(custos),
            "custo_fiscal_entradas": float(custos),
            "lucro_contabil": float(max(0, lucro)),
            "lucro": float(max(0, lucro)),
            "base_calculo": float(base_calculo),
            "regime": regime,
            "atividade": "comercio",
            "icms_pago": float(st_entradas),
            "icms_devido": float(st_saidas),
            "context_flags": inferir_flags_contexto_empresa(
                regime=regime,
                faturamento=float(faturamento),
                custos=float(custos),
            ),
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

        context = self._montar_contexto_engines(empresa_id)

        insights.extend(
            self._analisar_restituicao_st(empresa_id, context)
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
            self._analisar_st_sem_saida(context)
        )

        insights.extend(
            self._analisar_st_sem_saida_por_ncm(empresa_id)
        )

        insights.extend(
            self._analisar_mva_oficial_divergente(empresa_id, context)
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

        self.db.query(Insight).filter(
            Insight.empresa_id == empresa_id,
            Insight.superseded == False,
        ).update({"superseded": True})
        self.db.flush()

        for item in insights:
            uf = None

            # tentativa segura via contexto de item/documento
            if "ncm" in item:
                try:
                    ultimo_item = (
                        self.db.query(NotaFiscalItem)
                        .join(NotaFiscalItem.documento)
                        .filter(
                            NotaFiscalItem.ncm == item.get("ncm"),
                            DocumentoFiscal.empresa_id == empresa_id,
                        )
                        .order_by(NotaFiscalItem.id.desc())
                        .first()
                    )
                    if ultimo_item and ultimo_item.documento:
                        uf = ultimo_item.documento.uf_dest or ultimo_item.documento.uf_emit
                except:
                    pass

            if uf:
                item["uf"] = uf

            registro_insight = Insight(
                empresa_id=empresa_id,
                relatorio_analise_id=relatorio_analise_id,
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

        ultimo_snapshot = (
            self.db.query(InteligenciaSnapshot)
            .filter(InteligenciaSnapshot.empresa_id == empresa_id)
            .order_by(InteligenciaSnapshot.id.desc())
            .first()
        )
        if ultimo_snapshot and ultimo_snapshot.uf_cobertura is not None:
            if ultimo_snapshot.uf_cobertura < 50:
                item = {
                    "tipo": "QUALIDADE_DADOS_UF_BAIXA",
                    "impacto": "alto",
                    "descricao": "Cobertura de UF insuficiente para análises estaduais precisas.",
                    "recomendacao": "Submeter mais XMLs recentes para melhorar a precisão tributária.",
                }
                insights.append(item)
                self.db.add(
                    Insight(
                        empresa_id=empresa_id,
                        relatorio_analise_id=relatorio_analise_id,
                        tipo=item.get("tipo", "INSIGHT_GENERICO"),
                        valor_estimado=float(item.get("valor_estimado", 0) or 0),
                        impacto=item.get("impacto"),
                        descricao=item.get("descricao"),
                        recomendacao=item.get("recomendacao"),
                        ncm=item.get("ncm"),
                        payload_json=item,
                    )
                )
                self.db.flush()

        creditos_detectados = [i for i in insights if i.get("tipo") == "CREDITO_ST_ESTIMADO"]
        oportunidades = [i for i in insights if i.get("tipo") != "CREDITO_ST_ESTIMADO"]

        self.db.flush()
        resultados_engines = executar_engines(context)

        comparativo_regime = {}
        tax_planning = resultados_engines.get("tax_planning", {})
        comparacao = tax_planning.get("comparacao", {})
        carga_real = comparacao.get("lucro_real")
        carga_presumido = comparacao.get("lucro_presumido")

        if carga_real is not None and carga_presumido is not None:
            comparativo_regime = {
                "lucro_real": max(0, carga_real),
                "lucro_presumido": max(0, carga_presumido),
                "diferenca": abs((carga_real or 0) - (carga_presumido or 0)),
                "melhor_regime": tax_planning.get("melhor_regime")
            }

        motor_norm = 0
        # Normalização fiscal: impedir tributos negativos
        if "irpj" in resultados_engines:
            if resultados_engines["irpj"].get("total_irpj", 0) < 0:
                motor_norm += 1
                resultados_engines["irpj"]["total_irpj"] = 0
                resultados_engines["irpj"]["irpj"] = 0
                resultados_engines["irpj"]["adicional_irpj"] = 0

        if "csll" in resultados_engines:
            if resultados_engines["csll"].get("valor", 0) < 0:
                motor_norm += 1
                resultados_engines["csll"]["valor"] = 0

        self.db.flush()
        mapa_r = gerar_mapa_oportunidades(self.db, empresa_id)
        context_flags_final = merge_context_flags(
            context.get("context_flags"),
            mapa_r.get("context_flags"),
        )
        if context.get("uf_sem_dados_oficiais"):
            context_flags_final["uf_sem_dados_oficiais"] = True
        if motor_norm > 0:
            context_flags_final["valores_normalizados"] = True

        decomp = dict(mapa_r.get("decomposicao_impacto") or {})
        decomp["normalizacoes_aplicadas"] = int(decomp.get("normalizacoes_aplicadas", 0)) + motor_norm

        resultados_engines = anexar_flags_nos_resultados_engines(
            resultados_engines, context_flags_final
        )

        resultados_engines_enriquecidos = {}
        for nome, resultado in resultados_engines.items():
            res = dict(resultado)
            eng = ENGINES.get(nome)
            if eng is not None:
                cls = type(eng)
                res["_versao_engine"] = getattr(cls, "versao", None)
            resultados_engines_enriquecidos[nome] = res

            registro = EngineResultado(
                empresa_id=empresa_id,
                relatorio_analise_id=relatorio_analise_id,
                engine_nome=nome,
                resultado=res,
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
                "resultados_engines": resultados_engines_enriquecidos,
                "context_flags": context_flags_final,
                "decomposicao_impacto": decomp,
            }

        self.db.commit()

        return {
            "empresa_id": empresa_id,
            "oportunidades": oportunidades,
            "creditos_detectados": creditos_detectados,
            "risco_tributario": risco,
            "resultados_engines": resultados_engines_enriquecidos,
            "comparativo_regime": comparativo_regime,
            "context_flags": context_flags_final,
            "decomposicao_impacto": decomp,
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

    def _analisar_restituicao_st(self, empresa_id: int, context: dict):
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

        res_aliq = resolver_aliquota_e_mva(
            self.db,
            "",
            None,
            data_referencia=context.get("data_referencia"),
        )
        if not res_aliq.get("calculo_autorizado", True) or res_aliq.get("calculo_parcial", False):
            return insights
        st_devida = base_st_total * res_aliq["aliquota"]
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
        if res_aliq.get("confianca") != "oficial":
            insight["alerta_confianca"] = res_aliq.get(
                "aviso", "Dados MVA com confiança reduzida"
            )
            context["uf_sem_dados_oficiais"] = True

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

    def _analisar_st_sem_saida(self, context: dict):
        insights = []

        st_entradas = context.get("icms_pago", 0)
        st_saidas = context.get("icms_devido", 0)

        if not st_entradas:
            return insights

        st_saidas = st_saidas or 0

        st_em_estoque = st_entradas - st_saidas

        threshold_global = max(100.0, float(st_entradas or 0) * 0.05)
        if st_em_estoque <= threshold_global:
            return insights

        insight = {
            "tipo": "ST_SEM_SAIDA",
            "origem": "st_estoque",
            "impacto": "medio",
            "valor_estimado": round(st_em_estoque, 2),
            "descricao": f"ST estimada de R$ {round(st_em_estoque,2)} ainda não realizada em vendas.",
            "recomendacao": "Verificar itens em estoque ou divergências entre entradas e saídas."
        }

        insights.append(insight)

        return insights

    def _analisar_st_sem_saida_por_ncm(self, empresa_id: int):
        st_entrada = (
            self.db.query(
                NotaFiscalItem.ncm,
                func.sum(NotaFiscalItem.valor_st).label("st_entrada")
            )
            .join(NotaFiscalItem.documento)
            .filter(DocumentoFiscal.empresa_id == empresa_id)
            .filter(DocumentoFiscal.tipo == "entrada")
            .group_by(NotaFiscalItem.ncm)
            .all()
        )

        st_saida = (
            self.db.query(
                NotaFiscalItem.ncm,
                func.sum(NotaFiscalItem.valor_st).label("st_saida")
            )
            .join(NotaFiscalItem.documento)
            .filter(DocumentoFiscal.empresa_id == empresa_id)
            .filter(DocumentoFiscal.tipo == "saida")
            .group_by(NotaFiscalItem.ncm)
            .all()
        )

        mapa_saida = {row.ncm: row.st_saida for row in st_saida}

        # Threshold dinâmico baseado no volume real da empresa
        valores_entrada = [float(row.st_entrada or 0) for row in st_entrada]
        st_media = (sum(valores_entrada) / len(valores_entrada)) if valores_entrada else 0
        threshold_medio = max(50.0, st_media * 0.05)
        threshold_alto = max(500.0, st_media * 0.50)

        insights = []
        for row in st_entrada:
            ncm = row.ncm
            entrada = row.st_entrada or 0
            saida = mapa_saida.get(ncm, 0) or 0
            saldo = round(entrada - saida, 2)

            if saldo > threshold_medio:
                insights.append({
                    "tipo": "ESTOQUE_FANTASMA_NCM",
                    "tributo": "ST",
                    "categoria": "distorcao",
                    "ncm": ncm,
                    "impacto": "alto" if saldo > threshold_alto else "medio",
                    "valor_estimado": saldo,
                    "descricao": f"NCM {ncm}: ST de R$ {saldo} paga na entrada sem saida correspondente.",
                    "recomendacao": "Verificar se produto ainda esta em estoque ou houve perda/devolucao nao registada."
                })

        insights.sort(key=lambda x: x["valor_estimado"], reverse=True)
        return insights

    def _analisar_mva_oficial_divergente(self, empresa_id, context: dict):
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

            uf = uf_do_documento(item.documento)
            res = resolver_aliquota_e_mva(
                self.db,
                uf,
                item.ncm,
                data_referencia=item.documento.data_emissao,
            )

            if res.get("fonte") != "tabela":
                continue

            base = item.base_st or 0
            valor = item.valor_produto or 0

            if valor <= 0:
                continue

            mva_aplicada = (base - valor) / valor

            mva_oficial = float(res["mva"])

            diferenca = abs(mva_aplicada - mva_oficial)

            if diferenca > 0.1:
                insight = {
                    "tipo": "MVA_OFICIAL_DIVERGENTE",
                    "impacto": "medio",
                    "valor_estimado": 0,
                    "descricao": f"NCM {item.ncm} apresenta divergência entre MVA aplicada e MVA oficial.",
                    "recomendacao": "Verificar parametrização fiscal e possível restituição de ST.",
                }
                if res.get("confianca") != "oficial":
                    insight["alerta_confianca"] = res.get(
                        "aviso", "Dados MVA com confiança reduzida"
                    )
                    context["uf_sem_dados_oficiais"] = True
                insights.append(insight)

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
            # Guard NCM — alinhado com _analisar_mva_oficial_divergente
            if not item.ncm:
                continue

            valor = item.valor_produto or 0
            st_pago = item.valor_st or 0

            if valor <= 0:
                continue

            uf = uf_do_documento(item.documento)

            # B13-OPS-09: resolvedor soberano — elimina BYPASS-01
            res = resolver_aliquota_e_mva(
                self.db,
                uf,
                item.ncm,
                data_referencia=item.documento.data_emissao,
            )

            # Guard normativo: só decide com resolução autorizada e não parcial
            if not res.get("calculo_autorizado") or res.get("calculo_parcial"):
                continue

            decisao = decidir_acao_st(
                valor_produto=valor,
                st_pago=st_pago,
                mva=res["mva"],        # já decimal — resolvedor normaliza
                aliquota=res["aliquota"],
            )

            if decisao["decisao"] != "OPERACAO_CORRETA":
                insights.append({
                    "tipo": decisao["decisao"],
                    "impacto": "alto",
                    "valor_estimado": decisao["valor_estimado"],
                    "descricao": decisao["descricao"],
                    "recomendacao": decisao["recomendacao"],
                })

        return insights
