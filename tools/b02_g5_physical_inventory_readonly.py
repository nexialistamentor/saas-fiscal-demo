"""Read-only G5 physical inventory; does not install/activate G5."""
from pathlib import Path
import importlib.util, json, sys, hashlib
ROOT=Path(__file__).resolve().parents[1]
BRANCH="candidate/g5-successor-window-prep"
PAYLOAD=r'''
import json,os
from sqlalchemy import create_engine,text
from sqlalchemy.pool import NullPool
e=create_engine(os.environ["SOLVERIS_B02_POLICY_WRITER_DSN"],poolclass=NullPool)
try:
 with e.connect() as c:
  c.exec_driver_sql("SET TRANSACTION READ ONLY")
  db,user,current,version=c.execute(text("SELECT current_database(),session_user,current_user,current_setting('server_version')")).one()
  if (db,user,current)!=("solveris_b02_r4g_test","solveris_b02_policy_writer","solveris_b02_policy_writer"):
   raise RuntimeError("G5_PHYSICAL_IDENTITY_STOP")
  revision=c.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one()
  names=["b02g5_assert_signature","b02g5_native_profile","b02g5_precommit_validate","b02_g5_assert_one_shot","b02_g5_operational_approval_uses"]
  funcs={}
  for n in names:
   funcs[n]=bool(c.execute(text("SELECT EXISTS (SELECT 1 FROM pg_proc WHERE proname=:n)"),{"n":n}).scalar_one())
  table=bool(c.execute(text("SELECT to_regclass('public.b02_g5_operational_approval_uses') IS NOT NULL")).scalar_one())
  print("G5_PHYSICAL_READ_ONLY|"+json.dumps({"db":db,"role":user,"postgres_version":version,"alembic_revision":revision,"g5_function_present":funcs,"g5_one_shot_table_present":table},sort_keys=True))
  c.rollback()
finally:
 e.dispose()
'''.encode("utf-8")
# Separate minimal check: never repeats the 0063 / G5-functions inventory.
POLICY_PAYLOAD=r'''
import json,os
from sqlalchemy import create_engine,text
from sqlalchemy.pool import NullPool
engine=create_engine(os.environ["SOLVERIS_B02_POLICY_WRITER_DSN"],poolclass=NullPool)
try:
 with engine.connect() as conn:
  conn.exec_driver_sql("SET TRANSACTION READ ONLY")
  db,user,current=conn.execute(text("SELECT current_database(),session_user,current_user")).one()
  if (db,user,current)!=("solveris_b02_r4g_test","solveris_b02_policy_writer","solveris_b02_policy_writer"):
   raise RuntimeError("G5_POLICY_IDENTITY_STOP")
  rows=conn.execute(text(
   "SELECT policy_version,policy_hash,record_hash FROM public.policy_versions "
   "WHERE policy_id=:id ORDER BY policy_version"),
   {"id":"SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE"}).mappings().all()
  policies=[dict(r) for r in rows]
  print("G5_POLICY_VERSION_READ_ONLY|"+json.dumps({
   "db":db,
   "policy_id":"SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE",
   "existing_versions":policies,
   "same_version_1_already_occupied":any(r["policy_version"]==1 for r in policies),
   "record_count":len(policies)},sort_keys=True))
  conn.rollback()
finally:
 engine.dispose()
'''.encode("utf-8")
def main():
 policy_only=(len(sys.argv)==2 and sys.argv[1]=="--policy-version-only")
 if not policy_only and len(sys.argv)!=1:raise RuntimeError("STOP_UNEXPECTED_ARGS")
 if policy_only:
  source=(ROOT/"POLICY_G5_CANDIDATO_SUCESSOR_OUTUBRO_V4_PARA_REVISAO.json").read_bytes()
  if hashlib.sha256(source).hexdigest()!="2dd00187b3348847a4deb845167d4554749aaa71cdce8556a03163ea1f4f252e":raise RuntimeError("STOP_V4_SOURCE_CHANGED")
  body=json.loads(source)["policy_candidate_body"]
  canonical=json.dumps(body,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode("utf-8")
  candidate_hash=hashlib.sha256(canonical).hexdigest()
  if candidate_hash!="e35576a437d4f7b1868e281914e878331624106d6e50f4ee7a4e91289933e0d6":raise RuntimeError("STOP_CANONICAL_HASH_DISAGREES_WITH_REVIEW")
  print("G5_V4_CANONICAL_BODY_SHA256_CANDIDATE|"+candidate_hash)
 # Running a file directly from tools/ puts tools/, not the repository root,
 # on sys.path. The approved bridge imports app.database before the read-only
 # payload; resolve that existing package without changing application code.
 if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
 spec=importlib.util.spec_from_file_location("g5_bridge",ROOT/"tools"/"b02_g4_authorized_runner.py")
 b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
 if b.git("branch","--show-current")!=BRANCH:raise RuntimeError("STOP_BRANCH")
 if b.git("rev-parse","HEAD")!=b.git("rev-parse","origin/"+BRANCH):raise RuntimeError("STOP_HEAD_DIVERGED")
 b.assert_repo_and_approval()
 started=False
 try:
  if not b.check_container():
   b.docker("start",b.CONTAINER);started=True
  rc,_=b.execute_exact_bridge(POLICY_PAYLOAD if policy_only else PAYLOAD)
  print(("G5_POLICY_VERSION_CHECK_EXIT|" if policy_only else "G5_PHYSICAL_INVENTORY_EXIT|")+str(rc))
  if rc:raise RuntimeError("STOP_G5_INVENTORY_FAILED")
 finally:
  if started:
   if b.other_clients()==0:
    b.docker("stop",b.CONTAINER);print("CONTAINER|RESTORED_STOPPED")
   else:print("CONTAINER|PRESERVED_RUNNING_ACTIVE_CLIENTS")
if __name__=="__main__":
 try:main()
 except Exception as exc:
  print("STOP|"+(str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__),file=sys.stderr);sys.exit(2)
