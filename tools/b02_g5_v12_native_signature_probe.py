#!/usr/bin/env python3
"""B02/G5 V12: proof of native C signature validation in a throwaway PG17.10.

Not a G5 authority act, transaction signer, protected installation, or R5 commit.
No protected database, host volumes, port mapping, policy mutation, or secret export.
The message is an explicitly labelled transient TEST, not a server manifest.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import getpass
import hashlib
import json
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time

EXPECTED_ELF_SHA = "35a1b40edeffb86f5342c19f577c809aaed80e0a28fe6d6fae85b2a862813198"
EXPECTED_HEADER_SHA = "546a926b941c36164dacf8a68d3bec6de40120d36c811f4ac585e4f2949847c4"
EXPECTED_PUBLIC_DER_SHA = "6f0ede1267a208505b2443d765cf97f2206759049f938a1d95d92a86c4c5d63c"
EXPECTED_POLICY_SHA = "727acdbb8ba0775f73100ea86671bc30bbac58b5af22a99b6be595d50268fab9"
EXPECTED_KEY_ID = "SOLVERIS-B02-SEFA-PR-G5-COMMIT-MIGUEL-V1"
IMAGE = "postgres:17.10-trixie"


def stop(code):
    raise RuntimeError("STOP_B02_G5_V12_NATIVE_PROBE_" + code)


def hashed_bytes(path: Path, expected: str, name: str) -> bytes:
    if not path.is_file() or path.is_symlink():
        stop(name + "_MISSING_OR_LINK")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        stop(name + "_SHA256_DIVERGENT")
    return raw


def parse_root(header_bytes: bytes):
    src = header_bytes.decode("utf-8")
    if "#define B02_G5_NATIVE_ROOT_COUNT ((Size) 1)" not in src:
        stop("ROOT_COUNT_NOT_ONE")
    key = re.search(r'"' + re.escape(EXPECTED_KEY_ID) + r'"\s*,\s*\{(?P<raw>[\s0-9a-fA-Fx,]+)\}', src)
    if key is None:
        stop("ROOT_ID_OR_KEY_NOT_FOUND")
    octets = re.findall(r"0x([0-9a-fA-F]{2})", key.group("raw"))
    if len(octets) != 32:
        stop("ROOT_NOT_ED25519_RAW_32")
    match = re.search(
        r'(?m)^\s*(?P<json>"(?:[^"\\]|\\.)*")\s*,\s*\n'
        r'\s*"(?P<start>[^"]+)"\s*,\s*"(?P<end>[^"]+)"\s*\}', src
    )
    if match is None:
        stop("EXACT_CONSTRAINTS_NOT_FOUND")
    constraints = json.loads(json.loads(match.group("json")))
    if (constraints.get("capability_root_id") != EXPECTED_KEY_ID
            or constraints.get("release_policy_hash") != EXPECTED_POLICY_SHA
            or constraints.get("g5_policy_binding", {}).get("policy_version") != 12
            or constraints.get("synthetic_only") is not False):
        stop("V12_BINDING_DIVERGENT")
    start = datetime.fromisoformat(match.group("start").replace("Z", "+00:00"))
    end = datetime.fromisoformat(match.group("end").replace("Z", "+00:00"))
    if start.tzinfo is None or end.tzinfo is None:
        stop("ROOT_TIMEZONE_REQUIRED")
    if not (start <= datetime.now(timezone.utc) < end):
        stop("ROOT_NOT_CURRENT")
    return bytes.fromhex("".join(octets)), constraints, match.group("start"), match.group("end")


def docker(*args, input_text=None, timeout=180, check=True):
    result = subprocess.run(
        ["docker", *args], input=input_text, text=True,
        capture_output=True, timeout=timeout,
    )
    if check and result.returncode != 0:
        stop("DOCKER_COMMAND_FAIL_" + args[0] + ":" + (result.stderr or result.stdout)[-700:])
    return result


def q64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def sql_call(expected: bytes, message: bytes, signature: bytes) -> str:
    return (
        "pg_temp.b02_v12_verify("
        f"decode('{q64(expected)}','base64'),"
        f"decode('{q64(message)}','base64'),"
        f"decode('{q64(signature)}','base64'),"
        f"'{EXPECTED_KEY_ID}')"
    )


def expected_failure(call: str, error_code: str) -> str:
    return (
        "DO $negative$ BEGIN\n"
        "  BEGIN\n"
        f"    PERFORM {call};\n"
        "    RAISE EXCEPTION 'STOP_NATIVE_NEGATIVE_CASE_ACCEPTED';\n"
        "  EXCEPTION WHEN check_violation THEN\n"
        f"    IF SQLERRM <> '{error_code}' THEN RAISE; END IF;\n"
        "  END;\n"
        "END $negative$;\n"
    )


def native_sql(message: bytes, signature: bytes, bad_binding: bytes, bad_binding_signature: bytes):
    corrupted = bytes([signature[0] ^ 1]) + signature[1:]
    wrong_expected = b'not the server bytes'
    return (
        "\\set ON_ERROR_STOP on\n"
        "BEGIN;\n"
        "CREATE FUNCTION pg_temp.b02_v12_verify(bytea,bytea,bytea,text) "
        "RETURNS void AS '/usr/lib/postgresql/17/lib/b02_g5_native_v12_probe', "
        "'b02g5_assert_signature' LANGUAGE C VOLATILE;\n"
        f"SELECT {sql_call(message, message, signature)};\n"
        + expected_failure(sql_call(message, message, corrupted), "G5_NATIVE_SIGNATURE_INVALID")
        + expected_failure(sql_call(message, bad_binding, bad_binding_signature), "G5_NATIVE_EXPECTED_BYTES_DIVERGENCE")
        + expected_failure(sql_call(bad_binding, bad_binding, bad_binding_signature), "G5_NATIVE_ROOT_CONSTRAINT_DIVERGENCE")
        + "ROLLBACK;\nSELECT 'V12_NATIVE_CRYPTO_POSITIVE_NEGATIVE_PASS';\n"
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--elf", required=True, type=Path)
    ap.add_argument("--header", required=True, type=Path)
    ap.add_argument("--public-der", required=True, type=Path)
    ap.add_argument("--private-pem", required=True, type=Path)
    args = ap.parse_args()
    raw = hashed_bytes(args.elf, EXPECTED_ELF_SHA, "ELF")
    del raw
    root, constraints, start, end = parse_root(hashed_bytes(args.header, EXPECTED_HEADER_SHA, "HEADER"))
    pub_der = hashed_bytes(args.public_der, EXPECTED_PUBLIC_DER_SHA, "PUBLIC_DER")
    if not args.private_pem.is_file() or args.private_pem.is_symlink():
        stop("PRIVATE_PEM_MISSING_OR_LINK")
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
    public_key = serialization.load_der_public_key(pub_der)
    if not isinstance(public_key, Ed25519PublicKey):
        stop("PUBLIC_DER_NOT_ED25519")
    raw_pub = public_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    if raw_pub != root:
        stop("PUBLIC_KEY_NOT_COMPILED_ROOT")
    answer = input("Para assinar apenas o TESTE descartável, escreve TESTE V12: ").strip()
    if answer != "TESTE V12":
        stop("LOCAL_TEST_CONSENT_MISSING")
    password = getpass.getpass("Senha da chave Ed25519 local: ")
    try:
        private_key = serialization.load_pem_private_key(args.private_pem.read_bytes(), password=password.encode())
    finally:
        del password
    if not isinstance(private_key, Ed25519PrivateKey):
        stop("PRIVATE_PEM_NOT_ED25519")
    if private_key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw) != root:
        stop("PRIVATE_KEY_NOT_COMPILED_ROOT")
    manifest = dict(constraints)
    manifest["valid_from"] = start
    manifest["valid_until"] = end
    manifest["transient_probe_only"] = "NATIVE_ELF_CRYPTO_TEST_NOT_DB_MANIFEST_NOT_AUTHORITY"
    message = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf8")
    signature = private_key.sign(message)
    public_key.verify(signature, message)
    bad_manifest = json.loads(message)
    bad_manifest["g5_policy_binding"]["policy_version"] = 11
    bad_binding = json.dumps(bad_manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf8")
    bad_binding_signature = private_key.sign(bad_binding)
    del private_key
    sql = native_sql(message, signature, bad_binding, bad_binding_signature)

    name = "solveris-v12-native-probe-" + secrets.token_hex(6)
    started = False
    try:
        result = docker("run", "--rm", "--detach", "--network", "none",
                        "--name", name, "-e", "POSTGRES_HOST_AUTH_METHOD=trust", IMAGE, timeout=180)
        if not result.stdout.strip():
            stop("EPHEMERAL_CONTAINER_NOT_CREATED")
        started = True
        docker("cp", str(args.elf), name + ":/usr/lib/postgresql/17/lib/b02_g5_native_v12_probe.so")
        version = docker("exec", name, "pg_config", "--version").stdout
        if version.split()[:2] != ["PostgreSQL", "17.10"]:
            stop("SERVER_NOT_PG1710")
        for _ in range(30):
            p = docker("exec", "-u", "postgres", name, "pg_isready", "-U", "postgres", check=False, timeout=10)
            if p.returncode == 0:
                break
            time.sleep(1)
        else:
            stop("EPHEMERAL_POSTGRES_NOT_READY")
        result = docker("exec", "-i", "-u", "postgres", name, "psql", "-X", "-A", "-t",
                        "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres", "-f", "-",
                        input_text=sql, timeout=120)
        if "V12_NATIVE_CRYPTO_POSITIVE_NEGATIVE_PASS" not in result.stdout:
            stop("EXPECTED_NATIVE_PROBE_PASS_NOT_RETURNED")
        print("V12_NATIVE_CRYPTO_POSITIVE_NEGATIVE_PASS")
        print("ELF_SHA256=" + EXPECTED_ELF_SHA)
        print("TRANSIENT_PG17_NO_PROTECTED_DATABASE_NO_COMMIT")
        print("NOT_AUTHORITY_NOT_APPROVED_FOR_INSTALLATION")
    finally:
        if started:
            result = docker("stop", "--time", "2", name, timeout=40, check=False)
            if result.returncode != 0:
                stop("EPHEMERAL_CLEANUP_UNCERTAIN")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
