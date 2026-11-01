"""Only new successor bootstrap negative tests; no authority or real signing.

No PostgreSQL, network, private key, historical G4 or activation.
"""
from pathlib import Path

import pytest

from app.services import enterprise_b02_authorized_trust as trust


def test_successor_unrecognized_root_fails_before_filesystem_access(monkeypatch, tmp_path):
    """Source-level default is a STOP until the custodian pins current real bytes."""
    assert trust.SUCCESSOR_ROOT_SHA256 is None
    assert trust.SUCCESSOR_DECISION_SHA256 is None
    assert trust.SUCCESSOR_MANIFEST_SHA256 is None
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    with pytest.raises(ValueError, match="SUCCESSOR_RECOGNIZED_ROOT_AND_DECISION_PINS_REQUIRED"):
        trust.activate_successor_for_process()
    assert not (tmp_path / "AppData").exists()


def test_successor_pins_alone_cannot_provision_new_root(monkeypatch, tmp_path):
    """Even three syntactically valid pin values grant nothing without real custody."""
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    for key in ("SUCCESSOR_ROOT_SHA256", "SUCCESSOR_DECISION_SHA256", "SUCCESSOR_MANIFEST_SHA256"):
        monkeypatch.setattr(trust, key, "a" * 64)
    with pytest.raises(ValueError, match="SUCCESSOR_CUSTODY_LAYOUT_INCOMPLETE"):
        trust.activate_successor_for_process()


def test_successor_rejects_arbitrary_root_bytes_before_registration(monkeypatch, tmp_path):
    """Synthetic dummy ROOT is deliberately invalid, not a fake positive signature."""
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    for key in ("SUCCESSOR_ROOT_SHA256", "SUCCESSOR_DECISION_SHA256", "SUCCESSOR_MANIFEST_SHA256"):
        monkeypatch.setattr(trust, key, "a" * 64)
    home = tmp_path / "AppData" / "Local" / "SOLVERIS" / "B02Trust" / "SUCCESSOR_V3"
    (home / "BUNDLE_ASSINADO").mkdir(parents=True)
    (home / "STORE").mkdir()
    (home / "ROOT.json").write_bytes(b"{}")
    with pytest.raises(ValueError, match="SUCCESSOR_ROOT_NOT_DEPLOYMENT_PINNED"):
        trust.activate_successor_for_process()
