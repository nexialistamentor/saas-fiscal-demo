"""AG-VALIDACAO: testes de promoção e rejeição de candidatas_oficial."""

from datetime import date

import pytest

from app.database import SessionLocal
from app.agents.normative_validation_agent import NormativeValidationAgent
from app.models import TabelaMVA, TabelaPMPF


@pytest.fixture(autouse=True)
def limpar():
    db = SessionLocal()
    db.query(TabelaMVA).filter(TabelaMVA.estado == "XT").delete()
    db.query(TabelaPMPF).filter(TabelaPMPF.estado == "XT").delete()
    db.commit()
    db.close()
    yield
    db = SessionLocal()
    db.query(TabelaMVA).filter(TabelaMVA.estado == "XT").delete()
    db.query(TabelaPMPF).filter(TabelaPMPF.estado == "XT").delete()
    db.commit()
    db.close()


@pytest.mark.asyncio
async def test_promove_mva_candidata_valida():
    db = SessionLocal()
    db.add(
        TabelaMVA(
            estado="XT",
            ncm="22021000",
            mva=66.0,
            aliquota_interna=0.18,
            vigencia_inicio=date(2026, 1, 1),
            fonte_legal="Portaria Teste 001/2026 — SEFAZ-XT",
            url_fonte="https://sefaz.xt.gov.br/portaria-001-2026",
            nivel_confianca_fonte="candidata_oficial",
            importado_por="test",
        )
    )
    db.commit()
    db.close()

    agent = NormativeValidationAgent()
    result = await agent.run({})
    assert result["promovidas_mva"] >= 1
    assert result["rejeitadas"] == 0

    db = SessionLocal()
    reg = db.query(TabelaMVA).filter(
        TabelaMVA.estado == "XT", TabelaMVA.ncm == "22021000"
    ).first()
    assert reg is not None
    assert reg.nivel_confianca_fonte == "oficial"
    assert "AG-VALIDACAO" in (reg.importado_por or "")
    db.close()


@pytest.mark.asyncio
async def test_rejeita_mva_sem_fonte_legal():
    db = SessionLocal()
    db.add(
        TabelaMVA(
            estado="XT",
            ncm="22021000",
            mva=66.0,
            aliquota_interna=0.18,
            vigencia_inicio=date(2026, 1, 1),
            fonte_legal="",
            url_fonte="https://sefaz.xt.gov.br/portaria",
            nivel_confianca_fonte="candidata_oficial",
            importado_por="test",
        )
    )
    db.commit()
    db.close()

    agent = NormativeValidationAgent()
    result = await agent.run({})
    assert result["rejeitadas"] >= 1
    tipos = [a["tipo"] for a in result["alertas"]]
    assert "CANDIDATA_REJEITADA_MVA" in tipos


@pytest.mark.asyncio
async def test_nao_promove_se_conflito_oficial():
    db = SessionLocal()
    db.add(
        TabelaMVA(
            estado="XT",
            ncm="22021000",
            mva=40.0,
            aliquota_interna=0.18,
            vigencia_inicio=date(2024, 1, 1),
            fonte_legal="Portaria Oficial 001/2024 — SEFAZ-XT",
            url_fonte="https://sefaz.xt.gov.br/portaria-001-2024",
            nivel_confianca_fonte="oficial",
            importado_por="seed",
        )
    )
    db.add(
        TabelaMVA(
            estado="XT",
            ncm="22021000",
            mva=66.0,
            aliquota_interna=0.18,
            vigencia_inicio=date(2026, 1, 1),
            fonte_legal="Portaria Candidata 002/2026 — SEFAZ-XT",
            url_fonte="https://sefaz.xt.gov.br/portaria-002-2026",
            nivel_confianca_fonte="candidata_oficial",
            importado_por="test",
        )
    )
    db.commit()
    db.close()

    agent = NormativeValidationAgent()
    result = await agent.run({})
    assert result["rejeitadas"] >= 1


@pytest.mark.asyncio
async def test_skip_ag_validacao_para_empresa_id_nao_global():
    """Promoção normativa é global — não deve correr para empresa_id != 1."""
    db = SessionLocal()
    db.add(
        TabelaMVA(
            estado="XT",
            ncm="22021000",
            mva=66.0,
            aliquota_interna=0.18,
            vigencia_inicio=date(2026, 1, 1),
            fonte_legal="Portaria Skip 003/2026 — SEFAZ-XT",
            url_fonte="https://sefaz.xt.gov.br/portaria-003-2026",
            nivel_confianca_fonte="candidata_oficial",
            importado_por="test_skip",
        )
    )
    db.commit()
    db.close()

    agent = NormativeValidationAgent()
    result = await agent.run({"empresa_id": 99})
    assert result["status"] == "pulado_multi_empresa"
    assert result["promovidas_mva"] == 0
    assert result["total_alertas"] == 0

    db = SessionLocal()
    reg = db.query(TabelaMVA).filter(
        TabelaMVA.estado == "XT", TabelaMVA.ncm == "22021000"
    ).first()
    assert reg is not None
    assert reg.nivel_confianca_fonte == "candidata_oficial"
    db.close()


@pytest.mark.asyncio
async def test_ag_validacao_executa_com_empresa_id_1():
    db = SessionLocal()
    db.add(
        TabelaMVA(
            estado="XT",
            ncm="33049990",
            mva=55.0,
            aliquota_interna=0.18,
            vigencia_inicio=date(2026, 2, 1),
            fonte_legal="Portaria Um 004/2026 — SEFAZ-XT",
            url_fonte="https://sefaz.xt.gov.br/portaria-004-2026",
            nivel_confianca_fonte="candidata_oficial",
            importado_por="test_e1",
        )
    )
    db.commit()
    db.close()

    agent = NormativeValidationAgent()
    result = await agent.run({"empresa_id": 1})
    assert result["promovidas_mva"] >= 1
    assert result["status"] == "executado"

    db = SessionLocal()
    reg = db.query(TabelaMVA).filter(
        TabelaMVA.estado == "XT", TabelaMVA.ncm == "33049990"
    ).first()
    assert reg is not None
    assert reg.nivel_confianca_fonte == "oficial"
    db.close()
