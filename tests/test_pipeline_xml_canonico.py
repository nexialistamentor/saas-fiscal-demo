"""
Testes do eixo canónico XML — quatro camadas distintas, sem desvio.

1. executar_analise_xml          — núcleo puro (sem DB)
2. executar_e_registrar_analise_xml — persistência completa + InsightEngine
3. processar_xml_job             — delegação para o eixo canónico
4. lote_router                   — contrato documental (DT-FLUXO-02)
"""

import ast
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.database import SessionLocal
from app.jobs.analysis_job import processar_xml_job
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
from app.services.analysis_orchestrator import executar_analise_xml
from app.services.registro_analise_service import executar_e_registrar_analise_xml

XML_FIXTURE = (
    Path(__file__).resolve().parents[1] / "app" / "xmls_testes" / "xml_icms10_st_sintetico.xml"
)
CHAVE_NFE_ICMS10 = "35250912345678000199650100000030011833829765"
LOTE_ROUTER_PATH = (
    Path(__file__).resolve().parents[1] / "app" / "routes" / "lote_router.py"
)


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
    """User + empresa isolados por uuid (email único)."""
    email = f"pipeline_{uuid.uuid4().hex}@example.com"
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
    return user, empresa


def _cleanup_icms10_st(db, user_id: int, empresa_id: int):
    """Remove artefactos do fixture ICMS10 para user/empresa de teste."""
    relatorio_ids = [
        r.id
        for r in db.query(RelatorioAnalise.id)
        .filter(
            (RelatorioAnalise.empresa_id == empresa_id)
            | (RelatorioAnalise.user_id == user_id)
            | (RelatorioAnalise.xml_chave == CHAVE_NFE_ICMS10)
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
            | (DocumentoFiscal.chave_nfe == CHAVE_NFE_ICMS10)
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
        | (RelatorioAnalise.xml_chave == CHAVE_NFE_ICMS10)
    ).delete(synchronize_session=False)
    db.query(UsoPlataforma).filter(UsoPlataforma.empresa_id == empresa_id).delete()
    db.query(Empresa).filter(Empresa.id == empresa_id).delete()
    db.query(User).filter(User.id == user_id).delete()
    db.commit()


def _imports_de_modulo(caminho: Path) -> set[str]:
    tree = ast.parse(caminho.read_text(encoding="utf-8"))
    nomes: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                nomes.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                nomes.add(alias.asname or alias.name)
    return nomes


def test_executar_analise_xml_processa_fixture_real():
    xml_bytes = XML_FIXTURE.read_bytes()

    resultado = executar_analise_xml(xml_bytes)

    dados = resultado.get("dados_fiscais", {})
    assert dados.get("erro") is None

    # Caracterização do comportamento real do parser em HEAD —
    # mva_utilizada NÃO é extraído do XML hoje (None), conforme
    # CT-DOC-001: "mva_utilizada não vem do documento, é derivado
    # pelo motor fiscal após promotion".
    assert dados.get("mva_utilizada") is None

    # base_st e icms_st SÃO extraídos directamente do XML — provado.
    assert dados.get("base_st") == "350.00"
    assert dados.get("icms_st") == "18.00"


def test_executar_e_registrar_analise_xml_persiste_ciclo_completo():
    db = SessionLocal()
    user, empresa = _seed_user_empresa(db)
    try:
        _cleanup_icms10_st(db, user.id, empresa.id)

        xml_bytes = XML_FIXTURE.read_bytes()
        rel, resultado = executar_e_registrar_analise_xml(
            db, xml_bytes, user.id, empresa.id
        )

        assert rel.analysis_type == "xml_analise"
        assert rel.status != "erro"
        assert resultado.get("dados_fiscais", {}).get("erro") is None

        # Efeito do InsightEngine / score (mesmo que parcial ou zero)
        assert rel.total_alertas is not None
        assert rel.score_resultante is not None
    finally:
        _cleanup_icms10_st(db, user.id, empresa.id)
        db.close()


def test_processar_xml_job_delega_para_eixo_canonico():
    xml_bytes = XML_FIXTURE.read_bytes()
    empresa_id = 42

    mock_emp = MagicMock()
    mock_emp.user_id = 7

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_emp

    mock_rel = MagicMock()
    mock_rel.id = 99

    with patch("app.jobs.analysis_job.SessionLocal", return_value=mock_db), patch(
        "app.jobs.analysis_job.executar_e_registrar_analise_xml",
    ) as spy:
        spy.return_value = (mock_rel, {"dados_fiscais": {}})
        resultado = processar_xml_job(xml_bytes, empresa_id)

        spy.assert_called_once_with(
            db=mock_db,
            xml_bytes=xml_bytes,
            user_id=7,
            empresa_id=empresa_id,
        )
        assert resultado == {"relatorio_id": 99, "tem_resultado": True}
        mock_db.close.assert_called_once()


def test_lote_router_nao_usa_pipeline_canonico():
    """
    Contrato documental: confirma o estado actual (DT-FLUXO-02).

    lote_router usa apenas executar_analise_xml, sem persistência
    nem InsightEngine. Este teste falha se o desvio for corrigido
    sem actualizar este teste — é sinal intencional, não bug.
    """
    imports = _imports_de_modulo(LOTE_ROUTER_PATH)

    assert "executar_analise_xml" in imports
    assert "executar_e_registrar_analise_xml" not in imports
    assert "processar_e_persistir_xml" not in imports
