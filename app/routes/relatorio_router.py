from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models
from app.models import RelatorioAnalise
from app.database import get_db
from app.routes.imposto_router import DadosImposto
from app.security import get_usuario_atual, verificar_empresa_do_usuario
from app.services.analysis_orchestrator import executar_analise_xml
from app.services.registro_analise_service import executar_e_registrar_analise_xml
from app.services.usage_service import LimiteAnalisesAtingidoError
from app.services.assistente_service import (
    _obter_dados_fiscais_planejamento,
    _obter_dados_fiscais_recuperacao,
    simular_planejamento_tributario,
    simular_recuperacao_tributaria,
)
from app.services.insights_engine import InsightEngine
from app.services.pdf_report_service import gerar_pdf_imposto, gerar_pdf_relatorio
from app.services.imposto_service import calcular_imposto_simples
from app.services.score_global_tributario_service import calcular_score_global_tributario
from app.services.engine_resultado_service import EngineResultadoService
from app.services.context_flags_service import default_context_flags
from app.xml_security import validar_upload_xml

router = APIRouter()

ANALYSIS_TYPES = ("tax_recovery", "tax_planning")  # mei_tax: use POST /mei_tax e GET /mei_tax/{id}


def _pagamento_confirmado(usuario: models.User, perfil_id: int, db: Session) -> bool:
    """
    Verifica se o usuário pagou para acessar o relatório completo do perfil.
    Atualmente usa consulta_paga no usuário. Futuro: tabela consultas_pagamento por perfil.
    """
    verificar_empresa_do_usuario(perfil_id, usuario, db)
    return bool(usuario.consulta_paga)


@router.get("/empresas/{empresa_id}/engines")
def resultados_engines(
    empresa_id: int,
    db: Session = Depends(get_db),
    usuario_atual: models.User = Depends(get_usuario_atual),
):
    verificar_empresa_do_usuario(empresa_id, usuario_atual, db)
    service = EngineResultadoService(db)
    return service.listar_por_empresa(empresa_id)


@router.post("/gerar-relatorio")
async def gerar_relatorio(
    file: UploadFile = File(...),
    empresa_id: int | None = None,
    db: Session = Depends(get_db),
    usuario_atual: models.User = Depends(get_usuario_atual),
):
    """Retorna o relatório fiscal estruturado (preview JSON). Persiste em relatorios_analise."""
    xml_bytes = await validar_upload_xml(file)
    user_id = usuario_atual.id
    limite_analises = 100
    if usuario_atual.plano:
        limite_analises = getattr(usuario_atual.plano, "limite_analises", 100) or 100
    if empresa_id:
        verificar_empresa_do_usuario(empresa_id, usuario_atual, db)
        emp = db.query(models.Empresa).filter(models.Empresa.id == empresa_id).first()
        user_id = emp.user_id if emp else usuario_atual.id
    relatorio_obj = None
    if user_id:
        try:
            relatorio_obj, analise = executar_e_registrar_analise_xml(
                db, xml_bytes, user_id, empresa_id, limite_analises=limite_analises
            )
        except LimiteAnalisesAtingidoError as e:
            raise HTTPException(status_code=429, detail=str(e))
    else:
        analise = executar_analise_xml(xml_bytes)
    relatorio = _montar_relatorio(analise, empresa_id, db)
    if relatorio_obj:
        relatorio["relatorio_id"] = relatorio_obj.id
    return {
        "status": "processado",
        "mensagem": "Análise concluída. Desbloqueie o relatório completo para visualizar os detalhes.",
        "relatorio_id": relatorio.get("relatorio_id"),
    }


def _montar_relatorio(analise: dict, empresa_id: int | None, db: Session) -> dict:
    """Monta o relatório estruturado a partir da análise para PDF ou JSON."""
    score = None
    if empresa_id:
        score_dict = calcular_score_global_tributario(db, empresa_id)
        score = score_dict.get("score_global_tributario")
        if score is not None:
            score = round(score, 2)

    previsao = analise.get("previsao_recuperacao") or {}
    valor_estimado = previsao.get("potencial_recuperacao_nota", 0)

    insights_raw = analise.get("insights") or []
    insights = [
        i.get("descricao") or i.get("tipo", str(i))
        for i in insights_raw
        if isinstance(i, dict)
    ]

    return {
        "empresa_id": empresa_id,
        "potencial_recuperacao": {"valor_estimado": valor_estimado},
        "context_flags": analise.get("context_flags") or default_context_flags(),
        "decomposicao_impacto": analise.get("decomposicao_impacto"),
        "insights": insights,
        "score_global": score,
        "credito_pis_cofins_estimado": (
            analise.get("resultados_engines", {})
            .get("pis_cofins", {})
            .get("comparativo_icms_base", {})
            .get("credito_total_estimado")
        ),
        "irpj_total": (
            analise.get("resultados_engines", {})
            .get("irpj", {})
            .get("total_irpj")
        ),
        "csll_total": (
            analise.get("resultados_engines", {})
            .get("csll", {})
            .get("valor")
        ),
        "mei_das_mensal": (
            analise.get("resultados_engines", {})
            .get("mei", {})
            .get("das_mensal")
        ),
        "mei_alertas": (
            analise.get("resultados_engines", {})
            .get("mei", {})
            .get("alertas")
        ),
        "cpf_imposto_mensal": (
            analise.get("resultados_engines", {})
            .get("cpf", {})
            .get("imposto_mensal")
        ),
        "cpf_base_calculo": (
            analise.get("resultados_engines", {})
            .get("cpf", {})
            .get("base_calculo")
        ),
        "cpf_alertas": (
            analise.get("resultados_engines", {})
            .get("cpf", {})
            .get("alertas")
        ),
        "cpf_base_incompleta": (
            analise.get("resultados_engines", {})
            .get("cpf", {})
            .get("base_incompleta")
        ),
        "cpf_origem_base": (
            analise.get("resultados_engines", {})
            .get("cpf", {})
            .get("origem_base")
        ),
        "economia_regime_estimado": (
            abs(
                analise.get("comparativo_regime", {}).get("lucro_real", 0)
                - analise.get("comparativo_regime", {}).get("lucro_presumido", 0)
            )
        ),
        "melhor_regime": (
            analise.get("comparativo_regime", {}).get("melhor_regime")
        ),
        "recuperacao_imediata_fiscal": round(
            (
                analise.get("resultados_engines", {})
                .get("tax_recovery", {})
                .get("total_creditos")
                or 0
            ),
            2,
        ),
        "otimizacao_estimada": round(
            (
                (
                    analise.get("resultados_engines", {})
                    .get("pis_cofins", {})
                    .get("comparativo_icms_base", {})
                    .get("credito_total_estimado")
                    or 0
                )
                + (
                    analise.get("comparativo_regime", {})
                    .get("diferenca")
                    or 0
                )
            ),
            2,
        ),
        "capital_tributario_em_estoque": "saldo_fiscal_por_ncm",
        "recuperacao_imediata_fiscal_natureza": "recuperavel_fiscal",
        "otimizacao_estimada_natureza": "estimado",
        "capital_tributario_em_estoque_natureza": "saldo_fiscal_por_ncm",
        "potencial_total_recuperacao": round(
            (
                (
                    analise.get("resultados_engines", {})
                    .get("pis_cofins", {})
                    .get("comparativo_icms_base", {})
                    .get("credito_total_estimado")
                    or 0
                )
                + (analise.get("comparativo_regime", {}).get("diferenca") or 0)
                + (
                    analise.get("resultados_engines", {})
                    .get("tax_recovery", {})
                    .get("total_creditos")
                    or 0
                )
            ),
            2,
        ),
        "credito_pis_cofins_natureza": "estimado",
        "economia_regime_natureza": "estimado",
        "tax_recovery_natureza": "recuperavel_fiscal",
        "potencial_total_recuperacao_natureza": "misto_estimado",
        "estoque_fantasma_natureza": "saldo_fiscal_por_ncm",
        "estoque_fantasma_fonte": "ESTOQUE_FANTASMA_NCM",
        "estoque_fantasma_interpretacao": (
            "valor representa imposto pago na entrada ainda nao compensado em vendas; "
            "nao e credito imediato"
        ),
    }


class GerarRelatorioRequest(BaseModel):
    """Payload para gerar relatório completo (pós-pagamento)."""
    perfil_id: int


def _gerar_pdf_relatorio_completo(perfil_id: int, db: Session):
    """Orquestra geração do PDF do relatório completo a partir do mapa de oportunidades."""
    from app.services.mapa_oportunidades_service import gerar_mapa_oportunidades
    from app.services.score_global_tributario_service import calcular_score_global_tributario

    mapa = gerar_mapa_oportunidades(db, perfil_id)
    score_dict = calcular_score_global_tributario(db, perfil_id)
    score = score_dict.get("score_global_tributario")
    rows = db.query(models.Insight).filter(models.Insight.empresa_id == perfil_id).limit(20).all()
    insights = [r.descricao or r.tipo for r in rows if r.descricao or r.tipo] or ["Análise fiscal disponível."]

    relatorio = {
        "empresa_id": perfil_id,
        "potencial_recuperacao": {"valor_estimado": mapa.get("restituicao_st", 0) or 0},
        "context_flags": mapa.get("context_flags") or default_context_flags(),
        "decomposicao_impacto": mapa.get("decomposicao_impacto"),
        "insights": insights,
        "score_global": round(score, 2) if score is not None else None,
    }
    return gerar_pdf_relatorio(relatorio)


@router.post("/gerar")
async def gerar_relatorio(
    payload: GerarRelatorioRequest,
    db: Session = Depends(get_db),
    usuario_atual: models.User = Depends(get_usuario_atual),
):
    """
    Gera e retorna o relatório completo em PDF. Protegido por paywall.
    POST /relatorio/gerar — fluxo: checkout → pagamento → este endpoint.
    """
    if not _pagamento_confirmado(usuario_atual, payload.perfil_id, db):
        raise HTTPException(status_code=402, detail="Pagamento necessário")
    pdf = _gerar_pdf_relatorio_completo(payload.perfil_id, db)
    return StreamingResponse(
        iter([pdf.getvalue()]),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=relatorio-fiscal.pdf"},
    )


@router.get("/relatorio-pdf/{perfil_id}")
async def download_relatorio_pdf(
    perfil_id: int,
    db: Session = Depends(get_db),
    usuario_atual: models.User = Depends(get_usuario_atual),
):
    """
    Baixa o relatório fiscal em PDF. Exige pagamento confirmado.
    GET /relatorio/relatorio-pdf/{perfil_id}
    """
    if not _pagamento_confirmado(usuario_atual, perfil_id, db):
        raise HTTPException(status_code=402, detail="Pagamento necessário")
    pdf = _gerar_pdf_relatorio_completo(perfil_id, db)
    return StreamingResponse(
        iter([pdf.getvalue()]),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=relatorio-fiscal.pdf"},
    )


@router.post("/relatorio-pdf")
async def relatorio_pdf(
    file: UploadFile = File(...),
    empresa_id: int | None = None,
    db: Session = Depends(get_db),
    usuario_atual: models.User = Depends(get_usuario_atual),
):
    """Gera e retorna o relatório fiscal em PDF para download. Persiste em relatorios_analise. Exige consulta_paga."""
    if not usuario_atual.consulta_paga:
        raise HTTPException(
            status_code=403,
            detail="Pagamento necessário para acessar o relatório.",
        )
    xml_bytes = await validar_upload_xml(file)
    user_id = usuario_atual.id
    limite_analises = 100
    if usuario_atual.plano:
        limite_analises = getattr(usuario_atual.plano, "limite_analises", 100) or 100
    if empresa_id:
        verificar_empresa_do_usuario(empresa_id, usuario_atual, db)
        emp = db.query(models.Empresa).filter(models.Empresa.id == empresa_id).first()
        user_id = emp.user_id if emp else usuario_atual.id
    relatorio_obj = None
    if user_id:
        try:
            relatorio_obj, analise = executar_e_registrar_analise_xml(
                db, xml_bytes, user_id, empresa_id, limite_analises=limite_analises
            )
        except LimiteAnalisesAtingidoError as e:
            raise HTTPException(status_code=429, detail=str(e))
    else:
        analise = executar_analise_xml(xml_bytes)
    relatorio = _montar_relatorio(analise, empresa_id, db)
    if relatorio_obj:
        relatorio["relatorio_id"] = relatorio_obj.id
    pdf = gerar_pdf_relatorio(relatorio)

    return StreamingResponse(
        iter([pdf.getvalue()]),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=relatorio-fiscal.pdf"},
    )


@router.get("/{relatorio_id:int}")
def obter_relatorio(
    relatorio_id: int,
    db: Session = Depends(get_db),
    usuario_atual: models.User = Depends(get_usuario_atual),
):
    rel = db.query(RelatorioAnalise).filter(RelatorioAnalise.id == relatorio_id).first()

    if not rel:
        raise HTTPException(status_code=404, detail="Relatório não encontrado")

    if rel.user_id != usuario_atual.id:
        raise HTTPException(status_code=403, detail="Acesso negado")

    # Fallback para base atual: RelatorioAnalise não possui consulta_paga.
    # Se no futuro existir coluna por relatório, ela terá prioridade.
    consulta_paga_relatorio = getattr(rel, "consulta_paga", None)
    pagamento_ok = (
        bool(consulta_paga_relatorio)
        if consulta_paga_relatorio is not None
        else bool(usuario_atual.consulta_paga)
    )

    if not pagamento_ok:
        return {
            "status": "bloqueado",
            "mensagem": "Pagamento necessário",
            "relatorio_id": rel.id,
        }

    return rel.resultado_json


@router.get("/{analysis_type}")
def obter_relatorio_por_tipo(
    analysis_type: str,
    usuario_atual: models.User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    """
    Libera relatório após pagamento. Fluxo unificado: empresa → planejamento → recuperação.
    Rotas: /relatorio/tax_recovery | /relatorio/tax_planning
    MEI: POST /relatorio/mei_tax → GET /relatorio/mei_tax/{id}
    """
    if analysis_type not in ANALYSIS_TYPES:
        raise HTTPException(
            status_code=404,
            detail=f"Tipo inválido. Use: {', '.join(ANALYSIS_TYPES)}",
        )
    if not usuario_atual.consulta_paga:
        raise HTTPException(
            status_code=402,
            detail="Libere a análise fiscal para acessar o relatório.",
        )

    empresa_id = usuario_atual.empresas[0].id if usuario_atual.empresas else None
    pergunta_placeholder = ""

    if analysis_type == "tax_recovery":
        dados = _obter_dados_fiscais_recuperacao(pergunta_placeholder, usuario_atual, db)
        if dados:
            resultado = simular_recuperacao_tributaria(dados)
            return {"analysis_type": "tax_recovery", "relatorio": resultado}
        if empresa_id:
            engine = InsightEngine(db)
            resultado = engine.gerar_insights_empresa(empresa_id)
            return {"analysis_type": "tax_recovery", "relatorio": resultado}
        raise HTTPException(
            status_code=400,
            detail="Vincule uma empresa com NF-e ou informe faturamento para gerar o relatório.",
        )

    if analysis_type == "tax_planning":
        dados = _obter_dados_fiscais_planejamento(pergunta_placeholder, usuario_atual, db)
        if dados:
            resultado = simular_planejamento_tributario(dados)
            return {"analysis_type": "tax_planning", "relatorio": resultado}
        raise HTTPException(
            status_code=400,
            detail="Informe o faturamento ou vincule uma empresa com NF-e.",
        )


@router.post("/mei_tax")
async def gerar_relatorio_mei_tax(
    dados: DadosImposto,
    usuario_atual: models.User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    """
    Gera e persiste relatório MEI/CPF. Retorna o ID para download via GET /relatorio/mei_tax/{id}.
    Fluxo: assistente → pagamento → POST /relatorio/mei_tax.
    """
    if not usuario_atual.consulta_paga:
        raise HTTPException(
            status_code=402,
            detail="Libere a análise fiscal para acessar o relatório.",
        )
    resultado = calcular_imposto_simples(
        faturamento=dados.faturamento_mensal,
        despesas=dados.despesas,
        tipo=dados.tipo_usuario,
    )
    rel = models.RelatorioAnalise(
        user_id=usuario_atual.id,
        analysis_type="mei_tax",
        status="ok",
        resultado_json=resultado,
    )
    db.add(rel)
    db.commit()
    db.refresh(rel)
    return {"id": rel.id}


@router.get("/mei_tax/{relatorio_id}")
async def buscar_relatorio_mei_tax(
    relatorio_id: int,
    usuario_atual: models.User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    """Busca relatório MEI/CPF por ID (retorna PDF)."""
    rel = db.query(models.RelatorioAnalise).filter(
        models.RelatorioAnalise.id == relatorio_id,
        models.RelatorioAnalise.user_id == usuario_atual.id,
        models.RelatorioAnalise.analysis_type == "mei_tax",
    ).first()
    if not rel:
        raise HTTPException(status_code=404, detail="Relatório não encontrado.")
    resultado = rel.resultado_json
    pdf = gerar_pdf_imposto(resultado)
    return StreamingResponse(
        iter([pdf.getvalue()]),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=relatorio-mei.pdf"},
    )


@router.post("/imposto-pdf")
async def imposto_pdf(
    dados: DadosImposto,
    usuario_atual: models.User = Depends(get_usuario_atual),
):
    """
    Gera PDF com cálculo detalhado de imposto (MEI ou CPF/autônomo).
    Fluxo: /imposto/calcular → preview → pagamento → /relatorio/imposto-pdf.
    """
    resultado = calcular_imposto_simples(
        faturamento=dados.faturamento_mensal,
        despesas=dados.despesas,
        tipo=dados.tipo_usuario,
    )
    pdf = gerar_pdf_imposto(resultado)
    return StreamingResponse(
        iter([pdf.getvalue()]),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=relatorio-imposto.pdf"},
    )
