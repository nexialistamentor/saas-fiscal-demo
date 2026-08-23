import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.schemas.user_schema import UserCreate, UserResponse, UserSession
from app.security import (
    hash_senha,
    verificar_senha,
    criar_token,
    get_usuario_atual,
    decodificar_token_acesso_valido,
    oauth2_scheme,
)
from app.token_revocation import revogacao_jti
from app.seed_data import ensure_planos
from app.rate_limit import limiter, login_throttle
from app.constants import (
    VERSAO_TERMOS_ATUAL,
    TERMOS_CACHE_TTL,
    VERSAO_POLITICA_PRIVACIDADE,
    FINALIDADE_SIMULACAO,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


def _consulta_liberada_no_registro() -> bool:
    v = os.environ.get("LIBERAR_CONSULTA_REGISTRO", "").strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    url = os.environ.get("DATABASE_URL", "")
    return "sqlite" in url


@router.post("/register", response_model=UserResponse)
@limiter.limit("3/minute")
def register_user(request: Request, user: UserCreate, db: Session = Depends(get_db)) -> UserResponse:

    existing_user = db.query(models.User).filter(
        models.User.email == user.email
    ).first()

    if existing_user:
        raise HTTPException(status_code=400, detail="Email já cadastrado")

    ensure_planos(db)

    plano_basico = db.query(models.Plano).filter(
        models.Plano.nome == "Basico"
    ).first()

    if not plano_basico:
        raise HTTPException(status_code=500, detail="Falha ao garantir planos no banco")

    hashed = hash_senha(user.password)

    new_user = models.User(
        email=user.email,
        hashed_password=hashed,
        plano_id=plano_basico.id,
        consulta_paga=_consulta_liberada_no_registro(),
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    empresa_id = None

    if user.tipo_usuario == "cpf":
        if user.documento:
            new_user.cpf = user.documento.strip()
            db.commit()
            db.refresh(new_user)
    else:
        regime = "mei" if user.tipo_usuario == "mei" else "simples"
        emp = models.Empresa(
            razao_social=user.nome.strip() if user.nome else None,
            regime_tributario=regime,
            cnpj=user.documento.strip() if user.documento else None,
            user_id=new_user.id,
        )
        db.add(emp)
        db.commit()
        db.refresh(emp)
        empresa_id = emp.id

    return UserResponse(id=new_user.id, email=new_user.email, empresa_id=empresa_id, role=new_user.role)


@router.post("/login")
@limiter.limit("5/minute")
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> dict[str, str]:

    email = form_data.username

    if login_throttle.esta_bloqueado(email):
        restante = login_throttle.tempo_restante(email)
        raise HTTPException(
            status_code=429,
            detail=f"Conta temporariamente bloqueada. Tente novamente em {restante}s.",
            headers={"Retry-After": str(restante)},
        )

    usuario = db.query(models.User).filter(
        models.User.email == email,
    ).first()

    if not usuario:
        login_throttle.registrar_falha(email)
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    if not verificar_senha(form_data.password, usuario.hashed_password):
        login_throttle.registrar_falha(email)
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    login_throttle.limpar(email)
    token = criar_token({"sub": usuario.email, "user_id": usuario.id})

    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserSession)
def me(usuario_atual: models.User = Depends(get_usuario_atual)) -> UserSession:
    return usuario_atual


@router.post("/accept-terms")
def accept_terms(
    request: Request,
    db: Session = Depends(get_db),
    usuario_atual: models.User = Depends(get_usuario_atual),
):
    ip = request.client.host if request.client else None
    aceitacao = models.TermosAceitacao(
        user_id=usuario_atual.id,
        versao_termos=VERSAO_TERMOS_ATUAL,
        aceite_em=datetime.utcnow(),
        ip_address=ip,
    )
    db.add(aceitacao)
    db.commit()
    try:
        from app.redis_connection import get_redis_connection

        redis_client, _, _ = get_redis_connection()
        if redis_client:
            cache_key = f"termos:v{VERSAO_TERMOS_ATUAL}:{usuario_atual.email}"
            redis_client.setex(cache_key, TERMOS_CACHE_TTL, "1")
    except Exception:
        pass
    return {"status": "aceito"}


@router.get("/has-accepted-terms")
def has_accepted_terms(
    db: Session = Depends(get_db),
    usuario_atual: models.User = Depends(get_usuario_atual),
):
    aceitacao = db.query(models.TermosAceitacao).filter(
        models.TermosAceitacao.user_id == usuario_atual.id,
        models.TermosAceitacao.versao_termos == VERSAO_TERMOS_ATUAL,
    ).first()
    return {"accepted": aceitacao is not None}


@router.get("/privacy", include_in_schema=False)
def politica_privacidade():
    from fastapi.responses import HTMLResponse

    html = """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head><meta charset="UTF-8"><title>Política de Privacidade</title></head>
    <body>
    <h1>Política de Privacidade</h1>
    <p><strong>Versão 1.0 — vigente a partir de maio de 2026</strong></p>
    <h2>1. Quem somos</h2>
    <p>Esta plataforma é uma ferramenta de simulação tributária. Os dados recolhidos são usados exclusivamente para gerar simulações e insights fiscais.</p>
    <h2>2. Dados recolhidos</h2>
    <p>Email, CPF (opcional), endereço IP, dados fiscais enviados via XML (valores, NCM, ICMS). Estes dados são necessários para o funcionamento do serviço.</p>
    <h2>3. Finalidade</h2>
    <p>Simulação tributária, geração de insights fiscais e melhoria do serviço. Os dados não são partilhados com terceiros para fins comerciais.</p>
    <h2>4. Base legal</h2>
    <p>Consentimento explícito do titular (art. 7º, I, LGPD) e execução de contrato (art. 7º, V, LGPD).</p>
    <h2>5. Armazenamento</h2>
    <p>PostgreSQL e Redis hospedados no Railway (EUA). Dados encriptados em trânsito (TLS).</p>
    <h2>6. Retenção</h2>
    <p>Dados fiscais podem ser retidos por até 5 anos por obrigação legal (art. 195, CTN). Outros dados pessoais são eliminados ou anonimizados a pedido.</p>
    <h2>7. Direitos do titular</h2>
    <p>Acesso, rectificação, eliminação e portabilidade. Contacto: privacidade@saas-fiscal.com</p>
    <h2>8. Aviso legal</h2>
    <p>Esta plataforma é uma ferramenta de simulação e não substitui a consulta a um contador ou profissional qualificado.</p>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@router.post("/consent")
def registar_consentimento(
    request: Request,
    db: Session = Depends(get_db),
    usuario_atual: models.User = Depends(get_usuario_atual),
):
    ip = request.client.host if request.client else None
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0].strip()

    consentimento = models.ConsentimentoLGPD(
        user_id=usuario_atual.id,
        versao_politica=VERSAO_POLITICA_PRIVACIDADE,
        finalidade=FINALIDADE_SIMULACAO,
        consentiu=True,
        consentiu_em=datetime.utcnow(),
        ip_address=ip,
    )
    db.add(consentimento)
    db.commit()
    return {"status": "consentimento registado", "versao_politica": VERSAO_POLITICA_PRIVACIDADE}


@router.get("/has-consented")
def verificar_consentimento(
    db: Session = Depends(get_db),
    usuario_atual: models.User = Depends(get_usuario_atual),
):
    consentimento = (
        db.query(models.ConsentimentoLGPD)
        .filter(
            models.ConsentimentoLGPD.user_id == usuario_atual.id,
            models.ConsentimentoLGPD.versao_politica == VERSAO_POLITICA_PRIVACIDADE,
            models.ConsentimentoLGPD.consentiu.is_(True),
        )
        .first()
    )
    return {"consented": consentimento is not None}


@router.post("/logout")
@limiter.limit("30/minute")
def logout(request: Request, token: str = Depends(oauth2_scheme)) -> dict[str, str]:
    payload = decodificar_token_acesso_valido(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")
    jti = payload.get("jti")
    exp = payload.get("exp")
    if jti and exp is not None:
        if revogacao_jti.esta_revogado(jti):
            return {"detail": "Sessão encerrada"}
        revogacao_jti.registrar(jti, exp)
    return {"detail": "Sessão encerrada"}


@router.get("/my-data")
def obter_meus_dados(
    db: Session = Depends(get_db),
    usuario_atual: models.User = Depends(get_usuario_atual),
):
    """Direito de acesso — LGPD art. 18, II."""
    empresas = (
        db.query(func.count(models.Empresa.id))
        .filter(models.Empresa.user_id == usuario_atual.id)
        .scalar()
    )
    analises = (
        db.query(func.count(models.RelatorioAnalise.id))
        .filter(models.RelatorioAnalise.user_id == usuario_atual.id)
        .scalar()
    )
    termos = db.query(models.TermosAceitacao).filter(
        models.TermosAceitacao.user_id == usuario_atual.id
    ).all()
    consentimentos = db.query(models.ConsentimentoLGPD).filter(
        models.ConsentimentoLGPD.user_id == usuario_atual.id
    ).all()
    return {
        "email": usuario_atual.email,
        "cpf": usuario_atual.cpf,
        "role": usuario_atual.role,
        "empresas_registadas": empresas,
        "analises_realizadas": analises,
        "termos_aceites": [
            {"versao": t.versao_termos, "aceite_em": t.aceite_em.isoformat() if t.aceite_em else None, "ip": t.ip_address}
            for t in termos
        ],
        "consentimentos_lgpd": [
            {"versao_politica": c.versao_politica, "finalidade": c.finalidade, "consentiu_em": c.consentiu_em.isoformat() if c.consentiu_em else None, "ip": c.ip_address}
            for c in consentimentos
        ],
    }


@router.delete("/my-data")
def eliminar_meus_dados(
    db: Session = Depends(get_db),
    usuario_atual: models.User = Depends(get_usuario_atual),
):
    """
    Direito de eliminação — LGPD art. 18, VI.
    Dados fiscais são anonimizados (não apagados) por obrigação legal (CTN art. 195 — 5 anos).
    Dados pessoais identificáveis são eliminados ou anonimizados.
    """
    user_id = usuario_atual.id


    # 2. Eliminar consentimentos e termos
    db.query(models.ConsentimentoLGPD).filter(models.ConsentimentoLGPD.user_id == user_id).delete()
    db.query(models.TermosAceitacao).filter(models.TermosAceitacao.user_id == user_id).delete()

    # 3. Anonimizar dados pessoais do utilizador (não apagar — dados fiscais ficam)
    usuario_atual.email = f"deleted_{user_id}@anon.saas"
    usuario_atual.hashed_password = "ELIMINADO"
    usuario_atual.cpf = None

    db.commit()

    return {
        "status": "dados pessoais anonimizados",
        "aviso": "Dados fiscais retidos por obrigação legal (CTN art. 195 — 5 anos).",
    }