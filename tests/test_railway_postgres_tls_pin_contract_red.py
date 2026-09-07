from __future__ import annotations

import hashlib
import ssl
import tomllib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

ROOT_CA_PATH = (
    REPO_ROOT
    / "config"
    / "railway_postgres_root_ca.pem"
)

RAILWAY_TOML_PATH = REPO_ROOT / "railway.toml"

EXPECTED_ROOT_CA_SHA256 = (
    "86AF65635BFE3E97F5188207546393CD"
    "0D9D0228BAA193BE1768079D03271A9E"
)

EXPECTED_PREDEPLOY = (
    "ENVIRONMENT=production "
    "PGSSLROOTCERT=config/railway_postgres_root_ca.pem "
    "alembic upgrade head"
)

EXPECTED_START = (
    "ENVIRONMENT=production "
    "PGSSLROOTCERT=config/railway_postgres_root_ca.pem "
    "uvicorn app.main:app --host 0.0.0.0 --port $PORT"
)


def test_railway_postgres_root_ca_is_pinned_public_x509() -> None:
    assert ROOT_CA_PATH.is_file(), (
        "RAILWAY_POSTGRES_ROOT_CA_MISSING: "
        "expected config/railway_postgres_root_ca.pem"
    )

    pem = ROOT_CA_PATH.read_text(encoding="ascii")

    assert "-----BEGIN CERTIFICATE-----" in pem
    assert "-----END CERTIFICATE-----" in pem

    assert "PRIVATE KEY" not in pem, (
        "RAILWAY_POSTGRES_ROOT_CA_MUST_NOT_CONTAIN_PRIVATE_KEY"
    )

    der = ssl.PEM_cert_to_DER_cert(pem)
    fingerprint = hashlib.sha256(der).hexdigest().upper()

    assert fingerprint == EXPECTED_ROOT_CA_SHA256, (
        "RAILWAY_POSTGRES_ROOT_CA_FINGERPRINT_DIVERGENCE: "
        f"expected={EXPECTED_ROOT_CA_SHA256} "
        f"actual={fingerprint}"
    )


def test_railway_predeploy_and_runtime_share_production_tls_authority() -> None:
    assert RAILWAY_TOML_PATH.is_file()

    config = tomllib.loads(
        RAILWAY_TOML_PATH.read_text(encoding="utf-8")
    )

    deploy = config["deploy"]

    assert deploy["preDeployCommand"] == EXPECTED_PREDEPLOY, (
        "RAILWAY_PREDEPLOY_TLS_AUTHORITY_NOT_PINNED"
    )

    assert deploy["startCommand"] == EXPECTED_START, (
        "RAILWAY_RUNTIME_TLS_AUTHORITY_NOT_PINNED"
    )


def test_repository_contains_no_postgres_root_private_key() -> None:
    forbidden = sorted(
        path.relative_to(REPO_ROOT).as_posix()
        for path in REPO_ROOT.rglob("root.key")
        if ".git" not in path.parts
    )

    assert forbidden == [], (
        "POSTGRES_ROOT_PRIVATE_KEY_MUST_NEVER_BE_VERSIONED: "
        + ", ".join(forbidden)
    )
