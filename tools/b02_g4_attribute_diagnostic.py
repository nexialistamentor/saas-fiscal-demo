"""Isolate the G4 write-only AttributeError without any application writes.

Reuses the exact, previously approved Windows->127.0.0.1->docker exec->Postgres
loopback transport. Each diagnostic session is forced read-only by libpq options
and checked at connection creation; abort before any SQL if read-only is not on.
Never execute this diagnostic as an alternative G4 activation.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent.parent
RUNNER=ROOT/"tools"/"b02_g4_authorized_runner.py"
BRANCH="candidate/g5-successor-window-prep"

READ_ONLY_WRITE_PATH_DIAG=r'''
import argparse
import hashlib
import os
import subprocess
import sys
import traceback

APPROVED="1729e6d62c77510ef4dd7db0af56a6cbe985c168"
source=subprocess.check_output(["git","show","HEAD:executar_ativacao_g4_real.py"])
blob=hashlib.sha1(b"blob "+str(len(source)).encode()+b"\0"+source).hexdigest()
if blob!=APPROVED:
    raise RuntimeError("DIAG_STOP_APPROVED_BLOB_MISMATCH")

def report(exc):
    print("DIAG_EXCEPTION|"+type(exc).__name__)
    # No SQL statement, parameters, DSN or traceback source line is printed.
    orig=getattr(exc,"orig",exc)
    print("DIAG_SQLSTATE|"+str(getattr(orig,"pgcode",None) or "none"))
    pgdiag=getattr(orig,"diag",None)
    if pgdiag is not None:
        for key in ("constraint_name","function_name","source_function"):
            value=getattr(pgdiag,key,None)
            if value and isinstance(value,str) and len(value)<120:
                print("DIAG_PG_"+key.upper()+"|"+value)
        msg=getattr(pgdiag,"message_primary",None)
        if isinstance(msg,str) and msg.startswith("B02") and len(msg)<180:
            print("DIAG_B02_SERVER_CODE|"+msg.replace("\n"," "))
    tb=traceback.extract_tb(exc.__traceback__)
    for frame in tb[-12:]:
        name=frame.filename.replace("\\","/").rsplit("/",1)[-1]
        if name not in ("__init__.py",):
            print("DIAG_FRAME|"+name+"|"+str(frame.lineno)+"|"+frame.name)

try:
    # Import the real service and metadata without creating any SQL connection.
    import sqlalchemy
    from sqlalchemy import event
    from sqlalchemy.pool import NullPool
    from app.services.enterprise_b02_policy_activation_atomicity import stage_policy_activation
    from app.models_policy_activation_atomicity import PolicyActivationGeneration,PolicyActivationOutboxEvent
    print("DIAG_IMPORTS_PASS")
except Exception as exc:
    report(exc)
    raise SystemExit(0)

real_create_engine=sqlalchemy.create_engine

def read_only_engine(url,*args,**kwargs):
    # libpq startup option applies before any application SQL. Preserve the
    # same ephemeral host/port and identity from the approved bridge.
    sep="&" if "?" in url else "?"
    url=url+sep+"options=-c%20default_transaction_read_only%3Don"
    opts=dict(kwargs)
    opts.pop("poolclass",None)
    engine=real_create_engine(url,*args,poolclass=NullPool,**opts)

    @event.listens_for(engine,"connect")
    def check_read_only(dbapi_conn,conn_record):
        with dbapi_conn.cursor() as cursor:
            cursor.execute("SHOW default_transaction_read_only")
            if cursor.fetchone()[0]!="on":
                raise RuntimeError("DIAG_STOP_READ_ONLY_NOT_ENFORCED")
    return engine

sqlalchemy.create_engine=read_only_engine

ns={"__name__":"__g4_diagnostic_only__",
    "__file__":"executar_ativacao_g4_real.py"}
exec(compile(source,"executar_ativacao_g4_real.py","exec"),ns)
try:
    ns["run"](argparse.Namespace(
        execute=True,
        approval_reference="B02-G4-AUTH-MIGUEL-20261029-01"))
    print("DIAG_STOP_UNEXPECTED_SUCCESS_IN_READ_ONLY_MODE")
except BaseException as exc:
    report(exc)
finally:
    sqlalchemy.create_engine=real_create_engine
'''.encode("utf-8")


def main():
    if len(sys.argv)!=1:
        raise RuntimeError("DIAG_STOP_UNEXPECTED_ARGS")
    sys.path.insert(0,str(ROOT))
    spec=importlib.util.spec_from_file_location("b02_g4_runner_for_diag",RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("DIAG_STOP_RUNNER_UNAVAILABLE")
    runner=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    if runner.git("branch","--show-current")!=BRANCH:
        raise RuntimeError("DIAG_STOP_WRONG_BRANCH")
    if runner.git("rev-parse","HEAD")!=runner.git("rev-parse","origin/"+BRANCH):
        raise RuntimeError("DIAG_STOP_HEAD_NOT_SYNCED")
    runner.assert_repo_and_approval()
    initially_running=runner.check_container()
    started=False
    try:
        if not initially_running:
            runner.docker("start",runner.CONTAINER)
            started=True
        status,_=runner.execute_exact_bridge(READ_ONLY_WRITE_PATH_DIAG)
        print("DIAG_PYTHON_EXIT|"+str(status))
    finally:
        if started:
            try:
                if runner.other_clients()==0:
                    runner.docker("stop",runner.CONTAINER)
                    print("CONTAINER|RESTORED_STOPPED")
                else:
                    print("CONTAINER|PRESERVED_RUNNING_ACTIVE_CLIENTS")
            except Exception:
                print("CONTAINER|PRESERVED_RUNNING_CHECK_UNCERTAIN")


if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        print("DIAG_STOP|"+type(exc).__name__,file=sys.stderr)
        sys.exit(2)
