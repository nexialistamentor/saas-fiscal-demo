"""Local B02/G5 transport to the existing, isolated PostgreSQL test container.

Adaptation of the tested G4 loopback transport. No credentials, changed pg_hba,
role grants, SQL, migrations or signing. The target runner still enforces
institutional gates, transaction boundaries and independent reconciliation.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
BRANCH = 'candidate/g5-v5-publicacao-local'
CONTAINER = 'solveris-pg17-migration-test'
VOLUME_PREFIX = '4fe15764d8f4c6c2b5aaaad634c0ed54ec'
DATABASE = 'solveris_b02_r4g_test'
ROLE = 'solveris_b02_policy_writer'
ALLOWED = {
    'tools/b02_g5_v5_policy_runner.py',
    'tools/b02_g5_v5_atomic_transaction_harness.py',
    'tools/b02_g5_v5_physical_readonly_preflight.py',
    'tools/b02_g5_v5_institutional_owner_rollback_probe.py',
    'tools/b02_g5_v5_submission_runner.py',
}


def command(*args, timeout=25):
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError('STOP_COMMAND_FAILED_' + Path(args[0]).name + ':' + result.stderr[-500:])
    return result.stdout.strip()


def validate_checkout(script):
    if script not in ALLOWED:
        raise RuntimeError('STOP_TARGET_NOT_ALLOWLISTED')
    if command('git', 'branch', '--show-current') != BRANCH:
        raise RuntimeError('STOP_BRANCH_MISMATCH')
    local = command('git', 'rev-parse', 'HEAD')
    tracked = command('git', 'rev-parse', 'origin/' + BRANCH)
    published = command('git', 'ls-remote', '--heads', 'origin', BRANCH).split()
    if len(published) != 2 or published[1] != 'refs/heads/' + BRANCH:
        raise RuntimeError('STOP_REMOTE_REF_NOT_CONFIRMED')
    if local != tracked or local != published[0]:
        raise RuntimeError('STOP_HEAD_NOT_RECONCILED_FF_ONLY')
    if command('git', 'status', '--porcelain', '--untracked-files=no'):
        raise RuntimeError('STOP_TRACKED_FILES_MODIFIED_PRESERVE_WORKTREE')
    if not (ROOT / script).is_file():
        raise RuntimeError('STOP_SCRIPT_MISSING')


def container_info():
    result = json.loads(command('docker', 'inspect', CONTAINER))
    if len(result) != 1:
        raise RuntimeError('STOP_CONTAINER_NOT_UNIQUE')
    info = result[0]
    mounted = [m for m in info.get('Mounts', []) if m.get('Type') == 'volume' and
               m.get('Name', '').startswith(VOLUME_PREFIX)]
    if len(mounted) != 1:
        raise RuntimeError('STOP_PROTECTED_VOLUME_NOT_VERIFIED')
    return info


def ready_within(seconds=20):
    deadline = time.monotonic() + seconds
    while True:
        p = subprocess.run(['docker', 'exec', CONTAINER, 'pg_isready', '-q',
                            '-h', '127.0.0.1', '-p', '5432', '-U', ROLE,
                            '-d', DATABASE], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=5)
        if p.returncode == 0:
            return
        if time.monotonic() >= deadline:
            raise RuntimeError('STOP_POSTGRES_NOT_READY')
        time.sleep(0.4)


def no_other_clients():
    count = command('docker', 'exec', CONTAINER, 'psql', '-X', '-q', '-At', '-w',
                    '-U', ROLE, '-d', DATABASE, '-c',
                    "SELECT count(*) FROM pg_stat_activity WHERE backend_type='client backend' AND pid<>pg_backend_pid()")
    if not count.isdigit():
        raise RuntimeError('STOP_CLIENT_COUNT_UNVERIFIED')
    return int(count) == 0


@contextmanager
def managed_container():
    originally_running = bool(container_info()['State']['Running'])
    started = False
    if not originally_running:
        command('docker', 'start', CONTAINER)
        started = True
    try:
        ready_within()
        yield
    finally:
        if started:
            if no_other_clients():
                command('docker', 'stop', CONTAINER, timeout=35)
            else:
                print('CONTAINER_PRESERVED_RUNNING_ACTIVE_CLIENTS', file=sys.stderr)


@contextmanager
def loopback_transport():
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(('127.0.0.1', 0))
    listener.listen(8)
    listener.settimeout(0.5)
    stopping = threading.Event()
    workers = []
    clients = []
    processes = []

    def forward(client):
        proc = None
        try:
            proc = subprocess.Popen(
                ['docker', 'exec', '-i', '--user', 'postgres', CONTAINER,
                 'bash', '-c',
                 'exec 3<>/dev/tcp/127.0.0.1/5432; cat <&3 & cat >&3; wait'],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, bufsize=0)
            processes.append(proc)

            def upstream():
                try:
                    while True:
                        packet = client.recv(65536)
                        if not packet:
                            break
                        view = memoryview(packet)
                        while view:
                            sent = proc.stdin.write(view)
                            if not sent:
                                return
                            view = view[sent:]
                except (OSError, ValueError, BrokenPipeError):
                    pass
                finally:
                    try: proc.stdin.close()
                    except (OSError, ValueError): pass

            def downstream():
                try:
                    while True:
                        packet = os.read(proc.stdout.fileno(), 65536)
                        if not packet:
                            break
                        client.sendall(packet)
                except OSError:
                    pass
                finally:
                    try: client.shutdown(socket.SHUT_WR)
                    except OSError: pass

            up = threading.Thread(target=upstream, daemon=True)
            down = threading.Thread(target=downstream, daemon=True)
            up.start()
            down.start()
            proc.wait()
            up.join(timeout=2)
            down.join(timeout=2)
        finally:
            try: client.close()
            except OSError: pass
            if proc is not None and proc.poll() is None:
                proc.terminate()

    def serve():
        while not stopping.is_set():
            try:
                client, peer = listener.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            if peer[0] != '127.0.0.1':
                client.close()
                continue
            clients.append(client)
            worker = threading.Thread(target=forward, args=(client,), daemon=True)
            workers.append(worker)
            worker.start()

    server = threading.Thread(target=serve, daemon=True)
    server.start()
    try:
        yield listener.getsockname()[1]
    finally:
        stopping.set()
        listener.close()
        for client in clients:
            try: client.close()
            except OSError: pass
        for proc in processes:
            if proc.poll() is None:
                proc.terminate()
        server.join(timeout=2)
        for worker in workers:
            worker.join(timeout=2)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Run an allowlisted G5 runner over the pre-existing isolated loopback bridge')
    parser.add_argument('target', choices=sorted(ALLOWED))
    parser.add_argument('runner_args', nargs=argparse.REMAINDER)
    opts = parser.parse_args(argv)
    args = opts.runner_args
    if args and args[0] == '--':
        args = args[1:]
    validate_checkout(opts.target)
    with managed_container():
        with loopback_transport() as port:
            env = os.environ.copy()
            env['SOLVERIS_B02_POLICY_WRITER_DSN'] = (
                f'postgresql+psycopg2://{ROLE}@127.0.0.1:{port}/{DATABASE}'
                '?sslmode=disable&connect_timeout=8')
            env['DATABASE_URL'] = env['SOLVERIS_B02_POLICY_WRITER_DSN']
            # A non-zero exit is a hard STOP. Never retry an uncertain COMMIT.
            result = subprocess.run([sys.executable, '-u', str(ROOT / opts.target), *args],
                                    cwd=ROOT, env=env, timeout=180)
            if result.returncode:
                raise RuntimeError(f'STOP_RUNNER_EXIT_{result.returncode}_NO_AUTOMATIC_RETRY')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
