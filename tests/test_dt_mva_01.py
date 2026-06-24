"""
DT-MVA-01 — Escopo normativo MVA/ST do piloto (Pará)
=====================================================
Piloto = PA. Outras UFs = fora de escopo.
PA + NCM sem regra = lacuna normativa.
calculo_autorizado + calculo_parcial + mva_autorizada + aliquota_autorizada
são os campos soberanos.

Cobertura:
  MVA01-P1  PA + NCM com regra completa → tudo True
  MVA01-P2  PA + convenio_base → parcial (mva_autorizada=True, aliquota_autorizada=False)
  MVA01-N1  UF vazia → tudo False
  MVA01-N2  UF≠PA → fora_de_escopo_normativo_piloto, tudo False
  MVA01-N3  PA + NCM sem regra → lacuna_normativa, tudo False
  MVA01-N4  PA sem NCM → ncm_ausente, tudo False
  MVA01-C1  todos os ramos têm os 4 campos soberanos
  MVA01-C2  caller financeiro (motor_preditivo) não produz resultado quando bloqueado
  MVA01-C3  caller financeiro (detector_creditos) não produz resultado quando bloqueado
  MVA01-C4  caller MVA (analisador_distorcao) não produz resultado quando mva_autorizada=False
"""

from unittest.mock import MagicMock, patch, call
import pytest

from app.services.fiscal_utils import resolver_aliquota_e_mva


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    return MagicMock()


def _regra_completa():
    return {"mva": 0.35, "aliquota_interna": 0.17, "nivel_confianca_fonte": "oficial"}


def _regra_convenio():
    return {"mva": 40.0, "aliquota_interna": 0.0, "nivel_confianca_fonte": "convenio_base_sem_aliquota"}


# ---------------------------------------------------------------------------
# MVA01-P1 — PA + regra completa
# ---------------------------------------------------------------------------

def test_mva01_p1_pa_regra_completa_tudo_autorizado(db):
    with patch("app.services.fiscal_utils.uf_tem_dados_mva", return_value=True), \
         patch("app.services.fiscal_utils.buscar_mva", return_value=_regra_completa()):
        res = resolver_aliquota_e_mva(db, "PA", "22021000")

    assert res["fonte"] == "tabela"
    assert res["calculo_autorizado"] is True
    assert res["calculo_parcial"] is False
    assert res["mva_autorizada"] is True
    assert res["aliquota_autorizada"] is True
    assert res["bloqueio_normativo"] is False
    assert res["motivo_bloqueio"] is None


# ---------------------------------------------------------------------------
# MVA01-P2 — PA + convenio_base_sem_aliquota
# ---------------------------------------------------------------------------

def test_mva01_p2_pa_convenio_base_parcial(db):
    with patch("app.services.fiscal_utils.uf_tem_dados_mva", return_value=True), \
         patch("app.services.fiscal_utils.buscar_mva", return_value=_regra_convenio()):
        res = resolver_aliquota_e_mva(db, "PA", "22021000")

    assert res["fonte"] == "tabela"
    assert res["calculo_autorizado"] is False   # alíquota não autorizada → financeiro bloqueado
    assert res["calculo_parcial"] is True        # MVA real — análise de margem permitida
    assert res["mva_autorizada"] is True
    assert res["aliquota_autorizada"] is False
    assert res["mva"] == pytest.approx(0.40)
    assert res["aliquota"] == 0.18


# ---------------------------------------------------------------------------
# MVA01-N1 — UF vazia
# ---------------------------------------------------------------------------

def test_mva01_n1_uf_vazia_tudo_false(db):
    res = resolver_aliquota_e_mva(db, "", "22021000")
    assert res["fonte"] == "fallback_uf_desconhecida"
    assert res["calculo_autorizado"] is False
    assert res["calculo_parcial"] is False
    assert res["mva_autorizada"] is False
    assert res["aliquota_autorizada"] is False


# ---------------------------------------------------------------------------
# MVA01-N2 — UF ≠ PA
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("uf", ["SP", "RJ", "MG", "RS", "SC"])
def test_mva01_n2_uf_fora_escopo_tudo_false(db, uf):
    res = resolver_aliquota_e_mva(db, uf, "22021000")
    assert res["fonte"] == "fora_de_escopo_normativo_piloto"
    assert res["calculo_autorizado"] is False
    assert res["mva_autorizada"] is False
    assert res["aliquota_autorizada"] is False
    assert uf in res["aviso"]


# ---------------------------------------------------------------------------
# MVA01-N3 — PA + NCM sem regra (lacuna normativa I-MVA-06)
# ---------------------------------------------------------------------------

def test_mva01_n3_pa_ncm_sem_regra_lacuna(db):
    with patch("app.services.fiscal_utils.uf_tem_dados_mva", return_value=True), \
         patch("app.services.fiscal_utils.buscar_mva", return_value=None):
        res = resolver_aliquota_e_mva(db, "PA", "99999999")

    assert res["fonte"] == "lacuna_normativa"
    assert res["calculo_autorizado"] is False
    assert res["mva_autorizada"] is False
    assert res["aliquota_autorizada"] is False
    assert res["motivo_bloqueio"] == "lacuna_normativa"


# ---------------------------------------------------------------------------
# MVA01-N4 — PA sem NCM
# ---------------------------------------------------------------------------

def test_mva01_n4_pa_sem_ncm_bloqueado(db):
    res = resolver_aliquota_e_mva(db, "PA", "")
    assert res["fonte"] == "ncm_ausente"
    assert res["calculo_autorizado"] is False
    assert res["motivo_bloqueio"] == "ncm_ausente"


# ---------------------------------------------------------------------------
# MVA01-C1 — todos os ramos têm os 4 campos soberanos
# ---------------------------------------------------------------------------

def test_mva01_c1_todos_ramos_tem_campos_soberanos(db):
    campos = ["calculo_autorizado", "calculo_parcial", "mva_autorizada",
              "aliquota_autorizada", "bloqueio_normativo", "motivo_bloqueio"]

    casos = [
        (("", "22021000"), {}),
        (("SP", "22021000"), {}),
        (("PA", ""), {}),
    ]
    for (uf, ncm), patches in casos:
        res = resolver_aliquota_e_mva(db, uf, ncm)
        for campo in campos:
            assert campo in res, f"Campo '{campo}' ausente para uf='{uf}', ncm='{ncm}'"

    # PA + NCM sem regra
    with patch("app.services.fiscal_utils.uf_tem_dados_mva", return_value=True), \
         patch("app.services.fiscal_utils.buscar_mva", return_value=None):
        res = resolver_aliquota_e_mva(db, "PA", "99999999")
    for campo in campos:
        assert campo in res

    # PA + regra completa
    with patch("app.services.fiscal_utils.uf_tem_dados_mva", return_value=True), \
         patch("app.services.fiscal_utils.buscar_mva", return_value=_regra_completa()):
        res = resolver_aliquota_e_mva(db, "PA", "22021000")
    for campo in campos:
        assert campo in res


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
