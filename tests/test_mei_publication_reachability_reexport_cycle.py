"""RED: static reexport cycles must fail closed deterministically."""

from __future__ import annotations


def test_static_reexport_cycle_fails_closed_red(tmp_path, monkeypatch):
    import pytest
    import app.scripts.mei_publication_reachability_census as census_module

    app_root = tmp_path / "app"
    app_root.mkdir()

    (app_root / "a.py").write_text(
        "from app.b import calcular_das_mei\n",
        encoding="utf-8",
    )
    (app_root / "b.py").write_text(
        "from app.a import calcular_das_mei\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(census_module, "ROOT", tmp_path)

    with pytest.raises(RuntimeError, match="MEI_REACHABILITY_REEXPORT_CYCLE"):
        census_module._parse_app()
