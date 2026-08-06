from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path


BUNDLE_NAME = "BUNDLE-EVIDENCIA-9B4-REPORT-031-V1.0"
HEAD = "1b36b1cc569648cf6eb011a66d316447fc32c96e"
PARENT = "c742d7ca88e3568cff7864f2c354ab230c4f1d89"
BASE = "4aee707a3d25490080397dde303bca1b5a693ef6"
MISSION = "docs/MISSIONS/MISSION-013-ADR-020-INTENCAO-9B4-FK-DIRETA-NORMATIVE-ACTIVATION-EXECUTION-NOT-VALID-V1.0.md"
MIGRATION = "migrations/versions/0041_adr020_norm_exec_dec_fk.py"
TEST_FILE = "tests/test_adr020_activation_postgresql.py"
REPORT = "docs/REPORTS/REPORT-031-FECHAMENTO-TECNICO-MISSION-013-ADR-020-INTENCAO-9B4-V1.0.md"
IDENTITIES = {
    MISSION: (9085, "5971C9E9AB60580440824903C4DBAC2590BC65E63671369ACC7B67A906324D6F"),
    MIGRATION: (1201, "3F27EDD712745DE9F47A187D7EBF9CAABDE681399A16FD75104F05819C84047D"),
    TEST_FILE: (None, "E7F0D1E9A34CC5FD84711D4589E9BEA912774BAB8F1CA9F38654087B10FA0595"),
}
GATE1_TEST = "test_normative_activation_has_direct_exact_execution_decision_fk_not_valid"
GATE2_TESTS = (
    "test_normative_generation_decision_fk_is_physical_and_not_valid",
    GATE1_TEST,
)
EXPECTED_FILES = {
    "CAPTURE.py", "ENVIRONMENT.txt", "GIT-BEFORE.txt", "GIT-AFTER.txt",
    "RUN-SUMMARY.txt", "RED-RETROSPECTIVE.txt", "INCIDENT-TEST-DB-RETROSPECTIVE.txt",
    "GATE-1-GREEN-9B4.stdout.txt", "GATE-1-GREEN-9B4.stderr.txt", "GATE-1-GREEN-9B4.meta.json",
    "GATE-2-PRESERVACAO-9B2-GREEN-9B4.stdout.txt", "GATE-2-PRESERVACAO-9B2-GREEN-9B4.stderr.txt",
    "GATE-2-PRESERVACAO-9B2-GREEN-9B4.meta.json", "GATE-2-NODE-IDS.txt",
    "GATE-3-REGRESSAO-POSTGRESQL-ADR020.stdout.txt", "GATE-3-REGRESSAO-POSTGRESQL-ADR020.stderr.txt",
    "GATE-3-REGRESSAO-POSTGRESQL-ADR020.meta.json",
    "GATE-4-SUITE-GLOBAL.stdout.txt", "GATE-4-SUITE-GLOBAL.stderr.txt", "GATE-4-SUITE-GLOBAL.meta.json",
}
ZIP_DT = (1980, 1, 1, 0, 0, 0)


class CaptureError(RuntimeError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def file_digest(path: Path) -> str:
    return digest(path.read_bytes())


def write_bytes(path: Path, data: bytes) -> None:
    if path.exists():
        raise CaptureError(f"recusa de sobrescrita: {path}")
    path.write_bytes(data)


def write_text(path: Path, text: str) -> None:
    write_bytes(path, (text.rstrip() + "\n").encode("utf-8"))


def write_json(path: Path, value: object) -> None:
    write_bytes(path, (json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8"))


def run(root: Path, argv: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(argv, cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def checked(root: Path, *argv: str) -> str:
    result = run(root, list(argv))
    if result.returncode:
        raise CaptureError(f"comando falhou: {argv!r}: {result.stderr.decode(errors='replace')}")
    return result.stdout.decode("utf-8", errors="strict").strip()


def ps_command(argv: list[str]) -> str:
    return " ".join("'" + arg.replace("'", "''") + "'" for arg in argv)


def status(root: Path, branch: bool = False) -> str:
    args = ["git", "status", "--short", "--untracked-files=all"]
    if branch:
        args.insert(2, "--branch")
    return checked(root, *args)


def tracked_inventory(root: Path) -> list[tuple[str, int, str]]:
    names = checked(root, "git", "ls-files", "app", "migrations", "tests").splitlines()
    return [(name, (root / name).stat().st_size, file_digest(root / name)) for name in names]


def git_record(root: Path, inventory: list[tuple[str, int, str]]) -> str:
    commands = [
        ["git", "status", "--short", "--branch", "--untracked-files=all"],
        ["git", "rev-parse", "HEAD"], ["git", "rev-parse", "HEAD^"],
        ["git", "rev-parse", "origin/main"], ["git", "log", "-2", "--pretty=fuller"],
        ["git", "diff", "--check"], ["git", "diff", "--name-only"],
        ["git", "diff", "--cached", "--name-only"],
    ]
    blocks = []
    for argv in commands:
        result = run(root, argv)
        blocks.append(f"$ {ps_command(argv)}\nexit_code={result.returncode}\n" + result.stdout.decode(errors="replace") + result.stderr.decode(errors="replace"))
        if result.returncode:
            raise CaptureError(f"inventário Git falhou: {argv!r}")
    inv = "\n".join(f"{name}\t{size}\t{sha}" for name, size, sha in inventory)
    return "\n\n".join(blocks) + "\n\nTRACKED-PROTECTED-INVENTORY\n" + inv + "\n"


def assert_identity(root: Path) -> None:
    if checked(root, "git", "rev-parse", "HEAD") != HEAD:
        raise CaptureError("HEAD técnico divergente")
    if checked(root, "git", "rev-parse", "HEAD^") != PARENT:
        raise CaptureError("parentalidade divergente")
    if checked(root, "git", "rev-parse", "origin/main") != BASE:
        raise CaptureError("HEAD-base/origin/main divergente")
    if checked(root, "git", "log", "-1", "--pretty=%s", HEAD) != "feat(adr020): enforce direct activation execution decision fk":
        raise CaptureError("mensagem do HEAD divergente")
    if checked(root, "git", "log", "-1", "--pretty=%s", PARENT) != "docs(adr020): ratify MISSION-013 intention 9B4":
        raise CaptureError("mensagem do commit documental divergente")
    for rel, (size, sha) in IDENTITIES.items():
        path = root / rel
        if size is not None and path.stat().st_size != size:
            raise CaptureError(f"tamanho vinculante divergente: {rel}")
        if file_digest(path) != sha:
            raise CaptureError(f"SHA-256 vinculante divergente: {rel}")
    migration = (root / MIGRATION).read_text(encoding="utf-8")
    required = ["0041_adr020_norm_exec_dec_fk", "0040_adr020_norm_gen_decision_fk", "fk_normative_activations_exact_execution_decision", "NOT VALID", "RuntimeError"]
    if any(item not in migration for item in required) or "VALIDATE CONSTRAINT" in migration:
        raise CaptureError("contrato estático da migration divergente")
    if (root / REPORT).exists() or list((root / "docs/REPORTS").glob("REPORT-031*")):
        raise CaptureError("REPORT-031 já existe")


def identify_nodes(root: Path) -> tuple[str, list[str]]:
    source = (root / TEST_FILE).read_text(encoding="utf-8")
    definitions = set(re.findall(r"^def (test_[A-Za-z0-9_]+)\(", source, re.MULTILINE))
    for name in GATE2_TESTS:
        if name not in definitions:
            raise CaptureError(f"node ID não encontrado no ficheiro: {name}")
    node_ids = [f"{TEST_FILE}::{name}" for name in GATE2_TESTS]
    return f"{TEST_FILE}::{GATE1_TEST}", node_ids


def observed_summary(stdout: bytes, stderr: bytes) -> str:
    text = (stdout + b"\n" + stderr).decode("utf-8", errors="replace")
    for line in reversed(text.splitlines()):
        if re.search(r"\b\d+\s+(?:passed|failed)\b", line):
            return line.strip()
    return "resultado pytest não identificado"


def gate(root: Path, bundle: Path, label: str, argv: list[str], expected: str) -> dict[str, object]:
    fd, db_name = tempfile.mkstemp(prefix="evidence-9b4-", suffix=".sqlite3")
    os.close(fd)
    db = Path(db_name)
    env = os.environ.copy()
    env["DATABASE_URL"] = "sqlite:///" + db.as_posix()
    started = now()
    tick = time.monotonic()
    try:
        result = run(root, argv, env)
    finally:
        if db.exists():
            db.unlink()
    duration = time.monotonic() - tick
    finished = now()
    stdout_name = f"{label}.stdout.txt"
    stderr_name = f"{label}.stderr.txt"
    write_bytes(bundle / stdout_name, result.stdout)
    write_bytes(bundle / stderr_name, result.stderr)
    observed = observed_summary(result.stdout, result.stderr)
    meta = {
        "gate": label,
        "command": ps_command(argv),
        "argv": argv,
        "cwd": str(root),
        "started_utc": started,
        "finished_utc": finished,
        "duration_seconds": round(duration, 7),
        "exit_code": result.returncode,
        "expected_result": expected,
        "observed_result": observed,
        "database_url": "sqlite temporário isolado",
        "temporary_sqlite_removed": not db.exists(),
        "stdout_sha256": digest(result.stdout),
        "stderr_sha256": digest(result.stderr),
    }
    write_json(bundle / f"{label}.meta.json", meta)
    if result.returncode != 0 or expected not in observed:
        raise CaptureError(f"{label} divergiu: exit={result.returncode}; observado={observed!r}; esperado={expected!r}")
    return meta


def environment_text(root: Path) -> str:
    commands = {
        "Python": [sys.executable, "--version"], "pytest": [sys.executable, "-m", "pytest", "--version"],
        "Git": ["git", "--version"], "PostgreSQL client": ["psql", "--version"],
    }
    lines = ["ENVIRONMENT (sem segredos)", f"captured_utc={now()}", f"cwd={root}", f"platform={platform.platform()}", "DATABASE_URL=sqlite temporário isolado por gate", "Railway=não acedido", "External credentials=não usadas"]
    for name, argv in commands.items():
        try:
            result = run(root, argv)
            value = (result.stdout + result.stderr).decode(errors="replace").strip()
            lines.append(f"{name}={value}; exit_code={result.returncode}")
        except FileNotFoundError:
            lines.append(f"{name}=comando não disponível")
    return "\n".join(lines)


def retrospective_red() -> str:
    return """RED RETROSPECTIVO — NÃO É STDOUT BRUTO

Registo retrospectivo baseado na evidência observada durante a execução RED anterior à implementação.
- resultado: 1 failed;
- falha exclusiva: assert foreign_key is not None;
- causa: ausência da FK directa 9B4;
- o restante contrato estrutural ainda não foi alcançado.

Não foram fabricados timestamps, duração ou stdout inexistente. O teste antigo não foi reconstruído artificialmente.
"""


def retrospective_incident() -> str:
    return """INCIDENTE TEST.DB RETROSPECTIVO — NÃO É STDOUT BRUTO

- Uma suite global anterior teve: 2762 passed, 15 skipped, 1 failed.
- Falha: tests/test_ops11_h4_l2_m4_contract.py::test_h4_analise_st_periodo_empresa_de_outro_usuario_bloqueia.
- Erro: UNIQUE constraint failed: usuarios.cpf.
- CPF em colisão: 76240319147.
- O test.db persistente continha 55.030 utilizadores.
- O CPF já existia no utilizador id 45092.
- O teste isolado passou.
- O ficheiro completo passou com 10 passed.
- Conclusão: colisão aleatória contra base SQLite persistente acumulada, não defeito da implementação 9B4.
- Banco antigo arquivado fora do repositório.
- Tamanho do banco antigo: 38985728 bytes.
- SHA-256 do banco antigo: FE4E1ECEE8A4B1BDBD7D220081688BEAED719D9B024B7069CD6A13CC78884DC8.

Este registo não inclui email, credenciais ou dados adicionais e não constitui stdout bruto.
"""


def manifest_bytes(bundle: Path) -> bytes:
    lines = []
    for path in sorted(bundle.iterdir(), key=lambda item: item.name):
        if path.is_file() and path.name != "MANIFEST.txt":
            data = path.read_bytes()
            lines.append(f"{path.name}\t{len(data)}\t{digest(data)}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def create_zip(bundle: Path, zip_path: Path) -> None:
    if zip_path.exists():
        raise CaptureError("ZIP preexistente")
    with zipfile.ZipFile(zip_path, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(bundle.iterdir(), key=lambda item: item.name):
            info = zipfile.ZipInfo(f"{BUNDLE_NAME}/{path.name}", ZIP_DT)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            info.create_system = 3
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def audit_zip(bundle: Path, zip_path: Path) -> None:
    expected = {f"{BUNDLE_NAME}/{p.name}": p.read_bytes() for p in bundle.iterdir() if p.is_file()}
    with zipfile.ZipFile(zip_path, "r") as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or set(names) != set(expected):
            raise CaptureError("membros ZIP divergentes")
        for name, data in expected.items():
            if archive.read(name) != data:
                raise CaptureError(f"bytes ZIP divergentes: {name}")
            info = archive.getinfo(name)
            if info.date_time != ZIP_DT or info.filename.endswith(".zip"):
                raise CaptureError(f"normalização ZIP divergente: {name}")
        if archive.testzip() is not None:
            raise CaptureError("CRC ZIP inválido")


def main() -> int:
    root = Path(__file__).resolve().parents[3]
    bundle = Path(__file__).resolve().parent
    zip_path = bundle.parent / f"{BUNDLE_NAME}.zip"
    if {p.name for p in bundle.iterdir()} != {"CAPTURE.py"}:
        raise CaptureError("directório de destino não está vazio salvo CAPTURE.py")
    assert_identity(root)
    initial = status(root)
    capture_rel = f"docs/EVIDENCE/{BUNDLE_NAME}/CAPTURE.py"
    if initial.strip() != f"?? {capture_rel}":
        raise CaptureError(f"estado Git inicial inesperado: {initial!r}")
    if checked(root, "git", "diff", "--cached", "--name-only"):
        raise CaptureError("existem ficheiros staged")
    before = tracked_inventory(root)
    write_text(bundle / "GIT-BEFORE.txt", git_record(root, before))
    write_text(bundle / "ENVIRONMENT.txt", environment_text(root))
    write_text(bundle / "RED-RETROSPECTIVE.txt", retrospective_red())
    write_text(bundle / "INCIDENT-TEST-DB-RETROSPECTIVE.txt", retrospective_incident())
    gate1_node, gate2_nodes = identify_nodes(root)
    write_text(bundle / "GATE-2-NODE-IDS.txt", "\n".join(gate2_nodes))
    py = sys.executable
    gates = [
        gate(root, bundle, "GATE-1-GREEN-9B4", [py, "-m", "pytest", "-q", "--tb=short", gate1_node], "1 passed"),
        gate(root, bundle, "GATE-2-PRESERVACAO-9B2-GREEN-9B4", [py, "-m", "pytest", "-q", "--tb=short", *gate2_nodes], "2 passed"),
        gate(root, bundle, "GATE-3-REGRESSAO-POSTGRESQL-ADR020", [py, "-m", "pytest", "-q", "--tb=short", TEST_FILE], "179 passed"),
        gate(root, bundle, "GATE-4-SUITE-GLOBAL", [py, "-m", "pytest", "-q", "--tb=short"], "2763 passed, 15 skipped, 970 warnings"),
    ]
    after = tracked_inventory(root)
    if after != before:
        raise CaptureError("ficheiros protegidos de produção/teste foram alterados")
    assert_identity(root)
    if checked(root, "git", "diff", "--cached", "--name-only"):
        raise CaptureError("ficheiros staged detectados")
    if checked(root, "git", "diff", "--name-only"):
        raise CaptureError("alterações rastreadas detectadas")
    if (root / REPORT).exists() or list((root / "docs/REPORTS").glob("REPORT-031*")):
        raise CaptureError("REPORT-031 foi criado")
    write_text(bundle / "GIT-AFTER.txt", git_record(root, after))
    summary = "RUN SUMMARY\n\n1. RED retrospectivo\nVer RED-RETROSPECTIVE.txt; não é stdout bruto.\n\n2. Incidente ambiental retrospectivo\nVer INCIDENT-TEST-DB-RETROSPECTIVE.txt; não é stdout bruto.\n\n3. Provas brutas actuais\n" + "\n".join(f"{m['gate']}: exit_code={m['exit_code']}; resultado={m['observed_result']}; duration_seconds={m['duration_seconds']}" for m in gates) + "\n\n4. Resultado final\nTodas as quatro gates cumpriram as contagens e exit codes vinculantes.\nEVIDENCIA_9B4_CAPTURADA_INTEGRALMENTE\nBUNDLE_EVIDENCIA_9B4_APTO_PARA_VINCULACAO_DOCUMENTAL\n\n5. Limites operacionais\nCaptura local/de teste; sem Railway, Vercel, produção, deploy, credenciais externas ou autorização operacional. Cada gate usou SQLite temporário isolado, removido no fim. O RED e o incidente são retrospectivos.\n"
    write_text(bundle / "RUN-SUMMARY.txt", summary)
    if {p.name for p in bundle.iterdir() if p.is_file()} != EXPECTED_FILES:
        raise CaptureError("conjunto de ficheiros anterior ao MANIFEST divergente")
    write_bytes(bundle / "MANIFEST.txt", manifest_bytes(bundle))
    manifest_lines = (bundle / "MANIFEST.txt").read_text(encoding="utf-8").splitlines()
    if len(manifest_lines) != len(EXPECTED_FILES) or any(line.startswith("MANIFEST.txt\t") or ".zip\t" in line for line in manifest_lines):
        raise CaptureError("MANIFEST inválido")
    create_zip(bundle, zip_path)
    audit_zip(bundle, zip_path)
    expected_final = {f"docs/EVIDENCE/{BUNDLE_NAME}/{name}" for name in EXPECTED_FILES | {"MANIFEST.txt"}}
    expected_final.add(f"docs/EVIDENCE/{BUNDLE_NAME}.zip")
    entries = [line[3:] for line in status(root).splitlines() if line.startswith("?? ")]
    if set(entries) != expected_final:
        raise CaptureError("estado Git final fora da fronteira autorizada")
    print("capture complete")
    print(f"files={len(EXPECTED_FILES) + 1}")
    print(f"zip_size={zip_path.stat().st_size}")
    print(f"zip_sha256={file_digest(zip_path)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"CAPTURE FAILED: {exc}", file=sys.stderr)
        raise
