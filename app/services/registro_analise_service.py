"""
Serviço central de registro de execução de análise.

Conecta Motor Fiscal, Engines, Agentes e Score ao container relatorios_analise.
Cada execução vira um registro completo auditável.
"""

import logging
import time
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from app.models import Empresa, RelatorioAnalise, AlertaFiscal
from app.services.analysis_orchestrator import executar_analise_xml
from app.xml_service import DuplicataFiscalError, processar_e_persistir_xml
from app.services.score_global_tributario_service import calcular_score_global_tributario
from app.services.usage_service import verificar_limite_analises, incrementar_uso_analise
from app.services.resultado_provenance_service import (
    fingerprint_resultado_json,
    selar_resultado_nao_mei,
)

logger = logging.getLogger(__name__)


def criar_registro_analise(
    db,
    user_id: int,
    analysis_type: str,
    empresa_id: int | None = None,
    xml_chave: str | None = None,
) -> RelatorioAnalise:
    """Cria registro inicial de análise (status=processando)."""
    rel = RelatorioAnalise(
        user_id=user_id,
        empresa_id=empresa_id,
        analysis_type=analysis_type,
        xml_chave=xml_chave,
        status="processando",
    )
    db.add(rel)
    db.commit()
    db.refresh(rel)
    return rel


def finalizar_registro_analise(
    db,
    relatorio_id: int,
    *,
    status: str = "ok",
    tempo_execucao: float | None = None,
    total_alertas: int | None = None,
    score_resultante: float | None = None,
    resultado_json: dict | None = None,
):
    """Atualiza registro com resultado final da execução."""
    rel = db.query(RelatorioAnalise).filter(RelatorioAnalise.id == relatorio_id).first()
    if not rel:
        return
    if status == "cancelado":
        rel.status = "cancelado"
    else:
        rel.status = status
    if tempo_execucao is not None:
        rel.tempo_execucao = tempo_execucao
    if total_alertas is not None:
        rel.total_alertas = total_alertas
    if score_resultante is not None:
        rel.score_resultante = score_resultante
    if resultado_json is not None:
        rel.resultado_json = resultado_json
        rel.fingerprint = fingerprint_resultado_json(resultado_json)
    db.commit()


def contar_alertas_empresa(db, empresa_id: int, relatorio_id: int | None = None) -> int:
    """Conta alertas da empresa (opcionalmente vinculados ao relatório)."""
    q = db.query(AlertaFiscal).filter(AlertaFiscal.empresa_id == empresa_id)
    if relatorio_id is not None:
        q = q.filter(AlertaFiscal.relatorio_analise_id == relatorio_id)
    return q.count()


def executar_e_registrar_analise_xml(
    db,
    xml_bytes: bytes,
    user_id: int,
    empresa_id: int | None = None,
    limite_analises: int = 100,
) -> tuple[RelatorioAnalise, dict]:
    """
    Executa análise de XML e persiste em relatorios_analise.
    Motor fiscal grava execução, score grava resultado final.
    Verifica limite de uso antes e registra uso após conclusão.
    Retorna (RelatorioAnalise, resultado).
    """
    verificar_limite_analises(db, empresa_id, limite=limite_analises)

    inicio = time.perf_counter()
    resultado = executar_analise_xml(xml_bytes)

    if empresa_id and not resultado.get("dados_fiscais", {}).get("erro"):
        empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
        if empresa and empresa.user_id:
            class _UsuarioProxy:
                def __init__(self, user_id):
                    self.id = user_id

            usuario_proxy = _UsuarioProxy(empresa.user_id)
            try:
                processar_e_persistir_xml(
                    db=db,
                    usuario_atual=usuario_proxy,
                    empresa=empresa,
                    xml_bytes=xml_bytes,
                )
            except DuplicataFiscalError:
                logger.info(
                    "persistencia_xml_ignorada_duplicata empresa_id=%s",
                    empresa_id,
                )

    tempo = round(time.perf_counter() - inicio, 4)

    xml_chave = None
    if resultado.get("dados_fiscais") and not resultado["dados_fiscais"].get("erro"):
        xml_chave = resultado["dados_fiscais"].get("chave_nfe")

    if empresa_id and xml_chave:
        rel_existente = (
            db.query(RelatorioAnalise)
            .filter(
                RelatorioAnalise.empresa_id == empresa_id,
                RelatorioAnalise.analysis_type == "xml_analise",
                RelatorioAnalise.xml_chave == xml_chave,
            )
            .order_by(RelatorioAnalise.id.desc())
            .first()
        )
        if rel_existente:
            return rel_existente, {
                "status": "duplicado",
                "relatorio_id": rel_existente.id,
                "xml_chave": xml_chave,
            }

    try:
        rel = criar_registro_analise(
            db, user_id, "xml_analise", empresa_id=empresa_id, xml_chave=xml_chave
        )
    except IntegrityError:
        db.rollback()
        if empresa_id and xml_chave:
            rel_existente = (
                db.query(RelatorioAnalise)
                .filter(
                    RelatorioAnalise.empresa_id == empresa_id,
                    RelatorioAnalise.analysis_type == "xml_analise",
                    RelatorioAnalise.xml_chave == xml_chave,
                )
                .order_by(RelatorioAnalise.id.desc())
                .first()
            )
            if rel_existente:
                return rel_existente, {
                    "status": "duplicado",
                    "relatorio_id": rel_existente.id,
                    "xml_chave": xml_chave,
                }
        raise

    if empresa_id:
        try:
            from app.services.insights_engine import InsightEngine

            engine = InsightEngine(db)
            engine.gerar_insights_empresa(
                empresa_id=empresa_id,
                relatorio_analise_id=rel.id,
            )
        except Exception:
            logger.exception(
                "Falha ao gerar insights (InsightEngine): empresa_id=%s relatorio_analise_id=%s",
                empresa_id,
                rel.id,
            )

    score_resultante = None
    if empresa_id:
        try:
            score_dict = calcular_score_global_tributario(db, empresa_id)
            s = score_dict.get("score_global_tributario")
            if s is not None:
                score_resultante = round(float(s), 2)
        except Exception:
            logger.exception(
                "Falha ao calcular score global: empresa_id=%s",
                empresa_id,
            )

    total_alertas = contar_alertas_empresa(db, empresa_id) if empresa_id else 0

    resultado_persistido = selar_resultado_nao_mei(
        resultado,
        producer_id="app.services.analysis_orchestrator.executar_analise_xml",
    )

    finalizar_registro_analise(
        db,
        rel.id,
        status="erro" if resultado.get("dados_fiscais", {}).get("erro") else "ok",
        tempo_execucao=tempo,
        total_alertas=total_alertas,
        score_resultante=score_resultante,
        resultado_json=resultado_persistido,
    )
    incrementar_uso_analise(db, empresa_id)
    db.refresh(rel)
    return rel, resultado
