import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_legacy_mei_route_is_not_reopened():
    """The public MEI entry belongs to solveris.ia.br, not the retired origin."""
    config = json.loads(
        (ROOT / "frontend-dashboard/vercel.json").read_text(encoding="utf-8")
    )

    assert config["git"]["deploymentEnabled"] == {"main": True}
    assert not any(
        str(route.get("source", "")).rstrip("/") == "/mei"
        or str(route.get("source", "")).startswith("/mei/")
        for route in config.get("rewrites", [])
    )

    vite = (ROOT / "frontend-dashboard/vite.config.js").read_text(encoding="utf-8")
    frontend = (ROOT / "frontend-dashboard/src/config.js").read_text(encoding="utf-8")
    assert 'base: "/mei/"' in vite
    assert "window.location.href = import.meta.env.BASE_URL" in frontend
