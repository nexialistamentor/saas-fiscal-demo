"""Attack contract: a statically instantiated legacy MEI engine must expose its caller."""

from __future__ import annotations


def test_legacy_mei_engine_static_constructor_caller_is_reachable(
    tmp_path,
    monkeypatch,
):
    import app.scripts.mei_publication_reachability_census as census_module

    app_root = tmp_path / "app"
    app_root.mkdir(parents=True)

    (app_root / "legacy.py").write_text(
        "class MEIEngine:\n"
        "    def execute(self, context):\n"
        "        return {'regime': 'mei'}\n",
        encoding="utf-8",
    )
    (app_root / "caller.py").write_text(
        "from app.legacy import MEIEngine\n"
        "\n"
        "def usar_legacy():\n"
        "    engine = MEIEngine()\n"
        "    return engine.execute({})\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(census_module, "ROOT", tmp_path)
    modules = census_module._parse_app()

    result = census_module._class_reachability_inventory(
        modules,
        class_id="app.legacy.MEIEngine",
    )

    assert result == {
        "class_id": "app.legacy.MEIEngine",
        "present": True,
        "caller_ids": ["app.caller.usar_legacy"],
        "reachability": "STATIC_CALLER",
    }
