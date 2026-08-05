from __future__ import annotations

import hashlib
import json
import os
import signal
import shutil
import subprocess
import sys
import time
import traceback
import zipfile
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


EXPECTED_COMMIT = "868d5abec642865c7839eb02ea53db5f895b1002"
BUNDLE_NAME = "BUNDLE-EVIDENCIA-9B2-REPORT-030-V1.0"
REPORT_REL = (
    "docs/REPORTS/"
    "REPORT-030-FECHAMENTO-TECNICO-MISSION-012-ADR-020-INTENCAO-9B2-V1.0.md"
)
CAPTURE_REL = f"docs/EVIDENCE/{BUNDLE_NAME}/CAPTURE.py"
ZIP_REL = f"docs/EVIDENCE/{BUNDLE_NAME}.zip"
MIN_FREE_BYTES = 20 * 1024**3
SUCCESS_NAMES = {
    "CAPTURE.py",
    "ENVIRONMENT.txt",
    "GIT-BEFORE.txt",
    "GATE-1-POSTGRESQL.stdout.txt",
    "GATE-1-POSTGRESQL.stderr.txt",
    "GATE-1-POSTGRESQL.meta.json",
    "GATE-2-ADR020-FILES.txt",
    "GATE-2-ADR020.stdout.txt",
    "GATE-2-ADR020.stderr.txt",
    "GATE-2-ADR020.meta.json",
    "GATE-3-REGRESSAO-GLOBAL.stdout.txt",
    "GATE-3-REGRESSAO-GLOBAL.stderr.txt",
    "GATE-3-REGRESSAO-GLOBAL.meta.json",
    "INCIDENTE-AMBIENTAL-RETROSPECTIVO.txt",
    "GIT-AFTER.txt",
    "RUN-SUMMARY.txt",
}
MANIFEST_NAME = "MANIFEST.txt"
FAILED_NAME = "RUN-FAILED.txt"
ZIP_DATE_TIME = (1980, 1, 1, 0, 0, 0)
ZIP_EXTERNAL_ATTR = 0o100644 << 16
# Todos os nomes canonicos do bundle sao ASCII; zipfile produz flag efectiva zero.
ZIP_EXPECTED_FLAG_BITS = 0


class CaptureError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def clean_text(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.splitlines()).rstrip("\n") + "\n"


def temporary_path(destination: Path) -> Path:
    return destination.with_name(f".{destination.name}.{os.getpid()}.tmp")


def publish_temporary(temporary: Path, destination: Path) -> None:
    """Publish on Windows without ever replacing an existing destination."""
    if temporary.parent != destination.parent:
        raise CaptureError("O temporario de publicacao nao esta no directorio do destino")
    try:
        if destination.exists():
            raise CaptureError(f"Recusa de sobrescrita: {destination}")
        os.rename(temporary, destination)
    except BaseException:
        try:
            if temporary.exists():
                temporary.unlink()
        except OSError:
            pass
        raise


def publish_bytes(path: Path, data: bytes) -> None:
    temporary = temporary_path(path)
    if temporary.exists():
        raise CaptureError(f"Ficheiro temporario inesperado: {temporary}")
    try:
        with temporary.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        publish_temporary(temporary, path)
    except BaseException:
        try:
            if temporary.exists():
                temporary.unlink()
        except OSError:
            pass
        raise


def write_text(path: Path, text: str) -> None:
    publish_bytes(path, clean_text(text).encode("utf-8"))


def write_json(path: Path, value: object) -> None:
    data = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    publish_bytes(path, data)


def run_checked(argv: Sequence[str], cwd: Path, env: dict[str, str] | None = None) -> bytes:
    completed = subprocess.run(
        list(argv), cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise CaptureError(
            f"Comando falhou ({completed.returncode}): {powershell_command(argv)}"
            + (f"\n{stderr}" if stderr else "")
        )
    return completed.stdout


def powershell_command(argv: Sequence[str]) -> str:
    return " ".join("'" + item.replace("'", "''") + "'" for item in argv)


def git_output(root: Path, *args: str) -> bytes:
    return run_checked(["git", *args], root)


def git_status(root: Path) -> bytes:
    return git_output(root, "status", "--short", "--untracked-files=all")


def status_entries(status: bytes) -> list[tuple[str, str]]:
    text = status.decode("utf-8", errors="strict")
    entries: list[tuple[str, str]] = []
    for line in text.splitlines():
        if len(line) < 4:
            raise CaptureError(f"Linha Git inesperada: {line!r}")
        entries.append((line[:2], line[3:]))
    return entries


def assert_initial_git(root: Path, status: bytes) -> None:
    allowed = {("??", REPORT_REL), ("??", CAPTURE_REL)}
    if set(status_entries(status)) != allowed:
        raise CaptureError(
            "Estado Git inicial fora da fronteira autorizada:\n"
            + status.decode("utf-8", errors="replace")
        )


def expected_success_paths() -> set[str]:
    prefix = f"docs/EVIDENCE/{BUNDLE_NAME}/"
    return {REPORT_REL, ZIP_REL, *(prefix + name for name in SUCCESS_NAMES | {MANIFEST_NAME})}


def validate_success_git(status: bytes) -> None:
    entries = status_entries(status)
    actual = {path for code, path in entries if code == "??"}
    if any(code != "??" for code, _ in entries):
        raise CaptureError("Alteracao rastreada detectada durante a captura")
    if actual != expected_success_paths():
        raise CaptureError(f"Fronteira final Git incorrecta: {sorted(actual)!r}")


def assert_bundle_names(bundle: Path, expected: set[str]) -> None:
    actual = {path.name for path in bundle.iterdir() if path.is_file()}
    non_files = [path.name for path in bundle.iterdir() if not path.is_file()]
    if actual != expected or non_files:
        raise CaptureError(
            f"Conteudo inesperado do bundle: ficheiros={sorted(actual)!r}; "
            f"nao_ficheiros={sorted(non_files)!r}"
        )


def protected_inventory(root: Path) -> tuple[tuple[str, int, str], ...]:
    raw = git_output(root, "ls-files", "-z", "--", "app", "migrations", "tests")
    names = raw.split(b"\0")
    if names and names[-1] == b"":
        names.pop()
    records: list[tuple[str, int, str]] = []
    for encoded in names:
        relative = encoded.decode("utf-8", errors="strict")
        path = root / Path(relative)
        if not path.is_file():
            raise CaptureError(f"Caminho Git protegido nao e ficheiro regular: {relative}")
        records.append((Path(relative).as_posix(), path.stat().st_size, sha256_file(path)))
    return tuple(records)


def inventory_text(status: bytes, inventory: tuple[tuple[str, int, str], ...]) -> str:
    lines = ["GIT STATUS --SHORT --UNTRACKED-FILES=ALL", ""]
    lines.extend(status.decode("utf-8", errors="strict").splitlines())
    lines.extend(["", "PROTECTED TRACKED FILE INVENTORY", ""])
    lines.extend(f"{path}\t{size}\t{digest}" for path, size, digest in inventory)
    return "\n".join(lines)


def verify_protected(
    root: Path,
    initial: tuple[tuple[str, int, str], ...],
    report_hash: str,
    capture_hash: str,
) -> tuple[tuple[str, int, str], ...]:
    current = protected_inventory(root)
    if current != initial:
        raise CaptureError("O inventario protegido final diverge da fotografia inicial")
    if sha256_file(root / REPORT_REL) != report_hash:
        raise CaptureError("REPORT-030 foi modificado durante a captura")
    if sha256_file(root / CAPTURE_REL) != capture_hash:
        raise CaptureError("CAPTURE.py foi modificado durante a captura")
    return current


def command_record(argv: Sequence[str], root: Path, env: dict[str, str]) -> str:
    completed = subprocess.run(
        list(argv), cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    stdout = completed.stdout.decode("utf-8", errors="replace")
    stderr = completed.stderr.decode("utf-8", errors="replace")
    record = (
        f"$ {powershell_command(argv)}\n"
        f"exit_code: {completed.returncode}\n"
        "stdout:\n"
        f"{stdout}\n"
        "stderr:\n"
        f"{stderr}"
    )
    if completed.returncode != 0:
        raise CaptureError(
            f"Comando ambiental falhou ({completed.returncode}): "
            f"{powershell_command(argv)}\n{stderr.strip()}"
        )
    return record


def run_gate(
    bundle: Path,
    root: Path,
    label: str,
    stem: str,
    argv: Sequence[str],
    env: dict[str, str],
) -> dict[str, object]:
    started_utc = utc_now()
    started_monotonic = time.monotonic()
    completed = subprocess.run(
        list(argv), cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    duration = time.monotonic() - started_monotonic
    metadata: dict[str, object] = {
        "argv": list(argv),
        "cwd": str(root),
        "duration_monotonic_seconds": round(duration, 9),
        "end_utc": utc_now(),
        "exit_code": completed.returncode,
        "gate": label,
        "powershell": powershell_command(argv),
        "start_utc": started_utc,
        "stderr": {"sha256": sha256_bytes(completed.stderr), "size_bytes": len(completed.stderr)},
        "stdout": {"sha256": sha256_bytes(completed.stdout), "size_bytes": len(completed.stdout)},
    }
    publish_bytes(bundle / f"{stem}.stdout.txt", completed.stdout)
    publish_bytes(bundle / f"{stem}.stderr.txt", completed.stderr)
    write_json(bundle / f"{stem}.meta.json", metadata)
    print(f"{label}: exit_code={completed.returncode} duration={duration:.3f}s", flush=True)
    if completed.returncode != 0:
        raise CaptureError(f"{label} falhou com exit code {completed.returncode}")
    return metadata


def retrospective_text() -> str:
    return """INCIDENTE AMBIENTAL - RECONSTRUCAO RETROSPECTIVA

Este registo e uma transcricao retrospectiva da sessao interactiva. Nao e uma
captura bruta contemporanea produzida por este script e nao deve ser usado como
prova das novas gates.

- Tentativa directa anterior da Gate 1: 66 passed, 29 warnings, 1 error in
  307.49s (0:05:07).
- Causa observada: Docker Desktop sem conseguir iniciar PostgreSQL isolado por
  disco cheio.
- Foram removidos 18 containers efemeros `mission-009a-*`.
- `docker volume prune` reportou: Total reclaimed space: 160.5GB.
- `docker_data.vhdx` foi compactado de 148.15 GB para 11.70 GB.
- O disco C: ficou com 141.68 GB livres.
- Docker foi reiniciado e confirmado operacional.

Todos os numeros acima sao transcricao retrospectiva da sessao, nao stdout bruto
capturado por este script. Este ficheiro nao constitui prova das novas gates.
"""


def snapshot_success_files(bundle: Path) -> dict[str, bytes]:
    assert_bundle_names(bundle, SUCCESS_NAMES)
    return {name: (bundle / name).read_bytes() for name in sorted(SUCCESS_NAMES)}


def manifest_bytes(snapshot: dict[str, bytes]) -> bytes:
    lines = [
        f"{name}\t{len(data)}\t{sha256_bytes(data)}"
        for name, data in sorted(snapshot.items())
    ]
    return clean_text("\n".join(lines)).encode("utf-8")


def build_zip_temporary(
    bundle: Path, zip_path: Path, snapshot: dict[str, bytes], manifest: bytes
) -> tuple[Path, dict[str, bytes]]:
    temporary = temporary_path(zip_path)
    if temporary.exists() or zip_path.exists():
        raise CaptureError("ZIP final ou temporario ja existe")
    members = dict(snapshot)
    members[MANIFEST_NAME] = manifest
    try:
        with zipfile.ZipFile(
            temporary, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as archive:
            for name, data in sorted(members.items()):
                archive_name = f"{bundle.name}/{name}"
                info = zipfile.ZipInfo(archive_name, date_time=ZIP_DATE_TIME)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = ZIP_EXTERNAL_ATTR
                archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        with temporary.open("r+b") as stream:
            stream.flush()
            os.fsync(stream.fileno())
        return temporary, members
    except BaseException:
        if temporary.exists():
            temporary.unlink()
        raise


def validate_zip(path: Path, bundle: Path, members: dict[str, bytes], manifest: bytes) -> None:
    expected = [f"{bundle.name}/{name}" for name in sorted(members)]
    with zipfile.ZipFile(path, "r") as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if names != expected or len(names) != len(set(names)):
            raise CaptureError("Lista, ordem ou unicidade dos membros do ZIP incorrecta")
        if MANIFEST_NAME not in members:
            raise CaptureError("MANIFEST ausente do ZIP")
        for name in names:
            try:
                name.encode("ascii", errors="strict")
            except UnicodeEncodeError as error:
                raise CaptureError(f"Nome nao ASCII no ZIP: {name}") from error
            parts = name.split("/")
            if name.startswith("/") or "\\" in name or ".." in parts:
                raise CaptureError(f"Caminho inseguro no ZIP: {name}")
            if name == zip_path_member(bundle) or name.endswith(f"/{bundle.name}.zip"):
                raise CaptureError("O ZIP inclui a si proprio")
        for info in infos:
            short_name = info.filename.removeprefix(f"{bundle.name}/")
            expected_data = members[short_name]
            actual_data = archive.read(info)
            if actual_data != expected_data:
                raise CaptureError(f"Bytes divergentes no ZIP: {info.filename}")
            if info.file_size != len(expected_data) or sha256_bytes(actual_data) != sha256_bytes(expected_data):
                raise CaptureError(f"Tamanho ou SHA-256 divergente no ZIP: {info.filename}")
            if info.compress_type != zipfile.ZIP_DEFLATED:
                raise CaptureError(f"Compressao incorrecta no ZIP: {info.filename}")
            if info.CRC != (zlib.crc32(expected_data) & 0xFFFFFFFF):
                raise CaptureError(f"CRC divergente no ZIP: {info.filename}")
            if info.flag_bits != ZIP_EXPECTED_FLAG_BITS:
                raise CaptureError(f"Flag bits incorrectos no ZIP: {info.filename}")
            if info.date_time != ZIP_DATE_TIME or info.external_attr != ZIP_EXTERNAL_ATTR:
                raise CaptureError(f"Metadados nao deterministas no ZIP: {info.filename}")
    if members.get(MANIFEST_NAME) != manifest:
        raise CaptureError("MANIFEST definitivo nao esta incluido no ZIP")
    declared = {}
    for line in manifest.decode("utf-8", errors="strict").splitlines():
        name, size, digest = line.split("\t")
        declared[name] = (int(size), digest)
    expected_declared = {
        name: (len(data), sha256_bytes(data))
        for name, data in members.items()
        if name != MANIFEST_NAME
    }
    if declared != expected_declared:
        raise CaptureError("Itens declarados pelo MANIFEST divergem da fotografia")


def zip_path_member(bundle: Path) -> str:
    return f"{bundle.name}.zip"


def validate_published_files(
    bundle: Path, snapshot: dict[str, bytes], manifest: bytes | None = None
) -> None:
    expected = set(SUCCESS_NAMES)
    expected_bytes = dict(snapshot)
    if manifest is not None:
        expected.add(MANIFEST_NAME)
        expected_bytes[MANIFEST_NAME] = manifest
    actual_entries = list(bundle.iterdir())
    actual = {path.name for path in actual_entries}
    if actual != expected:
        raise CaptureError(
            f"Conteudo solto do bundle incorrecto: esperado={sorted(expected)!r}; "
            f"obtido={sorted(actual)!r}"
        )
    if FAILED_NAME in actual:
        raise CaptureError("RUN-FAILED.txt presente numa conclusao verde")
    for path in actual_entries:
        if not path.is_file():
            raise CaptureError(f"Item solto nao e ficheiro regular: {path}")
        data = path.read_bytes()
        photographed = expected_bytes[path.name]
        if data != photographed:
            raise CaptureError(f"Bytes soltos divergem da fotografia: {path.name}")
        if path.stat().st_size != len(photographed):
            raise CaptureError(f"Tamanho solto diverge da fotografia: {path.name}")
        if sha256_bytes(data) != sha256_bytes(photographed):
            raise CaptureError(f"SHA-256 solto diverge da fotografia: {path.name}")


def remove_final_publications(bundle: Path, zip_path: Path) -> dict[str, list[str]]:
    targets = (
        bundle / MANIFEST_NAME,
        zip_path,
        temporary_path(bundle / MANIFEST_NAME),
        temporary_path(zip_path),
    )
    errors: list[str] = []
    for attempt in range(1, 4):
        for path in targets:
            try:
                path.unlink()
            except FileNotFoundError:
                continue
            except OSError as error:
                errors.append(
                    f"tentativa {attempt}, {path}: {type(error).__name__}: {error}"
                )
        residues = []
        for path in targets:
            try:
                path.lstat()
                residues.append(str(path))
            except FileNotFoundError:
                continue
            except OSError as error:
                errors.append(
                    f"verificacao {attempt}, {path}: {type(error).__name__}: {error}"
                )
                residues.append(f"{path} (estado nao verificavel)")
        if not residues:
            break
        if attempt < 3:
            time.sleep(0.05)
    residues = []
    for path in targets:
        try:
            path.lstat()
            residues.append(str(path))
        except FileNotFoundError:
            continue
        except OSError as error:
            errors.append(
                f"verificacao final, {path}: {type(error).__name__}: {error}"
            )
            residues.append(f"{path} (estado nao verificavel)")
    return {"errors": errors, "residues": residues}


def failure_text(
    error: BaseException,
    phase: str,
    bundle: Path,
    root: Path,
    cleanup: dict[str, list[str]],
) -> str:
    artifacts = sorted(path.name for path in bundle.iterdir())
    try:
        state = git_status(root).decode("utf-8", errors="strict")
        git_section = "Git state available: yes\n" + state
    except BaseException as git_error:
        git_section = (
            "Git state available: no\n"
            f"Git state error: {type(git_error).__name__}: {git_error}\n"
        )
    return (
        f"Timestamp UTC: {utc_now()}\n"
        f"Exception type: {type(error).__name__}\n"
        f"Message: {error}\n"
        f"Phase: {phase}\n"
        "Existing artifacts:\n"
        + "".join(f"- {name}\n" for name in artifacts)
        + "Traceback:\n"
        + "".join(traceback.format_exception(type(error), error, error.__traceback__))
        + "Cleanup errors:\n"
        + "".join(f"- {item}\n" for item in cleanup["errors"])
        + "Cleanup residues:\n"
        + "".join(f"- {item}\n" for item in cleanup["residues"])
        + git_section
    )


def record_failure(
    error: BaseException, phase: str, bundle: Path, root: Path, zip_path: Path
) -> dict[str, object]:
    result: dict[str, object] = {
        "cleanup_ok": False,
        "publication_ok": False,
        "cleanup_errors": [],
        "residues": [],
        "secondary_errors": [],
    }
    secondary = result["secondary_errors"]
    assert isinstance(secondary, list)
    previous_handlers: dict[int, object] = {}
    signals = [signal.SIGINT]
    if os.name == "nt" and hasattr(signal, "SIGBREAK"):
        signals.append(signal.SIGBREAK)
    try:
        for signum in signals:
            try:
                previous_handlers[signum] = signal.getsignal(signum)
                signal.signal(signum, signal.SIG_IGN)
            except BaseException as block_error:
                secondary.append(
                    f"signal block {signum}: {type(block_error).__name__}: {block_error}"
                )
        cleanup = remove_final_publications(bundle, zip_path)
        result["cleanup_errors"] = cleanup["errors"]
        result["residues"] = cleanup["residues"]
        result["cleanup_ok"] = not cleanup["residues"]
        marker = bundle / FAILED_NAME
        marker_temporary = temporary_path(marker)
        try:
            definitive = clean_text(
                failure_text(error, phase, bundle, root, cleanup)
            ).encode("utf-8")
            expected_size = len(definitive)
            expected_hash = sha256_bytes(definitive)
            publish_bytes(marker, definitive)
            if not marker.exists() or not marker.is_file():
                raise CaptureError("RUN-FAILED.txt nao existe como ficheiro regular")
            persisted = marker.read_bytes()
            if (
                persisted != definitive
                or marker.stat().st_size != expected_size
                or sha256_bytes(persisted) != expected_hash
            ):
                raise CaptureError("Verificacao posterior de RUN-FAILED.txt falhou")
            result["publication_ok"] = True
        except BaseException as publication_error:
            secondary.append(
                f"RUN-FAILED publication: {type(publication_error).__name__}: "
                f"{publication_error}"
            )
        finally:
            try:
                if marker_temporary.exists():
                    marker_temporary.unlink()
            except OSError as temporary_error:
                secondary.append(
                    f"RUN-FAILED temporary cleanup: {type(temporary_error).__name__}: "
                    f"{temporary_error}"
                )
    except BaseException as recording_error:
        secondary.append(
            f"failure recorder: {type(recording_error).__name__}: {recording_error}"
        )
    finally:
        for signum, handler in previous_handlers.items():
            try:
                signal.signal(signum, handler)
            except BaseException as restore_error:
                secondary.append(
                    f"signal restore {signum}: {type(restore_error).__name__}: {restore_error}"
                )
    return result


def execute(state: dict[str, object]) -> int:
    state["phase"] = "pre-condicoes"
    capture_path = Path(__file__).resolve()
    bundle = capture_path.parent
    structural_root = capture_path.parents[3]
    state.update(bundle=bundle, root=structural_root, zip_path=structural_root / ZIP_REL)
    zip_path = structural_root / ZIP_REL
    if os.name != "nt" or sys.platform != "win32":
        raise CaptureError("Este capturador exige Windows")
    git_root = Path(
        git_output(structural_root, "rev-parse", "--show-toplevel").decode("utf-8", errors="strict").strip()
    ).resolve()
    cwd = Path.cwd().resolve()
    if not (structural_root == git_root == cwd):
        raise CaptureError(
            f"Raizes divergentes: estrutural={structural_root}; git={git_root}; cwd={cwd}"
        )
    expected_python = (structural_root / "venv/Scripts/python.exe").resolve()
    if Path(sys.executable).resolve() != expected_python:
        raise CaptureError(f"Python incorrecto: esperado {expected_python}; obtido {sys.executable}")
    if capture_path != (structural_root / CAPTURE_REL).resolve():
        raise CaptureError("CAPTURE.py nao esta no caminho canonico esperado")
    assert_bundle_names(bundle, {"CAPTURE.py"})
    if zip_path.exists():
        raise CaptureError(f"ZIP ja existe: {zip_path}")

    initial_status = git_status(structural_root)
    assert_initial_git(structural_root, initial_status)
    head = git_output(structural_root, "rev-parse", "HEAD").decode("ascii").strip()
    branch = git_output(structural_root, "branch", "--show-current").decode("utf-8").strip()
    origin_main = git_output(structural_root, "rev-parse", "origin/main").decode("ascii").strip()
    if branch != "main":
        raise CaptureError(f"Branch incorrecta: {branch!r}")
    if head != EXPECTED_COMMIT or origin_main != EXPECTED_COMMIT:
        raise CaptureError(f"Commit incorrecto: HEAD={head}; origin/main={origin_main}")
    initial_inventory = protected_inventory(structural_root)
    report_hash = sha256_file(structural_root / REPORT_REL)
    capture_hash = sha256_file(capture_path)

    free_c = shutil.disk_usage("C:\\").free
    if free_c < MIN_FREE_BYTES:
        raise CaptureError(f"Espaco livre insuficiente em C: {free_c} bytes")
    gate_env = os.environ.copy()
    gate_env.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"})
    python = str(expected_python)
    pytest_version = run_checked([python, "-m", "pytest", "--version"], structural_root, gate_env)
    docker_commands = (
        ["docker", "version"],
        ["docker", "info"],
        ["docker", "ps", "-a", "--no-trunc"],
        ["docker", "image", "inspect", "postgres:16-alpine"],
        ["docker", "run", "--rm", "--pull=never", "--entrypoint", "postgres", "postgres:16-alpine", "--version"],
    )
    docker_records = [command_record(argv, structural_root, gate_env) for argv in docker_commands]
    docker_text = "\n\n".join(docker_records)
    environment = f"""CAPTURE START UTC: {utc_now()}
WORKING DIRECTORY: {cwd}
STRUCTURAL REPOSITORY ROOT: {structural_root}
GIT REPOSITORY ROOT: {git_root}
OPERATING SYSTEM: os.name={os.name}; sys.platform={sys.platform}
FREE SPACE C BYTES: {free_c}
FREE SPACE C GIB: {free_c / 1024**3:.2f}
SYS.EXECUTABLE: {sys.executable}
PYTHON VERSION: {sys.version}
PYTEST VERSION: {pytest_version.decode('utf-8', errors='replace')}
GIT HEAD: {head}
GIT BRANCH: {branch}
GIT ORIGIN/MAIN: {origin_main}

POSTGRES VERSION QUERY NOTE
The docker run query is ephemeral, uses --rm and --pull=never, creates no volume,
and leaves no persistent resource.

DOCKER RECORDS
{docker_text}
"""
    state["phase"] = "evidencias iniciais"
    state["evidence_started"] = True
    write_text(bundle / "ENVIRONMENT.txt", environment)
    write_text(bundle / "GIT-BEFORE.txt", inventory_text(initial_status, initial_inventory))
    write_text(bundle / "INCIDENTE-AMBIENTAL-RETROSPECTIVO.txt", retrospective_text())

    gate2_paths = sorted(
        (path for path in (structural_root / "tests").glob("*adr020*.py") if path.is_file()),
        key=lambda path: path.relative_to(structural_root).as_posix(),
    )
    if len(gate2_paths) != 14:
        raise CaptureError(f"Gate 2 exige 14 ficheiros; obteve {len(gate2_paths)}")
    gate2_files = [path.relative_to(structural_root).as_posix() for path in gate2_paths]
    write_text(bundle / "GATE-2-ADR020-FILES.txt", "\n".join(gate2_files))

    specifications = (
        ("Gate 1 - PostgreSQL", "GATE-1-POSTGRESQL", [python, "-m", "pytest", "tests/test_adr020_activation_postgresql.py", "-q"]),
        ("Gate 2 - ADR-020", "GATE-2-ADR020", [python, "-m", "pytest", *gate2_files, "-q"]),
        ("Gate 3 - Regressao global", "GATE-3-REGRESSAO-GLOBAL", [python, "-m", "pytest", "-q"]),
    )
    results: list[dict[str, object]] = []
    for label, stem, argv in specifications:
        state["phase"] = label
        results.append(run_gate(bundle, structural_root, label, stem, argv, gate_env))

    state["phase"] = "fechamento preliminar"
    final_inventory = verify_protected(structural_root, initial_inventory, report_hash, capture_hash)
    preliminary_status = git_status(structural_root)
    write_text(bundle / "GIT-AFTER.txt", inventory_text(preliminary_status, final_inventory))
    summary = [
        "RUN SUMMARY",
        "",
        *[
            f"{item['gate']}: exit_code={item['exit_code']}; duration_monotonic_seconds={item['duration_monotonic_seconds']}"
            for item in results
        ],
        "",
        "A prova de preservacao e a igualdade observada entre as fotografias inicial e final.",
        "REPORT-030 SHA-256 remained unchanged.",
        "EVIDENCIA_9B2_CAPTURADA_INTEGRALMENTE",
    ]
    write_text(bundle / "RUN-SUMMARY.txt", "\n".join(summary))

    state["phase"] = "fotografia, MANIFEST e ZIP"
    snapshot = snapshot_success_files(bundle)
    manifest = manifest_bytes(snapshot)
    zip_temporary, zip_members = build_zip_temporary(bundle, zip_path, snapshot, manifest)
    validate_zip(zip_temporary, bundle, zip_members, manifest)

    state["phase"] = "verificacao anterior a publicacao"
    verify_protected(structural_root, initial_inventory, report_hash, capture_hash)
    before_publish_status = git_status(structural_root)
    zip_temporary_rel = zip_temporary.relative_to(structural_root).as_posix()
    expected_before_publish = (
        expected_success_paths()
        - {ZIP_REL, f"docs/EVIDENCE/{BUNDLE_NAME}/{MANIFEST_NAME}"}
    ) | {zip_temporary_rel}
    if {path for code, path in status_entries(before_publish_status) if code == "??"} != expected_before_publish or any(
        code != "??" for code, _ in status_entries(before_publish_status)
    ):
        raise CaptureError("Estado Git incorrecto antes da publicacao")

    state["phase"] = "publicacao final"
    validate_published_files(bundle, snapshot)
    publish_bytes(bundle / MANIFEST_NAME, manifest)
    publish_temporary(zip_temporary, zip_path)

    state["phase"] = "validacao final"
    validate_published_files(bundle, snapshot, manifest)
    validate_zip(zip_path, bundle, zip_members, manifest)
    verify_protected(structural_root, initial_inventory, report_hash, capture_hash)
    final_status = git_status(structural_root)
    validate_success_git(final_status)
    validate_published_files(bundle, snapshot, manifest)
    print(f"MANIFEST: {bundle / MANIFEST_NAME} size={len(manifest)} sha256={sha256_bytes(manifest)}")
    print(f"ZIP: {zip_path} size={zip_path.stat().st_size} sha256={sha256_file(zip_path)}")
    print("GIT FINAL:")
    print(final_status.decode("utf-8", errors="strict"), end="")
    print("EVIDENCIA_9B2_CAPTURADA_INTEGRALMENTE")
    return 0


def controlled_main() -> int:
    state: dict[str, object] = {"phase": "arranque", "evidence_started": False}
    try:
        return execute(state)
    except BaseException as error:
        print(
            f"CAPTURE ORIGINAL FAILURE: {type(error).__name__}: {error}",
            file=sys.stderr,
        )
        if state.get("evidence_started") is True:
            bundle = state.get("bundle")
            root = state.get("root")
            zip_path = state.get("zip_path")
            if isinstance(bundle, Path) and isinstance(root, Path) and isinstance(zip_path, Path):
                result = record_failure(
                    error, str(state["phase"]), bundle, root, zip_path
                )
                for cleanup_error in result["cleanup_errors"]:
                    print(f"CLEANUP ERROR: {cleanup_error}", file=sys.stderr)
                for residue in result["residues"]:
                    print(f"CLEANUP RESIDUE: {residue}", file=sys.stderr)
                for secondary in result["secondary_errors"]:
                    print(f"SECONDARY FAILURE: {secondary}", file=sys.stderr)
                if result["publication_ok"]:
                    print("RUN-FAILED.txt published and verified", file=sys.stderr)
                else:
                    print(
                        "RUN-FAILED.txt was not persisted and verified; full failure "
                        "fallback is stderr",
                        file=sys.stderr,
                    )
            else:
                print(
                    "Failure paths unavailable; cleanup and RUN-FAILED publication "
                    "could not be attempted",
                    file=sys.stderr,
                )
        else:
            print(
                "Execution failed before evidence started; no artifact was created, "
                "removed, or modified",
                file=sys.stderr,
            )
        return 1


if __name__ == "__main__":
    exit_code = controlled_main()
    raise SystemExit(exit_code)
