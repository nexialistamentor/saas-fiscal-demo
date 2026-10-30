"""B02 RCV31 A2 V4: one targeted disposable PG17 positive using archived V7 runner.

Never targets a protected DB. Requires exact C3 PDF SHA-256, frozen Windows worktree,
archived V7 diagnostic, and a pinned V4 patch. Does not rerun historical negatives.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

HISTORIC_ARCHIVE = 'SOLVERIS_B02_DELTA4_V3_ENTREGA_COMPLEMENTAR_20261025_163045.zip'
BASE = Path(__file__).resolve().parent
V7 = 'B02_RCV31_R3_DIAGNOSTICO_CAUSAL_V7.ps1'
BASE_SOURCE = 'B02_RCV31_R3_CONCRETE_PATH_DELTA4_V3_SOBRE_REAL.py'
CANDIDATE = 'B02_RCV31_R3_CONCRETE_PATH_DELTA4_V4_A2_SNAPSHOT_CANDIDATO.py'
PATCH = 'B02_RCV31_R3_DELTA4_V3_A2_SNAPSHOT_V4.patch'
ORIGINAL_OBSERVER = 'B02_RCV31_R3_OBSERVADOR_PROCESSO_SEPARADO.py'
PINS = {
    'archive': 'b90855ecc7a90a499b93b225516ae289ba98f2d8c1d35f597781d1b832a5a304',
    'v7': '04e9a26c100cb5958ab96124e5c7eb1fea4f6bbffb2c5e2095c540b252385465',
    'v3': '1fae5b1aefe9630e077eae9c98b44c91d4f9dd99f9e4560a6dab83b74e5e7779',
    'v4': '2fd9c8b9fdae373ec7622971a6d5efdca0f3d18f5082769065f7cd1f0e6bda11',
    'patch': 'bfd8b397bb245923a7cff10b0b1c06480bef29aa8e2c707691bcc992c5f8ce7e',
    'concrete_original': '2927a9b10e6e47f45088522fae15c39800ae75966a1cca340c7bb3564e63ef46',
    'observer_original': '4dc2b18af2942353b788b43bf41a2b6ef37b406bb16c942f335c94f6bc369e2e',
    'cas1245': 'e7bc013d6195e904f780a6be78a1ea0d0ca0bdcff530fba9ec4baa4c348e6832',
    'cas571': 'af53bf64313fefa45e5ed490fdd7ca57e7b2d87116f2f74a1ba1ae0cff874a5d',
    'g19': '31af40939138916e86ec917c1d228c7563ee06d035549133c520537d6e6064bb',
    'migration0062': 'bf8c953c6ed8448b33b90205540882f3dddcf46895cb1d6ef932148952fa1d0e',
    'migration0063': 'c2e80f3efc5a1b00ae7926c3dd8e459b64b88e7becd95a30255eafcb5effc475',
}

PDF_LENGTHS = {'cas1245': 258302, 'cas571': 1944929}
HISTORIC_BRANCH = 'candidate/g5-successor-window-prep'
HISTORIC_HEAD = '56d8b23c8af5f8a9b7fdf1eb8fb01a9f008dc9f8'


def stop(message):
    raise RuntimeError('STOP_A2_PHYSICAL_' + message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def pinned_bytes(data, key):
    v = sha(data)
    if v != PINS[key]:
        stop(key.upper() + '_SHA256_DIVERGENT_' + v)


def git_checkout_verification(root):
    for args, expect in ((['branch', '--show-current'], HISTORIC_BRANCH),
                         (['rev-parse', 'HEAD'], HISTORIC_HEAD)):
        got = subprocess.run(['git', '-C', str(root), *args], capture_output=True,
                             text=True, timeout=12, check=True).stdout.strip()
        if got != expect:
            stop('HISTORIC_CHECKOUT_MISMATCH_' + got)


def identify_cas(user_path, key, locations):
    if user_path:
        candidate = Path(user_path)
        if not candidate.is_file() or candidate.stat().st_size != PDF_LENGTHS[key]:
            stop(key.upper() + '_PATH_OR_LENGTH_DIVERGENT')
        pinned_bytes(candidate.read_bytes(), key)
        return candidate.resolve()
    # Only enumerate small, specific directories (not protected databases).
    for root in locations:
        if not root.is_dir():
            continue
        matches = []
        try:
            for path in root.rglob('*'):
                if not path.is_file() or path.is_symlink():
                    continue
                if path.stat().st_size == PDF_LENGTHS[key]:
                    matches.append(path)
                if len(matches) >= 120:
                    break
        except (OSError, PermissionError):
            pass
        for candidate in matches:
            try:
                if sha(candidate.read_bytes()) == PINS[key]:
                    return candidate.resolve()
            except (OSError, PermissionError):
                continue
    stop(key.upper() + '_ORIGINAL_C3_PDF_NOT_FOUND_PASS_EXACT_PATH')


def materialize_focal(tmp, zip_path, patch_path):
    pinned_bytes(zip_path.read_bytes(), 'archive')
    pinned_bytes(patch_path.read_bytes(), 'patch')
    with zipfile.ZipFile(zip_path) as z:
        if z.testzip() is not None:
            stop('ARCHIVE_ZIP_CORRUPT')
        for name in (V7, BASE_SOURCE):
            if name not in z.namelist():
                stop('ARCHIVE_MEMBER_MISSING_' + name)
        base_ps = z.read(V7)
        src = z.read(BASE_SOURCE)
    pinned_bytes(base_ps, 'v7')
    pinned_bytes(src, 'v3')
    (tmp / BASE_SOURCE).write_bytes(src)
    patch_result = subprocess.run(['git', '-C', str(tmp), 'apply', str(patch_path)],
                                  capture_output=True, text=True, timeout=30)
    if patch_result.returncode:
        stop('PATCH_APPLY_' + patch_result.stderr[-220:])
    changed = (tmp / BASE_SOURCE).read_bytes().replace(b'\r\n', b'\n')
    pinned_bytes(changed, 'v4')
    (tmp / CANDIDATE).write_bytes(changed)
    # The immutable V7 diagnostic generates a V3 candidate from the REAL
    # RunnerDir source. Inject only an exact SHA-checked V4 copy OVER its own
    # disposable runtime copy, never into RunnerDir or any protected worktree.
    marker = "  Write-Host ('  Candidato de entrega gravado em  : ' + $candPath)\n"
    script = base_ps.decode('utf-8-sig').replace('\r\n', '\n')
    if script.count(marker) != 1:
        stop('V7_RUNTIME_HOOK_NOT_UNIQUE')
    insertion = '''  # A2 V4 focal physical delta: replace ONLY the disposable execution copy.
  $v4Path = Join-Path $PSScriptRoot 'B02_RCV31_R3_CONCRETE_PATH_DELTA4_V4_A2_SNAPSHOT_CANDIDATO.py'
  $originalV3 = (Get-FileHash -LiteralPath $candPath -Algorithm SHA256).Hash.ToLower()
  if ($originalV3 -ne '1fae5b1aefe9630e077eae9c98b44c91d4f9dd99f9e4560a6dab83b74e5e7779') {
    throw ('STOP_A2_V3_RUNTIME_LINEAGE_DIVERGENT: ' + $originalV3)
  }
  $v4Hash = (Get-FileHash -LiteralPath $v4Path -Algorithm SHA256).Hash.ToLower()
  if ($v4Hash -ne '2fd9c8b9fdae373ec7622971a6d5efdca0f3d18f5082769065f7cd1f0e6bda11') {
    throw ('STOP_A2_V4_CANDIDATE_DIVERGENT: ' + $v4Hash)
  }
  Copy-Item -LiteralPath $v4Path -Destination $cpPath -Force
  $actual = (Get-FileHash -LiteralPath $cpPath -Algorithm SHA256).Hash.ToLower()
  if ($actual -ne $v4Hash) { throw 'STOP_A2_V4_DISPOSABLE_EXECUTION_COPY_DIVERGENT' }
  Write-Host ('  A2 V4 exact source snapshot active on disposable copy: ' + $actual)
'''
    built = script.replace(marker, marker + insertion)
    # V7's original lineage referred to the now-obsolete work/fiscal HEAD.
    # Retarget ONLY a disposable diagnostic copy, never RunnerDir or user Git.
    legacy_copy = "Copy-Item -LiteralPath $baseRunner -Destination (Join-Path $DiagDir '_BASE_RUNNER_REFERENCE.py') -Force\n"
    if built.count(legacy_copy) != 1:
        stop('V7_BASE_RUNNER_COPY_ANCHOR_MISSING')
    lineage_patch = '''  # A2 focal: exact 2026-10-30 historical worktree, already pinned by
  # the wrapper. Change only BRANCH/HEAD in the disposable diagnostic copy.
  $refCopy = Join-Path $DiagDir '_BASE_RUNNER_REFERENCE.py'
  $refText = [System.IO.File]::ReadAllText($refCopy)
  $oldLineage = "BRANCH='work/fiscal-assumptions-c0'; HEAD='b45ef5396189f5b6be1156535c9af9b19cca17b4'"
  $newLineage = "BRANCH='candidate/g5-successor-window-prep'; HEAD='56d8b23c8af5f8a9b7fdf1eb8fb01a9f008dc9f8'"
  if ([regex]::Matches($refText, [regex]::Escape($oldLineage)).Count -ne 1) {
    throw 'STOP_A2_HISTORICAL_REFERENCE_LINEAGE_NOT_EXACT'
  }
  $refText = $refText.Replace($oldLineage, $newLineage)
  [System.IO.File]::WriteAllText($refCopy, $refText, [System.Text.UTF8Encoding]::new($false))
  Write-Host 'A2: lineage original preservada; copia descartavel vinculada a 56d8b23c.'
'''
    built = built.replace(legacy_copy, legacy_copy + lineage_patch)
    if built.count('A2: lineage original preservada; copia descartavel') != 1:
        stop('V7_BASE_REFERENCE_PATCH_FAILED')
    if built.count('A2 V4 exact source snapshot active on disposable copy') != 1:
        stop('PATCHED_V7_MARKER_DIVERGENT')
    out = tmp / 'B02_RCV31_R3_A2_V4_POSITIVO_SOMENTE_DESCARTAVEL.ps1'
    out.write_bytes(b'\xef\xbb\xbf' + built.encode('utf-8'))
    return out


def run(args):
    if os.name != 'nt' or os.environ.get('OS') != 'Windows_NT':
        stop('WINDOWS_IS_REQUIRED')
    runner_dir = Path(args.runner_dir)
    history = Path(args.history)
    if not runner_dir.is_dir() or not history.is_dir():
        stop('RUNNERDIR_OR_HISTORIC_WORKTREE_NOT_FOUND')
    real_concrete = runner_dir / 'B02_RCV31_R3_CONCRETE_PATH.py'
    real_obs = runner_dir / ORIGINAL_OBSERVER
    if not real_concrete.is_file() or not real_obs.is_file():
        stop('R3_ORIGINAL_SOURCES_MISSING')
    pinned_bytes(real_concrete.read_bytes(), 'concrete_original')
    pinned_bytes(real_obs.read_bytes(), 'observer_original')
    git_checkout_verification(history)
    # These historical hard-coded source pins are checked against the new
    # frozen HEAD before a Docker container is launched. STOP on any delta.
    source_pins = {
        'g19': 'app/services/enterprise_g19_local_cas_custody.py',
        'migration0062': 'migrations/versions/0062_adr020_noncredential_acquisition.py',
        'migration0063': 'migrations/versions/0063_adr020_policy_activation_atomicity.py',
    }
    for key, relative in source_pins.items():
        target = history / relative
        if not target.is_file():
            stop('FROZEN_WORKTREE_SOURCE_MISSING_' + key)
        pinned_bytes(target.read_bytes(), key)
    folders = [runner_dir, Path.home() / 'Downloads',
               Path(os.environ['LOCALAPPDATA']) / 'SOLVERIS' / 'C3']
    pdf1245 = identify_cas(args.cas1245, 'cas1245', folders)
    pdf571 = identify_cas(args.cas571, 'cas571', folders)
    with tempfile.TemporaryDirectory(prefix='B02_RCV31_A2_V4_DISPOSABLE_') as d:
        tmp = Path(d)
        ps = materialize_focal(tmp, Path(args.archive).resolve(),
                               BASE / PATCH)
        summary = {'status': 'A2_V4_PHYSICAL_PREFLIGHT_PASS',
                   'branch': HISTORIC_BRANCH, 'head': HISTORIC_HEAD,
                   'source': PINS['v4'], 'observer': PINS['observer_original'],
                   'cas1245': PINS['cas1245'], 'cas571': PINS['cas571'],
                   'protected_writes': 0, 'physical_test': 'NOT_RUN'}
        print(json.dumps(summary, sort_keys=True), flush=True)
        if not args.execute:
            return
        proc = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                               '-File', str(ps), '-RunnerDir', str(runner_dir),
                               '-Cas1245', str(pdf1245), '-Cas571', str(pdf571),
                               '-ApplyFix', '-ApplyDelta4', '-Scenario', 'positive'],
                              capture_output=True, text=True, timeout=1800,
                              errors='replace')
        # Old diagnostic can return code 0 on internal STOP. Verify actual JSON.
        lines = proc.stdout.splitlines()
        for line in lines[-22:]:
            if 'POSTGRES_PASSWORD' not in line and 'DATABASE_URL' not in line:
                print(line[-300:])
        for line in proc.stderr.splitlines()[-8:]:
            if 'PASSWORD' not in line:
                print('STDERR ' + line[-260:], file=sys.stderr)
        if proc.returncode != 0:
            stop('V7_DIAGNOSTIC_EXIT_' + str(proc.returncode))
        reports = [ln.strip().split('REPORT=', 1)[-1] for ln in lines if 'REPORT=' in ln]
        if not reports or not Path(reports[-1]).is_file():
            stop('V7_RESULT_REPORT_NOT_FOUND')
        report = json.loads(Path(reports[-1]).read_text(encoding='utf-8-sig'))
        if (report.get('status') != 'PASS_DIAGNOSTIC_POSITIVE'
                or report.get('result_status') != 'PASS_CONCRETE_STAGE_AND_SEPARATE_READ_ONLY_PROCESS'
                or report.get('cleanup') != 'REMOVED'):
            stop('V7_FOCAL_RESULT_NOT_PASS_' + str(report.get('status')))
        if 'A2 V4 exact source snapshot active on disposable copy' not in proc.stdout:
            stop('A2_V4_NOT_APPLIED_TO_DISPOSABLE_RUN')
        print(json.dumps({'status': 'RCV31_A2_V4_DISPOSABLE_PG17_FOCAL_POSITIVE_PASS',
                          'candidate': PINS['v4'], 'report': reports[-1],
                          'cleanup': report['cleanup'], 'protected_writes': 0,
                          'institutional_audit': 'NOT_INFERRED'}, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', default=str(Path.home() / 'Downloads' / HISTORIC_ARCHIVE))
    parser.add_argument('--runner-dir', default=str(Path(os.environ.get('LOCALAPPDATA', '')) / 'SOLVERIS' / 'B02_RCV31_R3_BOOTSTRAP_CORRIGIDO'))
    parser.add_argument('--history', default=r'C:\dev\saas-fiscal-demo-a1')
    parser.add_argument('--cas1245', default=None)
    parser.add_argument('--cas571', default=None)
    parser.add_argument('--execute', action='store_true', help='Explicitly execute one disposable positive scenario')
    a = parser.parse_args()
    try:
        run(a)
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError, zipfile.BadZipFile) as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)
