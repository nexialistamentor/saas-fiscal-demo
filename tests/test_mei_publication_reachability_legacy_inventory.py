"""RED attack: legacy MEI engine presence alone must not imply reachability."""

from __future__ import annotations


def test_legacy_mei_engine_presence_without_callers_is_inventory_only_red(
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
    (app_root / "unrelated.py").write_text(
        "def ping():\n"
        "    return 'ok'\n",
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
        "caller_ids": [],
        "reachability": "INVENTORY_ONLY",
    }
