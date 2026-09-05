# Fix Windows: RQ usa fork que não existe no Windows - usar spawn
import sys
if sys.platform == "win32":
    import multiprocessing
    _orig_get_context = multiprocessing.get_context
    def _patched_get_context(method=None):
        if method == "fork":
            return _orig_get_context("spawn")
        return _orig_get_context(method)
    multiprocessing.get_context = _patched_get_context

from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, UploadFile, File, Depends, HTTPException, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.redis_connection import get_redis_connection
from app.constants import VERSAO_TERMOS_ATUAL, TERMOS_CACHE_TTL
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
import os
import logging
import httpx

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

_PROD = os.environ.get("ENVIRONMENT", "development") == "production"

from app.database import engine, get_db, SessionLocal
from app import models
from app.seed_data import ensure_planos

# IMPORTAR EXPLICITAMENTE OS MODELOS (registro para create_all)
from app.models import DocumentoFiscal, ItemFiscal, RequestLog
from app.auth_router import router as auth_router
from app.routes.fiscal_router import router as fiscal_router
from app.routes.lote_router import router as lote_router
from app.routes.relatorio_router import router as relatorio_router
from app.routes.imposto_router import router as imposto_router
from app.routes.metrics_router import router as metrics_router
from app.routes.auditoria import router as auditoria_router
from app.routes.estoque_dashboard import router as estoque_dashboard_router
from app.routes.cpf_router import router as cpf_router
from app.routers.st_router import router as st_router
from app.routers.insights_router import router as insights_router
from app.routers.empresa_router import router as empresa_router
from app.routers.documento_router import router as documento_router
from app.routers.ingestion_router import router as ingestion_router
from app.routers.formalizacao_router import router as formalizacao_router
from app.routers.contador_router import router as contador_router
from app.routers.inteligencia_router import inteligencia_router
from app.routers.dashboard_router import router as dashboard_router
from app.routers.assistente_router import assistente_router
from app.routers.checkout_offer_one_time_router import criar_checkout_offer_one_time_router
from app.routers.mercado_pago_webhook_router import criar_mercado_pago_webhook_router
from app.xml_security import validar_upload_xml
from app.security import get_usuario_atual, require_role, verificar_token
from app.rate_limit import limiter
from app.agents.agent_scheduler import AgentScheduler
from app.services.request_log_retention import purga_request_logs_mais_antigos_que
from app.services.mercado_pago_runtime_lifecycle import ativar_mercado_pago
from app.services.normative_update_service import (
    expirar_regras_revogadas,
    listar_alertas_normativos_pendentes,
    marcar_alerta_processado,
)
from app.services.parsers.orquestrador_parsers import executar_parsers
from app.services.perfil_contador_admin_service import (
    criar_perfil_contador_pendente,
    listar_perfis_contador,
    aprovar_perfil_contador,
)
import asyncio

logger = logging.getLogger(__name__)


def _dias_retenção_request_logs() -> int:
    raw = os.environ.get("REQUEST_LOG_RETENTION_DAYS", "30")
    try:
        return int(raw)
    except ValueError:
        logger.warning("REQUEST_LOG_RETENTION_DAYS inválido (%s), usando 30", raw)
        return 30


def _startup_purge_request_logs_sync() -> None:
    dias = _dias_retenção_request_logs()
    if dias <= 0:
        logger.info("Retenção request_logs desativada (REQUEST_LOG_RETENTION_DAYS <= 0).")
        return
    try:
        n = purga_request_logs_mais_antigos_que(dias)
        if n:
            logger.info(
                "Retenção request_logs: removidos %s registos com mais de %s dias.",
                n,
                dias,
            )
    except Exception as exc:
        logger.warning("Retenção request_logs no startup falhou: %s", exc)


def run_migrations():
    """Cria colunas e tabelas adicionais se não existirem."""
    from sqlalchemy import inspect
    insp = inspect(engine)
    with engine.begin() as conn:
        # regime_tributario em empresas
        if "empresas" in insp.get_table_names():
            cols = [c["name"] for c in insp.get_columns("empresas")]
            if "regime_tributario" not in cols:
                conn.execute(text("ALTER TABLE empresas ADD COLUMN regime_tributario VARCHAR(50)"))
        # quantidade em itens_fiscais
        if "itens_fiscais" in insp.get_table_names():
            cols = [c["name"] for c in insp.get_columns("itens_fiscais")]
            if "quantidade" not in cols:
                conn.execute(text("ALTER TABLE itens_fiscais ADD COLUMN quantidade REAL"))
        # role em usuarios (default 'user' para todos os existentes)
        if "usuarios" in insp.get_table_names():
            cols = [c["name"] for c in insp.get_columns("usuarios")]
            if "role" not in cols:
                conn.execute(text(
                    "ALTER TABLE usuarios ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user'"
                ))


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        ensure_planos(db)
    finally:
        db.close()
    await asyncio.to_thread(_startup_purge_request_logs_sync)

    activation = ativar_mercado_pago(
        values=dict(os.environ),
        session_factory=SessionLocal,
        http_client_factory=httpx.Client,
    )
    try:
        if activation is not None:
            checkout_router = criar_checkout_offer_one_time_router(
                application_service=activation.composition.checkout_application,
                current_user_dependency=get_usuario_atual,
            )
            app.include_router(checkout_router)
            webhook_router = criar_mercado_pago_webhook_router(
                orchestrator=activation.composition.webhook_orchestrator,
                max_body_bytes=activation.composition.max_body_bytes,
            )
            app.include_router(webhook_router)
        yield
    finally:
        if activation is not None:
            activation.close()


app = FastAPI(
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://saas-fiscal-demo.vercel.app",
        "https://fiscosoberano.com.br",
        "https://www.fiscosoberano.com.br",
        "https://app.fiscosoberano.com.br",
    ],
    allow_origin_regex=r"https://(frontend-dashboard-.*|saas-fiscal-demo(-[a-z0-9]+)*(-nexialistamentors-projects)?)\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

admin_router = APIRouter()

# Inserir na secção de Payloads admin (≈ linha 167), junto dos outros BaseModel

class CriarVinculoContadorPayload(BaseModel):
    contador_user_id: int           # user_id do contador (não perfil_id)
    empresa_id: int
    escopo_chave: str = "homologacao_documental"
    validade: str | None = None     # ISO 8601, ex: "2027-01-01T00:00:00"
    policy_version: str | None = None


class CriarPerfilContadorPendentePayload(BaseModel):
    email: str
    crc: str
    uf_crc: str


# ── Payloads admin ──────────────────────────────────────────────────────
class SetRolePayload(BaseModel):
    email: str
    role: str

class LiberarConsultaPayload(BaseModel):
    email: str


class PurgeRequestLogsPayload(BaseModel):
    """Se dias for omitido, usa REQUEST_LOG_RETENTION_DAYS (default 30)."""
    dias: int | None = None


class MarcarProcessadoPayload(BaseModel):
    alerta_id: int
    notas: str | None = None


class ExpirarRegrasPayload(BaseModel):
    estado: str
    ncm: str
    data_revogacao: str  # YYYY-MM-DD
    fonte_revogacao: str


class ExecutarParsersPayload(BaseModel):
    dry_run: bool = True


# ── L2 SOBERANA — REFORÇOS FUTUROS PARA ENDPOINTS ADMIN ─────────────────
# 1. Audit trail obrigatório
#    Registrar toda ação admin: quem, quando, endpoint, payload sanitizado, resultado.
# 2. Proteção anti-CSRF / intenção explícita
#    Header dedicado para ações administrativas mutáveis em contexto browser.
# 3. Validação forte de payload
#    Migrar role e campos sensíveis para enum/schema estrito (sem validação solta).
# 4. Idempotency-Key em mutações críticas
#    Suportar reenvio seguro sem duplicar efeito colateral.
# 5. Rate limit por identidade (RA8) — em app.rate_limit.obter_chave_rate_limit: JWT válido => user:email; senão IP.
# 6. Dry-run para operações destrutivas
#    Permitir simulação antes da execução real.
# 7. Sanitização de resposta e logs
#    Minimizar retorno de dados sensíveis e mascarar identificadores.
# ────────────────────────────────────────────────────────────────────────

# ── Endpoints admin (todos POST — nunca GET para mutação) ──────────────
@admin_router.post("/admin/create-tables")
@limiter.limit("5/minute")
def create_tables(
    request: Request,
    usuario: models.User = Depends(require_role("admin")),
):
    models.Base.metadata.create_all(bind=engine)
    return {"status": "tables created"}


@admin_router.post("/admin/fix-usuarios-plano")
@limiter.limit("5/minute")
def fix_plano_column(
    request: Request,
    usuario: models.User = Depends(require_role("admin")),
):
    with engine.connect() as conn:
        conn.execute(text("""
            ALTER TABLE usuarios
            ADD COLUMN IF NOT EXISTS plano_id INTEGER;
        """))
        conn.execute(text("""
            ALTER TABLE usuarios
            ADD COLUMN IF NOT EXISTS consulta_paga BOOLEAN DEFAULT false;
        """))
        conn.commit()
    return {"status": "usuarios fixed"}


@admin_router.post("/admin/set-role")
@limiter.limit("10/minute")
def set_user_role(
    request: Request,
    payload: SetRolePayload,
    db: Session = Depends(get_db),
    usuario: models.User = Depends(require_role("admin")),
):
    if payload.role not in models.ROLES_VALIDOS:
        raise HTTPException(status_code=400, detail=f"Role inválido. Válidos: {models.ROLES_VALIDOS}")
    target = db.query(models.User).filter(models.User.email == payload.email).first()
    if not target:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    target.role = payload.role
    db.commit()
    return {"status": "role atualizado", "email": payload.email, "role": payload.role}


@admin_router.post("/admin/liberar-consulta")
@limiter.limit("10/minute")
def liberar_consulta(
    request: Request,
    payload: LiberarConsultaPayload,
    usuario: models.User = Depends(require_role("admin")),
):
    with engine.connect() as conn:
        conn.execute(
            text("""
                UPDATE usuarios
                SET consulta_paga = true
                WHERE email = :email
            """),
            {"email": payload.email},
        )
        conn.commit()
    return {"status": "consulta liberada", "email": payload.email}


@admin_router.post("/admin/fix-planos")
@limiter.limit("5/minute")
def fix_planos(
    request: Request,
    usuario: models.User = Depends(require_role("admin")),
):
    with engine.connect() as conn:
        conn.execute(text("""
            ALTER TABLE planos
            ADD COLUMN IF NOT EXISTS limite_analises INTEGER DEFAULT 100;
        """))
        conn.commit()
    return {"status": "planos fixed"}


@admin_router.post("/admin/purge-request-logs")
@limiter.limit("5/minute")
def admin_purge_request_logs(
    request: Request,
    payload: PurgeRequestLogsPayload = Body(default_factory=PurgeRequestLogsPayload),
    usuario: models.User = Depends(require_role("admin")),
):
    """Remove request_logs mais antigos que N dias (operação de manutenção)."""
    dias = payload.dias if payload.dias is not None else _dias_retenção_request_logs()
    if dias <= 0:
        raise HTTPException(
            status_code=400,
            detail="dias deve ser > 0 (ou defina REQUEST_LOG_RETENTION_DAYS > 0)",
        )
    removidos = purga_request_logs_mais_antigos_que(dias)
    return {"status": "ok", "removidos": removidos, "dias": dias}


@admin_router.get("/admin/alertas-normativos")
@limiter.limit("30/minute")
def get_alertas_normativos(
    request: Request,
    db: Session = Depends(get_db),
    usuario: models.User = Depends(require_role("admin")),
):
    """Lista alertas normativos pendentes de acção."""
    return listar_alertas_normativos_pendentes(db)


@admin_router.post("/admin/alertas-normativos/processar")
@limiter.limit("30/minute")
def processar_alerta_normativo(
    request: Request,
    payload: MarcarProcessadoPayload,
    db: Session = Depends(get_db),
    usuario: models.User = Depends(require_role("admin")),
):
    ok = marcar_alerta_processado(
        db,
        payload.alerta_id,
        processado_por=usuario.email,
        notas=payload.notas,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Alerta não encontrado")
    return {"status": "processado", "alerta_id": payload.alerta_id}


@admin_router.post("/admin/normativos/expirar-regras")
@limiter.limit("10/minute")
def expirar_regras(
    request: Request,
    payload: ExpirarRegrasPayload,
    db: Session = Depends(get_db),
    usuario: models.User = Depends(require_role("admin")),
):
    """Encerra vigência de regras MVA/PMPF quando portaria é revogada."""
    return expirar_regras_revogadas(
        db,
        estado=payload.estado,
        ncm=payload.ncm,
        data_revogacao=payload.data_revogacao,
        processado_por=usuario.email,
        fonte_revogacao=payload.fonte_revogacao,
    )


@admin_router.post("/admin/parsers/executar")
@limiter.limit("5/minute")
def admin_executar_parsers(
    request: Request,
    payload: ExecutarParsersPayload,
    usuario: models.User = Depends(require_role("admin")),
):
    """Executa parsers normativos. dry_run=True por defeito."""
    resultado = executar_parsers(dry_run=payload.dry_run)
    return resultado


@admin_router.get("/admin/debug-insights-mva")
def debug_insights_mva(empresa_id: int, usuario: models.User = Depends(require_role("admin"))):
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT tipo, valor_estimado
            FROM insights
            WHERE empresa_id = :empresa_id
              AND tipo = 'DISTORCAO_MVA_REAL'
            ORDER BY id DESC
        """), {"empresa_id": empresa_id}).fetchall()

    return {
        "empresa_id": empresa_id,
        "count": len(rows),
        "sum": float(sum(float(r[1] or 0) for r in rows)),
        "rows": [{"tipo": r[0], "valor_estimado": float(r[1] or 0)} for r in rows]
    }


@app.middleware("http")
async def add_security_headers(request, call_next):
    """Headers de segurança HTTP: XSS, clickjacking, MIME sniffing, HSTS, referrer e APIs sensíveis."""
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), "
        "microphone=(), payment=(), usb=()"
    )
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' data: https://fastapi.tiangolo.com; "
        "connect-src 'self' https://cdn.jsdelivr.net; "
        "font-src 'self' https://cdn.jsdelivr.net;"
    )
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


def _persist_request_log(
    method: str,
    path: str,
    status_code: int,
    auth_header: str,
    user_agent: str | None,
    ip: str,
) -> None:
    """Persistência síncrona; chamada via asyncio.to_thread no middleware async."""
    db = None
    try:
        db = SessionLocal()
        user_id = None
        if auth_header.lower().startswith("bearer "):
            payload = verificar_token(auth_header[7:].strip())
            if payload:
                user_id = payload.get("user_id")
        log = RequestLog(
            method=method,
            path=path,
            status_code=status_code,
            user_id=user_id,
            ip=ip,
            user_agent=user_agent,
        )
        db.add(log)
        db.commit()
    except Exception as exc:
        if db is not None:
            db.rollback()
        logger.warning("log_requests middleware falhou: %s", exc)
    finally:
        if db is not None:
            db.close()


@app.middleware("http")
async def log_requests(request: Request, call_next):
    response = await call_next(request)
    auth_header = request.headers.get("authorization", "")
    user_agent = request.headers.get("user-agent")
    ip = request.client.host if request.client else "unknown"
    await asyncio.to_thread(
        _persist_request_log,
        request.method,
        str(request.url.path),
        response.status_code,
        auth_header,
        user_agent,
        ip,
    )
    return response


scheduler = AgentScheduler()


ROTAS_FISCAIS = (
    "/fiscal",
    "/lote",
    "/relatorio",
    "/imposto",
    "/estoque",
    "/analise-st",
    "/empresas",
    "/formalizacao",
    "/dashboard",
    "/documentos",
    "/inteligencia",
    "/insights",
    "/perguntar",
    "/cpf",
)
ROTAS_EXCLUIDAS = ("/auth", "/health", "/docs", "/openapi", "/metrics")


class TermosMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        if not any(path.startswith(r) for r in ROTAS_FISCAIS):
            return await call_next(request)
        if any(path.startswith(r) for r in ROTAS_EXCLUIDAS):
            return await call_next(request)
        if request.method == "OPTIONS":
            return await call_next(request)

        ip_real = request.client.host if request.client else None
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip_real = forwarded.split(",")[0].strip()
        else:
            real_ip = request.headers.get("X-Real-IP")
            if real_ip:
                ip_real = real_ip.strip()

        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if not token:
            return await call_next(request)

        from app.security import verificar_token

        payload = verificar_token(token)
        if not payload:
            return await call_next(request)

        email = payload.get("sub")
        if not email:
            return await call_next(request)

        redis_client, _, _ = get_redis_connection()
        cache_key = f"termos:v{VERSAO_TERMOS_ATUAL}:{email}"
        aceite = False

        if redis_client:
            try:
                cached = redis_client.get(cache_key)
                if cached is not None:
                    aceite = cached.decode("utf-8") == "1"
                else:
                    raise ValueError("cache miss")
            except Exception:
                redis_client = None

        if not redis_client or not aceite:
            from app.database import SessionLocal
            from app.models import TermosAceitacao
            from app import models as m

            db = SessionLocal()
            try:
                user = db.query(m.User).filter(m.User.email == email).first()
                if user:
                    reg = db.query(TermosAceitacao).filter(
                        TermosAceitacao.user_id == user.id,
                        TermosAceitacao.versao_termos == VERSAO_TERMOS_ATUAL,
                    ).first()
                    aceite = reg is not None
                    redis_c, _, _ = get_redis_connection()
                    if redis_c:
                        try:
                            redis_c.setex(cache_key, TERMOS_CACHE_TTL, "1" if aceite else "0")
                        except Exception:
                            pass
            finally:
                db.close()

        if not aceite:
            return JSONResponse(
                status_code=403,
                content={"detail": "Termos de Uso não aceites. Aceda a /auth/accept-terms."}
            )

        return await call_next(request)


app.add_middleware(TermosMiddleware)

app.include_router(auth_router)
app.include_router(fiscal_router, prefix="/fiscal")
app.include_router(lote_router, prefix="/lote")
app.include_router(relatorio_router, prefix="/relatorio")
app.include_router(imposto_router, prefix="/imposto")
app.include_router(st_router)
app.include_router(insights_router)
app.include_router(empresa_router)
app.include_router(formalizacao_router)
app.include_router(documento_router)
app.include_router(ingestion_router)
app.include_router(contador_router)
app.include_router(inteligencia_router)
app.include_router(dashboard_router)
app.include_router(assistente_router)
app.include_router(metrics_router)
app.include_router(auditoria_router, prefix="/estoque")
app.include_router(estoque_dashboard_router, prefix="/estoque")
app.include_router(cpf_router)
# Inserir na secção Endpoints admin (≈ linha 213)

@admin_router.post("/admin/contadores/vinculos", status_code=201)
@limiter.limit("20/minute")
def admin_criar_vinculo_contador_empresa(
    request: Request,
    payload: CriarVinculoContadorPayload,
    db: Session = Depends(get_db),
    usuario: models.User = Depends(require_role("admin")),
):
    """
    DT-VINCULO-ADMIN-01: cria vínculo soberano contador↔empresa.
    Exige role=admin. Origem=admin. Audita criado_por_user_id/email.
    Escopos admissíveis V1: homologacao_documental, parecer_tecnico, analise_xml.
    """
    from datetime import datetime as _dt
    from app.services.vinculo_admin_service import (
        ContadorNaoEncontradoError,
        ContadorNaoAprovadoParaVinculoError,
        EmpresaNaoEncontradaError,
        VinculoDuplicadoActivoError,
        VinculoAdminError,
        criar_vinculo_contador_empresa as _criar_vinculo,
    )

    validade = None
    if payload.validade:
        try:
            validade = _dt.fromisoformat(payload.validade)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="validade deve ser ISO 8601: ex. '2027-01-01T00:00:00'",
            )

    try:
        vinculo = _criar_vinculo(
            db=db,
            admin_user=usuario,
            contador_user_id=payload.contador_user_id,
            empresa_id=payload.empresa_id,
            escopo_chave=payload.escopo_chave,
            validade=validade,
            policy_version=payload.policy_version,
        )
        db.commit()
        db.refresh(vinculo)
    except (ContadorNaoEncontradoError, EmpresaNaoEncontradaError) as e:
        raise HTTPException(status_code=404, detail=e.mensagem)
    except VinculoDuplicadoActivoError as e:
        raise HTTPException(status_code=409, detail=e.mensagem)
    except VinculoAdminError as e:
        raise HTTPException(status_code=422, detail=e.mensagem)

    return {
        "status": "vinculo criado",
        "vinculo_id": vinculo.id,
        "contador_id": vinculo.contador_id,
        "empresa_id": vinculo.empresa_id,
        "escopo_chave": vinculo.escopo_chave,
        "origem": vinculo.origem,
        "status_vinculo": vinculo.status,
        "criado_por_email": vinculo.criado_por_email,
        "criado_em": vinculo.criado_em.isoformat() if vinculo.criado_em else None,
        "validade": vinculo.validade.isoformat() if vinculo.validade else None,
    }


@admin_router.get("/admin/contadores/vinculos")
@limiter.limit("30/minute")
def admin_listar_vinculos(
    request: Request,
    status: str | None = None,
    empresa_id: int | None = None,
    contador_user_id: int | None = None,
    escopo_chave: str | None = None,
    db: Session = Depends(get_db),
    usuario: models.User = Depends(require_role("admin")),
):
    """
    DT-VINCULO-ADMIN-02: lista vínculos contador↔empresa com filtros opcionais.
    Filtros: status, empresa_id, contador_user_id, escopo_chave.
    status inválido ou escopo inválido → 422 (não lista vazia silenciosa).
    """
    from app.services.vinculo_admin_service import (
        VinculoAdminError,
        listar_vinculos as _listar,
    )
    try:
        vinculos = _listar(
            db=db,
            admin_user=usuario,
            status=status,
            empresa_id=empresa_id,
            contador_user_id=contador_user_id,
            escopo_chave=escopo_chave,
        )
    except VinculoAdminError as e:
        raise HTTPException(status_code=422, detail=e.mensagem)
    return {"vinculos": vinculos, "total": len(vinculos)}


@admin_router.post("/admin/contadores/vinculos/{vinculo_id}/suspender")
@limiter.limit("20/minute")
def admin_suspender_vinculo(
    request: Request,
    vinculo_id: int,
    db: Session = Depends(get_db),
    usuario: models.User = Depends(require_role("admin")),
):
    """
    DT-VINCULO-ADMIN-02: suspende vínculo activo.
    activo → suspenso. Bloqueado se suspenso/revogado/expirado.
    """
    from app.services.vinculo_admin_service import (
        VinculoNaoEncontradoError,
        VinculoTransicaoInvalidaError,
        VinculoAdminError,
        suspender_vinculo as _suspender,
    )
    try:
        vinculo = _suspender(db=db, admin_user=usuario, vinculo_id=vinculo_id)
        db.commit()
    except VinculoNaoEncontradoError as e:
        raise HTTPException(status_code=404, detail=e.mensagem)
    except VinculoTransicaoInvalidaError as e:
        raise HTTPException(status_code=409, detail=e.mensagem)
    except VinculoAdminError as e:
        raise HTTPException(status_code=422, detail=e.mensagem)

    return {
        "status": "vinculo suspenso",
        "vinculo_id": vinculo.id,
        "status_vinculo": vinculo.status,
    }


@admin_router.post("/admin/contadores/vinculos/{vinculo_id}/revogar")
@limiter.limit("20/minute")
def admin_revogar_vinculo(
    request: Request,
    vinculo_id: int,
    db: Session = Depends(get_db),
    usuario: models.User = Depends(require_role("admin")),
):
    """
    DT-VINCULO-ADMIN-02: revoga vínculo activo ou suspenso.
    activo/suspenso → revogado. Preenche revogado_em e revogado_por_user_id.
    """
    from app.services.vinculo_admin_service import (
        VinculoNaoEncontradoError,
        VinculoTransicaoInvalidaError,
        VinculoAdminError,
        revogar_vinculo as _revogar,
    )
    try:
        vinculo = _revogar(db=db, admin_user=usuario, vinculo_id=vinculo_id)
        db.commit()
    except VinculoNaoEncontradoError as e:
        raise HTTPException(status_code=404, detail=e.mensagem)
    except VinculoTransicaoInvalidaError as e:
        raise HTTPException(status_code=409, detail=e.mensagem)
    except VinculoAdminError as e:
        raise HTTPException(status_code=422, detail=e.mensagem)

    return {
        "status": "vinculo revogado",
        "vinculo_id": vinculo.id,
        "status_vinculo": vinculo.status,
        "revogado_em": vinculo.revogado_em.isoformat() if vinculo.revogado_em else None,
        "revogado_por_user_id": vinculo.revogado_por_user_id,
    }


@admin_router.post("/admin/contadores/perfis", status_code=201)
@limiter.limit("20/minute")
def admin_criar_perfil_contador_pendente(
    request: Request,
    payload: CriarPerfilContadorPendentePayload,
    db: Session = Depends(get_db),
    usuario: models.User = Depends(require_role("admin")),
):
    """B10-ADMIN-CONT-01: cria PerfilContador pendente para User existente. Promove role=contador."""
    perfil = criar_perfil_contador_pendente(
        db=db,
        admin_user=usuario,
        email=payload.email,
        crc=payload.crc,
        uf_crc=payload.uf_crc,
    )
    return {
        "status": "perfil criado",
        "perfil_id": perfil.id,
        "user_id": perfil.user_id,
        "crc": perfil.crc,
        "uf_crc": perfil.uf_crc,
        "perfil_status": perfil.status,
    }


@admin_router.get("/admin/contadores/perfis")
@limiter.limit("30/minute")
def admin_listar_perfis_contador(
    request: Request,
    status: str = "pendente",
    db: Session = Depends(get_db),
    usuario: models.User = Depends(require_role("admin")),
):
    """B10-ADMIN-CONT-01: lista PerfilContador por status. Status inválido → 422."""
    perfis = listar_perfis_contador(db=db, status=status)
    return {"total": len(perfis), "perfis": perfis}


@admin_router.post("/admin/contadores/perfis/{perfil_id}/aprovar", status_code=200)
@limiter.limit("20/minute")
def admin_aprovar_perfil_contador(
    request: Request,
    perfil_id: int,
    db: Session = Depends(get_db),
    usuario: models.User = Depends(require_role("admin")),
):
    """B10-ADMIN-CONT-01: transição soberana pendente → aprovado. Preenche aprovado_em/aprovado_por."""
    perfil = aprovar_perfil_contador(
        db=db,
        admin_user=usuario,
        perfil_id=perfil_id,
    )
    return {
        "status": "perfil aprovado",
        "perfil_id": perfil.id,
        "perfil_status": perfil.status,
        "aprovado_em": perfil.aprovado_em.isoformat(),
        "aprovado_por": perfil.aprovado_por,
    }


app.include_router(admin_router)


@app.get("/")
@limiter.limit("100/minute")
def root(request: Request):
    return {"status": "API Fiscal Ativa"}


@app.get("/health")
@limiter.limit("100/minute")
def health(request: Request):
    return {"status": "ok"}


@app.get("/health/ready")
@limiter.limit("30/minute")
def health_ready(request: Request, db: Session = Depends(get_db)):
    """
    B12-02: readiness check — verifica BD e Redis (advisory).
    Usado para monitorização operacional.
    /health (liveness) permanece simples — usado pelo Railway healthcheck.
    Resposta:
      200 → database="ok"; redis pode ser ok|not_configured|unavailable
      503 → database="error" (BD inacessível)
    """
    from fastapi.responses import JSONResponse
    from app.redis_connection import get_redis_connection

    resultado = {
        "status": "ok",
        "database": "error",
        "redis": "not_configured",
    }

    # Verificar BD
    try:
        db.execute(text("SELECT 1"))
        resultado["database"] = "ok"
    except Exception:
        resultado["database"] = "error"
        resultado["status"] = "degraded"

    # Verificar Redis — advisory, não obrigatório (fallback síncrono existe)
    try:
        redis_conn, _, err = get_redis_connection()
        if redis_conn is not None:
            resultado["redis"] = "ok"
        elif err is not None:
            resultado["redis"] = "unavailable"
        else:
            resultado["redis"] = "not_configured"
    except Exception:
        resultado["redis"] = "unavailable"

    status_code = 503 if resultado["status"] == "degraded" else 200
    return JSONResponse(content=resultado, status_code=status_code)


@app.post("/upload-xml")
@limiter.limit("10/minute")
async def upload_xml(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario_atual: models.User = Depends(get_usuario_atual),
):
    """
    DT-FLUXO-01: wrapper canónico para upload de XML NF-e.
    Pipeline: validar → parse CNPJ → resolver empresa → executar_e_registrar_analise_xml
    Remove gravação em disco e motor antigo.
    Contrato: relatorio_id (documento_id não existe em RelatorioAnalise).
    """
    from app.services.registro_analise_service import executar_e_registrar_analise_xml
    from app.xml_service import ler_xml_unico

    conteudo = await validar_upload_xml(file)

    dados = ler_xml_unico(xml_bytes=conteudo)
    cnpj = dados.get("cnpj")
    if not cnpj:
        raise HTTPException(
            status_code=422,
            detail="XML não contém CNPJ identificável. Verifique o ficheiro.",
        )

    empresa = db.query(models.Empresa).filter(
        models.Empresa.user_id == usuario_atual.id,
        models.Empresa.cnpj == cnpj,
    ).first()

    if not empresa:
        plano = db.query(models.Plano).filter(
            models.Plano.id == usuario_atual.plano_id
        ).first()
        total_empresas = db.query(models.Empresa).filter(
            models.Empresa.user_id == usuario_atual.id
        ).count()
        if plano and total_empresas >= plano.limite_cnpjs:
            raise HTTPException(
                status_code=403,
                detail="Limite de CNPJs atingido para seu plano",
            )
        empresa = models.Empresa(
            cnpj=cnpj,
            razao_social=dados.get("razao_social", ""),
            user_id=usuario_atual.id,
        )
        db.add(empresa)
        db.flush()

    relatorio, resultado = executar_e_registrar_analise_xml(
        db=db,
        xml_bytes=conteudo,
        user_id=usuario_atual.id,
        empresa_id=empresa.id,
    )

    return {
        "relatorio_id": relatorio.id,
        "empresa_id": empresa.id,
        "status": resultado.get("status", "processado"),
    }


@app.post("/criar-planos")
@limiter.limit("5/minute")
def criar_planos(
    request: Request,
    db: Session = Depends(get_db),
    usuario_atual: models.User = Depends(require_role("admin")),
):
    nomes_existentes = {p.nome for p in db.query(models.Plano).all()}

    planos_base = [
        {"nome": "Basico", "limite_cnpjs": 5, "limite_analises": 100},
        {"nome": "Pro", "limite_cnpjs": 10, "limite_analises": 500},
        {"nome": "Ilimitado", "limite_cnpjs": 999999, "limite_analises": 999999},
        {"nome": "Teste", "limite_cnpjs": 2, "limite_analises": 2},
    ]

    criados = []
    for p in planos_base:
        if p["nome"] not in nomes_existentes:
            db.add(models.Plano(**p))
            criados.append(p["nome"])

    if criados:
        db.commit()

    return {
        "mensagem": f"Planos criados: {', '.join(criados)}" if criados else "Planos já existem",
        "criados": criados,
    }

