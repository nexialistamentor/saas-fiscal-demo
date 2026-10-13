"""C2: validação nas fronteiras, sem alterar o contrato C0 congelado."""
from datetime import date
from unittest.mock import patch
import pytest
from app.services import insights_engine
from app.services.tax_engines.lucro_presumido_engine import (
    LucroPresumidoEngine, calcular_lucro_presumido, AtividadeFiscalIndisponivelError,
)
from app.services.tax_engines.tax_planning_engine import simular_regimes


def _contexto(**alteracoes):
    c = {"regime": "presumido", "atividade": "comercio", "faturamento": 10000.0,
         "lucro": 2000.0, "data_referencia": date(2026, 1, 1)}
    c.update(alteracoes)
    return c


@pytest.mark.parametrize("regime", [None, "", " ", "invalido", 123, []])
def test_regime_invalido_bloqueia_todas_as_engines_dependentes_antes_da_execucao(regime):
    nomes = ['irpj', 'csll', 'pis_cofins', 'lucro_real', 'lucro_presumido', 'tax_planning', 'tax_recovery']
    class Proibida:
        def __init__(self):
            pytest.fail("Engine financeira executada sem regime comprovado")
    with patch.object(insights_engine, 'ENGINES', {n: Proibida for n in nomes}):
        r = insights_engine.executar_engines(_contexto(regime=regime))
    assert set(r) == set(nomes)
    assert all(v['calculo_autorizado'] is False and v['estado_l3'] == 'bloqueado' for v in r.values())
    assert all('comparacao' not in v and 'economia_estimada' not in v for v in r.values())


def test_campo_regime_ausente_tambem_bloqueia():
    c = _contexto(); del c['regime']
    with patch.object(insights_engine, 'ENGINES', {'lucro_presumido': LucroPresumidoEngine}):
        assert insights_engine.executar_engines(c)['lucro_presumido']['calculo_autorizado'] is False


@pytest.mark.parametrize('atividade', [None, '', 'atividade_desconhecida', 123, []])
def test_funcao_presumido_e_comparador_direto_nao_transformam_atividade_invalida_em_zero(atividade):
    with pytest.raises(AtividadeFiscalIndisponivelError):
        calcular_lucro_presumido(_contexto(atividade=atividade))
    with pytest.raises(AtividadeFiscalIndisponivelError):
        simular_regimes(_contexto(atividade=atividade))


@pytest.mark.parametrize('regime', [None, '', 'invalido'])
def test_engine_presumida_direta_bloqueia_regime_invalido(regime):
    res = LucroPresumidoEngine().execute(_contexto(regime=regime))
    assert res['calculo_autorizado'] is False
    assert res['estado_l3'] == 'bloqueado'
    assert 'data' not in res


@pytest.mark.parametrize('atividade,irpj,csll', [('comercio',120.0,108.0),('industria',120.0,108.0),('servicos',480.0,288.0)])
def test_tres_atividades_explicitas_mantem_formulas(atividade, irpj, csll):
    r = LucroPresumidoEngine().execute(_contexto(atividade=atividade))
    assert r['success'] is True
    assert r['data']['tributos']['irpj'] == pytest.approx(irpj)
    assert r['data']['tributos']['csll'] == pytest.approx(csll)
    res = simular_regimes(_contexto(atividade=atividade))
    assert res['comparacao']['lucro_presumido'] == pytest.approx(irpj+csll+365.0)
    assert 'melhor_regime' in res
