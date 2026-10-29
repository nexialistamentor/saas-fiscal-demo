"""B02 G4 October controlled execution; authority is entered by Miguel locally.

The October delta is *not* covered by the November authorization. The operator
must explicitly accept the exact October window+blob before this script can write.
Never make another INSERT after an attempted execution without fresh review.
"""
from __future__ import annotations

from datetime import datetime, timezone
import difflib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parent.parent
BRANCH="candidate/g5-successor-window-prep"
ORIGINAL="executar_ativacao_g4_real.py"
CANDIDATE="executar_ativacao_g4_antecipada_CANDIDATO.py"
PROPOSAL="PROPOSTA_G4_JANELA_IMEDIATA_20261029.json"
V3="POLICY_G5_CANDIDATO_V3_COMPLETO.json"
CANDIDATE_BLOB="646caf5f62c3520ab965077d2218ba9b4da38437"
ORIGINAL_BLOB="1729e6d62c77510ef4dd7db0af56a6cbe985c168"
V3_SHA="8b3b0cc0a880156b5659166b6878de580b1ddafcf245d811545a0f1ba60500d4"
REF="B02-G4-AUTH-MIGUEL-20261029-02"
FROM="2026-10-29T13:00:00+00:00"
UNTIL="2026-10-30T13:00:00+00:00"
AUTH="AUTORIZACAO_G4_MIGUEL_20261029_02.json"
ATTEMPT="B02_G4_TENTATIVA_UNICA_OUTUBRO_20261029.json"
PRIMARY="B02_G4_RESULTADO_RECONCILIADO_OUTUBRO_20261029.json"
G5="POLICY_G5_CANDIDATO_SUCESSOR_OUTUBRO_V4_PARA_REVISAO.json"
DIFF="DIFF_G5_V3_PARA_SUCESSOR_OUTUBRO_V4.diff"
CONSENT="AUTORIZO G4 OUTUBRO B02-G4-AUTH-MIGUEL-20261029-02"

def stop(code):
    raise RuntimeError(code)

def load_bridge():
    if str(ROOT) not in sys.path:
        sys.path.insert(0,str(ROOT))
    spec=importlib.util.spec_from_file_location("b02_october_approved_bridge",ROOT/"tools"/"b02_g4_authorized_runner.py")
    if spec is None or spec.loader is None:
        stop("STOP_BASE_BRIDGE_ABSENT")
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def sha_blob(b):
    return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()

def pin(bridge):
    if bridge.git("branch","--show-current")!=BRANCH:
        stop("STOP_BRANCH_MISMATCH")
    if bridge.git("rev-parse","HEAD")!=bridge.git("rev-parse","origin/"+BRANCH):
        stop("STOP_HEAD_NOT_SYNCED")
    bridge.assert_repo_and_approval()
    source=bridge.git("show","HEAD:"+CANDIDATE,binary=True)
    if sha_blob(source)!=CANDIDATE_BLOB:
        stop("STOP_CANDIDATE_BLOB")
    compile(source,CANDIDATE,"exec")
    if sha_blob(bridge.git("show","HEAD:"+ORIGINAL,binary=True))!=ORIGINAL_BLOB:
        stop("STOP_ORIGINAL_G4_BLOB")
    v3=bridge.git("show","HEAD:"+V3,binary=True)
    if hashlib.sha256(v3).hexdigest()!=V3_SHA:
        stop("STOP_V3_SOURCE_HASH")
    proposal=json.loads(bridge.git("show","HEAD:"+PROPOSAL,binary=True))
    exact={
        "candidate_procedure":CANDIDATE,
        "candidate_git_blob":CANDIDATE_BLOB,
        "predecessor_git_blob":ORIGINAL_BLOB,
        "authorization_required_reference":REF,
        "status":"PROPOSTA_NAO_AUTORIZADA_NAO_EXECUTADA",
        "database":"solveris_b02_r4g_test",
        "writer":"solveris_b02_policy_writer",
        "window":{"from":FROM,"until":UNTIL},
        "ids":{"execution":"B02-05ede-execution-v3",
               "activation":"B02-05ede-activation-v3",
               "generation":"B02-05ede-generation-v3",
               "outbox":"B02-05ede-outbox-v3"}}
    for k,v in exact.items():
        if proposal.get(k)!=v:
            stop("STOP_PROPOSAL_"+k.upper())
    return source,v3,proposal

def write_new(name,body):
    p=ROOT/name
    if p.exists():
        if p.read_bytes()!=body:
            stop("STOP_EXISTING_ARTIFACT_CONFLICT_"+name)
        return
    with p.open("xb") as f:
        f.write(body)
        f.flush()
        os.fsync(f.fileno())

def json_bytes(x):
    return (json.dumps(x,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode("utf-8")

def existing_auth():
    p=ROOT/AUTH
    if not p.exists():
        return False
    a=json.loads(p.read_bytes())
    if (a.get("reference")!=REF or a.get("procedure_git_blob")!=CANDIDATE_BLOB
        or a.get("window")!={"from":FROM,"until":UNTIL}
        or a.get("consent_literal")!=CONSENT or a.get("status")!="AUTORIZADO_PELO_OPERADOR_LOCAL"):
        stop("STOP_EXISTING_AUTH_INVALID")
    return True

def require_miguel_consent(proposal):
    if existing_auth():
        print("G4_OCTOBER_LOCAL_AUTH_ALREADY_PRESENT")
        return
    if (ROOT/ATTEMPT).exists():
        stop("STOP_ATTEMPT_WITHOUT_AUTH")
    print("ALTERACAO TEMPORAL G4. A AUTORIZACAO DE NOVEMBRO NAO ABRANGE ESTE DELTA.")
    print("ALVO|solveris_b02_r4g_test|solveris_b02_policy_writer")
    print("BLOB|"+CANDIDATE_BLOB)
    print("JANELA_UTC|"+FROM+"|"+UNTIL)
    print("IDS|"+json.dumps(proposal["ids"],sort_keys=True))
    print("Apenas esta unidade G4; sem G5, migrations, assinatura ou MEI.")
    print("Digite exatamente a frase abaixo para autorizar o delta de outubro:")
    print(CONSENT)
    entered=input("AUTORIZACAO_G4_OUTUBRO> ").strip()
    if entered!=CONSENT:
        stop("STOP_G4_OCTOBER_NOT_EXPLICITLY_AUTHORIZED")
    timestamp=datetime.now(timezone.utc).isoformat()
    authority={
        "schema":"B02_G4_OCTOBER_OPERATOR_EXPLICIT_AUTH_V1",
        "reference":REF,
        "status":"AUTORIZADO_PELO_OPERADOR_LOCAL",
        "actor":"Miguel",
        "source":"confirmacao_explicita_no_terminal_Windows",
        "consent_literal":entered,
        "consent_utc":timestamp,
        "procedure":CANDIDATE,
        "procedure_git_blob":CANDIDATE_BLOB,
        "original_unchanged_blob":ORIGINAL_BLOB,
        "window":{"from":FROM,"until":UNTIL},
        "database":"solveris_b02_r4g_test",
        "writer":"solveris_b02_policy_writer",
        "policy_hash":proposal["policy_hash"],
        "ids":proposal["ids"],
        "idempotency_key":proposal["idempotency_key"],
        "limited_to":"G4 four-record atomic unit only",
        "other_operations_not_authorized":["G5","migrations","signing","MEI"],
    }
    write_new(AUTH,json_bytes(authority))
    print("G4_OCTOBER_OPERATOR_AUTH_RECORDED|"+AUTH)

def record_attempt():
    if (ROOT/ATTEMPT).exists():
        return False
    obj={
        "schema":"B02_G4_OCTOBER_ONE_SHOT_ATTEMPT_V1",
        "reference":REF,
        "procedure_git_blob":CANDIDATE_BLOB,
        "execution_id":"B02-05ede-execution-v3",
        "idempotency_key":"B02-05ede-execution-v3-20261029T130000Z",
        "started_utc":datetime.now(timezone.utc).isoformat(),
        "status":"ATTEMPT_RESERVED_BEFORE_ANY_INSERT_NO_AUTOMATIC_RETRY",
    }
    write_new(ATTEMPT,json_bytes(obj))
    return True

def git_action(*args,env=None,input_bytes=None):
    p=subprocess.run(["git",*args],cwd=ROOT,env=env,input=input_bytes,
                     stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if p.returncode:
        stop("STOP_GIT_"+args[0].upper()+"_FAILED")
    return p.stdout.decode("utf-8").strip()

def push_isolated(files,message):
    if not files:
        return
    head=git_action("rev-parse","HEAD")
    if head!=git_action("rev-parse","origin/"+BRANCH):
        stop("STOP_REMOTE_MOVED")
    with tempfile.TemporaryDirectory(prefix="b02_g4_index_") as folder:
        env=dict(os.environ,GIT_INDEX_FILE=str(Path(folder)/"index"))
        git_action("read-tree",head,env=env)
        git_action("add","--",*files,env=env)
        tree=git_action("write-tree",env=env)
    # Build and publish a commit from a temporary index; do not stage other
    # tracked local edits, delete untracked items, reset or force.
    commit=git_action("commit-tree",tree,"-p",head,env=os.environ,
                      input_bytes=(message+"\n").encode("utf-8"))
    git_action("update-ref","refs/heads/"+BRANCH,commit,head)
    git_action("push","origin","HEAD:refs/heads/"+BRANCH)
    if git_action("rev-parse","HEAD")!=git_action("rev-parse","origin/"+BRANCH):
        stop("STOP_GIT_POSTPUSH_VERIFY")
    print("B02_ARTIFACTS_PUSHED|"+commit)

def probe_bytes():
    source=r'''
import hashlib,json,os,subprocess
from sqlalchemy import create_engine,text
from sqlalchemy.pool import NullPool
raw=subprocess.check_output(["git","show","HEAD:executar_ativacao_g4_antecipada_CANDIDATO.py"])
blob=hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
if blob!="646caf5f62c3520ab965077d2218ba9b4da38437":
    raise RuntimeError("STOP_INDEPENDENT_SOURCE_BLOB")
ns={"__name__":"__b02_g4_read_only__","__file__":"executar_ativacao_g4_antecipada_CANDIDATO.py"}
exec(compile(raw,"executar_ativacao_g4_antecipada_CANDIDATO.py","exec"),ns)
engine=create_engine(os.environ["SOLVERIS_B02_POLICY_WRITER_DSN"],poolclass=NullPool)
try:
    with engine.connect() as conn:
        conn.exec_driver_sql("SET TRANSACTION READ ONLY")
        policy,_,scope_hash=ns["preflight"](conn)
        result=ns["reconcile"](conn,scope_hash,policy)
        if result is None:
            print("G4_OCTOBER_UNIT_NOT_PRESENT")
        else:
            txid=conn.execute(text("SELECT b02_policy_txid FROM public.policy_activation_executions WHERE policy_activation_execution_id=:id"),
                {"id":result["execution_id"]}).scalar_one()
            if not str(txid).isdigit():
                raise RuntimeError("STOP_TXID_NOT_NUMERIC")
            result["transaction_id"]=str(txid)
            print(json.dumps(result,sort_keys=True))
        conn.rollback()
finally:
    engine.dispose()
'''
    return source.encode("utf-8")

def get_result(out):
    for line in out.splitlines():
        if line.startswith("{"):
            try:
                obj=json.loads(line)
            except (TypeError,ValueError):
                continue
            if obj.get("status")=="FOUR_RECORDS_RECONCILED":
                expected={
                    "execution_id":"B02-05ede-execution-v3",
                    "activation_id":"B02-05ede-activation-v3",
                    "generation_id":"B02-05ede-generation-v3",
                    "outbox_id":"B02-05ede-outbox-v3",
                    "policy_hash":"05ede0f8c8788b93d41e451288efd88d91614a560bdd2191a115f0d736c4fe2a"}
                for k,v in expected.items():
                    if obj.get(k)!=v:
                        stop("STOP_RECONCILIATION_ID_OR_POLICY_"+k)
                for k in ("execution_hash","activation_hash","generation_hash","outbox_hash",
                          "outbox_payload_hash","scope_hash"):
                    v=obj.get(k)
                    if not isinstance(v,str) or len(v)!=64 or any(c not in "0123456789abcdef" for c in v):
                        stop("STOP_BAD_RECONCILED_HASH_"+k)
                if not str(obj.get("transaction_id","")).isdigit():
                    stop("STOP_RECONCILED_TXID_MISSING")
                return obj
    return None

def create_g5_successor(v3raw,result):
    old=v3raw.decode("utf-8")
    mapping={
        "2026-11-03T12:00:00+00:00":(FROM,4),
        "2026-11-04T07:56:30.910737+00:00":(UNTIL,4),
        "B02-05ede-activation-v1":(result["activation_id"],2),
        "06321ef4c9df17e251a08428a534ab6af8e1f868df2c48b64c3342ecc703dae5":(result["activation_hash"],2)}
    revised=old
    for literal,(replacement,count) in mapping.items():
        if revised.count(literal)!=count:
            stop("STOP_G5_V3_REFERENCE_COUNT_CONFLICT")
        revised=revised.replace(literal,replacement)
    x=json.loads(revised)
    body=x["policy_candidate_body"]
    docs=body["rules"]["b02_noncredential"]["security"]["g5_release"]["documents"]
    if len(docs)!=2 or any(d["g4"]["policy_binding"]["policy_activation_id"]!=result["activation_id"] for d in docs):
        stop("STOP_G5_SUCCESSOR_LINKS")
    if body["rules"]["b02_noncredential"]["security"]["g5_release"]["from"]!=FROM:
        stop("STOP_G5_SUCCESSOR_WINDOW")
    # V3's caveats belong to its historical state. Do not falsely claim that
    # approval of the G4 four-record unit ratifies the G5 successor.
    x["__AVISO_VALIDADE_G4__"]="Ativacao G4 de outubro reconciliada por leitura independente; G5 ainda exige parecer, ratificacao e propria autorizacao operacional."
    x["__AVISO_G4_PREENCHIDO__"]="Os vinculos e hashes G4 sao observados; os valores da politica G5 sao somente candidato, NAO ratificados."
    x["status"]="CANDIDATO_SUCESSOR_G4_RECONCILIADO_G5_NAO_RATIFICADO"
    revised=json.dumps(x,ensure_ascii=False,indent=2)+"\n"
    diff="".join(difflib.unified_diff(old.splitlines(keepends=True),
        revised.splitlines(keepends=True),fromfile=V3,tofile=G5))
    if not diff:
        stop("STOP_G5_DIFF_EMPTY")
    write_new(G5,revised.encode("utf-8"))
    write_new(DIFF,diff.encode("utf-8"))
    print("G5_SUCCESSOR_FOR_REVIEW_SAVED|"+G5)
    print("G5_SUCCESSOR_SHA256|"+hashlib.sha256(revised.encode("utf-8")).hexdigest())
    print("G5_DIFF_SAVED|"+DIFF)

def execute():
    if len(sys.argv)!=1:
        stop("STOP_NO_ARGUMENTS_EXPECTED")
    os.chdir(ROOT)
    bridge=load_bridge()
    source,v3,proposal=pin(bridge)
    now=datetime.now(timezone.utc)
    start=datetime.fromisoformat(FROM)
    end=datetime.fromisoformat(UNTIL)
    if not start<=now<end:
        stop("STOP_OCTOBER_WINDOW_NOT_CURRENT")
    was_running=bridge.check_container()
    started=False
    try:
        if not was_running:
            bridge.docker("start",bridge.CONTAINER)
            started=True
        bridge.SCRIPT=CANDIDATE
        bridge.APPROVAL=REF
        # Independent read-only confirmation before ANY possible INSERT.
        check_rc,check_stdout=bridge.execute_exact_bridge(probe_bytes())
        if check_rc!=0:
            stop("STOP_EXISTING_UNIT_READ_FAILED")
        completed=get_result(check_stdout)
        if completed is None and "G4_OCTOBER_UNIT_NOT_PRESENT" not in check_stdout:
            stop("STOP_EXISTING_UNIT_UNDETERMINED")
        if completed:
            if not existing_auth():
                stop("STOP_EXISTING_G4_UNIT_AUTHORIZATION_RECORD_MISSING")
            print("G4_OCTOBER_EXISTING_UNIT_RECONCILED_NO_NEW_INSERT")
        else:
            if (ROOT/ATTEMPT).exists():
                stop("STOP_PRIOR_G4_ATTEMPT_PRESENT_READ_ONLY_ONLY")
            require_miguel_consent(proposal)
            if not existing_auth():
                stop("STOP_MISSING_OPERATOR_CONSENT")
            if not datetime.fromisoformat(FROM)<=datetime.now(timezone.utc)<datetime.fromisoformat(UNTIL):
                stop("STOP_OCTOBER_WINDOW_ELAPSED_BEFORE_WRITE")
            if not record_attempt():
                stop("STOP_REPEAT_ATTEMPT")
            push_isolated([AUTH,ATTEMPT],"B02 G4: Miguel confirms bounded October v3 activation and one-shot attempt")
            # No additional INSERT attempt is made after this call, regardless
            # of exit code or an uncertain COMMIT acknowledgement.
            run_rc,_=bridge.execute_exact_bridge(source)
            print("G4_OCTOBER_APPROVED_EXECUTION_EXIT|"+str(run_rc))
            reconcile_rc,reconcile_stdout=bridge.execute_exact_bridge(probe_bytes())
            print("G4_OCTOBER_INDEPENDENT_RECONCILIATION_EXIT|"+str(reconcile_rc))
            if reconcile_rc!=0:
                stop("STOP_INDEPENDENT_RECONCILIATION_FAILED_NO_RETRY")
            completed=get_result(reconcile_stdout)
            if completed is None:
                stop("STOP_NO_FOUR_RECORDS_RECONCILED_NO_RETRY")
        primary={
            "schema":"B02_G4_OCTOBER_FOUR_RECORDS_RECONCILED_V1",
            "authorization_reference":REF,
            "authorization_file":AUTH,
            "candidate_procedure_blob":CANDIDATE_BLOB,
            "transport":"Windows Python localhost ephemeral -> docker exec -> PostgreSQL internal loopback TCP",
            "evidence":"independent read-only four-record reconciliation; transaction IDs equal",
            "result":completed}
        write_new(PRIMARY,json_bytes(primary))
        create_g5_successor(v3,completed)
        print("B02_G4_FOUR_RECORDS_RECONCILED|"+completed["transaction_id"])
    finally:
        bridge.SCRIPT=ORIGINAL
        bridge.APPROVAL="B02-G4-AUTH-MIGUEL-20261029-01"
        os.environ.pop(bridge.DSN_ENV,None)
        if started:
            try:
                if bridge.other_clients()==0:
                    bridge.docker("stop",bridge.CONTAINER)
                    print("CONTAINER|RESTORED_STOPPED")
                else:
                    print("CONTAINER|PRESERVED_RUNNING_OTHER_CLIENTS")
            except Exception:
                print("CONTAINER|PRESERVED_RUNNING_STOP_UNCERTAIN")
    # Never present this Git push as evidence of G5 authorization.
    push_isolated([PRIMARY,G5,DIFF],"B02 G4: preserve independently reconciled v3 and unratified G5 October successor")
    print("G4_COMPLETED_G5_NOT_EXECUTED")

if __name__=="__main__":
    try:
        execute()
    except BaseException as exc:
        print("STOP|"+(str(exc) if type(exc) is RuntimeError else type(exc).__name__),file=sys.stderr)
        sys.exit(2)
