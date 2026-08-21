"""RED: relative app imports must never disappear from the reachability graph."""

from __future__ import annotations


def test_relative_import_fails_closed_instead_of_hiding_mei_path_red(
    tmp_path,
    monkeypatch,
):
    import pytest
    import app.scripts.mei_publication_reachability_census as census_module

    app_root = tmp_path / "app"
    jobs_root = app_root / "jobs"
    tax_engines_root = app_root / "services" / "tax_engines"
    jobs_root.mkdir(parents=True)
    tax_engines_root.mkdir(parents=True)

    (jobs_root / "root.py").write_text(
        "from .worker import run_worker\n"
        "\n"
        "def processar():\n"
        "    return run_worker()\n",
        encoding="utf-8",
    )
    (jobs_root / "worker.py").write_text(
        "from app.services.tax_engines.mei_constants import calcular_das_mei\n"
        "\n"
        "def run_worker():\n"
        "    return calcular_das_mei(1621, 'servicos')\n",
        encoding="utf-8",
    )
    (tax_engines_root / "mei_constants.py").write_text(
        "def calcular_das_mei(salario, atividade):\n"
        "    return salario\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(census_module, "ROOT", tmp_path)

    with pytest.raises(
        RuntimeError,
        match="MEI_REACHABILITY_UNRESOLVED_RELATIVE_IMPORT",
    ):
        census_module._parse_app()
