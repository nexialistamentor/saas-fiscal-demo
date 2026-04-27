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

from fastapi import APIRouter, FastAPI, UploadFile, File, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
import os
import logging

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
from app.routers.inteligencia_router import inteligencia_router
from app.routers.dashboard_router import router as dashboard_router
from app.routers.assistente_router import assistente_router
from app.xml_service import ler_xml_unico, processar_e_persistir_xml, DuplicataFiscalError
from app.xml_security import validar_upload_xml
from app.security import get_usuario_atual, require_role, verificar_token
from app.rate_limit import limiter
from app.agents.agent_scheduler import AgentScheduler
import asyncio

logger = logging.getLogger(__name__)

app = FastAPI(
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
    ],
    allow_origin_regex=r"https://(frontend-dashboard-.*|saas-fiscal-demo(-[a-z0-9]+)*(-nexialistamentors-projects)?)\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

admin_router = APIRouter()


# ── Payloads admin ──────────────────────────────────────────────────────
class SetRolePayload(BaseModel):
    email: str
    role: str

class LiberarConsultaPayload(BaseModel):
    email: str


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
    """Headers de segurança HTTP: XSS, clickjacking, MIME sniffing, HSTS."""
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
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


@app.middleware("http")
async def log_requests(request: Request, call_next):
    response = await call_next(request)
    db = None
    try:
        db = SessionLocal()
        user_id = None
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            payload = verificar_token(auth[7:].strip())
            if payload:
                user_id = payload.get("user_id")
        ip = request.client.host if request.client else "unknown"
        log = RequestLog(
            method=request.method,
            path=str(request.url.path),
            status_code=response.status_code,
            user_id=user_id,
            ip=ip,
            user_agent=request.headers.get("user-agent"),
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
    return response


scheduler = AgentScheduler()


app.include_router(auth_router)
app.include_router(fiscal_router, prefix="/fiscal")
app.include_router(lote_router, prefix="/lote")
app.include_router(relatorio_router, prefix="/relatorio")
app.include_router(imposto_router, prefix="/imposto")
app.include_router(st_router)
app.include_router(insights_router)
app.include_router(empresa_router)
app.include_router(documento_router)
app.include_router(inteligencia_router)
app.include_router(dashboard_router)
app.include_router(assistente_router)
app.include_router(metrics_router)
app.include_router(auditoria_router, prefix="/estoque")
app.include_router(estoque_dashboard_router, prefix="/estoque")
app.include_router(cpf_router)
app.include_router(admin_router)


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


@app.on_event("startup")
async def startup():
    models.Base.metadata.create_all(bind=engine)
    run_migrations()
    db = SessionLocal()
    try:
        ensure_planos(db)
    finally:
        db.close()

    # Scheduler desativado temporariamente para estabilizar o banco
    # asyncio.create_task(scheduler.iniciar_loop(empresa_id=1, intervalo_segundos=300))


@app.get("/")
@limiter.limit("100/minute")
def root(request: Request):
    return {"status": "API Fiscal Ativa"}


@app.get("/health")
@limiter.limit("100/minute")
def health(request: Request):
    return {"status": "ok"}


@app.post("/upload-xml")
@limiter.limit("10/minute")
async def upload_xml(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario_atual: models.User = Depends(get_usuario_atual),
):

    total_empresas = db.query(models.Empresa).filter(
        models.Empresa.user_id == usuario_atual.id
    ).count()

    plano = db.query(models.Plano).filter(
        models.Plano.id == usuario_atual.plano_id
    ).first()

    if total_empresas >= plano.limite_cnpjs:
        raise HTTPException(
            status_code=403,
            detail="Limite de CNPJs atingido para seu plano"
        )

    pasta = "app/xmls_testes"
    os.makedirs(pasta, exist_ok=True)

    caminho = os.path.join(pasta, file.filename)

    conteudo = await validar_upload_xml(file)

    with open(caminho, "wb") as f:
        f.write(conteudo)

    dados = ler_xml_unico(caminho)

    empresa = db.query(models.Empresa).filter(
        models.Empresa.user_id == usuario_atual.id,
        models.Empresa.cnpj == dados.get("cnpj")
    ).first()
    if not empresa:
        empresa = models.Empresa(
            cnpj=dados.get("cnpj"),
            razao_social=dados.get("razao_social"),
            user_id=usuario_atual.id
        )
        db.add(empresa)
        db.flush()

    try:
        documento, dados, analise = processar_e_persistir_xml(
            db=db,
            usuario_atual=usuario_atual,
            empresa=empresa,
            xml_bytes=conteudo,
            dados_pre_parse=dados,
        )
    except DuplicataFiscalError as e:
        raise HTTPException(
            status_code=409,
            detail={
                "erro": "Documento fiscal duplicado",
                "chave_nfe": e.chave_nfe,
                "documento_id": e.documento_id,
            },
        )
    return {"documento_id": documento.id}


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


