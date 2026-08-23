"""RED: SQLAlchemy Column isnot() must be qualified as an inert descriptor helper."""

from __future__ import annotations


def test_sqlalchemy_column_isnot_descriptor_is_qualified_red():
    import app.scripts.mei_publication_reachability_census as census_module

    modules = census_module._parse_app()

    assert census_module._is_sqlalchemy_column_descriptor_helper(
        modules,
        "app.models.TabelaMVA.vigencia_fim.isnot",
    )
    assert census_module._is_sqlalchemy_column_descriptor_helper(
        modules,
        "app.models.TabelaPMPF.vigencia_fim.isnot",
    )
