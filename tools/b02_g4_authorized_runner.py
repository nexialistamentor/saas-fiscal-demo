"""B02 G4: approved blob via the same Windows localhost -> docker exec -> PostgreSQL loopback bridge.
The G4 operation is already institutionally authorized. Never retry an uncertain COMMIT.
No password files, grants, migrations or G5 execution.
"""
from __future__ import annotations
import difflib
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading

REPO=Path(__file__).resolve().parent.parent
CONTAINER="solveris-pg17-migration-test"
VOLUME="4fe15764d8f4c6c2b5aaaad634c0ed54ec42200f1a35edcc3e693da153a0410d"
BRANCH="candidate/g5-successor-window-prep"
APPROVAL="B02-G4-AUTH-MIGUEL-20261029-01"
APPROVED_BLOB="1729e6d62c77510ef4dd7db0af56a6cbe985c168"
G5_V3_SHA256="8b3b0cc0a880156b5659166b6878de580b1ddafcf245d811545a0f1ba60500d4"
SCRIPT="executar_ativacao_g4_real.py"
AUTH="AUTORIZACAO_G4_MIGUEL_20261029.json"
V3="POLICY_G5_CANDIDATO_V3_COMPLETO.json"
PRIMARY="B02_G4_RESULTADO_RECONCILIADO_20261029.json"
G5_CANDIDATE="POLICY_G5_CANDIDATO_SUCESSOR_G4_PARA_REVISAO.json"
DSN_ENV="SOLVERIS_B02_POLICY_WRITER_DSN"

def git(*args,binary=False):
    p=subprocess.run(["git",*args],cwd=REPO,stdout=subprocess.PIPE,
                     stderr=subprocess.DEVNULL,check=True)
    return p.stdout if binary else p.stdout.decode("utf-8").strip()

def stop(code):
    raise RuntimeError(code)

def assert_repo_and_approval():
    if git("branch","--show-current")!=BRANCH:
        stop("STOP_BRANCH_MISMATCH")
    if git("rev-parse","HEAD")!=git("rev-parse","origin/"+BRANCH):
        stop("STOP_LOCAL_REMOTE_HEAD_MISMATCH_USE_FF_ONLY")
    source=git("show","HEAD:"+SCRIPT,binary=True)
    blob=hashlib.sha1(b"blob "+str(len(source)).encode()+b"\0"+source).hexdigest()
    if blob!=APPROVED_BLOB:
        stop("STOP_APPROVED_PROCEDURE_BLOB_MISMATCH")
    auth=json.loads(git("show","HEAD:"+AUTH,binary=True))
    obj=auth["objeto_autorizado"]
    if (auth["reference"]!=APPROVAL or obj["blob_sha"]!=APPROVED_BLOB
        or obj["procedimento"]!=SCRIPT
        or obj["database"]!="solveris_b02_r4g_test"
        or obj["writer"]!="solveris_b02_policy_writer"
        or obj["policy_hash"]!="05ede0f8c8788b93d41e451288efd88d91614a560bdd2191a115f0d736c4fe2a"
        or obj["ids"]!={"execution":"B02-05ede-execution-v2",
                          "activation":"B02-05ede-activation-v2",
                          "generation":"B02-05ede-generation-v2",
                          "outbox":"B02-05ede-outbox-v2"}
        or obj["window"]!={"from":"2026-11-03T12:00:00+00:00",
                            "until":"2026-11-04T07:56:30.910737+00:00"}):
        stop("STOP_AUTHORIZATION_SCOPE_MISMATCH")
    if auth["status"]!="AUTORIZADO_AGUARDA_EXECUCAO":
        stop("STOP_AUTHORIZATION_STATUS_MISMATCH")
    for path in ("app/models.py","app/models_policy_activation_atomicity.py",
                 "app/services/enterprise_b02_policy_activation_atomicity.py",
                 "app/services/enterprise_b02_noncredential_acquisition.py"):
        expected=git("rev-parse","HEAD:"+path)
        local=REPO/path
        if not local.is_file() or git("hash-object",str(local))!=expected:
            stop("STOP_TRACKED_SERVICE_BYTES_DIVERGENT")
    if hashlib.sha256((REPO/V3).read_bytes()).hexdigest()!=G5_V3_SHA256:
        stop("STOP_G5_V3_BYTES_DIVERGENT")
    return source

def docker(*args):
    return subprocess.run(["docker",*args],stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL,check=True)

def check_container():
    i=json.loads(docker("inspect",CONTAINER).stdout)[0]
    if not any(m.get("Type")=="volume" and m.get("Name")==VOLUME
               for m in i.get("Mounts",[])):
        stop("STOP_PROTECTED_VOLUME_MISMATCH")
    return bool(i["State"]["Running"])

def other_clients():
    sql=("SELECT count(*) FROM pg_stat_activity "
         "WHERE backend_type='client backend' AND pid<>pg_backend_pid()")
    out=docker("exec","--user","postgres",CONTAINER,"psql","-X","-q",
        "-At","-w","-U","solveris_test","-d","solveris_b02_r4g_test",
        "-c",sql).stdout.decode("utf-8").strip()
    return int(out)

class Tee(io.TextIOBase):
    def __init__(self):
        self.lines=[]
    def write(self,s):
        sys.__stdout__.write(s)
        self.lines.append(s)
        return len(s)
    def flush(self):
        sys.__stdout__.flush()

def execute_exact_bridge(source):
    """Proven preflight transport: Windows listener -> docker exec -> /dev/tcp internal."""
    server=socket.socket()
    server.bind(("127.0.0.1",0))
    server.listen(1)
    server.settimeout(20)
    port=server.getsockname()[1]
    state={}

    def bridge():
        try:
            client,_=server.accept()
            state["client"]=client
            proc=subprocess.Popen(
                ["docker","exec","-i","--user","postgres",
                 "solveris-pg17-migration-test","bash","-c",
                 "exec 3<>/dev/tcp/127.0.0.1/5432; cat <&3 & cat >&3; wait"],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,bufsize=0)
            state["proc"]=proc

            def upstream():
                try:
                    while True:
                        data=client.recv(65536)
                        if not data: break
                        view=memoryview(data)
                        while view:
                            n=proc.stdin.write(view)
                            if not n: return
                            view=view[n:]
                except (OSError,ValueError):
                    pass
                finally:
                    try: proc.stdin.close()
                    except OSError: pass

            def downstream():
                try:
                    while True:
                        data=os.read(proc.stdout.fileno(),65536)
                        if not data: break
                        client.sendall(data)
                except OSError:
                    pass
                finally:
                    try: client.shutdown(socket.SHUT_WR)
                    except OSError: pass

            threading.Thread(target=upstream,daemon=True).start()
            threading.Thread(target=downstream,daemon=True).start()
            proc.wait()
        except (OSError,TimeoutError):
            pass

    thread=threading.Thread(target=bridge,daemon=True)
    thread.start()
    old_argv=sys.argv
    old_stdout=sys.stdout
    captured=Tee()
    os.environ[DSN_ENV]=(
        f"postgresql+psycopg2://solveris_b02_policy_writer"
        f"@127.0.0.1:{port}/solveris_b02_r4g_test"
        "?sslmode=disable&connect_timeout=8")
    sys.argv=[SCRIPT,"--execute","--approval-reference",APPROVAL]
    status=None
    try:
        sys.stdout=captured
        try:
            exec(compile(source,SCRIPT,"exec"),
                 {"__name__":"__main__","__file__":SCRIPT})
            status=0
        except SystemExit as exc:
            status=int(exc.code or 0)
    finally:
        sys.stdout=old_stdout
        sys.argv=old_argv
        os.environ.pop(DSN_ENV,None)
        server.close()
        if "client" in state:
            state["client"].close()
        if "proc" in state and state["proc"].poll() is None:
            state["proc"].terminate()
        thread.join(timeout=3)
    return status,"".join(captured.lines)

def safe_save(path,content):
    if path.exists():
        if path.read_bytes()!=content:
            stop("STOP_EXISTING_RESULT_ARTIFACT_CONFLICT")
        return
    with path.open("xb") as f:
        f.write(content)

def persist_success(stdout):
    docs=[]
    for line in stdout.splitlines():
        if line.startswith("{"):
            try:
                data=json.loads(line)
                if isinstance(data,dict): docs.append(data)
            except ValueError:
                pass
    result=next((x for x in docs
                 if x.get("status")=="FOUR_RECORDS_RECONCILED"),None)
    if result is None:
        stop("STOP_NO_FOUR_RECORDS_RECONCILED")
    exact={"execution_id":"B02-05ede-execution-v2",
           "activation_id":"B02-05ede-activation-v2",
           "generation_id":"B02-05ede-generation-v2",
           "outbox_id":"B02-05ede-outbox-v2"}
    for key,value in exact.items():
        if result.get(key)!=value: stop("STOP_RESULT_ID_MISMATCH")
    for key in ("execution_hash","activation_hash","generation_hash",
                "outbox_hash","outbox_payload_hash","scope_hash","policy_hash"):
        value=result.get(key)
        if (not isinstance(value,str) or len(value)!=64
            or any(ch not in "0123456789abcdef" for ch in value)):
            stop("STOP_RESULT_HASH_INVALID")
    if result["policy_hash"]!="05ede0f8c8788b93d41e451288efd88d91614a560bdd2191a115f0d736c4fe2a":
        stop("STOP_RESULT_POLICY_MISMATCH")
    primary={"schema":"SOLVERIS_B02_G4_RECONCILED_EXECUTION_V1",
             "approval_reference":APPROVAL,
             "approved_procedure_blob":APPROVED_BLOB,
             "branch":BRANCH,"commit":git("rev-parse","HEAD"),
             "transport":"Windows Python -> ephemeral 127.0.0.1 -> docker exec -> internal PostgreSQL loopback TCP",
             "evidence":"FOUR_RECORDS_RECONCILED, independent read-only reconciliation",
             "result":result}
    safe_save(REPO/PRIMARY,
              (json.dumps(primary,indent=2,ensure_ascii=False)+"\n").encode("utf-8"))
    print("PRIMARY_RECONCILED_SAVED|"+PRIMARY)
    original=(REPO/V3).read_text(encoding="utf-8")
    candidate=json.loads(original)
    documents=(candidate["policy_candidate_body"]["rules"]
               ["b02_noncredential"]["security"]["g5_release"]["documents"])
    if len(documents)!=2:
        stop("STOP_G5_DOCUMENT_SCOPE_DIVERGENT")
    old_id="B02-05ede-activation-v1"
    old_hash="06321ef4c9df17e251a08428a534ab6af8e1f868df2c48b64c3342ecc703dae5"
    for doc in documents:
        binding=doc["g4"]["policy_binding"]
        if (binding["policy_activation_id"]!=old_id
            or binding["policy_activation_record_hash"]!=old_hash):
            stop("STOP_G5_V3_BINDING_DIVERGENT")
        binding["policy_activation_id"]=result["activation_id"]
        binding["policy_activation_record_hash"]=result["activation_hash"]
    revised=json.dumps(candidate,ensure_ascii=False,indent=2)+"\n"
    safe_save(REPO/G5_CANDIDATE,revised.encode("utf-8"))
    print("G5_SUCCESSOR_FOR_REVIEW_SAVED|"+G5_CANDIDATE)
    for line in difflib.unified_diff(
        original.splitlines(),revised.splitlines(),fromfile=V3,
        tofile=G5_CANDIDATE,lineterm=""):
        if line.startswith(("---","+++","@@","+","-")):
            print(line)
    print("G5_CANDIDATE_NOT_RATIFIED_OR_EXECUTED")

def main():
    if len(sys.argv)!=1:
        stop("STOP_NO_ARGS_EXPECTED_APPROVAL_ALREADY_PINNED")
    os.chdir(REPO)
    source=assert_repo_and_approval()
    running=check_container()
    started=False
    try:
        if not running:
            docker("start",CONTAINER)
            started=True
        status,output=execute_exact_bridge(source)
        print("PYTHON_EXIT|"+str(status))
        if status!=0:
            stop("STOP_APPROVED_EXECUTION_FAILED_NO_BLIND_RETRY")
        if '"status": "FOUR_RECORDS_RECONCILED"' not in output:
            stop("STOP_NO_FULL_RECONCILIATION")
        persist_success(output)
    finally:
        os.environ.pop(DSN_ENV,None)
        if started:
            try:
                if other_clients()==0:
                    docker("stop",CONTAINER)
                    print("CONTAINER|RESTORED_STOPPED")
                else:
                    print("CONTAINER|PRESERVED_RUNNING_ACTIVE_CLIENTS")
            except Exception:
                print("CONTAINER|PRESERVED_RUNNING_CHECK_UNCERTAIN")

if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        print("STOP|"+str(exc),file=sys.stderr)
        sys.exit(2)
