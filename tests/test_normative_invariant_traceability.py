import re
from pathlib import Path


_PADRAO = re.compile(rb"INVARIANTE-NR-\d+")
_PROPRIO_FICHEIRO = Path(__file__).resolve()
_ROOT = _PROPRIO_FICHEIRO.parents[1]

_INVARIANTES_HISTORICAS = {
    "INVARIANTE-NR-01",
    "INVARIANTE-NR-02",
    "INVARIANTE-NR-03",
}

_DIVIDA_ATUAL_ESPERADA = {
    "INVARIANTE-NR-02",
    "INVARIANTE-NR-03",
}


def _extrair(ficheiros) -> set[str]:
    encontrados: set[str] = set()
    for caminho in ficheiros:
        if not caminho.is_file() or caminho.resolve() == _PROPRIO_FICHEIRO:
            continue
        encontrados.update(
            item.decode("ascii")
            for item in _PADRAO.findall(caminho.read_bytes())
        )
    return encontrados


def test_catraca_de_rastreabilidade_das_invariantes_normativas():
    invariantes_docs = _extrair((_ROOT / "docs").rglob("*"))
    invariantes_tests = _extrair((_ROOT / "tests").rglob("*.py"))

    removidas = _INVARIANTES_HISTORICAS - invariantes_docs
    assert not removidas, (
        "Invariantes historicas desapareceram de docs/: "
        f"{sorted(removidas)}"
    )

    divida_real = invariantes_docs - invariantes_tests
    assert divida_real == _DIVIDA_ATUAL_ESPERADA, (
        "A divida normativa mudou. Nova divida ou divida quitada sem "
        "actualizar _DIVIDA_ATUAL_ESPERADA no mesmo commit. "
        f"Esperada={sorted(_DIVIDA_ATUAL_ESPERADA)}; "
        f"real={sorted(divida_real)}"
    )
