import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import pytest

from app.scripts.extract_mei_anexo_xi import extract_anexo_xi


SNAPSHOT = Path("data/mei/Anexo_XI_Res_CGSN_140_snapshot_2026-08-17.pdf")
DATASET = Path("data/mei/anexo_xi_ocupacoes_v1.json")
SOURCE_SHA256 = "CB3845804F3C14CB9CB1320AEE19BF14498CF15988CD9263FD4618D8FAAAB8B6"
RECORD_FIELDS = {
    "tabela",
    "ocupacao",
    "cnae",
    "descricao_subclasse_cnae",
    "iss",
    "icms",
    "pagina_fonte",
}


@pytest.fixture(scope="module")
def dataset():
    return json.loads(DATASET.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def extracted_records():
    return [asdict(record) for record in extract_anexo_xi(SNAPSHOT).registros]


def test_dataset_matches_extractor_integrally(dataset, extracted_records):
    assert dataset["records"] == extracted_records


def test_source_metadata_and_exact_sha256(dataset):
    source = dataset["source"]
    assert source == {
        "artifact": "Anexo XI da Resolução CGSN nº 140/2018",
        "snapshot": "Anexo_XI_Res_CGSN_140_snapshot_2026-08-17.pdf",
        "snapshot_date": "2026-08-17",
        "sha256": SOURCE_SHA256,
        "pages": 43,
    }
    assert hashlib.sha256(SNAPSHOT.read_bytes()).hexdigest().upper() == source["sha256"]


def test_schema_version_and_counts(dataset):
    assert dataset["schema_version"] == 1
    assert dataset["counts"] == {"table_a": 467, "table_b": 4, "total": 471}
    assert len(dataset["records"]) == 471


def test_table_b_records_remain_classified_as_b(dataset):
    assert [record["tabela"] for record in dataset["records"]].count("B") == 4


def test_records_only_belong_to_tables_a_or_b(dataset):
    assert {record["tabela"] for record in dataset["records"]} == {"A", "B"}


def test_every_record_has_exactly_the_seven_canonical_fields(dataset):
    assert all(set(record) == RECORD_FIELDS for record in dataset["records"])
    assert all(type(record["iss"]) is bool for record in dataset["records"])
    assert all(type(record["icms"]) is bool for record in dataset["records"])
