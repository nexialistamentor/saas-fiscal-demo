import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_legacy_mei_route_is_not_reopened():
    """Keep canonical MEI routing while automatic publication remains held."""
    config = json.loads(
        (ROOT / "frontend-dashboard/vercel.json").read_text(encoding="utf-8")
    )

    # Coordinated release hold established by 79207c0; routing cannot lift it.
    assert config["git"]["deploymentEnabled"] == {"main": False}
    assert not any(
        str(route.get("source", "")).rstrip("/") == "/mei"
        or str(route.get("source", "")).startswith("/mei/")
        for route in config.get("rewrites", [])
    )

    vite = (ROOT / "frontend-dashboard/vite.config.js").read_text(encoding="utf-8")
    frontend = (ROOT / "frontend-dashboard/src/config.js").read_text(encoding="utf-8")
    assert 'base: "/mei/"' in vite
    assert "window.location.href = import.meta.env.BASE_URL" in frontend
