import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_mei_vercel_routing_contract():
    config = json.loads(
        (ROOT / "frontend-dashboard/vercel.json").read_text(encoding="utf-8")
    )

    assert config["git"]["deploymentEnabled"] == {"main": True}
    assert config["rewrites"] == [
        {"source": "/mei", "destination": "/index.html"},
        {"source": "/mei/", "destination": "/index.html"},
        {"source": "/mei/:path*", "destination": "/:path*"},
    ]

    vite = (ROOT / "frontend-dashboard/vite.config.js").read_text(encoding="utf-8")
    frontend = (ROOT / "frontend-dashboard/src/config.js").read_text(encoding="utf-8")

    assert 'base: "/mei/"' in vite
    assert "window.location.href = import.meta.env.BASE_URL" in frontend
