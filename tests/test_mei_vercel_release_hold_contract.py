import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_mei_release_holds_automatic_main_deployment():
    config = json.loads(
        (ROOT / "frontend-dashboard/vercel.json").read_text(
            encoding="utf-8-sig"
        )
    )

    assert config["git"]["deploymentEnabled"]["main"] is False
    assert isinstance(config["ignoreCommand"], str)
    assert config["ignoreCommand"].strip()
