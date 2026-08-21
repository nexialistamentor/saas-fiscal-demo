"""RED: a negated MEI condition must not create a false MEI blocker."""

from __future__ import annotations


def test_negated_mei_condition_does_not_create_false_blocker_red(
    tmp_path,
    monkeypatch,
):
    import app.scripts.mei_publication_reachability_census as census_module

    app_root = tmp_path / "app"
    app_root.mkdir()
    consumer_path = app_root / "consumer.py"
    consumer_path.write_text(
        "from fastapi import HTTPException\n"
        "\n"
        "def executar(regime):\n"
        "    if not (regime == 'mei'):\n"
        "        raise HTTPException(\n"
        "            status_code=400,\n"
        "            detail={'tipo_bloqueio': 'NON_MEI_ONLY'},\n"
        "        )\n"
        "    return 1\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(census_module, "ROOT", tmp_path)

    modules = census_module._parse_app()
    node = modules["app.consumer"].functions["executar"]

    assert census_module._mei_blocker(node) is None
