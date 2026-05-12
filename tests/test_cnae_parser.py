"""
Testes do parser CNAE soberano.
"""

from app.services.parsers.cnae_parser import (
    buscar_por_codigo,
    buscar_por_descricao,
    carregar_csv,
    subclasses_por_secao,
    validar_cnae,
)


def test_carregar_csv_sem_erro():
    resultado = carregar_csv()
    assert resultado.erro is None


def test_total_subclasses_correcto():
    resultado = carregar_csv()
    assert resultado.total_subclasses >= 1300


def test_versao_cnae_actual():
    resultado = carregar_csv()
    assert resultado.versao == "2.3"


def test_checksum_preenchido():
    resultado = carregar_csv()
    assert len(resultado.checksum_csv) == 64  # SHA-256


def test_checksum_deterministico():
    r1 = carregar_csv()
    r2 = carregar_csv()
    assert r1.checksum_csv == r2.checksum_csv


def test_buscar_por_descricao_software():
    resultados = buscar_por_descricao("software")
    assert len(resultados) > 0
    assert all("software" in r.descricao.lower() for r in resultados)


def test_buscar_por_descricao_limite():
    resultados = buscar_por_descricao("comercio", limite=5)
    assert len(resultados) <= 5


def test_buscar_por_descricao_sem_resultado():
    resultados = buscar_por_descricao("zzz_inexistente_zzz")
    assert resultados == []


def test_buscar_por_codigo_valido():
    subclasse = buscar_por_codigo("6202-3/00")
    assert subclasse is not None
    assert subclasse.codigo_subclasse == "6202-3/00"


def test_buscar_por_codigo_invalido():
    subclasse = buscar_por_codigo("9999-9/99")
    assert subclasse is None


def test_validar_cnae_existente():
    assert validar_cnae("6202-3/00") is True


def test_validar_cnae_inexistente():
    assert validar_cnae("0000-0/00") is False


def test_subclasses_por_secao_j():
    """Secção J = Informação e Comunicação."""
    resultados = subclasses_por_secao("J")
    assert len(resultados) > 0
    assert all(s.secao == "J" for s in resultados)


def test_subclasses_por_secao_case_insensitive():
    lower = subclasses_por_secao("j")
    upper = subclasses_por_secao("J")
    assert len(lower) == len(upper)


def test_campos_subclasse_preenchidos():
    subclasse = buscar_por_codigo("6202-3/00")
    assert subclasse is not None
    assert subclasse.descricao
    assert subclasse.codigo_classe
    assert subclasse.codigo_grupo
    assert subclasse.codigo_divisao
    assert subclasse.secao
    assert subclasse.versao_cnae == "2.3"
