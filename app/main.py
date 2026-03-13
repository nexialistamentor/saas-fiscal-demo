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
from sqlalchemy.orm import Session
from sqlalchemy import text
import os

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.database import engine, get_db
from app import models

# IMPORTAR EXPLICITAMENTE OS MODELOS (registro para create_all)
from app.models import DocumentoFiscal, ItemFiscal
from app.auth_router import router as auth_router
from app.routes.fiscal_router import router as fiscal_router
from app.routes.lote_router import router as lote_router
from app.routes.relatorio_router import router as relatorio_router
from app.routes.imposto_router import router as imposto_router
from app.routes.metrics_router import router as metrics_router
from app.routes.auditoria import router as auditoria_router
from app.routers.st_router import router as st_router
from app.routers.insights_router import router as insights_router
from app.routers.empresa_router import router as empresa_router
from app.routers.documento_router import router as documento_router
from app.routers.inteligencia_router import inteligencia_router
from app.routers.dashboard_router import router as dashboard_router
from app.routers.assistente_router import assistente_router
from app.xml_service import ler_xml_unico, persistir_documento_fiscal, enriquecer_st_se_necessario
from app.xml_security import validar_upload_xml
from app.motor_fiscal import analisar_xml
from app.services.tax_consistency.tax_consistency_engine import TaxConsistencyEngine
from app.security import get_usuario_atual
from app.agents.agent_scheduler import AgentScheduler
import asyncio

_PROD = os.environ.get("ENVIRONMENT", "development") == "production"
# Rate limit: 100 req/min por IP (global) - impede brute force
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])

app = FastAPI(
    title="SaaS Fiscal Inteligente",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    swagger_ui_parameters={"syntaxHighlight.theme": "obsidian"}
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

admin_router = APIRouter()


@admin_router.get("/admin/create-tables")
def create_tables():
    import app.models

    from app.models import DocumentoFiscal, ItemFiscal

    models.Base.metadata.create_all(bind=engine)

    return {"status": "tables created"}


@app.middleware("http")
async def add_security_headers(request, call_next):
    """Headers de segurança HTTP: XSS, clickjacking, MIME sniffing, HSTS."""
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
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
app.include_router(admin_router)


def run_migrations():
    """Cria colunas e tabelas adicionais se não existirem."""
    with engine.begin() as conn:
        conn.execute(text("""
            ALTER TABLE empresas
            ADD COLUMN IF NOT EXISTS regime_tributario VARCHAR(50);
        """))
        # quantidade em itens_fiscais
        from sqlalchemy import inspect
        insp = inspect(engine)
        if "itens_fiscais" in insp.get_table_names():
            cols = [c["name"] for c in insp.get_columns("itens_fiscais")]
            if "quantidade" not in cols:
                conn.execute(text("ALTER TABLE itens_fiscais ADD COLUMN quantidade REAL"))


@app.on_event("startup")
async def startup():
    models.Base.metadata.create_all(bind=engine)
    run_migrations()

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


@app.get("/teste-banco")
@limiter.limit("30/minute")
def teste_banco(request: Request):
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        return {
            "status": "Banco conectado",
            "resultado": result.scalar()
        }


@app.post("/upload-xml")
async def upload_xml(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario_atual: models.User = Depends(get_usuario_atual)
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
    analise = analisar_xml(conteudo)

    engine = TaxConsistencyEngine()
    consistencia = engine.verificar_consistencia(
        dados_xml=dados,
        dados_motor=analise
    )
    analise["consistencia_fiscal"] = consistencia

    # Motor dual: ST no XML → validar; ST ausente → calcular
    enriquecer_st_se_necessario(dados, analise)
    mva = analise.get("mva_utilizada") or analise.get("mva_percentual")
    if mva is not None:
        dados["mva_utilizada"] = float(mva) if isinstance(mva, str) else mva

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

    print(dados)
    documento = persistir_documento_fiscal(db, usuario_atual, empresa, dados)
    return {"documento_id": documento.id}


@app.post("/criar-planos")
@limiter.limit("5/minute")
def criar_planos(
    request: Request,
    db: Session = Depends(get_db),
    usuario_atual: models.User = Depends(get_usuario_atual),
):

    planos = [
        models.Plano(nome="Basico", limite_cnpjs=5, limite_analises=100),
        models.Plano(nome="Pro", limite_cnpjs=10, limite_analises=500),
        models.Plano(nome="Ilimitado", limite_cnpjs=999999, limite_analises=999999),
        models.Plano(nome="Teste", limite_cnpjs=2, limite_analises=2),  # para teste de limite
    ]

    for plano in planos:
        db.add(plano)

    db.commit()

    return {"mensagem": "Planos criados com sucesso"}