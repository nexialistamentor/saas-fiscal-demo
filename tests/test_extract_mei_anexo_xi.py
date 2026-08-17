from pathlib import Path

import pytest

from app.scripts.extract_mei_anexo_xi import (
    AnexoXIExtractionError,
    SHA256_OFICIAL,
    extract_anexo_xi,
)


SNAPSHOT = Path("data/mei/Anexo_XI_Res_CGSN_140_snapshot_2026-08-17.pdf")


@pytest.fixture(scope="module")
def resultado():
    return extract_anexo_xi(SNAPSHOT)


def test_sha_oficial_aceito(resultado):
    assert SHA256_OFICIAL == "CB3845804F3C14CB9CB1320AEE19BF14498CF15988CD9263FD4618D8FAAAB8B6"
    assert resultado.paginas == 43


def test_sha_incorreto_bloqueia_antes_da_extracao(tmp_path, monkeypatch):
    fonte_adulterada = tmp_path / "snapshot-adulterado.pdf"
    fonte_adulterada.write_bytes(SNAPSHOT.read_bytes() + b"adulterado")

    def nao_deve_abrir_pdf(*args, **kwargs):
        raise AssertionError("pdfplumber não pode ser chamado antes da validação do hash")

    monkeypatch.setattr("app.scripts.extract_mei_anexo_xi.pdfplumber.open", nao_deve_abrir_pdf)
    with pytest.raises(AnexoXIExtractionError, match="SHA-256 divergente"):
        extract_anexo_xi(fonte_adulterada)


def test_contagens_a_b_e_total(resultado):
    tabela_a = [r for r in resultado.registros if r.tabela == "A"]
    tabela_b = [r for r in resultado.registros if r.tabela == "B"]
    assert len(tabela_a) == 467
    assert len(tabela_b) == 4
    assert len(resultado.registros) == 471


def test_tabela_b_contem_quatro_registros(resultado):
    assert sum(r.tabela == "B" for r in resultado.registros) == 4


def test_flags_iss_icms_sao_booleanas_e_mapeadas(resultado):
    assert all(type(r.iss) is bool and type(r.icms) is bool for r in resultado.registros)
    combinacoes_b = {(r.iss, r.icms) for r in resultado.registros if r.tabela == "B"}
    assert combinacoes_b == {(True, False), (False, True), (True, True)}


def test_recomposicao_estrutural(resultado):
    assert resultado.recomposicoes == 1
    assert any(
        r.ocupacao == "POCEIRO/CISTERNEIRO/CACIMBEIRO INDEPENDENTE"
        for r in resultado.registros
    )


def test_snapshot_sem_anomalias_ou_duplicados(resultado):
    assert resultado.anomalias == ()
    assert resultado.duplicados == ()
