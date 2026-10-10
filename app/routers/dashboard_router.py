from datetime import date
from uuid import UUID
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, StrictStr, field_validator
from sqlalchemy.exc import SQLAlchemyError

from app.services.mei_receita_informada_writer import (
    MeiReceitaInformadaWriter, MeiReceitaInformadaWriterError,
)
from app.services.mei_receita_anual_apuracao import apurar_receitas_anuais

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.models import AlertaFiscal, RelatorioAnalise, EngineResultado
from app.security import get_usuario_atual, tenant_empresa, verificar_empresa_do_usuario, verificar_acesso_relatorio
from app.services.resultado_provenance_service import (
    ResultadoProvenanceError,
    verificar_resultado_persistido,
)
from app.services.analysis_types import ANALYSIS_TYPE_MEI_TAX
from app.services.mei_receita_documental_selection import (
    selecionar_documentos_para_conferencia,
)
from app.services.mei_emitente_observation import comparar_emitente_observado
from app.services.mei_receita_composicao_consultiva import compor_receitas_mei

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


class ReceitaInformadaEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")
    identidade_receita: StrictStr
    data_receita: StrictStr
    valor: StrictStr
    categoria: StrictStr

    @field_validator("identidade_receita")
    @classmethod
    def identidade_canonica(cls, value):
        try:
            identity = UUID(value)
        except ValueError:
            raise ValueError("IDENTIDADE_INVALIDA") from None
        if str(identity) != value or identity.version != 4:
            raise ValueError("IDENTIDADE_INVALIDA")
        return value

    @field_validator("data_receita")
    @classmethod
    def data_canonica(cls, value):
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            raise ValueError("DATA_INVALIDA") from None
        if parsed.isoformat() != value or parsed.year < 1900:
            raise ValueError("DATA_INVALIDA")
        return value

    @field_validator("valor")
    @classmethod
    def valor_canonico(cls, value):
        import re
        if not re.fullmatch(r"(?:0|[1-9][0-9]{0,12})\.[0-9]{2}", value, re.ASCII):
            raise ValueError("VALOR_INVALIDO")
        return value

    @field_validator("categoria")
    @classmethod
    def categoria_valida(cls, value):
        if value not in ("comercio_industria", "servicos"):
            raise ValueError("CATEGORIA_INVALIDA")
        return value


def _exigir_mei_ativo_receitas(empresa):
    if empresa.regime_tributario != "mei" or empresa.status_empresa != "ativa":
        raise HTTPException(status_code=403, detail="RECEITAS_INFORMADAS_INDISPONIVEIS")


def _receita_informada_publica(row):
    return {
        "id": row.id, "empresa_id": row.empresa_id,
        "identidade_receita": row.identidade_receita,
        "data_receita": row.data_receita.isoformat(),
        "valor": format(row.valor, ".2f"), "categoria": row.categoria,
        "origem": row.origem,
    }


@router.post("/mei/{empresa_id}/receitas-informadas")
def registrar_receita_informada_mei(
    dados: ReceitaInformadaEntrada,
    response: Response,
    empresa: models.Empresa = Depends(tenant_empresa),
    usuario: models.User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    _exigir_mei_ativo_receitas(empresa)
    response.headers["Cache-Control"] = "private, no-store"
    try:
        row = MeiReceitaInformadaWriter(db).registrar(
            empresa_id=empresa.id, usuario_id=usuario.id, **dados.model_dump()
        )
        resultado = _receita_informada_publica(row)
        db.commit()
        return resultado
    except MeiReceitaInformadaWriterError:
        db.rollback()
        # A validated request conflicts only when its identity already exists.
        # Infrastructure failures without a saved identity remain unavailable.
        try:
            existing = db.query(models.MeiReceitaInformada).filter(
                models.MeiReceitaInformada.empresa_id == empresa.id,
                models.MeiReceitaInformada.identidade_receita == dados.identidade_receita,
            ).first()
        except SQLAlchemyError:
            raise HTTPException(status_code=503, detail="RECEITAS_INFORMADAS_INDISPONIVEIS") from None
        if existing is not None and (
            existing.usuario_id != usuario.id
            or existing.data_receita.isoformat() != dados.data_receita
            or existing.valor != Decimal(dados.valor)
            or existing.categoria != dados.categoria
            or existing.origem != "informada_sem_nota"
        ):
            raise HTTPException(status_code=409, detail="RECEITA_IDENTIDADE_CONFLITANTE") from None
        raise HTTPException(status_code=503, detail="RECEITAS_INFORMADAS_INDISPONIVEIS") from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="RECEITAS_INFORMADAS_INDISPONIVEIS") from None


@router.get("/mei/{empresa_id}/receitas-informadas")
def apurar_receitas_informadas_mei(
    response: Response,
    ano_calendario: int = Query(..., ge=1900, le=9999),
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    _exigir_mei_ativo_receitas(empresa)
    response.headers["Cache-Control"] = "private, no-store"
    try:
        rows = db.query(models.MeiReceitaInformada).filter(
            models.MeiReceitaInformada.empresa_id == empresa.id,
            models.MeiReceitaInformada.data_receita.between(
                date(ano_calendario, 1, 1), date(ano_calendario, 12, 31)
            ),
        ).order_by(models.MeiReceitaInformada.id).limit(100001).all()
        if len(rows) > 100000:
            raise ValueError("RECEITAS_INVALIDAS")
        receitas = []
        for row in rows:
            if row.usuario_id != empresa.user_id or row.origem != "informada_sem_nota":
                raise ValueError("RECEITA_ORIGEM_INVALIDA")
            item = _receita_informada_publica(row)
            item.pop("id")
            receitas.append({**item, "estado": "vigente"})
        return apurar_receitas_anuais(
            empresa_id=empresa.id, ano_calendario=ano_calendario, receitas=receitas
        )
    except (SQLAlchemyError, ValueError, TypeError, AttributeError):
        raise HTTPException(status_code=503, detail="RECEITAS_INFORMADAS_INDISPONIVEIS") from None


@router.get("/mei/{empresa_id}/conferencia-documental")
def listar_documentos_para_conferencia_mei(
    response: Response,
    ano_calendario: int = Query(..., ge=1900, le=9999),
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    """Read owned documentary observations without certifying revenue."""
    documentos = (
        db.query(models.DocumentoFiscal)
        .filter(
            models.DocumentoFiscal.empresa_id == empresa.id,
            or_(
                models.DocumentoFiscal.data_emissao.is_(None),
                models.DocumentoFiscal.data_emissao.between(
                    date(ano_calendario, 1, 1), date(ano_calendario, 12, 31)
                ),
            ),
        )
        .order_by(models.DocumentoFiscal.id)
        .limit(100001)
        .all()
    )
    if len(documentos) > 100000:
        raise HTTPException(status_code=503, detail="CONFERENCIA_DOCUMENTAL_INDISPONIVEL")
    metadados = [
        {
            "id": documento.id,
            "empresa_id": documento.empresa_id,
            "data_emissao": documento.data_emissao.isoformat()
            if documento.data_emissao is not None else None,
            "tipo": documento.tipo,
            "valor_total": documento.valor_total,
            "chave_nfe": documento.chave_nfe,
            "conteudo_sha256": documento.conteudo_sha256,
        }
        for documento in documentos
    ]
    try:
        resultado = selecionar_documentos_para_conferencia(
            empresa_id=empresa.id,
            ano_calendario=ano_calendario,
            documentos=metadados,
        )
    except ValueError:
        raise HTTPException(
            status_code=503, detail="CONFERENCIA_DOCUMENTAL_INDISPONIVEL"
        ) from None
    resultado["observacoes_emitente"] = [
        comparar_emitente_observado(
            documento_id=documento.id,
            cnpj_empresa=empresa.cnpj,
            cnpj_emitente=documento.cnpj_emitente,
        )
        for documento in documentos
    ]
    itens = (
        db.query(models.ItemFiscal)
        .join(models.DocumentoFiscal,
              models.ItemFiscal.documento_id == models.DocumentoFiscal.id)
        .filter(
            models.DocumentoFiscal.empresa_id == empresa.id,
            or_(
                models.DocumentoFiscal.data_emissao.is_(None),
                models.DocumentoFiscal.data_emissao.between(
                    date(ano_calendario, 1, 1), date(ano_calendario, 12, 31)
                ),
            ),
        )
        .order_by(models.ItemFiscal.documento_id, models.ItemFiscal.id)
        .limit(100001)
        .all()
    )
    if len(itens) > 100000:
        raise HTTPException(status_code=503, detail="CONFERENCIA_DOCUMENTAL_INDISPONIVEL")
    itens_por_documento = {documento.id: [] for documento in documentos}
    for item in itens:
        if item.documento_id not in itens_por_documento:
            raise HTTPException(status_code=503, detail="CONFERENCIA_DOCUMENTAL_INDISPONIVEL")
        itens_por_documento[item.documento_id].append(
            {"item_id": item.id, "cfop_observado": item.cfop}
        )
    resultado["observacoes_operacao"] = [
        {
            "documento_id": documento.id,
            "natureza_operacao_observada": documento.natureza_operacao_observada,
            "finalidade_emissao_observada": documento.finalidade_emissao_observada,
            "itens": itens_por_documento[documento.id],
        }
        for documento in documentos
    ]
    response.headers["Cache-Control"] = "private, no-store"
    return resultado


@router.get("/mei/{empresa_id}/composicao-consultiva")
def consultar_composicao_consultiva_mei(
    response: Response,
    ano_calendario: int = Query(..., ge=1900, le=9999),
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    """Composicao somente leitura, sem certificar receita documental."""
    _exigir_mei_ativo_receitas(empresa)
    response.headers["Cache-Control"] = "private, no-store"

    inicio = date(ano_calendario, 1, 1)
    fim = date(ano_calendario, 12, 31)

    try:
        linhas_receitas = (
            db.query(models.MeiReceitaInformada)
            .filter(
                models.MeiReceitaInformada.empresa_id == empresa.id,
                models.MeiReceitaInformada.data_receita.between(inicio, fim),
            )
            .order_by(models.MeiReceitaInformada.id)
            .limit(100001)
            .all()
        )

        if len(linhas_receitas) > 100000:
            raise ValueError("RECEITAS_INVALIDAS")

        receitas = []
        for linha in linhas_receitas:
            if (
                linha.usuario_id != empresa.user_id
                or linha.origem != "informada_sem_nota"
            ):
                raise ValueError("RECEITA_ORIGEM_INVALIDA")

            item = _receita_informada_publica(linha)
            item.pop("id")
            receitas.append({**item, "estado": "vigente"})

        apuracao = apurar_receitas_anuais(
            empresa_id=empresa.id,
            ano_calendario=ano_calendario,
            receitas=receitas,
        )

        linhas_documentos = (
            db.query(models.DocumentoFiscal)
            .filter(
                models.DocumentoFiscal.empresa_id == empresa.id,
                or_(
                    models.DocumentoFiscal.data_emissao.is_(None),
                    models.DocumentoFiscal.data_emissao.between(inicio, fim),
                ),
            )
            .order_by(models.DocumentoFiscal.id)
            .limit(100001)
            .all()
        )

        if len(linhas_documentos) > 100000:
            raise ValueError("DOCUMENTOS_INVALIDOS")

        metadados = [
            {
                "id": documento.id,
                "empresa_id": documento.empresa_id,
                "data_emissao": (
                    documento.data_emissao.isoformat()
                    if documento.data_emissao is not None
                    else None
                ),
                "tipo": documento.tipo,
                "valor_total": documento.valor_total,
                "chave_nfe": documento.chave_nfe,
                "conteudo_sha256": documento.conteudo_sha256,
            }
            for documento in linhas_documentos
        ]

        selecao = selecionar_documentos_para_conferencia(
            empresa_id=empresa.id,
            ano_calendario=ano_calendario,
            documentos=metadados,
        )

        return compor_receitas_mei(
            empresa_id=empresa.id,
            ano_calendario=ano_calendario,
            apuracao=apuracao,
            selecao_documental=selecao,
        )

    except (SQLAlchemyError, ValueError, TypeError, AttributeError, KeyError):
        raise HTTPException(
            status_code=503,
            detail="COMPOSICAO_CONSULTIVA_INDISPONIVEL",
        ) from None

@router.get("/analises/{empresa_id}")
def listar_analises_empresa(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    """
    Histórico de análises da empresa. Dashboard usa para histórico, status, score,
    número de alertas e tempo de processamento.
    """
    analises = (
        db.query(RelatorioAnalise)
        .filter(RelatorioAnalise.empresa_id == empresa.id)
        .order_by(RelatorioAnalise.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id": a.id,
            "xml_chave": a.xml_chave,
            "status": a.status,
            "tempo_execucao": a.tempo_execucao,
            "total_alertas": a.total_alertas,
            "score": a.score_resultante,
            "data": a.created_at
        }
        for a in analises
    ]


@router.get("/relatorio/{relatorio_id}")
def detalhe_relatorio(
    relatorio_id: int,
    db: Session = Depends(get_db),
    usuario_atual: models.User = Depends(get_usuario_atual),
):
    """
    Detalhe da análise por ID. Inclui tempo de processamento, status, score.
    Alimenta header/card de resumo das telas de alertas e oportunidades.
    """
    rel = db.query(RelatorioAnalise).filter(RelatorioAnalise.id == relatorio_id).first()
    if not rel:
        raise HTTPException(status_code=404, detail="Relatório não encontrado")
    verificar_acesso_relatorio(rel, usuario_atual, db)
    return {
        "id": rel.id,
        "empresa_id": rel.empresa_id,
        "analysis_type": rel.analysis_type,
        "xml_chave": rel.xml_chave,
        "status": rel.status,
        "tempo_execucao": rel.tempo_execucao,
        "tempo_processamento_segundos": rel.tempo_execucao,
        "total_alertas": rel.total_alertas,
        "score_resultante": rel.score_resultante,
        "created_at": rel.created_at,
    }


@router.get("/relatorio/{relatorio_id}/alertas")
def alertas_por_relatorio(
    relatorio_id: int,
    db: Session = Depends(get_db),
    usuario_atual: models.User = Depends(get_usuario_atual),
):
    """
    Alertas vinculados a um relatório de análise específico.
    Alimenta a tela principal de alertas do dashboard.
    """
    rel = db.query(RelatorioAnalise).filter(RelatorioAnalise.id == relatorio_id).first()
    if not rel:
        raise HTTPException(status_code=404, detail="Relatório não encontrado")
    verificar_acesso_relatorio(rel, usuario_atual, db)
    alertas = (
        db.query(AlertaFiscal)
        .filter(
            AlertaFiscal.relatorio_analise_id == relatorio_id,
            AlertaFiscal.silenciado != True,
        )
        .order_by(AlertaFiscal.criado_em.desc())
        .all()
    )
    return {
        "relatorio_id": relatorio_id,
        "tempo_processamento_segundos": rel.tempo_execucao,
        "total_alertas": len(alertas),
        "alertas": [
            {
                "id": a.id,
                "agente": a.agente,
                "tipo": a.tipo,
                "descricao": a.descricao,
                "nivel": a.nivel,
                "data": a.criado_em,
            }
            for a in alertas
        ],
    }


@router.get("/relatorio/{relatorio_id}/oportunidades")
def oportunidades_por_relatorio(
    relatorio_id: int,
    db: Session = Depends(get_db),
    usuario_atual: models.User = Depends(get_usuario_atual),
):
    """
    Oportunidades vinculadas a um relatório de análise específico.
    Alimenta a tela principal de oportunidades do dashboard.
    Extrai de resultado_json ou engine_resultados.
    """
    rel = db.query(RelatorioAnalise).filter(RelatorioAnalise.id == relatorio_id).first()
    if not rel:
        raise HTTPException(status_code=404, detail="Relatório não encontrado")
    verificar_acesso_relatorio(rel, usuario_atual, db)
    oportunidades = []
    creditos = []
    try:
        rj = verificar_resultado_persistido(rel)
    except ResultadoProvenanceError:
        raise HTTPException(
            status_code=409,
            detail={
                "bloqueado": True,
                "tipo_bloqueio": "RESULTADO_PERSISTIDO_PROVENIENCIA_NAO_COMPROVADA",
                "estado_l3": "bloqueado",
            },
        ) from None
    oportunidades = rj.get("oportunidades") or []
    creditos = rj.get("creditos_detectados") or []
    engines = (
        db.query(EngineResultado)
        .filter(EngineResultado.relatorio_analise_id == relatorio_id)
        .all()
    )
    oportunidades_engines = []
    for e in engines:
        r = (e.resultado or {}) if hasattr(e, "resultado") else {}
        if not isinstance(r, dict):
            continue

        engine_oportunidades = r.get("oportunidades") or []

        if (
            getattr(e, "engine_nome", None) == ANALYSIS_TYPE_MEI_TAX
            and engine_oportunidades
        ):
            raise HTTPException(
                status_code=409,
                detail={
                    "bloqueado": True,
                    "tipo_bloqueio": (
                        "RESULTADO_PERSISTIDO_PROVENIENCIA_NAO_COMPROVADA"
                    ),
                    "estado_l3": "bloqueado",
                },
            )

        oportunidades_engines.extend(engine_oportunidades)
    if not oportunidades and oportunidades_engines:
        oportunidades = oportunidades_engines
    return {
        "relatorio_id": relatorio_id,
        "tempo_processamento_segundos": rel.tempo_execucao,
        "oportunidades": oportunidades,
        "creditos_detectados": creditos,
        "total_oportunidades": len(oportunidades) + len(creditos),
    }


@router.get("/risco/{empresa_id}")
def score_risco(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    alertas = (
        db.query(AlertaFiscal)
        .filter(AlertaFiscal.empresa_id == empresa.id)
        .all()
    )

    score = 0

    for alerta in alertas:
        if alerta.nivel == "critico":
            score += 40
        elif alerta.nivel == "alto":
            score += 20
        elif alerta.nivel == "medio":
            score += 10

    score = min(score, 100)

    return {
        "empresa_id": empresa.id,
        "score_risco": score
    }


@router.get("/resumo/{empresa_id}")
def resumo_dashboard(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    alertas = (
        db.query(AlertaFiscal)
        .filter(AlertaFiscal.empresa_id == empresa.id)
        .all()
    )

    total_alertas = len(alertas)

    criticos = len([a for a in alertas if a.nivel == "critico"])
    altos = len([a for a in alertas if a.nivel == "alto"])
    medios = len([a for a in alertas if a.nivel == "medio"])

    return {
        "empresa_id": empresa.id,
        "total_alertas": total_alertas,
        "alertas_criticos": criticos,
        "alertas_altos": altos,
        "alertas_medios": medios
    }


@router.get("/alertas/{empresa_id}")
def listar_alertas(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    alertas = (
        db.query(AlertaFiscal)
        .filter(AlertaFiscal.empresa_id == empresa.id, AlertaFiscal.silenciado != True)
        .order_by(AlertaFiscal.criado_em.desc())
        .all()
    )

    return [
        {
            "id": a.id,
            "agente": a.agente,
            "tipo": a.tipo,
            "descricao": a.descricao,
            "nivel": a.nivel,
            "data": a.criado_em
        }
        for a in alertas
    ]


@router.get("/alertas/timeline/{empresa_id}")
def timeline_alertas(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    """
    Retorna linha do tempo de alertas da empresa.
    Alimenta: gráfico de linha, evolução do risco, histórico operacional,
    quando os problemas começaram, picos de atividade fiscal.
    """
    alertas = (
        db.query(AlertaFiscal)
        .filter(AlertaFiscal.empresa_id == empresa.id)
        .order_by(AlertaFiscal.criado_em.asc())
        .all()
    )

    return [
        {
            "data": a.criado_em,
            "nivel": a.nivel,
            "tipo": a.tipo
        }
        for a in alertas
    ]


@router.get("/alertas/agentes/{empresa_id}")
def alertas_por_agente(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    """
    Retorna alertas agrupados por agente.
    Alimenta: gráfico de origem dos alertas, saúde da plataforma, análise operacional.
    Tipos: alertas fiscais, alertas de sistema, alertas normativos, alertas de performance.
    """
    alertas = (
        db.query(AlertaFiscal)
        .filter(AlertaFiscal.empresa_id == empresa.id)
        .all()
    )

    resultado = {}

    for alerta in alertas:
        agente = alerta.agente or "nao_definido"
        if agente not in resultado:
            resultado[agente] = 0
        resultado[agente] += 1

    return {
        "empresa_id": empresa.id,
        "alertas_por_agente": resultado
    }


@router.patch("/alertas/silenciar/{alerta_id}")
def silenciar_alerta(
    alerta_id: int,
    db: Session = Depends(get_db),
    usuario_atual: models.User = Depends(get_usuario_atual),
):
    alerta = db.query(AlertaFiscal).filter(AlertaFiscal.id == alerta_id).first()

    if not alerta:
        raise HTTPException(status_code=404, detail="alerta não encontrado")

    verificar_empresa_do_usuario(alerta.empresa_id, usuario_atual, db)
    alerta.silenciado = True
    db.commit()

    return {
        "status": "alerta silenciado",
        "alerta_id": alerta_id
    }


@router.patch("/alertas/restaurar/{alerta_id}")
def restaurar_alerta(
    alerta_id: int,
    db: Session = Depends(get_db),
    usuario_atual: models.User = Depends(get_usuario_atual),
):
    alerta = db.query(AlertaFiscal).filter(AlertaFiscal.id == alerta_id).first()

    if not alerta:
        raise HTTPException(status_code=404, detail="alerta não encontrado")

    verificar_empresa_do_usuario(alerta.empresa_id, usuario_atual, db)
    alerta.silenciado = False
    db.commit()

    return {
        "status": "alerta restaurado",
        "alerta_id": alerta_id
    }


@router.get("/alertas/grafico/{empresa_id}")
def grafico_alertas(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    alertas = (
        db.query(AlertaFiscal)
        .filter(AlertaFiscal.empresa_id == empresa.id)
        .all()
    )

    critico = len([a for a in alertas if a.nivel == "critico"])
    alto = len([a for a in alertas if a.nivel == "alto"])
    medio = len([a for a in alertas if a.nivel == "medio"])

    return {
        "empresa_id": empresa.id,
        "grafico_alertas": {
            "critico": critico,
            "alto": alto,
            "medio": medio
        }
    }
