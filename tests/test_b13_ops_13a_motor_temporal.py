"""
B13-OPS-13A — Testes do motor temporal normativo.
"""

from pathlib import Path

import pytest

from app.services.tax_engines.base_tax_engine import (
    BaseTaxEngine,
    TempoNormativoAusenteError,
)

ENGINES_EM_ESCOPO = [
    "app/services/tax_engines/cpf_tax_engine.py",
    "app/services/tax_engines/csll_engine.py",
    "app/services/tax_engines/irpj_engine.py",
    "app/services/tax_engines/lucro_presumido_engine.py",
    "app/services/tax_engines/lucro_real_engine.py",
    "app/services/tax_engines/mei_engine.py",
    "app/services/tax_engines/mei_tax_engine.py",
    "app/services/tax_engines/pis_cofins_engine.py",
    "app/services/tax_engines/tax_planning_engine.py",
    "app/services/tax_engines/tax_recovery_engine.py",
]


def test_base_tax_engine_sem_ano_vigencia_fixo():
    src = Path("app/services/tax_engines/base_tax_engine.py").read_text(encoding="utf-8")
    assert "ano_vigencia = 2024" not in src
    assert "ano_vigencia = 2026" not in src


def test_resolver_usa_ano_referencia():
    eng = BaseTaxEngine()
    assert eng.resolver_ano_referencia({"ano_referencia": 2026}) == 2026


def test_resolver_usa_data_referencia():
    from datetime import date

    eng = BaseTaxEngine()
    assert eng.resolver_ano_referencia({"data_referencia": date(2026, 3, 1)}) == 2026


def test_resolver_bloqueia_sem_dado_temporal():
    eng = BaseTaxEngine()
    with pytest.raises(TempoNormativoAusenteError):
        eng.resolver_ano_referencia({})


@pytest.mark.parametrize("caminho", ENGINES_EM_ESCOPO)
def test_engine_usa_resolver_ano_referencia(caminho):
    src = Path(caminho).read_text(encoding="utf-8")
    assert "resolver_ano_referencia" in src, f"{caminho} não chama resolver_ano_referencia"


def test_cpf_engine_fora_do_escopo_nao_herda_base():
    src = Path("app/services/tax_engines/cpf_engine.py").read_text(encoding="utf-8")
    assert "BaseTaxEngine" not in src


def test_insights_engine_converte_erro_temporal_em_bloqueio_l3():
    src = Path("app/services/insights_engine.py").read_text(encoding="utf-8")
    assert "TempoNormativoAusenteError" in src
    assert "TEMPO_NORMATIVO_AUSENTE" in src
    assert '"estado_l3": "bloqueado"' in src or "'estado_l3': 'bloqueado'" in src
