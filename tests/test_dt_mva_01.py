"""Contrato nacional fail-closed do resolvedor MVA/ST — Bloco A0 test-only.

DC-003: UF é dimensão da consulta, nunca autorização regional.
"oficial" representa a fonte promovida no modelo actual; candidata/estimativa
não têm autoridade financeira. Convênio sem alíquota conserva só análise MVA.
Os testes dos consumidores C2–C6 abaixo são preservados sem alterações.
"""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.services.fiscal_utils import resolver_aliquota_e_mva
from app.services.tax_engines.base_tax_engine import TempoNormativoAusenteError


REFERENCIA = date(2026, 1, 1)
NCM = "22021000"
UFS = (
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT",
    "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO",
    "RR", "SC", "SP", "SE", "TO",
)


@pytest.fixture
def db():
    return MagicMock()


def _regra_completa(**alteracoes):
    regra = {
        "mva": 0.35,
        "aliquota_interna": 0.17,
        "nivel_confianca_fonte": "oficial",
        "fonte_legal": "Portaria SEFAZ de teste — regra sintética validada",
        "vigencia_inicio": date(2025, 1, 1),
        "vigencia_fim": None,
    }
    regra.update(alteracoes)
    return regra


def _resolver(db, regra, uf="PA", ncm=NCM, referencia=REFERENCIA, cobertura=True):
    # Só o acesso aos dados é simulado; o resolvedor de produção é executado.
    with patch("app.services.fiscal_utils.uf_tem_dados_mva", return_value=cobertura), \
         patch("app.services.fiscal_utils.buscar_mva", return_value=regra):
        return resolver_aliquota_e_mva(db, uf, ncm, data_referencia=referencia)


def _assert_bloqueado(res):
    # Fallback numérico é compatível, mas não tem autoridade normativa.
    for campo in ("calculo_autorizado", "calculo_parcial", "mva_autorizada", "aliquota_autorizada"):
        assert res[campo] is False, f"Autoridade indevida: {campo}={res[campo]}"
    assert res["bloqueio_normativo"] is True
    assert res["motivo_bloqueio"]
    assert res["confianca"] == "indisponivel"
    assert res.get("aviso")
    assert res["fonte"] != "fora_de_escopo_normativo_piloto"
    assert res["motivo_bloqueio"] != "fora_de_escopo_normativo_piloto"


@pytest.mark.parametrize("uf", UFS)
def test_regra_oficial_vigente_autoriza_qualquer_uf(db, uf):
    res = _resolver(db, _regra_completa(), uf=uf)
    assert res["calculo_autorizado"] is True
    assert res["calculo_parcial"] is False
    assert res["mva_autorizada"] is True
    assert res["aliquota_autorizada"] is True
    assert res["bloqueio_normativo"] is False
    assert res["motivo_bloqueio"] is None
    assert res["fonte"] == "tabela"
    assert res["uf"] == uf
    assert res["ncm"] == NCM
    assert res["mva"] == pytest.approx(0.35)
    assert res["aliquota"] == pytest.approx(0.17)


@pytest.mark.parametrize("uf", ["PA", "SP", "MG", "RJ"])
def test_consulta_preserva_uf_ncm_e_data_explicita(db, uf):
    with patch("app.services.fiscal_utils.uf_tem_dados_mva", return_value=True), \
         patch("app.services.fiscal_utils.buscar_mva", return_value=_regra_completa()) as buscar:
        resolver_aliquota_e_mva(db, uf, NCM, data_referencia=REFERENCIA)
    buscar.assert_called_once_with(db, uf, NCM, data_referencia=REFERENCIA)


@pytest.mark.parametrize("uf", ["PA", "SP", "MG", "RJ"])
@pytest.mark.parametrize("cobertura", [True, False], ids=["uf_com_outros_dados", "uf_sem_dados"])
def test_sem_regra_vigente_bloqueia_independentemente_da_uf(db, uf, cobertura):
    _assert_bloqueado(_resolver(db, None, uf=uf, cobertura=cobertura))


@pytest.mark.parametrize("uf", [None, "", "  ", "ZZ", "P", "PARA", "PA-extra"])
def test_uf_ausente_ou_invalida_nao_adquire_autoridade(db, uf):
    _assert_bloqueado(_resolver(db, _regra_completa(), uf=uf))


@pytest.mark.parametrize("ncm", [None, "", "  ", "2202100", "220210000", "abcdefgh", "2202100X"])
def test_ncm_ausente_ou_invalido_nao_adquire_autoridade(db, ncm):
    _assert_bloqueado(_resolver(db, _regra_completa(), ncm=ncm))


def test_data_referencia_ausente_nao_adquire_autoridade(db):
    try:
        res = _resolver(db, _regra_completa(), referencia=None)
    except TempoNormativoAusenteError:
        return  # Exceção normativa explícita já prevista no contrato temporal.
    _assert_bloqueado(res)


@pytest.mark.parametrize("fonte", [None, "", "  ", 123])
def test_fonte_legal_ausente_ou_invalida_bloqueia(db, fonte):
    _assert_bloqueado(_resolver(db, _regra_completa(fonte_legal=fonte)))


def test_campo_fonte_legal_ausente_bloqueia(db):
    regra = _regra_completa()
    del regra["fonte_legal"]
    _assert_bloqueado(_resolver(db, regra))


@pytest.mark.parametrize("inicio", [None, "", "data-invalida"])
def test_inicio_vigencia_ausente_ou_invalido_bloqueia(db, inicio):
    _assert_bloqueado(_resolver(db, _regra_completa(vigencia_inicio=inicio)))


def test_campo_inicio_vigencia_ausente_bloqueia(db):
    regra = _regra_completa()
    del regra["vigencia_inicio"]
    _assert_bloqueado(_resolver(db, regra))


@pytest.mark.parametrize("alteracoes", [
    {"vigencia_inicio": date(2026, 1, 2)},
    {"vigencia_fim": date(2025, 12, 31)},
    {"vigencia_inicio": date(2025, 6, 1), "vigencia_fim": date(2025, 1, 1)},
    {"vigencia_fim": "data-invalida"},
], ids=["futura", "expirada_sem_substituto", "intervalo_invertido", "fim_invalido"])
def test_regra_fora_da_vigencia_ou_com_intervalo_invalido_bloqueia(db, alteracoes):
    # O retorno do acesso aos dados não é, por si só, prova de vigência.
    _assert_bloqueado(_resolver(db, _regra_completa(**alteracoes)))


@pytest.mark.parametrize("referencia", [date(2025, 1, 1), date(2025, 12, 31)])
def test_limites_inclusivos_da_vigencia_autorizam(db, referencia):
    res = _resolver(db, _regra_completa(vigencia_fim=date(2025, 12, 31)), referencia=referencia)
    assert res["calculo_autorizado"] is True


@pytest.mark.parametrize("nivel", [None, "", "sem_fonte", "estimativa", "candidata_oficial", "desconhecido"])
def test_fonte_nao_promovida_a_oficial_nao_adquire_autoridade(db, nivel):
    _assert_bloqueado(_resolver(db, _regra_completa(nivel_confianca_fonte=nivel)))


def test_nivel_de_fonte_ausente_nao_adquire_autoridade(db):
    regra = _regra_completa()
    del regra["nivel_confianca_fonte"]
    _assert_bloqueado(_resolver(db, regra))


def test_convenio_base_nao_autoriza_aliquota_financeira(db):
    res = _resolver(db, _regra_completa(nivel_confianca_fonte="convenio_base"))
    assert res["calculo_autorizado"] is False
    assert res["aliquota_autorizada"] is False


@pytest.mark.parametrize("uf", ["PA", "SP", "MG", "RJ"])
def test_convenio_sem_aliquota_preserva_mva_parcial_sem_financeiro(db, uf):
    res = _resolver(db, _regra_completa(
        nivel_confianca_fonte="convenio_base_sem_aliquota", mva=40.0, aliquota_interna=0.0,
    ), uf=uf)
    assert res["calculo_autorizado"] is False
    assert res["calculo_parcial"] is True
    assert res["mva_autorizada"] is True
    assert res["aliquota_autorizada"] is False
    assert res["bloqueio_normativo"] is False
    assert res["mva"] == pytest.approx(0.40)
    assert res["aliquota"] == 0.18


@pytest.mark.parametrize("alteracoes", [
    {"fonte_legal": None}, {"vigencia_inicio": None},
    {"vigencia_fim": date(2025, 12, 31)},
], ids=["sem_fonte", "sem_inicio", "expirado"])
def test_convenio_invalido_tambem_perde_autoridade_parcial(db, alteracoes):
    _assert_bloqueado(_resolver(db, _regra_completa(
        nivel_confianca_fonte="convenio_base_sem_aliquota", **alteracoes,
    )))


@pytest.mark.parametrize("campo", ["mva", "aliquota_interna"])
@pytest.mark.parametrize("valor", [None, float("nan"), float("inf"), -0.1, 0.0])
def test_valor_normativo_invalido_nao_adquire_autoridade_financeira(db, campo, valor):
    _assert_bloqueado(_resolver(db, _regra_completa(**{campo: valor})))


def test_aliquota_acima_de_um_nao_adquire_autoridade_financeira(db):
    res = _resolver(db, _regra_completa(aliquota_interna=1.01))
    assert res["calculo_autorizado"] is False
    assert res["aliquota_autorizada"] is False


def test_mva_percentual_bruta_acima_de_um_preserva_autoridade(db):
    res = _resolver(db, _regra_completa(mva=40.0))
    assert res["calculo_autorizado"] is True
    assert res["mva_autorizada"] is True
    assert res["mva"] == pytest.approx(0.40)


# ---------------------------------------------------------------------------
# MVA01-C2 — motor_preditivo_service não produz quando bloqueado
# ---------------------------------------------------------------------------

def test_mva01_c2_motor_preditivo_skip_quando_nao_autorizado(db):
    """
    motor_preditivo_service deve respeitar:
    if not res["calculo_autorizado"] or res["calculo_parcial"]: continue
    """
    from app.services.motor_preditivo_service import calcular_potencial_recuperacao

    # Mock DB que devolve itens com UF fora de escopo
    mock_row = MagicMock()
    mock_row.ncm = "22021000"
    mock_row.base_st_total = 1000.0
    mock_row.st_pago_total = 200.0
    db.execute.return_value.fetchall.return_value = [mock_row]

    with patch(
        "app.services.motor_preditivo_service.resolver_aliquota_e_mva",
        return_value={
            "aliquota": 0.18,
            "mva": 0.40,
            "fonte": "fora_de_escopo_normativo_piloto",
            "confianca": "indisponivel",
            "calculo_autorizado": False,
            "calculo_parcial": False,
            "mva_autorizada": False,
            "aliquota_autorizada": False,
        }
    ):
        resultado = calcular_potencial_recuperacao(db, empresa_id=1)

    assert resultado == [], (
        f"motor_preditivo não deve produzir estimativa sem calculo_autorizado. "
        f"Obtido: {resultado}"
    )


# ---------------------------------------------------------------------------
# MVA01-C3 — detector_creditos não produz quando bloqueado
# ---------------------------------------------------------------------------

def test_mva01_c3_detector_creditos_skip_quando_nao_autorizado(db):
    """
    detector_creditos_service deve respeitar:
    if not res["calculo_autorizado"] or res["calculo_parcial"]: continue
    """
    from app.services.detector_creditos_service import detectar_creditos

    mock_row = MagicMock()
    mock_row.ncm = "22021000"
    mock_row.base_st = 1000.0
    mock_row.st_pago = 200.0
    db.execute.return_value.fetchall.return_value = [mock_row]

    with patch(
        "app.services.detector_creditos_service.resolver_aliquota_e_mva",
        return_value={
            "aliquota": 0.18,
            "fonte": "lacuna_normativa",
            "confianca": "indisponivel",
            "calculo_autorizado": False,
            "calculo_parcial": False,
            "mva_autorizada": False,
            "aliquota_autorizada": False,
        }
    ):
        resultado = detectar_creditos(db, empresa_id=1)

    assert resultado == [], (
        f"detector_creditos não deve produzir crédito sem calculo_autorizado. "
        f"Obtido: {resultado}"
    )


# ---------------------------------------------------------------------------
# MVA01-C4 — analisador_distorcao não produz quando mva_autorizada=False
# ---------------------------------------------------------------------------

def test_mva01_c4_analisador_distorcao_skip_quando_mva_nao_autorizada(db):
    """
    analisador_distorcao_service deve respeitar:
    if not res["mva_autorizada"]: continue
    """
    from app.services.analisador_distorcao_service import detectar_distorcoes

    mock_row = MagicMock()
    mock_row.ncm = "22021000"
    mock_row.preco_medio = 10.0
    mock_row.base_st = 8.0
    db.execute.return_value.fetchall.return_value = [mock_row]

    with patch(
        "app.services.analisador_distorcao_service.resolver_aliquota_e_mva",
        return_value={
            "mva": 0.40,
            "fonte": "lacuna_normativa",
            "confianca": "indisponivel",
            "calculo_autorizado": False,
            "calculo_parcial": False,
            "mva_autorizada": False,
            "aliquota_autorizada": False,
        }
    ):
        resultado = detectar_distorcoes(db, empresa_id=1)

    assert resultado == [], (
        f"analisador_distorcao não deve produzir distorção sem mva_autorizada. "
        f"Obtido: {resultado}"
    )


# ---------------------------------------------------------------------------
# MVA01-C5 — caller financeiro bloqueado quando calculo_parcial=True
# ---------------------------------------------------------------------------

def test_mva01_c5_motor_preditivo_skip_quando_calculo_parcial(db):
    """
    fonte=tabela não é suficiente para gerar cálculo financeiro
    quando calculo_parcial=True (convenio_base — alíquota estimada).
    Guard financeiro: if not calculo_autorizado or calculo_parcial: continue
    """
    from app.services.motor_preditivo_service import calcular_potencial_recuperacao

    mock_row = MagicMock()
    mock_row.ncm = "22021000"
    mock_row.base_st_total = 1000.0
    mock_row.st_pago_total = 200.0
    db.execute.return_value.fetchall.return_value = [mock_row]

    with patch(
        "app.services.motor_preditivo_service.resolver_aliquota_e_mva",
        return_value={
            "aliquota": 0.18,
            "mva": 0.40,
            "fonte": "tabela",
            "confianca": "estimativa",
            "calculo_autorizado": False,   # alíquota estimada → financeiro bloqueado
            "calculo_parcial": True,        # convenio_base_sem_aliquota
            "mva_autorizada": True,
            "aliquota_autorizada": False,
        }
    ):
        resultado = calcular_potencial_recuperacao(db, empresa_id=1)

    assert resultado == [], (
        f"motor_preditivo não deve calcular quando calculo_parcial=True. "
        f"Obtido: {resultado}"
    )


# ---------------------------------------------------------------------------
# MVA01-C6 — analisador_distorcao aceita MVA autorizada mesmo com calculo_parcial
# ---------------------------------------------------------------------------

def test_mva01_c6_analisador_distorcao_aceita_mva_autorizada_parcial(db):
    """
    analisador_distorcao usa só MVA — deve aceitar mva_autorizada=True
    mesmo quando calculo_autorizado=False e calculo_parcial=True.
    Guard MVA: if not mva_autorizada: continue

    margem_real = (10 - 8) / 10 = 0.20
    mva = 0.50 → distorcao = 0.50 - 0.20 = 0.30 > 0.20 → produz resultado
    """
    from app.services.analisador_distorcao_service import detectar_distorcoes

    mock_row = MagicMock()
    mock_row.ncm = "22021000"
    mock_row.preco_medio = 10.0
    mock_row.base_st = 8.0
    db.execute.return_value.fetchall.return_value = [mock_row]

    with patch(
        "app.services.analisador_distorcao_service.resolver_aliquota_e_mva",
        return_value={
            "mva": 0.50,
            "fonte": "tabela",
            "confianca": "estimativa",
            "calculo_autorizado": False,   # alíquota não autorizada
            "calculo_parcial": True,
            "mva_autorizada": True,        # MVA é real — análise de margem permitida
            "aliquota_autorizada": False,
        }
    ):
        resultado = detectar_distorcoes(db, empresa_id=1)

    assert len(resultado) == 1, (
        f"analisador_distorcao deve produzir resultado quando mva_autorizada=True. "
        f"Obtido: {resultado}"
    )
    assert resultado[0]["mva_fonte"] == "tabela"
