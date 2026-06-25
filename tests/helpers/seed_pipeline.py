"""
tests/helpers/seed_pipeline.py
Helper partilhado para testes de integração do pipeline XML.

Unifica:
  - _cpf_unico_valido (duplicado em 3 ficheiros)
  - seed_user_empresa
  - cleanup_icms10_st (limpa estritamente por user_id + empresa_id)
"""

import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import (
    AlertaFiscal,
    DocumentoFiscal,
    Empresa,
    EngineResultado,
    Insight,
    InteligenciaSnapshot,
    ItemFiscal,
    Pagamento,
    PagamentoTentativa,
    RelatorioAnalise,
    UsoPlataforma,
    User,
)
from app.security import hash_senha

# ---------------------------------------------------------------------------
# Constantes de fixture
# ---------------------------------------------------------------------------

XML_FIXTURE = (
    Path(__file__).resolve().parents[2] / "app" / "xmls_testes" / "xml_icms10_st_sintetico.xml"
)
# Fixture sintética. Não usar XML real no repositório.
CNPJ_FIXTURE = "12345678000199"
CHAVE_NFE = "35250912345678000199650100000030011833829765"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cpf_unico_valido() -> str:
    base = f"{uuid.uuid4().int % 10**9:09d}"
    s = sum(int(d) * (10 - i) for i, d in enumerate(base))
    r = s % 11
    d1 = 0 if r < 2 else 11 - r
    s2 = sum(int(base[i]) * (11 - i) for i in range(9)) + d1 * 2
    r2 = s2 % 11
    d2 = 0 if r2 < 2 else 11 - r2
    return base + f"{d1}{d2}"


def seed_user_empresa(db: Session) -> tuple:
    """
    Cria User + Empresa isolados por UUID.
    Empresa com CNPJ do emitente no XML de fixture — /upload-xml resolve por emitente.
    """
    email = f"pipeline_{uuid.uuid4().hex}@example.com"
    user = User(
        email=email,
        hashed_password=hash_senha("testpass"),
        cpf=_cpf_unico_valido(),
    )
    db.add(user)
    db.flush()
    empresa = Empresa(
        cnpj=CNPJ_FIXTURE,
        razao_social="DISTRIBUIDORA EXEMPLO LTDA",
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
    return user, empresa


def cleanup_icms10_st(db: Session, user_id: int, empresa_id: int) -> None:
    """
    Remove artefactos estritamente por user_id + empresa_id.
    Ordem inversa de FK para evitar IntegrityError.
    Inclui Pagamento → FK opcional para RelatorioAnalise.
    """
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
        # Pagamento tem FK opcional para RelatorioAnalise — limpar antes
        pagamento_ids = [
            p.id
            for p in db.query(Pagamento).filter(
                Pagamento.relatorio_analise_id.in_(relatorio_ids)
            ).all()
        ]
        if pagamento_ids:
            db.query(PagamentoTentativa).filter(
                PagamentoTentativa.pagamento_id.in_(pagamento_ids)
            ).delete(synchronize_session=False)
            db.query(Pagamento).filter(
                Pagamento.id.in_(pagamento_ids)
            ).delete(synchronize_session=False)

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

    db.query(RelatorioAnalise).filter(
        (RelatorioAnalise.empresa_id == empresa_id)
        | (RelatorioAnalise.user_id == user_id)
        | (RelatorioAnalise.xml_chave == CHAVE_NFE)
    ).delete(synchronize_session=False)

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
        db.query(ItemFiscal).filter(
            ItemFiscal.documento_id.in_(doc_ids)
        ).delete(synchronize_session=False)
        db.query(DocumentoFiscal).filter(
            DocumentoFiscal.id.in_(doc_ids)
        ).delete(synchronize_session=False)

    # Pagamentos do user sem relatório
    pagamento_user_ids = [
        p.id
        for p in db.query(Pagamento).filter(
            Pagamento.user_id == user_id
        ).all()
    ]
    if pagamento_user_ids:
        db.query(PagamentoTentativa).filter(
            PagamentoTentativa.pagamento_id.in_(pagamento_user_ids)
        ).delete(synchronize_session=False)
        db.query(Pagamento).filter(
            Pagamento.id.in_(pagamento_user_ids)
        ).delete(synchronize_session=False)

    db.query(UsoPlataforma).filter(UsoPlataforma.empresa_id == empresa_id).delete()
    db.query(Empresa).filter(Empresa.id == empresa_id).delete()
    db.query(User).filter(User.id == user_id).delete()
    db.commit()
