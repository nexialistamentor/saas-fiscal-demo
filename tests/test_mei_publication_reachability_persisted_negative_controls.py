"""Negative controls for persisted-report publication reachability."""

from __future__ import annotations

from pathlib import Path


def _generic_path(census: dict) -> dict:
    matches = [
        item
        for item in census["paths"]
        if item["entrypoint"] == "/relatorio/{relatorio_id:int}"
    ]
    assert len(matches) == 1
    return matches[0]


def test_generic_persisted_reader_falls_unresolved_if_fingerprint_guard_is_weakened(
    monkeypatch,
):
    import app.scripts.mei_publication_reachability_census as scanner

    target = (
        scanner.ROOT
        / "app"
        / "services"
        / "resultado_provenance_service.py"
    )

    old = "if not _fingerprint_formato_valido(fingerprint):"
    new = "if _fingerprint_formato_valido(fingerprint):"

    original_read_text = Path.read_text

    def mutated_read_text(self, *args, **kwargs):
        text = original_read_text(self, *args, **kwargs)
        if self == target:
            assert text.count(old) == 1
            return text.replace(old, new, 1)
        return text

    monkeypatch.setattr(Path, "read_text", mutated_read_text)

    census = scanner.build_census()
    path = _generic_path(census)

    assert path["mei_reachability"] == "UNRESOLVED_MEI"
    assert path["blocked_before_producer"] is False
    assert path["blocker_code"] == "PERSISTED_MEI_PROVENANCE_UNPROVEN"
    assert path["producer_ids"] == []
    assert "PUBLICATION" in path["sink_kinds"]
    assert path["persistence_source"]["lineage_proven"] is False
