"""B02 G4 October candidate preflight: read-only, approved localhost bridge, no new authorization inferred.

Reuses the already versioned G4 runner transport. Does not execute G4 or G5,
create credentials, install a migration, or persist operational authority.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent.parent
BRANCH="candidate/g5-successor-window-prep"
CANDIDATE="executar_ativacao_g4_antecipada_CANDIDATO.py"
ORIGINAL="executar_ativacao_g4_real.py"
PROPOSAL="PROPOSTA_G4_JANELA_IMEDIATA_20261029.json"
BLOB="646caf5f62c3520ab965077d2218ba9b4da38437"
ORIGINAL_BLOB="1729e6d62c77510ef4dd7db0af56a6cbe985c168"
NEW_START="2026-10-29T13:00:00+00:00"
NEW_END="2026-10-30T13:00:00+00:00"

PREP_READ_ONLY = r'''
import argparse, hashlib, json, os, subprocess
source=subprocess.check_output(["git","show","HEAD:executar_ativacao_g4_antecipada_CANDIDATO.py"])
blob=hashlib.sha1(b"blob "+str(len(source)).encode()+b"\0"+source).hexdigest()
if blob!="646caf5f62c3520ab965077d2218ba9b4da38437":
    raise RuntimeError("STOP_CANDIDATE_BLOB_DIFFERENT")
ns={"__name__":"__b02_g4_candidate_read_only__","__file__":"executar_ativacao_g4_antecipada_CANDIDATO.py"}
exec(compile(source,"executar_ativacao_g4_antecipada_CANDIDATO.py","exec"),ns)
ns["run"](argparse.Namespace(execute=False,approval_reference=None))
'''.encode("utf-8")

def main():
    if len(sys.argv)!=1:
        raise RuntimeError("STOP_UNEXPECTED_ARGS")
    if str(ROOT) not in sys.path:
        sys.path.insert(0,str(ROOT))
    spec=importlib.util.spec_from_file_location(
        "b02_october_preflight_bridge",ROOT/"tools"/"b02_g4_authorized_runner.py")
    if not spec or not spec.loader:
        raise RuntimeError("STOP_APPROVED_BRIDGE_MISSING")
    old=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    if old.git("branch","--show-current")!=BRANCH:
        raise RuntimeError("STOP_WRONG_BRANCH")
    if old.git("rev-parse","HEAD")!=old.git("rev-parse","origin/"+BRANCH):
        raise RuntimeError("STOP_HEAD_NOT_SYNCED")
    old.assert_repo_and_approval()
    source=old.git("show","HEAD:"+CANDIDATE,binary=True)
    sha=hashlib.sha1(b"blob "+str(len(source)).encode()+b"\0"+source).hexdigest()
    if sha!=BLOB:
        raise RuntimeError("STOP_OCTOBER_BLOB_MISMATCH")
    compile(source,CANDIDATE,"exec")
    proposal=json.loads(old.git("show","HEAD:"+PROPOSAL,binary=True))
    if (proposal["candidate_git_blob"]!=BLOB
       or proposal["predecessor_git_blob"]!=ORIGINAL_BLOB
       or proposal["status"]!="PROPOSTA_NAO_AUTORIZADA_NAO_EXECUTADA"
       or proposal["window"]!={"from":NEW_START,"until":NEW_END}
       or proposal["authorization_required_reference"]!="B02-G4-AUTH-MIGUEL-20261029-02"):
        raise RuntimeError("STOP_PROPOSAL_SCOPE_MISMATCH")
    for path in ("migrations/candidates/0064_b02_g5_controlled_real_cas_CANDIDATE.py",
                 "migrations/candidates/0065_b02_g5_one_shot_real_CANDIDATE.py"):
        compile(old.git("show","HEAD:"+path,binary=True),path,"exec")
    print("B02_G5_ISOLATED_CANDIDATES_SYNTAX_PASS")
    print("G4_OCTOBER_CANDIDATE_BLOB|"+BLOB)
    print("G4_OCTOBER_WINDOW|"+NEW_START+"|"+NEW_END)

    was_running=old.check_container()
    started=False
    try:
        if not was_running:
            old.docker("start",old.CONTAINER)
            started=True
        rc,output=old.execute_exact_bridge(PREP_READ_ONLY)
        print("G4_OCTOBER_READ_ONLY_EXIT|"+str(rc))
        if rc!=0:
            raise RuntimeError("STOP_G4_OCTOBER_PREFLIGHT_FAILED")
        if "EXISTING_UNIT_RECONCILED" in output:
            print("G4_OCTOBER_ALREADY_RECONCILED_NO_WRITES")
        elif "DRY_RUN_DB_READ_ONLY_PASS" in output:
            print("G4_OCTOBER_READY_FOR_DISTINCT_APPROVAL_NO_WRITES")
        else:
            raise RuntimeError("STOP_G4_OCTOBER_NO_ACCEPTABLE_PREFLIGHT_RESULT")
    finally:
        if started:
            try:
                if old.other_clients()==0:
                    old.docker("stop",old.CONTAINER)
                    print("CONTAINER|RESTORED_STOPPED")
                else:
                    print("CONTAINER|PRESERVED_RUNNING_ACTIVE_CLIENTS")
            except Exception:
                print("CONTAINER|PRESERVED_RUNNING_CHECK_UNCERTAIN")

if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        print("STOP|"+str(exc) if isinstance(exc,RuntimeError)
              else "STOP|"+type(exc).__name__,file=sys.stderr)
        sys.exit(2)
