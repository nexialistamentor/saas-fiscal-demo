"""Bloco B: queries reais preservam a chave normativa antes do cálculo."""
from datetime import date
from importlib import import_module
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

SERVICOS = [
    ("detector_creditos_service", "detectar_creditos"),
    ("analisador_distorcao_service", "detectar_distorcoes"),
    ("motor_preditivo_service", "calcular_potencial_recuperacao"),
]


@pytest.fixture(params=SERVICOS, ids=[s[0] for s in SERVICOS])
def servico(request):
    modulo, funcao = request.param
    return import_module("app.services." + modulo), funcao


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE documentos_fiscais (id INTEGER PRIMARY KEY, empresa_id INTEGER, uf_dest TEXT, uf_emit TEXT, data_emissao DATE)"))
        conn.execute(text("CREATE TABLE itens_fiscais (documento_id INTEGER, ncm TEXT, valor_st REAL, base_st REAL, valor_produto REAL, st_observado_xml BOOLEAN)"))
    with Session(engine) as session:
        yield session
    engine.dispose()


def documento(db, id, uf_dest="PA", uf_emit="RJ", data="2026-01-01", ncm="22021000", empresa=1):
    db.execute(text("INSERT INTO documentos_fiscais VALUES (:id, :empresa, :dest, :emit, :data)"),
               {"id": id, "empresa": empresa, "dest": uf_dest, "emit": uf_emit, "data": data})
    db.execute(text("INSERT INTO itens_fiscais VALUES (:id, :ncm, 100, 8, 10, 1)"), {"id": id, "ncm": ncm})


def executar(db, servico, bloqueado=False, parcial=False):
    modulo, nome = servico
    from app.services.fiscal_utils import resolver_aliquota_e_mva
    def regra(_db, uf, ncm, data_referencia):
        if bloqueado:
            return None
        return {"mva": 0.50, "aliquota_interna": 0.17,
                "fonte_legal": "Fonte sintética validada", "vigencia_inicio": date(2025, 1, 1),
                "vigencia_fim": None,
                "nivel_confianca_fonte": "convenio_base_sem_aliquota" if parcial else "oficial"}
    with patch.object(modulo, "resolver_aliquota_e_mva", wraps=resolver_aliquota_e_mva) as resolver, \
         patch("app.services.fiscal_utils.uf_tem_dados_mva", return_value=True), \
         patch("app.services.fiscal_utils.buscar_mva", side_effect=regra):
        resultado = getattr(modulo, nome)(db, 1)
    return resultado, resolver.call_args_list


def chaves(chamadas):
    return {(c.args[1], c.args[2], c.kwargs["data_referencia"]) for c in chamadas}


def test_mesmo_ncm_ufs_distintas_resolvem_parcelas_separadas(db, servico):
    documento(db, 1, uf_dest="PA")
    documento(db, 2, uf_dest="SP")
    resultado, chamadas = executar(db, servico)
    assert chaves(chamadas) == {("PA", "22021000", date(2026, 1, 1)), ("SP", "22021000", date(2026, 1, 1))}
    assert len(chamadas) == len(resultado) == 2
    if servico[1] == "detectar_creditos":
        assert [r["credito_estimado"] for r in resultado] == pytest.approx([98.64, 98.64])
    elif servico[1] == "calcular_potencial_recuperacao":
        assert [r["potencial_recuperacao"] for r in resultado] == pytest.approx([98.64, 98.64])
        assert [r["volume_operacoes"] for r in resultado] == [1, 1]


def test_mesma_uf_ncm_vigencias_distintas_usam_datas_proprias(db, servico):
    documento(db, 1, data="2025-12-31")
    documento(db, 2, data="2026-01-01")
    modulo, nome = servico
    from app.services.fiscal_utils import resolver_aliquota_e_mva
    def regra(_db, uf, ncm, data_referencia):
        antiga = data_referencia < date(2026, 1, 1)
        return {"mva": 0.50 if antiga else 0.60, "aliquota_interna": 0.10 if antiga else 0.20,
                "fonte_legal": "Fonte sintética validada", "nivel_confianca_fonte": "oficial",
                "vigencia_inicio": date(2025, 1, 1) if antiga else date(2026, 1, 1),
                "vigencia_fim": date(2025, 12, 31) if antiga else None}
    with patch.object(modulo, "resolver_aliquota_e_mva", wraps=resolver_aliquota_e_mva) as resolver, \
         patch("app.services.fiscal_utils.uf_tem_dados_mva", return_value=True), \
         patch("app.services.fiscal_utils.buscar_mva", side_effect=regra):
        resultado = getattr(modulo, nome)(db, 1)
    assert chaves(resolver.call_args_list) == {("PA", "22021000", date(2025, 12, 31)), ("PA", "22021000", date(2026, 1, 1))}
    assert len(resultado) == 2
    campo = {"detectar_creditos": "credito_estimado", "calcular_potencial_recuperacao": "potencial_recuperacao", "detectar_distorcoes": "distorcao"}[nome]
    esperado = [0.30, 0.40] if nome == "detectar_distorcoes" else [98.40, 99.20]
    assert sorted(r[campo] for r in resultado) == pytest.approx(esperado)


@pytest.mark.parametrize("dest", [None, ""])
def test_uf_emissor_usada_so_quando_destino_ausente(db, servico, dest):
    documento(db, 1, uf_dest=dest, uf_emit="MG")
    resultado, chamadas = executar(db, servico)
    assert len(resultado) == 1
    assert chaves(chamadas) == {("MG", "22021000", date(2026, 1, 1))}


@pytest.mark.parametrize("alteracoes", [
    {"uf_dest": None, "uf_emit": None}, {"uf_dest": "ZZ", "uf_emit": "PA"},
    {"data": None}, {"ncm": None}, {"ncm": "invalido"},
], ids=["uf_ausente", "destino_invalido_nao_usa_emissor", "data_ausente", "ncm_ausente", "ncm_invalido"])
def test_chave_invalida_nao_produz_resultado(db, servico, alteracoes):
    documento(db, 1, **alteracoes)
    resultado, chamadas = executar(db, servico)
    assert resultado == []
    assert len(chamadas) == 1
    assert "data_referencia" in chamadas[0].kwargs
    if "data" in alteracoes:
        assert chamadas[0].kwargs["data_referencia"] is None


def test_regra_bloqueada_nao_produz_resultado(db, servico):
    documento(db, 1)
    resultado, chamadas = executar(db, servico, bloqueado=True)
    assert resultado == []
    assert len(chamadas) == 1


def test_parcial_so_autoriza_analise_mva(db, servico):
    documento(db, 1)
    resultado, chamadas = executar(db, servico, parcial=True)
    assert len(chamadas) == 1
    assert len(resultado) == (1 if servico[1] == "detectar_distorcoes" else 0)


def test_flags_ausentes_nao_geram_autoridade(db, servico):
    documento(db, 1)
    modulo, nome = servico
    with patch.object(modulo, "resolver_aliquota_e_mva", return_value={"aliquota": 0.17, "mva": 0.50, "fonte": "fallback"}):
        assert getattr(modulo, nome)(db, 1) == []


def test_parcela_bloqueada_nao_contamina_parcela_autorizada(db, servico):
    documento(db, 1, uf_dest="PA")
    documento(db, 2, uf_dest="SP", data=None)
    resultado, chamadas = executar(db, servico)
    assert len(resultado) == 1
    assert len(chamadas) == 2
    assert chaves(chamadas) == {("PA", "22021000", date(2026, 1, 1)), ("SP", "22021000", None)}


def test_agrega_so_mesma_chave_e_filtra_empresa(db, servico):
    documento(db, 1)
    documento(db, 2)
    documento(db, 3, uf_dest="SP", empresa=2)
    resultado, chamadas = executar(db, servico)
    assert len(chamadas) == 1
    if servico[1] == "detectar_creditos":
        assert resultado[0]["credito_estimado"] == pytest.approx(197.28)
    elif servico[1] == "calcular_potencial_recuperacao":
        assert resultado[0]["potencial_recuperacao"] == pytest.approx(197.28)
        assert resultado[0]["volume_operacoes"] == 2
