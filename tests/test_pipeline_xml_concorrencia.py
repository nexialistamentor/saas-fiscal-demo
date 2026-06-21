"""
Testes de concorrência — DT-FLUXO-03.

Proteção via UNIQUE(empresa_id, xml_chave, analysis_type) em
relatorios_analise (migration 0011 + ORM) e IntegrityError em
executar_e_registrar_analise_xml.

O teste de race só é fiável contra PostgreSQL (skipif em SQLite local).
Confirmação em produção depende do deploy aplicar a migration 0011.
"""

import threading
import uuid
from pathlib import Path

import pytest

from app.database import SessionLocal, engine
from app.models import (
    AlertaFiscal,
    DocumentoFiscal,
    Empresa,
    EngineResultado,
    Insight,
    InteligenciaSnapshot,
    ItemFiscal,
    RelatorioAnalise,
    UsoPlataforma,
    User,
)
from app.security import hash_senha
from app.services.registro_analise_service import executar_e_registrar_analise_xml

XML_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "app" / "xmls_testes" / "xml_icms10_st_entrada.xml"
)
CHAVE_NFE = "35250912345678000199650100000030011833829765"

_USA_POSTGRES = engine.url.get_backend_name().startswith("postgresql")


def _cpf_unico_valido() -> str:
    base = f"{uuid.uuid4().int % 10**9:09d}"
    s = sum(int(d) * (10 - i) for i, d in enumerate(base))
    r = s % 11
    d1 = 0 if r < 2 else 11 - r
    s = sum(int(base[i]) * (11 - i) for i in range(9)) + d1 * 2
    r2 = s % 11
    d2 = 0 if r2 < 2 else 11 - r2
    return base + f"{d1}{d2}"


def _seed_user_empresa(db):
    """User + empresa isolados por uuid (email único) — mesmo contrato do canónico."""
    email = f"race_{uuid.uuid4().hex}@pytest.local"
    user = User(
        email=email,
        hashed_password=hash_senha("testpass"),
        cpf=_cpf_unico_valido(),
    )
    db.add(user)
    db.flush()

    empresa = Empresa(
        cnpj="98765432000188",
        razao_social="COMERCIO DESTINO LTDA",
        regime_tributario="presumido",
        user_id=user.id,
        uf="SP",
        porte="me",
        status_empresa="ativa",
    )
    db.add(empresa)
    db.commit()
    db.refresh(user)
    db.refresh(empresa)
    return user, empresa, email


def _cleanup_race(db, user_id: int, empresa_id: int, email: str | None = None):
    """Remove artefactos do fixture ICMS10 para user/empresa de teste."""
    relatorio_ids = [
        r.id
        for r in db.query(RelatorioAnalise.id)
        .filter(
            (RelatorioAnalise.empresa_id == empresa_id)
            | (RelatorioAnalise.user_id == user_id)
            | (RelatorioAnalise.xml_chave == CHAVE_NFE)
        )
        .all()
    ]

    if relatorio_ids:
        db.query(EngineResultado).filter(
            EngineResultado.relatorio_analise_id.in_(relatorio_ids)
        ).delete(synchronize_session=False)
        db.query(AlertaFiscal).filter(
            AlertaFiscal.relatorio_analise_id.in_(relatorio_ids)
        ).delete(synchronize_session=False)

    db.query(AlertaFiscal).filter(AlertaFiscal.empresa_id == empresa_id).delete()
    db.query(Insight).filter(Insight.empresa_id == empresa_id).delete()
    db.query(InteligenciaSnapshot).filter(
        InteligenciaSnapshot.empresa_id == empresa_id
    ).delete()

    doc_ids = [
        d.id
        for d in db.query(DocumentoFiscal.id)
        .filter(
            (DocumentoFiscal.empresa_id == empresa_id)
            | (DocumentoFiscal.chave_nfe == CHAVE_NFE)
        )
        .all()
    ]
    if doc_ids:
        db.query(ItemFiscal).filter(ItemFiscal.documento_id.in_(doc_ids)).delete(
            synchronize_session=False
        )
        db.query(DocumentoFiscal).filter(DocumentoFiscal.id.in_(doc_ids)).delete(
            synchronize_session=False
        )

    db.query(RelatorioAnalise).filter(
        (RelatorioAnalise.empresa_id == empresa_id)
        | (RelatorioAnalise.user_id == user_id)
        | (RelatorioAnalise.xml_chave == CHAVE_NFE)
    ).delete(synchronize_session=False)
    db.query(UsoPlataforma).filter(UsoPlataforma.empresa_id == empresa_id).delete()
    db.query(Empresa).filter(Empresa.id == empresa_id).delete()
    db.query(User).filter(User.id == user_id).delete()
    db.commit()


@pytest.mark.integration
def test_chamadas_sequenciais_nao_duplicam_relatorio():
    db = SessionLocal()
    user, empresa, email = _seed_user_empresa(db)
    try:
        _cleanup_race(db, user.id, empresa.id, email)

        xml_bytes = XML_FIXTURE.read_bytes()

        rel1, _ = executar_e_registrar_analise_xml(
            db, xml_bytes, user.id, empresa.id
        )
        rel2, resultado2 = executar_e_registrar_analise_xml(
            db, xml_bytes, user.id, empresa.id
        )

        assert resultado2.get("status") == "duplicado"
        assert resultado2.get("relatorio_id") == rel1.id
        assert rel2.id == rel1.id

        count = (
            db.query(RelatorioAnalise)
            .filter(
                RelatorioAnalise.empresa_id == empresa.id,
                RelatorioAnalise.xml_chave == CHAVE_NFE,
            )
            .count()
        )
        assert count == 1
    finally:
        _cleanup_race(db, user.id, empresa.id, email)
        db.close()


@pytest.mark.integration
@pytest.mark.skipif(
    not _USA_POSTGRES,
    reason=(
        "DT-FLUXO-03 race test só é fiável contra PostgreSQL. "
        "SQLite local serializa escritas ao nível do ficheiro."
    ),
)
def test_executar_e_registrar_analise_xml_mesmo_xml_concorrente_nao_duplica():
    db_setup = SessionLocal()
    try:
        user, empresa, email = _seed_user_empresa(db_setup)
        _cleanup_race(db_setup, user.id, empresa.id, email)
        user_id, empresa_id = user.id, empresa.id
    finally:
        db_setup.close()

    xml_bytes = XML_FIXTURE.read_bytes()
    barrier = threading.Barrier(2)
    erros = []

    def _chamada():
        db = SessionLocal()
        try:
            barrier.wait(timeout=5)
            executar_e_registrar_analise_xml(db, xml_bytes, user_id, empresa_id)
        except Exception as exc:
            erros.append(exc)
        finally:
            db.close()

    t1 = threading.Thread(target=_chamada)
    t2 = threading.Thread(target=_chamada)
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert not erros, f"Threads falharam: {erros}"

    db_check = SessionLocal()
    try:
        count = (
            db_check.query(RelatorioAnalise)
            .filter(
                RelatorioAnalise.empresa_id == empresa_id,
                RelatorioAnalise.analysis_type == "xml_analise",
                RelatorioAnalise.xml_chave == CHAVE_NFE,
            )
            .count()
        )
        assert count == 1, f"Esperado 1 RelatorioAnalise, encontrados {count}"
    finally:
        _cleanup_race(db_check, user_id, empresa_id, email)
        db_check.close()
